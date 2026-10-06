#!/usr/bin/env python3
"""
One-plate filament calibration suite with questions between tests (v2).

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
    "PETG": dict(bed=80, temps=[248, 244, 240, 236, 232, 228, 224], fan=102,
                 retracts=[0.2, 0.4, 0.6, 0.8, 1.0, 1.2], rspeed=60, start_retract=0.4),
}
P = PROFILES[MAT]
PA_VALUES = [round(0.01 * i, 2) for i in range(9)]       # 0.00 .. 0.08
FLOWS = [92, 96, 100, 104, 108]
VOLS = list(range(8, 25))                                # 8 .. 24 mm3/s

LH, FIRST_LH, W = 0.2, 0.25, 0.45
BASE_H = 1.05                                            # solid base slab: 0.25 + 4 x 0.2
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

# ================================================================ header
objects = {
    "temp_tower": rect(128, ROW["temp"] - 13, 172, ROW["temp"] + 13),
    "stringing":  rect(110, ROW["string"] - 10, 190, ROW["string"] + 10),
    "pa_triangles": rect(18, ROW["pa"] - 12, 282, ROW["pa"] + 12),
    "flow":       rect(55, ROW["flow"] - 8, 245, ROW["flow"] + 8),
    "max_flow":   rect(90, ROW["maxflow"] - 16, 210, ROW["maxflow"] + 16),
}
g(f"; {NAME} calibration suite v2 ({MAT}), generated by Claude: tools/calsuite.py")
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

# ================================================================ 1. temperature tower (E)
cy = ROW["temp"]
# capital E, 40 x 20mm, spine on the left, arms 4mm thick, CCW from bottom-left
ex0, ey0 = 130.0, cy - 10
E = [(0, 0), (40, 0), (40, 4), (6, 4), (6, 8), (30, 8), (30, 12), (6, 12), (6, 16), (40, 16),
     (40, 20), (0, 20)]
E = [(ex0 + x, ey0 + y) for x, y in E]
BAND = 5.0
g("EXCLUDE_OBJECT_START NAME=temp_tower")
go_to_test(ex0 - 2, ey0 - 2)
base_slab(ex0 - 2, ey0 - 2, ex0 + 42, ey0 + 22)
cur = None
for i, z, h in layer_list(BASE_H + BAND * len(P["temps"]), start=round(BASE_H + LH, 3)):
    b = min(int((z - BASE_H - 1e-6) // BAND), len(P["temps"]) - 1)
    t = P["temps"][b]
    if t != cur:
        cur = t
        g(f"; ---- temp band {b + 1}: {t}C from Z={z:.2f}"); g(f"M104 S{t}"); g(f"M117 Temp {t}C")
    inset = 0.3 if b % 2 else 0.0                       # alternate bands step in by 0.3mm
    g(f";LAYER Z:{z:.2f}"); g(f"G1 Z{z:.3f} F1200")
    walls(offset_poly(E, inset), z, h, WALL_F)
state["safe_z"] = max(state["safe_z"], BASE_H + BAND * len(P["temps"]))
g("EXCLUDE_OBJECT_END NAME=temp_tower")
temps = P["temps"]
ask("temp", f"{NAME} 1/5: temperature",
    "Bands are 5mm each above the base, bottom to top: " + ", ".join(f"{t}C" for t in temps)
    + ". Pick the coolest band with clean walls, sharp E arms and good layer bonding.",
    temps, [f"{t}C" for t in temps])

# ================================================================ 2. stringing pyramids
g("_CAL_APPLY WHAT=temp")
cy, BAND, base_s, tip_s = ROW["string"], 3.0, 14.0, 2.0
H = BAND * len(P["retracts"])
xs = (128.0, 172.0)
g("EXCLUDE_OBJECT_START NAME=stringing")
go_to_test(xs[0] - base_s / 2 - 3, cy - base_s / 2 - 3)
base_slab(xs[0] - base_s / 2 - 3, cy - base_s / 2 - 3, xs[1] + base_s / 2 + 3, cy + base_s / 2 + 3)
cur = None
for i, z, h in layer_list(BASE_H + H, start=round(BASE_H + LH, 3)):
    b = min(int((z - BASE_H - 1e-6) // BAND), len(P["retracts"]) - 1)
    r = P["retracts"][b]
    if r != cur:
        cur = r
        g(f"; ---- retraction band {b + 1}: {r}mm from Z={z:.2f}")
        g(f"SET_RETRACTION RETRACT_LENGTH={r}"); g(f"M117 Retract {r}mm")
    s = base_s - (base_s - tip_s) * (z - BASE_H) / H
    g(f";LAYER Z:{z:.2f}"); g(f"G1 Z{z:.3f} F1200")
    for px in xs:                                       # travel across the gap every layer
        sq = rect(px - s / 2, cy - s / 2, px + s / 2, cy + s / 2)
        walls(sq, z, h, WALL_F, count=2 if s > 4 * W else 1)
state["safe_z"] = max(state["safe_z"], BASE_H + H)
g("EXCLUDE_OBJECT_END NAME=stringing")
ask("retract_len", f"{NAME} 2/5: retraction",
    "Pyramid bands are 3mm each above the base, bottom to top: " + ", ".join(f"{r}mm" for r in P["retracts"])
    + ". Pick the lowest band with a clean gap between the pyramids.",
    P["retracts"], [f"{r}mm" for r in P["retracts"]])

# ================================================================ 3. PA triangles
g("_CAL_APPLY WHAT=retract")
g("SET_VELOCITY_LIMIT ACCEL=500 SQUARE_CORNER_VELOCITY=1")
cy, side = ROW["pa"], 22.0
th = side * math.sqrt(3) / 2
xs = [30 + i * 30 for i in range(len(PA_VALUES))]       # 30 .. 270
g("EXCLUDE_OBJECT_START NAME=pa_triangles")
go_to_test(xs[0] - side / 2, cy - th / 2)
for k, (cx, pa) in enumerate(zip(xs, PA_VALUES)):
    g(f"; ---- triangle {k + 1}: PA {pa} at X={cx}")
    g(f"SET_PRESSURE_ADVANCE ADVANCE={pa}"); g(f"M117 PA {pa}")
    for i, z, h in layer_list(0.85):                    # 4 layers
        g(f"G1 Z{z:.3f} F1200"); fan_on(z)
        f = FIRST_F if i == 0 else 100 * 60
        tri = [(cx - side / 2, cy - th / 2), (cx + side / 2, cy - th / 2), (cx, cy + th / 2)]   # CCW
        for n in reversed(range(3)):                    # 3 nested outlines, outer last
            loop(offset_poly(tri, (n + 0.5) * W), z, h, f)
    state["safe_z"] = max(state["safe_z"], 1.0)
g("EXCLUDE_OBJECT_END NAME=pa_triangles")
g("SET_VELOCITY_LIMIT ACCEL=3000 SQUARE_CORNER_VELOCITY=5")
ask("pa", f"{NAME} 3/5: pressure advance",
    "Triangles left to right: PA " + ", ".join(str(p) for p in PA_VALUES)
    + ". Pick the one with the sharpest corners and even line width (no bulge, no gap).",
    PA_VALUES)

# ================================================================ 4. flow blocks
g("_CAL_APPLY WHAT=pa")
cy, bw, bd = ROW["flow"], 25.0, 12.5
g("EXCLUDE_OBJECT_START NAME=flow")
for k, (cx, fl) in enumerate(zip([70.0, 110.0, 150.0, 190.0, 230.0], FLOWS)):
    g(f"; ---- block {k + 1}: flow {fl}% at X={cx}")
    g(f"M221 S{fl}"); g(f"M117 Flow {fl}%")
    go_to_test(cx - bw / 2, cy - bd / 2)
    for i, z, h in layer_list(3.0):
        g(f"G1 Z{z:.3f} F1200"); fan_on(z)
        top = z > 3.0 - 5 * LH
        solid_rect(cx - bw / 2, cy - bd / 2, cx + bw / 2, cy + bd / 2, z, h, i,
                   FIRST_F if i == 0 else WALL_F, FIRST_F if i == 0 else (50 * 60 if top else FILL_F))
    state["safe_z"] = max(state["safe_z"], 3.0)
g("M221 S100")
g("EXCLUDE_OBJECT_END NAME=flow")
ask("flow", f"{NAME} 4/5: flow",
    "Blocks left to right: " + ", ".join(f"{f}%" for f in FLOWS) + ". Pick the smoothest, fully closed top surface.",
    FLOWS, [f"{f}%" for f in FLOWS])

# ================================================================ 5. max volumetric ramp
g("_CAL_APPLY WHAT=flow")
g("SET_VELOCITY_LIMIT VELOCITY=300 ACCEL=3000 SQUARE_CORNER_VELOCITY=5")
cy, hx, hy, w5 = ROW["maxflow"], 55.0, 12.0, 0.5   # 24mm deep so the thin wall stays put
g("EXCLUDE_OBJECT_START NAME=max_flow")
go_to_test(150 - hx - 3, cy - hy - 3)
base_slab(150 - hx - 3, cy - hy - 3, 150 + hx + 3, cy + hy + 3)
hop_travel(150 - hx, cy - hy, round(BASE_H + LH, 3))
cur = None
for i, z, h in layer_list(BASE_H + 2.0 * len(VOLS), start=round(BASE_H + LH, 3)):
    b = min(int((z - BASE_H - 1e-6) // 2.0), len(VOLS) - 1)
    if VOLS[b] != cur:
        cur = VOLS[b]
        g(f"; ---- band {b + 1}: {cur} mm3/s"); g(f"M117 Flow {cur}mm3/s")
    g(f"G1 Z{z:.3f} F1200")
    f = cur / (h * w5) * 60
    for p in [(150 + hx, cy - hy), (150 + hx, cy + hy), (150 - hx, cy + hy), (150 - hx, cy - hy)]:
        ext(p[0], p[1], h, f, w5)
state["safe_z"] = max(state["safe_z"], BASE_H + 2.0 * len(VOLS))
g("EXCLUDE_OBJECT_END NAME=max_flow")
g("G10"); g(f"G1 Z{state['safe_z'] + 10:.3f} F1200")
ask("max_flow", f"{NAME} 5/5: max flow",
    "2mm bands above the base, mm3/s bottom to top: " + ", ".join(str(v) for v in VOLS)
    + ". Pick the LAST band that still looks solid.",
    VOLS[::2], [str(v) for v in VOLS[::2]])

g("M107")
g("_CAL_REPORT")
g("PRINT_END")
open(OUT, "w").write("\n".join(out) + "\n")
print(f"{OUT}: {len(out)} lines, tallest item {state['safe_z']:.1f}mm")
