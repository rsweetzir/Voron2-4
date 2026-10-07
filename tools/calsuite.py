#!/usr/bin/env python3
"""
One-plate filament calibration suite with questions between tests (v5).

Speed first: every test runs at the filament's rated top speed (VMAX, from the spool label),
the temperature range leans hot, and the max-flow test starts at VMAX and ramps up from there.

Prints, front to back, one test at a time (OrcaSlicer models sliced by tools/orca_calib.py):
  1. Temperature tower: Orca's temperature_tower (10mm labelled blocks, overhangs, bridge,
     cone), hot to cool                                       -> asks: best temperature
  2. Max volumetric speed: Orca's SpeedTestStructure at 60% size (single-wall vase, 0.32mm
     layers, 0.7mm lines), 2.56mm bands from VMAX up in 2 mm3/s steps
                                                              -> asks: last good band
  3. Pressure-advance triangles with solid-filled bottoms (no square base), each printed
     on its own from bottom to top at its PA value           -> asks: sharpest triangle
  4. Flow blocks (25 x 12.5mm), all printed together, flow switched per block
                                                              -> asks: smoothest top
  5. Retraction: Orca's retraction_tower (two pillars), retraction length changes every
     1mm (one tick on the pillars)                            -> asks: lowest clean length
  6. Tolerance: Orca's OrcaToleranceTest (hex holes 0 .. 0.4mm clearance, key printed in
     the 0.4mm hole)                                          -> asks: tightest hole the key fits
Questions are Mainsail prompts (klipper/calibration.cfg: _CAL_ASK/_CAL_ANSWER); answers
are stored with SAVE_VARIABLE and applied by _CAL_APPLY before the next test.

The tests are printed one after another, so the layout keeps the Stealthburner clear of
finished tests (OrcaSlicer's standard clearances, see CLEAR_*); check_clearance() refuses to
write G-code for a plate that breaks them, and check_moves() refuses G-code that moves off
the bed or through a finished test. Rows go front to back because the Voron gantry sits
behind the nozzle: tests taller than the gantry clearance stay in front of everything printed
after them. The last row has two low tests side by side, far enough apart for the toolhead.

Usage: calsuite.py MATERIAL OUT.gcode NAME ORCA_DIR [FROM=test ANSWER=value ...]
       MATERIAL: a PROFILES key. ORCA_DIR holds temp/speed/retract/tolerance.gcode from
       orca_calib.py (tools/calsuite.sh runs the whole thing).
       Resume: FROM=speed|pa|flow|retract|tolerance writes only that test and the ones after
       it, with the earlier answers given as TEMP= MAX_FLOW= PA= FLOW= RETRACT_LEN= (needed:
       TEMP for anything after the tower). Earlier tests are treated as still on the bed.
"""
import math, os, re, sys

MAT = (sys.argv[1] if len(sys.argv) > 1 else "PLA").upper()
OUT = sys.argv[2] if len(sys.argv) > 2 else f"{MAT}_calibration_suite.gcode"
NAME = sys.argv[3] if len(sys.argv) > 3 else MAT
ORCA_DIR = sys.argv[4]
EXTRA = dict(a.split("=", 1) for a in sys.argv[5:])
SECTIONS = ["temp", "speed", "pa", "flow", "retract", "tolerance"]   # print order
FROM = EXTRA.pop("FROM", "temp").lower()
if FROM not in SECTIONS:
    sys.exit(f"FROM must be one of {SECTIONS}")
ANSWERS = {k.lower(): v for k, v in EXTRA.items()}
if FROM != "temp" and "temp" not in ANSWERS:
    sys.exit("resuming after the temperature tower needs TEMP=<answer>")
mark = {"temp": 0}                                       # out[] index where each test starts

# vmax: the label's top print speed (mm/s); every test starts from it
PROFILES = {
    "PLA":      dict(bed=60, temps=[220, 215, 210, 205, 200, 195, 190], fan=255,
                     rspeed=40, start_retract=0.6, vmax=80),
    "PLA_PLUS": dict(bed=60, temps=[240, 235, 230, 225, 220, 215, 210], fan=255,
                     rspeed=40, start_retract=0.6, vmax=80),
    "PLA_WOOD": dict(bed=60, temps=[230, 225, 220, 215, 210, 205, 200], fan=255,
                     rspeed=40, start_retract=0.6, vmax=60),
    "PETG":     dict(bed=80, temps=[248, 244, 240, 236, 232, 228, 224], fan=102,
                     rspeed=60, start_retract=0.4, vmax=60),
}
P = PROFILES[MAT]
VMAX = P["vmax"]
PA_VALUES = [round(0.01 * i, 2) for i in range(9)]       # 0.00 .. 0.08
FLOWS = [92, 96, 100, 104, 108]
RETRACTS = [round(0.2 + 0.1 * k, 1) for k in range(11)]  # 0.2 .. 1.2, one per 1mm of tower
TOLERANCES = [0, 0.05, 0.1, 0.2, 0.3, 0.4]               # OrcaToleranceTest hole clearances

