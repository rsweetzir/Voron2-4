#!/usr/bin/env python3
"""
One-plate filament calibration suite with questions between tests (v3).

Prints, back to front, one test at a time, each on a solid base slab:
  1. Temperature tower: one tower with a capital-E footprint (arms give overhang/bridge
     detail); each temperature band is alternately inset/outset so bands are easy to see
                                                         -> asks: best temperature
  2. Stringing test: two square pyramids tapering from the base to a point, 3mm bands
     of retraction length at the chosen temperature     -> asks: best retraction length
  3. Pressure-advance triangles at temp + retraction     -> asks: sharpest triangle
  4. Flow blocks (25 x 12.5mm) at temp + retraction + PA -> asks: smoothest top
  5. Max volumetric ramp (single wall) with everything applied -> asks: last good band
Questions are Mainsail prompts (klipper/calibration.cfg: _CAL_ASK/_CAL_ANSWER); answers
are stored with SAVE_VARIABLE and applied by _CAL_APPLY before the next test.

Usage: calsuite.py MATERIAL OUT.gcode NAME     (MATERIAL: PLA or PETG)
"""
import math, sys

MAT = (sys.argv[1] if len(sys.argv) > 1 else "PLA").upper()
OUT = sys.argv[2] if len(sys.argv) > 2 else f"{MAT}_calibration_suite.gcode"
NAME = sys.argv[3] if len(sys.argv) > 3 else MAT

PROFILES = {
    "PLA":  dict(bed=60, temps=[220, 215, 210, 205, 200, 195, 190], fan=255,
                 retracts=[0.2, 0.4, 0.6, 0.8, 1.0, 1.2], rspeed=40, start_retract=0.6),
    "PLA_WOOD": dict(bed=60, temps=[230, 225, 220, 215, 210, 205, 200], fan=255,
                 retracts=[0.2, 0.4, 0.6, 0.8, 1.0, 1.2], rspeed=40, start_retract=0.6),
    "PETG": dict(bed=80, temps=[248, 244, 240, 236, 232, 228, 224], fan=102,
                 retracts=[0.2, 0.4, 0.6, 0.8, 1.0, 1.2], rspeed=60, start_retract=0.4),
}
P = PROFILES[MAT]
PA_VALUES = [round(0.01 * i, 2) for i in range(9)]       # 0.00 .. 0.08
FLOWS = [92, 96, 100, 104, 108]
VOLS = list(range(8, 25))                                # 8 .. 24 mm3/s

LH, FIRST_LH, W = 0.2, 0.25, 0.45
BASE_H = 0.45                                            # solid base slab: 2 layers (0.25 + 0.2)
FIL_A = math.pi * (1.75 / 2) ** 2
TRAVEL_F, WALL_F, FIRST_F, FILL_F = 200 * 60, 60 * 60, 25 * 60, 80 * 60
ROW = dict(temp=262, string=195, pa=145, flow=100, maxflow=40)   # nozzle Y of each row

out, pos, state = [], [0.0, 0.0], {"safe_z": 0.0}
g = out.append

# ---------------------------------------------------------------- motion helpers
def ext(x, y, h, f, w=W):
    d = math.hypot(x - pos[0], y - pos[1])
    if d > 1e-6:
        g(f"G1 X{x:.3f} Y{y:.3f} E{d * w * h / FIL_A:.5f} F{f:.0f}")
    pos[0], pos[1] = x, y

def hop_travel(x, y, z, hop=0.4):
    if math.hypot(x - pos[0], y - pos[1]) < 1.0:              # short hop: no retract needed
        g(f"G1 X{x:.3f} Y{y:.3f} F{TRAVEL_F}")
    else:
        g("G10"); g(f"G1 Z{z + hop:.3f} F1200")
        g(f"G0 X{x:.3f} Y{y:.3f} F{TRAVEL_F}")
        g(f"G1 Z{z:.3f} F1200"); g("G11")
    pos[0], pos[1] = x, y

def go_to_test(x, y):
    """Move to the next test's start, above everything printed so far."""
    z = state["safe_z"] + 10
    g("G10"); g(f"G1 Z{z:.3f} F1200")
    g(f"G0 X{x:.3f} Y{y:.3f} F{TRAVEL_F}")
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

