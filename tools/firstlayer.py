#!/usr/bin/env python3
# First-layer test: nine 30x30mm single-layer squares spread over the bed (corners, edge
# midpoints, centre). Squares are printed through the normal PRINT_START, so the adaptive
# mesh covers the whole bed. Compare the squares: all alike = mesh matches the bed;
# squished/transparent or rough on some = nozzle too close there; gaps/round lines = too far.
#   Square names: FL FC FR / ML MC MR / BL BC BR (front/mid/back, left/centre/right as you
#   face the printer; front = low Y).
import math, sys

TEMP, BED, PA = 210, 60, 0.05
SIZE, LH, W = 30.0, 0.2, 0.5
FIL_A = math.pi * (1.75 / 2) ** 2
COLS = {"L": 40.0, "C": 150.0, "R": 260.0}
ROWS = {"F": 40.0, "M": 150.0, "B": 260.0}
PRINT_F, TRAVEL_F = 30 * 60, 200 * 60
OUT = sys.argv[1] if len(sys.argv) > 1 else "first_layer_test_9sq.gcode"

out, pos = [], [0.0, 0.0]
g = out.append

def ext(x, y, f=PRINT_F):
    d = math.hypot(x - pos[0], y - pos[1])
    if d > 0:
        g(f"G1 X{x:.3f} Y{y:.3f} E{d * W * LH / FIL_A:.5f} F{f}")
    pos[0], pos[1] = x, y

def travel(x, y):
    g("G10"); g(f"G1 Z{LH + 0.4:.3f} F1200")
    g(f"G0 X{x:.3f} Y{y:.3f} F{TRAVEL_F}")
    g(f"G1 Z{LH:.3f} F1200"); g("G11")
    pos[0], pos[1] = x, y

def square(cx, cy):
    for size in (SIZE - W, SIZE - 3 * W):                   # two perimeters, outer first
        h = size / 2
        travel(cx - h, cy - h)
        for p in ((cx + h, cy - h), (cx + h, cy + h), (cx - h, cy + h), (cx - h, cy - h)):
            ext(*p)
    lo, hi = -(SIZE / 2) + 2.5 * W, (SIZE / 2) - 2.5 * W  # zig-zag fill along X
    n = int((hi - lo) / W) + 1
    travel(cx + lo, cy + lo)
    for i in range(n):
        y = cy + lo + i * W
        a, b = (cx + lo, y), (cx + hi, y)
        if i % 2:
            a, b = b, a
        if i:
            ext(*a)
        else:
            pos[0], pos[1] = a
        ext(*b)

squares = [(r + c, COLS[c], ROWS[r]) for r in "FMB" for c in "LCR"]
g(f"; first-layer test, {len(squares)} squares {SIZE:.0f}mm, layer {LH}mm, {TEMP}C / bed {BED}C")
for name, cx, cy in squares:
    h = SIZE / 2
    poly = f"[{cx - h:.1f},{cy - h:.1f}],[{cx + h:.1f},{cy - h:.1f}],[{cx + h:.1f},{cy + h:.1f}],[{cx - h:.1f},{cy + h:.1f}]"
    g(f"EXCLUDE_OBJECT_DEFINE NAME={name} CENTER={cx:.1f},{cy:.1f} POLYGON=[{poly}]")
g(f"PRINT_START EXTRUDER={TEMP} BED={BED} FILAMENT=PLA")
g(f"SET_PRESSURE_ADVANCE ADVANCE={PA}")
g("G90"); g("M83"); g("M107")
# Snake through the grid: front row left->right, middle right->left, back left->right
for row in ("F", "M", "B"):
    order = "LCR" if row != "M" else "RCL"
    for col in order:
        name = row + col
        g(f"EXCLUDE_OBJECT_START NAME={name}")
        square(COLS[col], ROWS[row])
        g(f"EXCLUDE_OBJECT_END NAME={name}")
g("G10"); g("G1 Z5 F1200")
g("PRINT_END")

with open(OUT, "w") as f:
    f.write("\n".join(out) + "\n")
print(f"wrote {OUT}: {len(out)} lines")
