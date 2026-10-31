#!/usr/bin/env python3
# SPDX-License-Identifier: MIT  (c) 2026 The Voron2-4 authors, see LICENSE
# Fine flow test: eight 15x15mm solid squares printed together, layer by layer, each with its
# own flow baked into the G-code extrusion amounts (base 1.00, no M221; PRINT_START resets M221
# to 100). Squares are numbered 1-8 by raised dots along their front edge; front row left to
# right is 1-4, back row 5-8. The top 5 layers all run at 45deg, so the top surface shows:
# grooves / gaps between lines = too little flow, ridges / rough raised lines = too much.
# After PRINT_END (heaters off) a Mainsail pop-up asks for the best square and saves
# cal_<name>_flow (calibration.cfg _CAL_ASK).
#   flowfine.py OUT.gcode [OUT.svg]
#   e.g. tools/flowfine.py ~/Downloads/PLA_Matte_WoodBrown_flow_100-104.gcode
import math, sys

NAME = "PLA_Matte_WoodBrown"                  # _CAL filament name: saves cal_pla_matte_woodbrown_flow
# "Voron PLA Matte Wood Brown" preset: 210C (215 first layer), bed 60, PA 0.05, retraction 0.2@40
TEMP, FIRST_TEMP, BED, PA, RETRACT, RSPEED, FAN = 210, 215, 60, 0.05, 0.2, 40, 255
FLOWS = [100.0, 100.6, 101.1, 101.7, 102.3, 102.9, 103.4, 104.0]   # percent, squares 1-8
SIZE, HEIGHT, TOP_LAYERS = 15.0, 2.85, 5      # 0.25 + 13 x 0.2 = 2.85mm, 14 layers
LH, FIRST_LH, W = 0.2, 0.25, 0.45
FIL_A = math.pi * (1.75 / 2) ** 2
XS, YS = [105.0, 135.0, 165.0, 195.0], [135.0, 165.0]   # 15mm gaps, centred on the bed
CENTRES = [(x, y) for y in YS for x in XS]
OUTER_F, INNER_F, FILL_F, TOP_F, FIRST_F, TRAVEL_F = 60 * 60, 80 * 60, 80 * 60, 80 * 60, 25 * 60, 200 * 60
DOT, DOT_PITCH = 0.9, 1.6                    # label dots: 0.9mm dashes, one extra layer on top
OUT = sys.argv[1] if len(sys.argv) > 1 else f"{NAME}_flow_100-104.gcode"
SVG = sys.argv[2] if len(sys.argv) > 2 else None

out, pos, state = [], [0.0, 0.0], {"retracted": False, "flow": 1.0}
g = out.append

def retract():
    if not state["retracted"]:
        g("G10"); state["retracted"] = True

def ext(x, y, h, f):
    if state["retracted"]:
        g("G11"); state["retracted"] = False
    d = math.hypot(x - pos[0], y - pos[1])
    if d > 1e-6:
        g(f"G1 X{x:.3f} Y{y:.3f} E{d * W * h * state['flow'] / FIL_A:.5f} F{f:.0f}")
    pos[0], pos[1] = x, y

def hop_travel(x, y, z, hop=0.4):
    if math.hypot(x - pos[0], y - pos[1]) < 1.0:              # short hop: no retract needed
        g(f"G1 X{x:.3f} Y{y:.3f} F{TRAVEL_F}")
    else:
        retract(); g(f"G1 Z{z + hop:.3f} F1200")
        g(f"G0 X{x:.3f} Y{y:.3f} F{TRAVEL_F}")
        g(f"G1 Z{z:.3f} F1200")
    pos[0], pos[1] = x, y

def loop(cx, cy, size, h, f, z):
    half = size / 2
    hop_travel(cx - half, cy - half, z)
    for p in [(cx + half, cy - half), (cx + half, cy + half), (cx - half, cy + half), (cx - half, cy - half)]:
        ext(p[0], p[1], h, f)