def loop(poly, z, h, f, start_travel=True):
    if start_travel:
        hop_travel(poly[0][0], poly[0][1], z)
    else:
        g(f"G1 X{poly[0][0]:.3f} Y{poly[0][1]:.3f} F{TRAVEL_F}"); pos[0], pos[1] = poly[0]
    for p in poly[1:] + poly[:1]:
        ext(p[0], p[1], h, f)

def walls(poly, z, h, f, count=2):
    """Inner walls first, outer wall last."""
    for k in reversed(range(count)):
        loop(offset_poly(poly, (k + 0.5) * W), z, h, f, start_travel=True)

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

def base_slab(x0, y0, x1, y1):
    """Solid base under a tower: BASE_H tall."""
    for i, z, h in layer_list(BASE_H):
        g(f";BASE LAYER:{i} Z:{z:.2f}"); g(f"G1 Z{z:.3f} F1200"); fan_on(z)
        solid_rect(x0, y0, x1, y1, z, h, i, FIRST_F if i == 0 else WALL_F, FIRST_F if i == 0 else FILL_F)

def ask(var, title, text, options, labels=None):
    opts = ",".join(str(o) for o in options)
    lab = ",".join(labels) if labels else opts
    g(f'_CAL_ASK VAR={var} TITLE="{title}" TEXT="{text}" OPTIONS="{opts}" LABELS="{lab}"')


# ================================================================ v3 additions
# ---- retraction-aware motion (overrides the v2 helpers)
state["retracted"] = False
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
    if math.hypot(x - pos[0], y - pos[1]) < 1.0:
        g(f"G1 X{x:.3f} Y{y:.3f} F{TRAVEL_F}")
    else:
        retract(); g(f"G1 Z{z + hop:.3f} F1200")
        g(f"G0 X{x:.3f} Y{y:.3f} F{TRAVEL_F}")
        g(f"G1 Z{z:.3f} F1200")
    pos[0], pos[1] = x, y

ROW = dict(temp=262, string=195, pa=145, flow=100, maxflow=40)
WAIT_X = 8.0                                             # left lane, nothing is printed at X < 15

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