LH, FIRST_LH, W = 0.2, 0.25, 0.45
BASE_H = 0.45                                            # PA triangle solid bottom: 2 layers
FIL_A = math.pi * (1.75 / 2) ** 2
TRAVEL_F, FIRST_F = 200 * 60, 25 * 60
TEST_F = VMAX * 60                                       # walls and fill of every test
V0 = round(VMAX * LH * 0.5)                              # label top speed as mm3/s (0.2 x 0.5 line)
SPEED_VOLS = list(range(V0, V0 + 24, 2))                 # 12 bands, e.g. 8 .. 30 mm3/s
SPEED_BAND = 2.56                                        # 8 vase layers of 0.32mm per band
RETRACT_BASE, RETRACT_BAND = 0.4, 1.0                    # Orca: base 0.4mm, one step per 1mm

# ---- Stealthburner clearance for tests printed one after another (OrcaSlicer standard values)
CLEAR_RADIUS = 65.0      # extruder_clearance_radius: a taller finished test stays >= half of it away
LOW_H, LOW_GAP = 2.0, 15.0   # tests up to LOW_H pass under the ducts and need only LOW_GAP
GANTRY_H = 34.0          # extruder_clearance_height_to_rod (36) less 2mm: taller tests stay in front
WAIT_X = 8.0             # empty left lane: pauses and prime lines

out, pos, state = [], [0.0, 0.0], {"safe_z": 0.0, "retracted": False}
g = out.append

# ---------------------------------------------------------------- motion helpers
def retract():
    if not state["retracted"]:
        g("G10"); state["retracted"] = True

def ext(x, y, h, f, w=W):
    if state["retracted"]:
        g("G11"); state["retracted"] = False
    d = math.hypot(x - pos[0], y - pos[1])
    if d > 1e-6:
        g(f"G1 X{x:.3f} Y{y:.3f} E{d * w * h / FIL_A:.5f} F{f:.0f}")
    pos[0], pos[1] = x, y

def hop_travel(x, y, z, hop=0.4):
    if math.hypot(x - pos[0], y - pos[1]) < 1.0:              # short hop: no retract needed
        g(f"G1 X{x:.3f} Y{y:.3f} F{TRAVEL_F}")
    else:
        retract(); g(f"G1 Z{z + hop:.3f} F1200")
        g(f"G0 X{x:.3f} Y{y:.3f} F{TRAVEL_F}")
        g(f"G1 Z{z:.3f} F1200")
    pos[0], pos[1] = x, y

def layer_list(top, start=FIRST_LH):
    z, i = start, 0
    while z <= top + 1e-6:
        yield i, z, (FIRST_LH if abs(z - FIRST_LH) < 1e-6 else LH)
        i += 1
        z = round(z + LH, 3)

def fan_on(z):
    if abs(z - (FIRST_LH + LH)) < 1e-6:
        g(f"M106 S{P['fan']}")

# ---------------------------------------------------------------- geometry helpers
def offset_poly(poly, d):
    """Offset a counter-clockwise polygon inward by d (negative = outward), mitered corners."""
    n, res = len(poly), []
    for i in range(n):
        p0, p1, p2 = poly[i - 1], poly[i], poly[(i + 1) % n]
        e1 = (p1[0] - p0[0], p1[1] - p0[1]); e2 = (p2[0] - p1[0], p2[1] - p1[1])
        l1, l2 = math.hypot(*e1), math.hypot(*e2)
        n1 = (-e1[1] / l1, e1[0] / l1); n2 = (-e2[1] / l2, e2[0] / l2)   # inward (left) normals
        k = d / (1 + n1[0] * n2[0] + n1[1] * n2[1])                     # miter length
        res.append((p1[0] + k * (n1[0] + n2[0]), p1[1] + k * (n1[1] + n2[1])))
    return res

def loop(poly, z, h, f):
    hop_travel(poly[0][0], poly[0][1], z)
    for p in poly[1:] + poly[:1]:
        ext(p[0], p[1], h, f)

def walls(poly, z, h, f, count=2):
    """Inner walls first, outer wall last."""
    for k in reversed(range(count)):
        loop(offset_poly(poly, (k + 0.5) * W), z, h, f)

def fill_concentric(poly, inradius, z, h, f):
    """Solid layer as loops from the outside in (used for the triangle bottoms)."""
    n = 0
    while (n + 0.5) * W <= inradius - 0.25 * W:
        loop(offset_poly(poly, (n + 0.5) * W), z, h, f)
        n += 1

def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]

def solid_rect(x0, y0, x1, y1, z, h, layer, f_wall, f_fill):
    """Two walls plus zig-zag fill, alternating direction per layer."""
    walls(rect(x0, y0, x1, y1), z, h, f_wall)
    lx0, ly0, lx1, ly1 = x0 + 2.5 * W, y0 + 2.5 * W, x1 - 2.5 * W, y1 - 2.5 * W
    if layer % 2 == 0:
        n = int((ly1 - ly0) / W) + 1
        hop_travel(lx0, ly0, z)
        for j in range(n):
            yy = ly0 + j * W
            a, b = (lx0, yy), (lx1, yy)
            if j % 2: a, b = b, a
            ext(a[0], a[1], h, f_fill); ext(b[0], b[1], h, f_fill)
    else:
        n = int((lx1 - lx0) / W) + 1
        hop_travel(lx0, ly0, z)
        for j in range(n):
            xx = lx0 + j * W
            a, b = (xx, ly0), (xx, ly1)
            if j % 2: a, b = b, a
            ext(a[0], a[1], h, f_fill); ext(b[0], b[1], h, f_fill)