def diag_lines(cx, cy, half, angle45):
    """Solid infill inside [cx-half, cx+half]^2 at +45deg (x - y = c) or -45deg (x + y = c),
    W apart, ordered one way across the square (monotonic)."""
    step = W * math.sqrt(2)
    n = int(4 * half / step)
    lines = []
    for i in range(n + 1):
        c = -n * step / 2 + i * step                       # centred: equal margins at both corners
        if angle45:      # u - v = c, u, v in [-half, half] (u = x - cx, v = y - cy)
            a = (max(-half, c - half), max(-half, c - half) - c)
            b = (min(half, c + half), min(half, c + half) - c)
        else:            # u + v = c
            a = (max(-half, c - half), c - max(-half, c - half))
            b = (min(half, c + half), c - min(half, c + half))
        if math.hypot(b[0] - a[0], b[1] - a[1]) > W:
            lines.append(((cx + a[0], cy + a[1]), (cx + b[0], cy + b[1])))
    return lines

def square_layer(cx, cy, z, h, layer, top):
    first = layer == 0
    loop(cx, cy, SIZE - 3 * W, h, FIRST_F if first else INNER_F, z)   # inner wall (centre line)
    loop(cx, cy, SIZE - W, h, FIRST_F if first else OUTER_F, z)       # outer wall: outside edge = SIZE
    half = SIZE / 2 - 2.35 * W                                       # line centres: 15% overlap with the inner wall
    lines = diag_lines(cx, cy, half, top or layer % 2 == 0)
    for i, (a, b) in enumerate(lines):
        if i % 2:
            a, b = b, a
        if i == 0:
            hop_travel(*a, z)
        else:
            g(f"G1 X{a[0]:.3f} Y{a[1]:.3f} F{TRAVEL_F}")             # step over to the next line
            pos[0], pos[1] = a
        ext(b[0], b[1], h, FIRST_F if first else (TOP_F if top else FILL_F))

def label(cx, cy, n, z):
    """n raised dashes (along Y) in a row 1.4mm inside the front edge, one 0.2mm layer."""
    x0 = cx - (n - 1) * DOT_PITCH / 2
    y0 = cy - SIZE / 2 + 1.4
    for k in range(n):
        x = x0 + k * DOT_PITCH
        hop_travel(x, y0, z)
        ext(x, y0 + DOT, LH, FILL_F / 4)

def rect(cx, cy, half):
    return [(cx - half, cy - half), (cx + half, cy - half), (cx + half, cy + half), (cx - half, cy + half)]

# ---------------------------------------------------------------- header
g(f"; {NAME} fine flow test {FLOWS[0]:.1f}-{FLOWS[-1]:.1f}%, generated by Claude: tools/flowfine.py")
g("; Flow is in the extrusion amounts of each square (base 1.00), not M221")
for k, ((cx, cy), fl) in enumerate(zip(CENTRES, FLOWS)):
    g(f"; square {k + 1} ({k + 1} dot{'s' if k else ''}) at X{cx:.0f} Y{cy:.0f}: flow {fl:.1f}%")
for k, (cx, cy) in enumerate(CENTRES):
    poly = ",".join(f"[{x:.1f},{y:.1f}]" for x, y in rect(cx, cy, SIZE / 2))
    g(f"EXCLUDE_OBJECT_DEFINE NAME=flow_{k + 1} CENTER={cx:.1f},{cy:.1f} POLYGON=[{poly}]")
g(f"_CAL_BEGIN FILAMENT={NAME} TEMP={TEMP} RETRACT={RETRACT} RETRACT_SPEED={RSPEED} PA={PA} FLOW=100")
g(f"PRINT_START EXTRUDER={FIRST_TEMP} BED={BED} FILAMENT=PLA")
# filament start G-code of the preset
g(f"SET_PRESSURE_ADVANCE ADVANCE={PA}")
g(f"SET_RETRACTION RETRACT_LENGTH={RETRACT} RETRACT_SPEED={RSPEED} UNRETRACT_SPEED=30")
g("SET_VELOCITY_LIMIT ACCEL=3000 SQUARE_CORNER_VELOCITY=5")
g("G90"); g("M83"); g("M107")

# ---------------------------------------------------------------- squares, layer by layer
layers, z, i = [], FIRST_LH, 0
while z <= HEIGHT + 1e-6:
    layers.append((i, z, FIRST_LH if i == 0 else LH)); i += 1; z = round(z + LH, 3)