def emboss_front(text, cx, face_y, z, z_text0, row_h, px, f=40 * 60):
    """Raised label on a front (-Y) face: one bump line per lit pixel run at this layer."""
    if z < z_text0 or z >= z_text0 + 5 * row_h - 1e-6:
        return
    row = 4 - int((z - z_text0 + 1e-6) // row_h)
    x0 = cx - text_width(text, px) / 2
    yb = face_y - 0.35 * W                                # bump overlaps the face slightly
    for a, b in row_runs(text, row):
        hop_travel(x0 + a * px, yb, z, hop=0.2)
        ext(x0 + b * px, yb, LH, f)

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
def route(x, y, front_gap_y, z_clear=None):
    """Lift, step out to the gap in front of the current row, slide along it, then go to (x, y)."""
    z = (state["safe_z"] if z_clear is None else z_clear) + 5
    retract(); g(f"G1 Z{z:.3f} F1200")
    g(f"G0 X{pos[0]:.3f} Y{front_gap_y:.3f} F{TRAVEL_F}")
    g(f"G0 X{x:.3f} Y{front_gap_y:.3f} F{TRAVEL_F}")
    g(f"G0 X{x:.3f} Y{y:.3f} F{TRAVEL_F}")
    pos[0], pos[1] = x, y

def wait_spot(front_gap_y):
    """Leave the finished test via the front gap and wait in the empty left lane (no parking)."""
    route(WAIT_X, front_gap_y, front_gap_y)
    g("M400")

def ask(var, title, text, options, labels=None):
    opts = ",".join(str(o) for o in options)
    lab = ",".join(labels) if labels else opts
    g(f'_CAL_ASK VAR={var} TITLE="{title}" TEXT="{text}" OPTIONS="{opts}" LABELS="{lab}" PARK=0')

def fmt(v):
    s = f"{v:.2f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)
    return s

# ================================================================ header
E_W, E_D = 40.0, 20.0
PYR_BASE, PYR_TIP = 20.0, 2.0
TRI_SIDE = 22.0
SPEED_VOLS = list(range(8, 25, 2))                      # 8 .. 24 mm3/s, 9 bands
objects = {
    "temp_tower": rect(128, ROW["temp"] - 13, 172, ROW["temp"] + 13),
    "stringing":  rect(103, ROW["string"] - 13, 197, ROW["string"] + 13),
    "pa_triangles": rect(16, ROW["pa"] - 13, 284, ROW["pa"] + 13),
    "flow":       rect(55, ROW["flow"] - 8, 245, ROW["flow"] + 8),
    "max_flow":   rect(85, ROW["maxflow"] - 21, 215, ROW["maxflow"] + 21),
}
g(f"; {NAME} calibration suite v3 ({MAT}), generated by Claude: tools/calsuite.py")
for name, r in objects.items():
    poly = ",".join(f"[{x:.1f},{y:.1f}]" for x, y in r)
    cx = (r[0][0] + r[1][0]) / 2; cy = (r[0][1] + r[2][1]) / 2
    g(f"EXCLUDE_OBJECT_DEFINE NAME={name} CENTER={cx:.1f},{cy:.1f} POLYGON=[{poly}]")
g(f"_CAL_BEGIN FILAMENT={NAME} TEMP={P['temps'][0]} RETRACT={P['start_retract']} RETRACT_SPEED={P['rspeed']}")
g(f"PRINT_START EXTRUDER={P['temps'][0]} BED={P['bed']} FILAMENT={MAT} MESH=SAVED")
g("_CAL_APPLY WHAT=retract")
g("SET_PRESSURE_ADVANCE ADVANCE=0")
g("SET_VELOCITY_LIMIT ACCEL=3000 SQUARE_CORNER_VELOCITY=5")
g("G90"); g("M83"); g("M107")

# ================================================================ 1. temperature tower (E) with labels
cy = ROW["temp"]
ex0, ey0 = 130.0, cy - E_D / 2
E = [(0, 0), (40, 0), (40, 4), (6, 4), (6, 8), (30, 8), (30, 12), (6, 12), (6, 16), (40, 16),
     (40, 20), (0, 20)]
E = [(ex0 + x, ey0 + y) for x, y in E]
BAND = 5.0
g("EXCLUDE_OBJECT_START NAME=temp_tower")
z_clear = 10.0
retract(); g(f"G1 Z{z_clear:.3f} F1200"); g(f"G0 X{ex0 - 2:.3f} Y{ey0 - 2:.3f} F{TRAVEL_F}"); pos[0], pos[1] = ex0 - 2, ey0 - 2
base_slab(ex0 - 2, ey0 - 2, ex0 + 42, ey0 + 22)
cur = None
for i, z, h in layer_list(BASE_H + BAND * len(P["temps"]), start=round(BASE_H + LH, 3)):
    b = min(int((z - BASE_H - 1e-6) // BAND), len(P["temps"]) - 1)
    t = P["temps"][b]
    if t != cur:
        cur = t
        g(f"; ---- temp band {b + 1}: {t}C from Z={z:.2f}"); g(f"M104 S{t}"); g(f"M117 Temp {t}C")
    inset = 0.3 if b % 2 else 0.0
    g(f";LAYER Z:{z:.2f}"); g(f"G1 Z{z:.3f} F1200")
    walls(offset_poly(E, inset), z, h, WALL_F)
    emboss_front(str(t), ex0 + 20, ey0 + inset, z, BASE_H + b * BAND + 1.0, 0.6, 0.6)
state["safe_z"] = max(state["safe_z"], BASE_H + BAND * len(P["temps"]))
g("EXCLUDE_OBJECT_END NAME=temp_tower")
gap = ROW["temp"] - 13 - 12                             # gap in front of the temp row
wait_spot(gap)
ask("temp", f"{NAME} 1/5: temperature",
    "Each 5mm band is labelled on the front face. Pick the coolest band with clean walls, sharp E arms and good layer bonding.",
    P["temps"], [f"{t}C" for t in P["temps"]])

# ================================================================ 2. stringing pyramids (0.1mm steps)
g("_CAL_APPLY WHAT=temp")
retracts = [round(0.2 + 0.1 * k, 1) for k in range(12)]   # 0.2 .. 1.3
cy, BAND = ROW["string"], 3.0
H = BAND * len(retracts)
xs = (128.0, 172.0)
g("EXCLUDE_OBJECT_START NAME=stringing")
x_b0, y_b0 = xs[0] - PYR_BASE / 2 - 3, cy - PYR_BASE / 2 - 3
route(x_b0, y_b0, gap)
g(f"G1 Z{FIRST_LH + 0.4:.3f} F1200")
base_slab(x_b0, y_b0, xs[1] + PYR_BASE / 2 + 3, cy + PYR_BASE / 2 + 3)
cur = None
for i, z, h in layer_list(BASE_H + H, start=round(BASE_H + LH, 3)):
    b = min(int((z - BASE_H - 1e-6) // BAND), len(retracts) - 1)
    r = retracts[b]
    if r != cur:
        cur = r
        g(f"; ---- retraction band {b + 1}: {r}mm from Z={z:.2f}")
        g(f"SET_RETRACTION RETRACT_LENGTH={r}"); g(f"M117 Retract {r}mm")
    s = PYR_BASE - (PYR_BASE - PYR_TIP) * (z - BASE_H) / H
    inset = 0.3 if b % 2 else 0.0
    g(f";LAYER Z:{z:.2f}"); g(f"G1 Z{z:.3f} F1200")
    for px_ in xs:
        sq = offset_poly(rect(px_ - s / 2, cy - s / 2, px_ + s / 2, cy + s / 2), inset)
        walls(sq, z, h, WALL_F, count=2 if s > 4 * W else 1)
        label = fmt(r)
        if s - 2 * inset > text_width(label, 0.45) + 1.5:
            emboss_front(label, px_, cy - s / 2 + inset, z, BASE_H + b * BAND + 0.5, 0.4, 0.45)
state["safe_z"] = max(state["safe_z"], BASE_H + H)
g("EXCLUDE_OBJECT_END NAME=stringing")
gap = ROW["string"] - 13 - 10
wait_spot(gap)
ask("retract_len", f"{NAME} 2/5: retraction",
    "Pyramid bands are 3mm each, 0.2 to 1.3mm in 0.1mm steps, labelled on the front faces where they fit. Pick the lowest band with a clean gap.",
    retracts, [f"{r}mm" for r in retracts])

# ================================================================ 3. PA triangles on labelled bases
g("_CAL_APPLY WHAT=retract")
g("SET_VELOCITY_LIMIT ACCEL=500 SQUARE_CORNER_VELOCITY=1")
cy = ROW["pa"]
th = TRI_SIDE * math.sqrt(3) / 2
xs = [30 + i * 30 for i in range(len(PA_VALUES))]       # 30 .. 270
row_gap = cy - th / 2 - 2 - 8                           # just in front of the triangle bases
g("EXCLUDE_OBJECT_START NAME=pa_triangles")
for k, (cx, pa) in enumerate(zip(xs, PA_VALUES)):
    g(f"; ---- triangle {k + 1}: PA {pa} at X={cx}")
    bx0, by0, bx1, by1 = cx - TRI_SIDE / 2 - 1.5, cy - th / 2 - 1.5, cx + TRI_SIDE / 2 + 1.5, cy + th / 2 + 1.5
    route(bx0, by0, gap if k == 0 else row_gap)
    g("SET_VELOCITY_LIMIT ACCEL=3000 SQUARE_CORNER_VELOCITY=5")
    g(f"G1 Z{FIRST_LH + 0.4:.3f} F1200")
    base_slab(bx0, by0, bx1, by1)
    g("SET_VELOCITY_LIMIT ACCEL=500 SQUARE_CORNER_VELOCITY=1")
    g(f"SET_PRESSURE_ADVANCE ADVANCE={pa}"); g(f"M117 PA {pa}")
    tri = [(cx - TRI_SIDE / 2, cy - th / 2), (cx + TRI_SIDE / 2, cy - th / 2), (cx, cy + th / 2)]
    centroid_y = cy - th / 2 + th / 3
    for i, z, h in layer_list(BASE_H + 0.8, start=round(BASE_H + LH, 3)):   # 4 layers on the base
        g(f"G1 Z{z:.3f} F1200")
        for n in reversed(range(3)):
            loop(offset_poly(tri, (n + 0.5) * W), z, h, 100 * 60)
        if i == 0:
            emboss_top(fmt(pa), cx, centroid_y, z, 0.55)
    state["safe_z"] = max(state["safe_z"], BASE_H + 0.8)
    retract(); g(f"G1 Z{BASE_H + 3:.3f} F1200")
    pos[0], pos[1] = pos[0], pos[1]
g("EXCLUDE_OBJECT_END NAME=pa_triangles")
g("SET_VELOCITY_LIMIT ACCEL=3000 SQUARE_CORNER_VELOCITY=5")
wait_spot(row_gap)
ask("pa", f"{NAME} 3/5: pressure advance",
    "Each triangle has its PA value printed on its base. Pick the one with the sharpest corners and even line width.",
    PA_VALUES, [fmt(p) for p in PA_VALUES])

# ================================================================ 4. flow blocks with top labels
g("_CAL_APPLY WHAT=pa")
cy, bw, bd = ROW["flow"], 25.0, 12.5
row_gap = cy - bd / 2 - 8
g("EXCLUDE_OBJECT_START NAME=flow")
for k, (cx, fl) in enumerate(zip([70.0, 110.0, 150.0, 190.0, 230.0], FLOWS)):
    g(f"; ---- block {k + 1}: flow {fl}% at X={cx}")
    route(cx - bw / 2, cy - bd / 2, (ROW["pa"] - TRI_SIDE * math.sqrt(3) / 4 - 2 - 8) if k == 0 else row_gap)
    g(f"G1 Z{FIRST_LH + 0.4:.3f} F1200")
    g(f"M221 S{fl}"); g(f"M117 Flow {fl}%")
    for i, z, h in layer_list(3.0):
        g(f"G1 Z{z:.3f} F1200"); fan_on(z)
        top = z > 3.0 - 5 * LH
        solid_rect(cx - bw / 2, cy - bd / 2, cx + bw / 2, cy + bd / 2, z, h, i,
                   FIRST_F if i == 0 else WALL_F, FIRST_F if i == 0 else (50 * 60 if top else FILL_F))
    z = round(3.0 + LH, 3)
    g(f"G1 Z{z:.3f} F1200"); g("M221 S100")
    emboss_top(f"{fl}%", cx, cy, z, 0.9)
    state["safe_z"] = max(state["safe_z"], z)
    retract(); g(f"G1 Z{z + 3:.3f} F1200")
g("EXCLUDE_OBJECT_END NAME=flow")
wait_spot(row_gap)
ask("flow", f"{NAME} 4/5: flow",
    "Each block shows its flow on top. Pick the smoothest, fully closed top surface.",
    FLOWS, [f"{f}%" for f in FLOWS])

# ================================================================ 5. speed wall: dents + labels each band
g("_CAL_APPLY WHAT=flow")
g("SET_VELOCITY_LIMIT VELOCITY=300 ACCEL=3000 SQUARE_CORNER_VELOCITY=5")
cy, hx, hy, w5 = ROW["maxflow"], 55.0, 12.0, 0.5
BAND = 4.0
g("EXCLUDE_OBJECT_START NAME=max_flow")
route(150 - hx - 8, cy - hy - 8, row_gap)
g(f"G1 Z{FIRST_LH + 0.4:.3f} F1200")
base_slab(150 - hx - 8, cy - hy - 8, 150 + hx + 8, cy + hy + 8)   # wide base doubles as a brim
g("M106 S128")                                           # half fan: less curl on the thin wall
cur = None
for i, z, h in layer_list(BASE_H + BAND * len(SPEED_VOLS), start=round(BASE_H + LH, 3)):
    b = min(int((z - BASE_H - 1e-6) // BAND), len(SPEED_VOLS) - 1)
    vol = SPEED_VOLS[b]
    if vol != cur:
        cur = vol
        g(f"; ---- band {b + 1}: {vol} mm3/s ({vol / (LH * w5):.0f} mm/s)"); g(f"M117 Flow {vol}mm3/s")
    d = -0.3 if b % 2 else 0.0                           # alternate bands step out 0.3mm
    ring = offset_poly(rect(150 - hx, cy - hy, 150 + hx, cy + hy), d)
    g(f"G1 Z{z:.3f} F1200")
    hop_travel(ring[0][0], ring[0][1], z)
    f = vol / (h * w5) * 60
    for p in ring[1:] + ring[:1]:
        ext(p[0], p[1], h, f, w5)
    emboss_front(str(vol), 150, cy - hy + d - w5 / 2, z, BASE_H + b * BAND + 0.8, 0.6, 0.6)
state["safe_z"] = max(state["safe_z"], BASE_H + BAND * len(SPEED_VOLS))
g("EXCLUDE_OBJECT_END NAME=max_flow")
wait_spot(cy - hy - 8 - 6)
ask("max_flow", f"{NAME} 5/5: max flow",
    "Each 4mm band shows its flow in mm3/s on the front face (x10 = mm/s). Pick the LAST band that still looks solid.",
    SPEED_VOLS)

g("M107")
g("_CAL_REPORT")
g("PRINT_END")
open(OUT, "w").write("\n".join(out) + "\n")
print(f"{OUT}: {len(out)} lines, tallest item {state['safe_z']:.1f}mm")