# ---- 3x5 dot-matrix font for raised labels
FONT = {
    "0": ["111", "101", "101", "101", "111"], "1": ["010", "110", "010", "010", "111"],
    "2": ["111", "001", "111", "100", "111"], "3": ["111", "001", "111", "001", "111"],
    "4": ["101", "101", "111", "001", "001"], "5": ["111", "100", "111", "001", "111"],
    "6": ["111", "100", "111", "101", "111"], "7": ["111", "001", "001", "001", "001"],
    "8": ["111", "101", "111", "101", "111"], "9": ["111", "101", "111", "001", "111"],
    ".": ["0", "0", "0", "0", "1"], "%": ["101", "001", "010", "100", "101"],
    "C": ["111", "100", "100", "100", "111"],
}

def text_cols(text):
    """Return list of column bit-strings (top row first) for a text, 1 blank column between chars."""
    cols = []
    for k, ch in enumerate(text):
        glyph = FONT[ch]
        for c in range(len(glyph[0])):
            cols.append("".join(glyph[r][c] for r in range(5)))
        if k < len(text) - 1:
            cols.append("00000")
    return cols

def text_width(text, px):
    return len(text_cols(text)) * px

def row_runs(text, row):
    """Runs of lit columns (start, end_exclusive) in font row 0..4 (0 = top)."""
    cols, runs, start = text_cols(text), [], None
    for i, c in enumerate(cols + ["00000"]):
        on = c[row] == "1"
        if on and start is None: start = i
        if not on and start is not None: runs.append((start, i)); start = None
    return runs

def emboss_top(text, cx, cy, z, px, f=30 * 60):
    """Raised label on a top surface: lines along X, two lines per pixel row."""
    x0 = cx - text_width(text, px) / 2
    y_top = cy + 2.5 * px
    for row in range(5):
        for sub in range(max(1, round(px / W))):
            yy = y_top - row * px - (sub + 0.5) * (px / max(1, round(px / W)))
            for a, b in row_runs(text, row):
                hop_travel(x0 + a * px, yy, z, hop=0.2)
                ext(x0 + b * px, yy, LH, f)

# ---- travel that never crosses printed parts
def route(x, y, gap_y):
    """Lift above everything printed so far, slide along a gap row, then go to (x, y)."""
    z = state["safe_z"] + 5
    retract(); g(f"G1 Z{z:.3f} F1200")
    g(f"G0 X{pos[0]:.3f} Y{gap_y:.3f} F{TRAVEL_F}")
    g(f"G0 X{x:.3f} Y{gap_y:.3f} F{TRAVEL_F}")
    g(f"G0 X{x:.3f} Y{y:.3f} F{TRAVEL_F}")
    pos[0], pos[1] = x, y

def wait_spot(gap_y):
    """Leave the finished test via a gap row and wait in the empty left lane (no parking)."""
    route(WAIT_X, gap_y, gap_y)
    g("M400")

PURGE_H, PURGE_W, PURGE_LINES, PURGE_LEN = 0.6, 1.2, 4, 25.0   # ~72 mm3 = 30mm of filament
PURGE_F = 12 / (PURGE_H * PURGE_W) * 60                  # 12 mm3/s, like the KAMP start purge

def prime(y0):
    """Purge pad in the empty left lane before the next test: refills the nozzle after a
    question pause (ooze) and after the speed test (it runs past the hotend's limit and can
    leave the nozzle starved). Four 25mm lines side by side, X 4.4 .. 8, Y y0 .. y0+25."""
    x0 = WAIT_X - (PURGE_LINES - 1) * PURGE_W
    g(f"G0 X{x0:.3f} Y{y0:.3f} F{TRAVEL_F}"); pos[0], pos[1] = x0, y0
    g(f"G1 Z{PURGE_H:.3f} F1200")
    for k in range(PURGE_LINES):
        x = x0 + k * PURGE_W
        if k:
            ext(x, pos[1], PURGE_H, PURGE_F, w=PURGE_W)        # step over to the next line
        ext(x, y0 + PURGE_LEN if k % 2 == 0 else y0, PURGE_H, PURGE_F, w=PURGE_W)
    retract(); g(f"G1 Z{state['safe_z'] + 5:.3f} F1200")

def ask(var, title, text, options, labels=None):
    opts = ",".join(str(o) for o in options)
    lab = ",".join(labels) if labels else opts
    g(f'_CAL_ASK VAR={var} TITLE="{title}" TEXT="{text}" OPTIONS="{opts}" LABELS="{lab}" PARK=0')

def fmt(v):
    return f"{v:.2f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)