for layer, z, h in layers:
    g(f";LAYER:{layer} Z:{z:.2f}")
    if layer == 1:
        g(f"M104 S{TEMP}")
    if layer == 2:
        g(f"M106 S{FAN}")
    top = layer >= len(layers) - TOP_LAYERS
    order = range(8) if layer % 2 == 0 else reversed(range(8))      # shorter travels: snake
    for k in order:
        cx, cy = CENTRES[k]
        state["flow"] = FLOWS[k] / 100
        g(f"EXCLUDE_OBJECT_START NAME=flow_{k + 1}")
        g(f"M117 Flow {FLOWS[k]:.1f}% L{layer + 1}/{len(layers) + 1}")
        square_layer(cx, cy, z, h, layer, top)
        retract()
        g(f"EXCLUDE_OBJECT_END NAME=flow_{k + 1}")
# label dots: one more layer, at 100% flow so the dots don't differ between squares
z = round(layers[-1][1] + LH, 3)
g(f";LAYER:{len(layers)} Z:{z:.2f} label dots")
state["flow"] = 1.0
for k, (cx, cy) in enumerate(CENTRES):
    g(f"EXCLUDE_OBJECT_START NAME=flow_{k + 1}")
    label(cx, cy, k + 1, z)
    retract()
    g(f"EXCLUDE_OBJECT_END NAME=flow_{k + 1}")
g(f"G1 Z{z + 10:.3f} F1200")
g("M107")
g("PRINT_END")                                # heaters off and filament parked before the question
labels = [f"{k + 1}: {f:.1f}%" for k, f in enumerate(FLOWS)]
g(f'_CAL_ASK VAR=flow TITLE="{NAME}: fine flow" TEXT="Squares are numbered by the dots on their front edge (front row 1-4 left to right, back row 5-8). '
  f'Look at the top surface at a low angle: pick the square with the smoothest, fully closed top: no grooves (too little) and no raised ridges (too much)." '
  f'OPTIONS="{",".join(f"{f:.1f}" for f in FLOWS)}" LABELS="{",".join(labels)}" PARK=0')
g('M117 Flow saved')
open(OUT, "w").write("\n".join(out) + "\n")
print("->", OUT)

# ---------------------------------------------------------------- preview
if SVG:
    s = 3.0                                                  # px per mm, bed area X 80-220, Y 110-190
    X0, Y1 = 80, 190
    px = lambda x: (x - X0) * s
    py = lambda y: (Y1 - y) * s
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{140 * s:.0f}" height="{100 * s:.0f}" font-family="sans-serif">',
           f'<rect width="100%" height="100%" fill="#f4efe6"/>',
           f'<text x="8" y="16" font-size="13" fill="#333">{NAME} fine flow test (top view, front at the bottom)</text>']
    for k, ((cx, cy), fl) in enumerate(zip(CENTRES, FLOWS)):
        x, y = px(cx - SIZE / 2), py(cy + SIZE / 2)
        svg.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{SIZE * s:.1f}" height="{SIZE * s:.1f}" fill="#8b5a2b" stroke="#4a2f14"/>')
        for (ax, ay), (bx, by) in diag_lines(cx, cy, SIZE / 2 - 2.35 * W, True)[::3]:   # 45deg top lines
            svg.append(f'<line x1="{px(ax):.1f}" y1="{py(ay):.1f}" x2="{px(bx):.1f}" y2="{py(by):.1f}" stroke="#a8743f" stroke-width="1"/>')
        x0 = cx - k * DOT_PITCH / 2
        for d in range(k + 1):
            svg.append(f'<rect x="{px(x0 + d * DOT_PITCH) - 1.5:.1f}" y="{py(cy - SIZE / 2 + 1.4 + DOT):.1f}" width="3" height="{DOT * s:.1f}" fill="#f4efe6"/>')
        svg.append(f'<text x="{px(cx):.1f}" y="{py(cy - SIZE / 2) + 14:.1f}" font-size="12" text-anchor="middle" fill="#333">{k + 1}: {fl:.1f}%</text>')
    svg.append("</svg>")
    open(SVG, "w").write("\n".join(svg) + "\n")
    print("->", SVG)