# ---------------------------------------------------------------- OrcaSlicer G-code
class Orca:
    """G-code sliced by orca_calib.py, centred on (cx, cy)."""
    def __init__(self, kind, cx, cy):
        path = os.path.join(ORCA_DIR, f"{kind}.gcode")
        self.lines = open(path).read().splitlines()
        self.header = dict(re.findall(r"(\w+)=([\d.]+)", self.lines[0]))
        if not self.lines[0].startswith(f"; orca calib {kind} "):
            sys.exit(f"{path} is not orca_calib.py {kind} output")
        xs, ys, zs, self.first = [], [], [], None
        for l in self.lines:
            if l.startswith(("G0 ", "G1 ")):
                d = dict(re.findall(r"([XYZ])(-?[\d.]+)", l.split(";")[0]))
                if "X" in d: xs.append(float(d["X"]))
                if "Y" in d: ys.append(float(d["Y"]))
                if self.first is None and "X" in d and "Y" in d:
                    self.first = (float(d["X"]), float(d["Y"]))
            elif l.startswith(";Z:"):
                zs.append(float(l[3:]))
        self.dx, self.dy = cx - (min(xs) + max(xs)) / 2, cy - (min(ys) + max(ys)) / 2
        up = lambda v: math.ceil(v * 10) / 10                # round outward to 0.1mm
        dn = lambda v: math.floor(v * 10) / 10
        self.foot = rect(dn(min(xs) + self.dx), dn(min(ys) + self.dy), up(max(xs) + self.dx), up(max(ys) + self.dy))
        self.height = max(zs)
        self.start = (self.first[0] + self.dx, self.first[1] + self.dy)

    def emit(self, on_layer=None, on_extrude=None):
        """Copy the G-code, moved into place. on_layer(z) runs at each Orca layer change;
        on_extrude(line, z, dist) may rewrite an extruding move."""
        z = 0.0
        for l in self.lines:
            if l.startswith(";Z:"):
                z = float(l[3:])
                if on_layer: on_layer(z)
            c = l.split(";")[0].strip()
            if not c or c.startswith(("M73", "M104", "M109", "M140", "M190", "G21", "G90", "M83", "M106 P")):
                continue
            if c.startswith("M106"):
                s = int(float(re.search(r"S([\d.]+)", c).group(1)))
                c = f"M106 S{min(s, P['fan'])}"
            elif c.startswith("SET_VELOCITY_LIMIT"):
                c = re.sub(r" ACCEL_TO_DECEL=\S+", "", c)    # Klipper 0.13 dropped max_accel_to_decel
            elif c.startswith(("G0 ", "G1 ")):
                c = re.sub(r"X(-?[\d.]+)", lambda m: f"X{float(m.group(1)) + self.dx:.3f}", c)
                c = re.sub(r"Y(-?[\d.]+)", lambda m: f"Y{float(m.group(1)) + self.dy:.3f}", c)
                d = dict(re.findall(r"([XYE])(-?[\d.]+)", c))
                nx, ny = float(d.get("X", pos[0])), float(d.get("Y", pos[1]))
                if on_extrude and float(d.get("E", 0)) > 0:
                    c = on_extrude(c, z, math.hypot(nx - pos[0], ny - pos[1]))
                pos[0], pos[1] = nx, ny
            elif c in ("G10", "G11"):
                state["retracted"] = c == "G10"
            g(c)

# ================================================================ plate plan
TRI_SIDE = 22.0
TRI_H = TRI_SIDE * math.sqrt(3) / 2
PA_X = [35 + i * 30 for i in range(len(PA_VALUES))]     # 35 .. 275
PA_TOP = BASE_H + 0.8                                   # 2 solid layers + 4 wall layers
FLOW_X, FLOW_W, FLOW_D, FLOW_H = [70.0, 110.0, 150.0, 190.0, 230.0], 25.0, 12.5, 3.0

ROW = dict(temp=25, speed=101, pa=176, flow=207, last=254)   # Y centre of each row, front to back
TOWER = Orca("temp", 150, ROW["temp"])
SPEED = Orca("speed", 150, ROW["speed"])
RETRACT = Orca("retract", 80, ROW["last"])
TOL = Orca("tolerance", 165, ROW["last"])

TOWER_TEMPS = list(range(int(TOWER.header["high"]), int(TOWER.header["low"]) - 1, -5))
if TOWER_TEMPS != P["temps"]:
    sys.exit(f"temp.gcode has blocks {TOWER_TEMPS}, profile {MAT} wants {P['temps']}")
if abs(SPEED.height - SPEED_BAND * len(SPEED_VOLS)) > 0.01:
    sys.exit(f"speed.gcode is {SPEED.height}mm tall, want {SPEED_BAND * len(SPEED_VOLS):.2f}mm")
if SPEED.height > GANTRY_H:
    sys.exit("speed test is taller than the gantry clearance")
if RETRACT.height < RETRACT_BASE + RETRACT_BAND * len(RETRACTS) - 0.01:
    sys.exit(f"retract.gcode is {RETRACT.height}mm tall, want {RETRACT_BASE + RETRACT_BAND * len(RETRACTS):.2f}mm")

# (name, footprint, height) in print order
PLAN = [
    ("temp_tower", TOWER.foot, TOWER.height),
    ("max_flow", SPEED.foot, SPEED.height),
    ("pa_triangles", rect(PA_X[0] - TRI_SIDE / 2, ROW["pa"] - TRI_H / 2, PA_X[-1] + TRI_SIDE / 2, ROW["pa"] + TRI_H / 2),
     PA_TOP),
    ("flow", rect(FLOW_X[0] - FLOW_W / 2, ROW["flow"] - FLOW_D / 2, FLOW_X[-1] + FLOW_W / 2, ROW["flow"] + FLOW_D / 2),
     FLOW_H + LH),
    ("retraction", RETRACT.foot, RETRACT.height),
    ("tolerance", TOL.foot, TOL.height),
]

TRI_NOZZLE_GAP = 6.0     # triangles are printed one by one: only the nozzle tip reaches below them
def tri_poly(k):
    cx, cy = PA_X[k], ROW["pa"]
    return [(cx - TRI_SIDE / 2, cy - TRI_H / 2), (cx + TRI_SIDE / 2, cy - TRI_H / 2), (cx, cy + TRI_H / 2)]
TRI_OBJECTS = [(f"pa_{k + 1}", rect(PA_X[k] - TRI_SIDE / 2, ROW["pa"] - TRI_H / 2, PA_X[k] + TRI_SIDE / 2, ROW["pa"] + TRI_H / 2), PA_TOP)
               for k in range(len(PA_VALUES))]
if PA_TOP > LOW_H or PA_X[1] - PA_X[0] - TRI_SIDE < TRI_NOZZLE_GAP:
    sys.exit("PA triangles printed one by one must stay low and at least TRI_NOZZLE_GAP apart")

def objects():
    """Exclude-objects in print order: the PA row is one object per triangle."""
    for n, r, h in PLAN:
        yield from (TRI_OBJECTS if n == "pa_triangles" else [(n, r, h)])

def check_clearance(plan):
    """Stealthburner clearance for tests printed one after another. A finished test must be
    far enough from each later one (behind it, in front of it or beside it) for the toolhead
    body, and far enough from the left waiting lane; low tests pass under the ducts. Tests
    taller than the gantry clearance must be in front of every later test, because the
    gantry runs behind the nozzle."""
    problems = []
    for j, (nj, rj, hj) in enumerate(plan):
        x0, y0, x1, y1 = rj[0][0], rj[0][1], rj[2][0], rj[2][1]
        if x0 < 0 or y0 < 0 or x1 > 300 or y1 > 300:
            problems.append(f"{nj} is off the bed")
        need = LOW_GAP if hj <= LOW_H else CLEAR_RADIUS / 2
        if x0 - WAIT_X < need:
            problems.append(f"{nj} is {x0 - WAIT_X:.1f}mm from the waiting lane, needs {need:.1f}mm")
        for ni, ri, hi in plan[:j]:
            behind = y0 - ri[2][1]                       # this test's front edge - finished test's back edge
            sep = max(behind, ri[0][1] - y1, x0 - ri[2][0], ri[0][0] - x1)
            need = LOW_GAP if hi <= LOW_H else CLEAR_RADIUS / 2
            if sep < need:
                problems.append(f"{nj} is {sep:.1f}mm from {ni} ({hi:.1f}mm tall), needs {need:.1f}mm")
            if hi > GANTRY_H and behind < need:
                problems.append(f"{nj} is not behind {ni} ({hi:.1f}mm tall, above the gantry clearance)")
    if problems:
        sys.exit("Stealthburner clearance check failed:\n  " + "\n  ".join(problems))

check_clearance(PLAN)

def gap_behind(name, extra=6):
    """Y of a travel/wait row just behind a finished test."""
    return next(r for n, r, h in PLAN if n == name)[2][1] + extra

# ================================================================ header
header_start = len(out)
g(f"; {NAME} calibration suite v5 ({MAT}, speed first from {VMAX}mm/s), generated by Claude: tools/calsuite.py")
for name, r, h in objects():
    poly = ",".join(f"[{x:.1f},{y:.1f}]" for x, y in r)
    cx = (r[0][0] + r[1][0]) / 2; cy = (r[0][1] + r[2][1]) / 2
    g(f"; {name}: {h:.1f}mm tall")
    g(f"EXCLUDE_OBJECT_DEFINE NAME={name} CENTER={cx:.1f},{cy:.1f} POLYGON=[{poly}]")
g(f"_CAL_BEGIN FILAMENT={NAME} TEMP={P['temps'][0]} RETRACT={P['start_retract']} RETRACT_SPEED={P['rspeed']}")
g(f"PRINT_START EXTRUDER={P['temps'][0]} BED={P['bed']} FILAMENT={MAT}")   # fresh adaptive mesh
g("_CAL_APPLY WHAT=retract")
g("SET_PRESSURE_ADVANCE ADVANCE=0")
g("SET_VELOCITY_LIMIT VELOCITY=300 ACCEL=3000 SQUARE_CORNER_VELOCITY=5")
g("G90"); g("M83"); g("M107")
mark["temp"] = len(out)

# ================================================================ 1. Orca temperature tower
g("EXCLUDE_OBJECT_START NAME=temp_tower")
retract(); g("G1 Z10.000 F1200")
g(f"G0 X{TOWER.start[0]:.3f} Y{TOWER.start[1]:.3f} F{TRAVEL_F}")
pos[0], pos[1] = TOWER.start
cur = [None]
def tower_layer(z):
    b = min(int((z - 0.1) // 10), len(TOWER_TEMPS) - 1)  # 10mm block per temperature
    if b != cur[0]:
        cur[0] = b
        g(f"; ---- temp block {b + 1}: {TOWER_TEMPS[b]}C from Z={z}")
        g(f"M104 S{TOWER_TEMPS[b]}"); g(f"M117 Temp {TOWER_TEMPS[b]}C")
TOWER.emit(on_layer=tower_layer)
g("SET_VELOCITY_LIMIT ACCEL=3000 SQUARE_CORNER_VELOCITY=5")
state["safe_z"] = max(state["safe_z"], TOWER.height)
g("EXCLUDE_OBJECT_END NAME=temp_tower")
gap = gap_behind("temp_tower")
wait_spot(gap)
ask("temp", f"{NAME} 1/6: temperature",
    f"Orca tower: each 10mm block is labelled with its temperature, walls at {VMAX}mm/s. Speed first: pick the HOTTEST block whose overhang, bridge and cone are still clean (more heat = more flow).",
    P["temps"], [f"{t}C" for t in P["temps"]])

# ================================================================ 2. Orca max volumetric speed (vase)
g("_CAL_APPLY WHAT=temp")
prime(gap)
mark["speed"] = len(out)
g("EXCLUDE_OBJECT_START NAME=max_flow")
route(*SPEED.start, gap)
cur = [None]
def speed_layer(z):
    if z <= SPEED_BAND / 8 + 1e-6:                       # first layer: as sliced (25mm/s)
        return
    b = min(int((z - 1e-6) // SPEED_BAND), len(SPEED_VOLS) - 1)
    if b != cur[0]:
        cur[0] = b
        g(f"; ---- band {b + 1}: {SPEED_VOLS[b]} mm3/s from Z={z}"); g(f"M117 Flow {SPEED_VOLS[b]}mm3/s")
def speed_move(c, z, dist):
    """Set each wall move's speed from its own extrusion so the band's mm3/s is exact."""
    if cur[0] is None or dist < 1e-6:
        return c
    mm3_per_mm = float(re.search(r"E([\d.]+)", c).group(1)) * FIL_A / dist
    f = SPEED_VOLS[cur[0]] / mm3_per_mm * 60
    return re.sub(r" F[\d.]+", "", c) + f" F{f:.0f}"
SPEED.emit(on_layer=speed_layer, on_extrude=speed_move)
state["safe_z"] = max(state["safe_z"], SPEED.height)
g("EXCLUDE_OBJECT_END NAME=max_flow")
gap = gap_behind("max_flow")
wait_spot(gap)
bands = [f"{v} ({b * SPEED_BAND:.1f}-{(b + 1) * SPEED_BAND:.1f}mm)" for b, v in enumerate(SPEED_VOLS)]
ask("max_flow", f"{NAME} 2/6: max volumetric speed",
    f"Orca speed test (60% size), single wall: every {SPEED_BAND}mm band (8 layers) is 2 mm3/s faster, from {V0} mm3/s ({VMAX}mm/s at 0.2mm layers) at the bed. Measure from the bed up to where the wall first gets rough, thin or gappy and pick the LAST band below it.",
    SPEED_VOLS, bands)

# ================================================================ 3. PA triangles: each on its own, filled bottoms, no base
prime(gap)
mark["pa"] = len(out)
tri_inradius = TRI_SIDE / (2 * math.sqrt(3))
for k, (cx, pa) in enumerate(zip(PA_X, PA_VALUES)):
    tri = tri_poly(k)
    g(f"EXCLUDE_OBJECT_START NAME=pa_{k + 1}")
    if k == 0:
        route(tri[0][0], tri[0][1], gap)
    else:                                               # over the finished triangles, then down
        retract(); g(f"G1 Z{PA_TOP + 2:.3f} F1200")
        g(f"G0 X{tri[0][0]:.3f} Y{tri[0][1]:.3f} F{TRAVEL_F}")
        pos[0], pos[1] = tri[0]
    g(f"G1 Z{FIRST_LH + 0.4:.3f} F1200")
    g(f"; triangle {k + 1}: PA {pa}"); g(f"SET_PRESSURE_ADVANCE ADVANCE={pa}"); g(f"M117 PA {fmt(pa)}")
    g("M107"); g("SET_VELOCITY_LIMIT ACCEL=3000 SQUARE_CORNER_VELOCITY=5")
    for i, z, h in layer_list(PA_TOP):
        g(f";LAYER Z:{z:.2f}"); g(f"G1 Z{z:.3f} F1200")
        if i == 1: g(f"M106 S{P['fan']}")
        if i == 2: g("SET_VELOCITY_LIMIT ACCEL=500 SQUARE_CORNER_VELOCITY=1")
        if z <= BASE_H + 1e-6:                          # solid bottom: concentric fill
            fill_concentric(tri, tri_inradius, z, h, FIRST_F if i == 0 else TEST_F)
        else:
            for n in reversed(range(3)):
                loop(offset_poly(tri, (n + 0.5) * W), z, h, TEST_F)
            if i == 2:
                emboss_top(fmt(pa), cx, ROW["pa"] - TRI_H / 2 + TRI_H / 3, z, 0.7)
    g(f"EXCLUDE_OBJECT_END NAME=pa_{k + 1}")
state["safe_z"] = max(state["safe_z"], PA_TOP)
g("SET_VELOCITY_LIMIT ACCEL=3000 SQUARE_CORNER_VELOCITY=5")
gap = gap_behind("pa_triangles")
wait_spot(gap)
ask("pa", f"{NAME} 3/6: pressure advance",
    f"Each triangle was printed on its own with its PA value printed on its filled bottom; walls ran at {VMAX}mm/s. Pick the one with the sharpest corners and even line width.",
    PA_VALUES, [fmt(p) for p in PA_VALUES])

# ================================================================ 4. flow blocks, printed together
g("_CAL_APPLY WHAT=pa")
prime(gap)
mark["flow"] = len(out)
cy = ROW["flow"]
g("EXCLUDE_OBJECT_START NAME=flow")
route(FLOW_X[0] - FLOW_W / 2, cy - FLOW_D / 2, gap)
g(f"G1 Z{FIRST_LH + 0.4:.3f} F1200")
g("M107")
for i, z, h in layer_list(FLOW_H):
    g(f";LAYER Z:{z:.2f}"); g(f"G1 Z{z:.3f} F1200"); fan_on(z)
    top = z > FLOW_H - 5 * LH
    for cx, fl in zip(FLOW_X, FLOWS):
        g(f"M221 S{fl}")
        solid_rect(cx - FLOW_W / 2, cy - FLOW_D / 2, cx + FLOW_W / 2, cy + FLOW_D / 2, z, h, i,
                   FIRST_F if i == 0 else TEST_F, FIRST_F if i == 0 else (50 * 60 if top else TEST_F))
z = round(FLOW_H + LH, 3)
g(f"G1 Z{z:.3f} F1200"); g("M221 S100")
for cx, fl in zip(FLOW_X, FLOWS):
    emboss_top(f"{fl}%", cx, cy, z, 1.2)
state["safe_z"] = max(state["safe_z"], FLOW_H + LH)
g("EXCLUDE_OBJECT_END NAME=flow")
gap = gap_behind("flow")
wait_spot(gap)
ask("flow", f"{NAME} 4/6: flow",
    "Each block shows its flow on top. Pick the smoothest, fully closed top surface.",
    FLOWS, [f"{f}%" for f in FLOWS])

# ================================================================ 5. Orca retraction tower
g("_CAL_APPLY WHAT=flow")
prime(gap)
mark["retract"] = len(out)
g("EXCLUDE_OBJECT_START NAME=retraction")
route(*RETRACT.start, gap)
cur = [None]
def retract_layer(z):
    b = min(max(int((z - RETRACT_BASE - 1e-6) // RETRACT_BAND), 0), len(RETRACTS) - 1)
    if b != cur[0]:
        cur[0] = b
        g(f"; ---- retraction band {b + 1}: {RETRACTS[b]}mm from Z={z}")
        g(f"SET_RETRACTION RETRACT_LENGTH={RETRACTS[b]}"); g(f"M117 Retract {RETRACTS[b]}mm")
RETRACT.emit(on_layer=retract_layer)
state["safe_z"] = max(state["safe_z"], RETRACT.height)
g("EXCLUDE_OBJECT_END NAME=retraction")
gap = gap_behind("retraction")
wait_spot(gap)
ask("retract_len", f"{NAME} 5/6: retraction",
    f"Orca retraction tower: the length goes up 0.1mm every 1mm (one tick on the pillars), from {RETRACTS[0]}mm just above the base to {RETRACTS[-1]}mm at the top, printed at {VMAX}mm/s. Pick the lowest band with no strings between the pillars.",
    RETRACTS, [f"{r}mm (Z{RETRACT_BASE + k * RETRACT_BAND:.1f}-{RETRACT_BASE + (k + 1) * RETRACT_BAND:.1f})"
               for k, r in enumerate(RETRACTS)])

# ================================================================ 6. Orca tolerance test
g("_CAL_APPLY WHAT=retract")
prime(gap)
mark["tolerance"] = len(out)
g("EXCLUDE_OBJECT_START NAME=tolerance")
route(*TOL.start, gap)
TOL.emit()
state["safe_z"] = max(state["safe_z"], TOL.height)
g("EXCLUDE_OBJECT_END NAME=tolerance")
wait_spot(gap)
ask("tolerance", f"{NAME} 6/6: tolerance",
    "Orca tolerance test: pop the hex key out of the 0.4mm hole and try it in each hole (0, 0.05, 0.1, 0.2, 0.3, 0.4mm clearance). Pick the TIGHTEST hole the key slides into without forcing.",
    TOLERANCES, [f"{fmt(t)}mm" for t in TOLERANCES])

g("M107")
g("_CAL_REPORT")
g("PRINT_END")

# ================================================================ resume: later tests only
SECTION_OBJECTS = dict(temp=["temp_tower"], speed=["max_flow"], pa=[n for n, r, h in TRI_OBJECTS],
                       flow=["flow"], retract=["retraction"], tolerance=["tolerance"])
already = [n for sec in SECTIONS[:SECTIONS.index(FROM)] for n in SECTION_OBJECTS[sec]]
if FROM != "temp":
    body = out[mark[FROM]:]
    out[:] = []
    g(f"; {NAME} calibration suite v5 ({MAT}), RESUMED from {FROM} with " + " ".join(f"{k}={v}" for k, v in ANSWERS.items()))
    g(f"; already printed (treated as still on the bed): {', '.join(already)}")
    for name, r, h in objects():
        if name in already:
            continue
        poly = ",".join(f"[{x:.1f},{y:.1f}]" for x, y in r)
        cx = (r[0][0] + r[1][0]) / 2; cy = (r[0][1] + r[2][1]) / 2
        g(f"; {name}: {h:.1f}mm tall")
        g(f"EXCLUDE_OBJECT_DEFINE NAME={name} CENTER={cx:.1f},{cy:.1f} POLYGON=[{poly}]")
    g(f"_CAL_BEGIN FILAMENT={NAME} TEMP={ANSWERS['temp']} RETRACT={ANSWERS.get('retract_len', P['start_retract'])} RETRACT_SPEED={P['rspeed']}")
    for k, v in ANSWERS.items():
        if k not in ("temp", "retract_len"):
            g(f"SET_GCODE_VARIABLE MACRO=_CAL VARIABLE={k} VALUE={v}")
    g(f"PRINT_START EXTRUDER={ANSWERS['temp']} BED={P['bed']} FILAMENT={MAT}")   # fresh adaptive mesh
    g("_CAL_APPLY WHAT=all")                             # earlier answers: temp, retraction, PA, flow
    g("SET_VELOCITY_LIMIT VELOCITY=300 ACCEL=3000 SQUARE_CORNER_VELOCITY=5")
    g("G90"); g("M83"); g("M107")
    g("G10")                                             # the body starts retracted (Klipper ignores a 2nd G10)
    out.extend(body)

# ================================================================ self-check of the G-code
def check_moves(lines):
    """Simulate the toolhead: no move may leave the bed, and no move may pass through a
    finished test below its height (+1mm)."""
    foot = {n: (r[0][0], r[0][1], r[2][0], r[2][1], h) for n, r, h in objects()}
    done, current, x, y, z, problems = list(already), None, 150.0, 150.0, 10.0, []
    def hits(box, ax, ay, bx, by):                    # segment vs rectangle (Liang-Barsky)
        x0, y0, x1, y1 = box[:4]
        t0, t1, dx, dy = 0.0, 1.0, bx - ax, by - ay
        for p, q in ((-dx, ax - x0), (dx, x1 - ax), (-dy, ay - y0), (dy, y1 - ay)):
            if abs(p) < 1e-12:
                if q < 0: return False
            else:
                t = q / p
                if p < 0: t0 = max(t0, t)
                else: t1 = min(t1, t)
        return t0 < t1
    for n, l in enumerate(lines):
        if l.startswith("EXCLUDE_OBJECT_START"):
            current = l.split("NAME=")[1]
        elif l.startswith("EXCLUDE_OBJECT_END"):
            done.append(current); current = None
        elif l.startswith(("G0 ", "G1 ")):
            d = dict(re.findall(r"([XYZ])(-?[\d.]+)", l))
            nx, ny, nz = float(d.get("X", x)), float(d.get("Y", y)), float(d.get("Z", z))
            if not (0 <= nx <= 300 and 0 <= ny <= 300):
                problems.append(f"line {n + 1}: off the bed ({nx:.1f},{ny:.1f})")
            lift = (nx, ny) == (x, y) and nz >= z               # straight up off a finished test
            for name in done:
                if not lift and min(z, nz) < foot[name][4] + 1.0 and hits(foot[name], x, y, nx, ny):
                    problems.append(f"line {n + 1}: through finished {name} at Z{min(z, nz):.2f}")
            x, y, z = nx, ny, nz
    if problems:
        sys.exit(f"Move check failed ({len(problems)}):\n  " + "\n  ".join(problems[:20]))

check_moves(out)
open(OUT, "w").write("\n".join(out) + "\n")
print(f"{OUT}: {len(out)} lines, tallest item {state['safe_z']:.1f}mm")
for name, r, h in PLAN:
    print(f"  {name:13s} X {r[0][0]:5.1f}-{r[2][0]:5.1f}  Y {r[0][1]:5.1f}-{r[2][1]:5.1f}  {h:5.2f}mm")
