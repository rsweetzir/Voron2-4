#!/usr/bin/env python3
# SPDX-License-Identifier: MIT  (c) 2026 The Voron2-4 authors, see LICENSE
"""
Slice OrcaSlicer's own calibration models for calsuite.py (v5).

  temp HIGH LOW SPEED OUT    calib/temperature_tower: one 700mm tower of 10mm blocks labelled
                             500C (bottom) .. 155C (top); keeps the blocks HIGH..LOW
  speed HEIGHT SCALE OUT     calib/volumetric_speed/SpeedTestStructure: single-wall vase print,
                             Orca's settings (layer 0.8 x nozzle, line 1.75 x nozzle), cut to HEIGHT,
                             XY scaled by SCALE (full size is 180 x 100mm)
  retract HEIGHT SPEED OUT   calib/retraction/retraction_tower: 0.4mm base + two pillars, cut to HEIGHT
  tolerance SPEED OUT        handy_models/OrcaToleranceTest: hex holes 0/.05/.1/.2/.3/.4mm with
                             the hex key printed in the .4 hole

The models are cut like Orca's calibration dialogs do, then sliced with the OrcaSlicer CLI
using this repo's Voron presets (walls and infill at SPEED, the filament's top speed). The
G-code has no start/end G-code and no temperatures; calsuite.py places it on the plate and
adds the per-band temperature / volumetric speed / retraction changes.

Needs a Python with DracoPy, manifold3d and numpy (e.g. a venv) and OrcaSlicer: the macOS app
in /Applications, or the Linux snap (ORCA_APP / ORCA_RESOURCES / ORCA_BIN override the paths).
The presets come from this repo's orca/ folder.
"""
import glob, json, os, shutil, struct, subprocess, sys
import DracoPy, manifold3d, numpy as np

KIND, ARGS = sys.argv[1], sys.argv[2:]
if sys.platform == "darwin":
    _app = os.environ.get("ORCA_APP", "/Applications/OrcaSlicer.app")
    ORCA = os.environ.get("ORCA_RESOURCES", f"{_app}/Contents/Resources")
    ORCA_BIN = os.environ.get("ORCA_BIN", f"{_app}/Contents/MacOS/OrcaSlicer")
    WORK = os.path.expanduser("~/.cache/calsuite")
else:
    ORCA = os.environ.get("ORCA_RESOURCES", "/snap/orcaslicer/current/usr/local/share/OrcaSlicer")
    ORCA_BIN = os.environ.get("ORCA_BIN", "/snap/bin/orcaslicer")
    WORK = os.path.expanduser("~/snap/orcaslicer/common/calsuite")   # the snap can only read files here
USER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "orca")   # repo presets
MACHINE = "Voron 2.4 300 0.4 FW Retraction"   # standalone user printer (no parent preset)
# The CLI checks process/filament compatibility against the printer's system parent (exit 239,
# "process not compatible" without one), so the flattened printer is hung off Orca's stock
# Voron preset; every setting still comes from the repo printer.
MACHINE_PARENT = "Voron 2.4 300 0.4 nozzle"
# Another printer (calsuite.sh PRINTER=vegas): the same presets with its nozzle and bed size
NOZZLE = float(os.environ.get("CALSUITE_NOZZLE", "0.4"))
BED = float(os.environ.get("CALSUITE_BED", "300"))

def speeds(v):
    v = str(v)
    return dict(outer_wall_speed=v, inner_wall_speed=v, sparse_infill_speed=v, internal_solid_infill_speed=v,
                top_surface_speed=v, gap_infill_speed=v, initial_layer_speed="25", initial_layer_infill_speed="25")

# Tall towers stand on a raft: the ASA temperature tower broke free of its 15mm brim at 245C
# (Las Vegas 2026-11-12). calsuite.py reads the raft height from the header and counts the
# tower's temperature/retraction bands from the top of the raft.
RAFT = dict(raft_layers="3", raft_first_layer_expansion="4", raft_expansion="2", raft_contact_distance="0.2",
            brim_type="no_brim")

if KIND == "temp":
    high, low, speed, out = int(ARGS[0]), int(ARGS[1]), int(ARGS[2]), ARGS[3]
    model, z0, z1 = "calib/temperature_tower/temperature_tower.drc", (500 - high) / 5 * 10, (500 - low) / 5 * 10 + 10
    brim = "0"                                           # a raft instead of a brim (see RAFT below)
    proc, fil = dict(speeds(speed), **RAFT), {}
    # Tall, thin tower (44 x 9 mm, 70 mm): the nozzle knocked it loose on fast travel twice (ASA,
    # Las Vegas 2026-11-11; curled overhang edges + 0.4 mm hop + 500 mm/s travel moves). Slower,
    # gentler travel, a higher hop, and travel that goes around the walls instead of over them.
    proc.update(travel_speed="120", travel_acceleration="1500", reduce_crossing_wall="1",
                max_travel_detour_distance="0")
    fil.update(filament_z_hop=["0.8"], filament_z_hop_types=["Normal Lift"],
               filament_retract_lift_enforce=["All Surfaces"])
    # Optional per material (calsuite.sh, from the profile): slower bridges/overhangs, and a fan
    # only on bridges and steep overhangs (general cooling off), e.g. ASA
    bs = os.environ.get("CALSUITE_BRIDGE_SPEED")
    if bs:
        b = int(bs)
        proc.update(bridge_speed=str(b), internal_bridge_speed=str(b), enable_overhang_speed="1",
                    overhang_2_4_speed=str(b), overhang_3_4_speed=str(max(b * 3 // 5, 5)),
                    overhang_4_4_speed=str(max(b * 2 // 5, 5)))
    of = os.environ.get("CALSUITE_OVERHANG_FAN")
    if of:
        gf = os.environ.get("CALSUITE_FAN", "0")       # general fan % (profile fan), e.g. ASA 30
        fil.update(fan_min_speed=[gf], fan_max_speed=[gf], overhang_fan_speed=[of],
                   enable_overhang_bridge_fan=["1"], overhang_fan_threshold=["50%"])
    header = f"high={high} low={low} speed={speed} brim={brim}"
elif KIND == "speed":
    height, scale, out = float(ARGS[0]), float(ARGS[1]), ARGS[2]
    lh, lw = round(NOZZLE * 0.8, 2), round(NOZZLE * 1.75, 2)          # as Orca's Max flowrate test
    model, z0, z1 = "calib/volumetric_speed/SpeedTestStructure.drc", 0, height
    proc = dict(speeds(50), layer_height=str(lh), initial_layer_print_height=str(lh),
                outer_wall_line_width=str(lw), wall_loops="1", top_shell_layers="0", bottom_shell_layers="1",
                sparse_infill_density="0%", spiral_mode="1", enable_overhang_speed="0",
                brim_type="outer_and_inner", brim_width="3")
    fil = dict(filament_max_volumetric_speed=["200"], slow_down_layer_time=["0"])
    header = f"height={height} scale={scale} layer={lh} line={lw}"
elif KIND == "retract":
    height, speed, out = float(ARGS[0]), int(ARGS[1]), ARGS[2]
    model, z0, z1 = "calib/retraction/retraction_tower.drc", 0, height
    proc, fil = dict(speeds(speed), **RAFT), {}
    header = f"height={height} speed={speed}"
elif KIND == "tolerance":
    speed, out = int(ARGS[0]), ARGS[1]
    model, z0, z1 = "handy_models/OrcaToleranceTest.drc", 0, 1000
    proc, fil = dict(speeds(speed), brim_type="no_brim"), {}
    header = f"speed={speed}"
else:
    sys.exit(__doc__)
os.makedirs(WORK, exist_ok=True)

# ---- cut the model to z0..z1 and drop it on the bed
m = DracoPy.decode(open(f"{ORCA}/{model}", "rb").read())
solid = manifold3d.Manifold(manifold3d.Mesh(
    vert_properties=np.asarray(m.points, np.float32).reshape(-1, 3),
    tri_verts=np.asarray(m.faces, np.uint32).reshape(-1, 3)))
box = manifold3d.Manifold.cube([400, 400, z1 - z0]).translate([-50, -50, z0])
cut = (solid ^ box).translate([0, 0, -z0])
if KIND == "speed":
    cut = cut.scale([scale, scale, 1])
cut = cut.to_mesh()
v, f = np.asarray(cut.vert_properties)[:, :3], np.asarray(cut.tri_verts)
with open(f"{WORK}/{KIND}.stl", "wb") as o:
    o.write(b"\0" * 80 + struct.pack("<I", len(f)))
    for a, b, c in v[f]:
        o.write(struct.pack("<12fH", 0, 0, 0, *a, *b, *c, 0))

# ---- presets: the repo's user presets, flattened (the CLI needs complete presets)
index = {}
for p in glob.glob(f"{ORCA}/profiles/Voron/**/*.json", recursive=True) + glob.glob(f"{USER}/**/*.json", recursive=True):
    try:
        j = json.load(open(p))
    except ValueError:
        continue
    if isinstance(j, dict) and "name" in j:
        index.setdefault(j["name"], p)

def resolve(name):
    j = json.load(open(index[name]))
    full = resolve(j["inherits"]) if j.get("inherits") else {}
    full.update(j)
    return full

machine = resolve(MACHINE)
machine.update(type="machine", inherits=MACHINE_PARENT, machine_start_gcode="", machine_end_gcode="",
               layer_change_gcode="")   # no printer macros in the test models (_WOOD_GRAIN_LAYER is Edmonton-only)
if NOZZLE != 0.4 or BED != 300:
    b = f"{BED:g}"
    machine.update(nozzle_diameter=[f"{NOZZLE:g}"], printable_area=["0x0", f"{b}x0", f"{b}x{b}", f"0x{b}"],
                   max_layer_height=[f"{NOZZLE * 0.8:g}"])
process = resolve("Voron 0.20mm PLA")
process.update(type="process", name="calsuite " + KIND, print_settings_id="calsuite " + KIND,
               layer_height="0.2", initial_layer_print_height="0.25", skirt_loops="0",
               exclude_object="0", enable_arc_fitting="0",
               # no scarf seam: its Z ramp is a burst of tiny moves (E.00001 segments) that, with
               # input shaping on a Pi 3, ended two ASA runs in "Timer too close" (2026-11-11)
               seam_slope_type="none",
               default_acceleration="3000", inner_wall_acceleration="3000", outer_wall_acceleration="3000",
               travel_acceleration="3000", top_surface_acceleration="2000", initial_layer_acceleration="500")
if NOZZLE != 0.4:                              # the repo's process presets are 0.4mm lines
    lw = f"{NOZZLE * 1.125:.2f}"
    process.update({k: lw for k in ("line_width", "outer_wall_line_width", "inner_wall_line_width",
                    "sparse_infill_line_width", "internal_solid_infill_line_width", "top_surface_line_width",
                    "support_line_width")}, initial_layer_line_width=f"{NOZZLE * 1.25:.2f}")
process.update(proc)
filament = resolve("Generic PLA template @Voron Voron 2.4 300 0.4 nozzle")
filament.update(type="filament", name="calsuite " + KIND, filament_settings_id=["calsuite " + KIND],
                filament_start_gcode=[""], enable_pressure_advance=["0"], filament_flow_ratio=["1"])
filament.update(fil)
for j in (process, filament):
    j["inherits"] = ""                         # flattened above
    j["compatible_printers"] = [MACHINE_PARENT, MACHINE]
    j["compatible_printers_condition"] = ""
for name, j in (("machine", machine), ("process", process), ("filament", filament)):
    json.dump(j, open(f"{WORK}/{name}.json", "w"), indent=1)

# ---- slice
shutil.rmtree(f"{WORK}/out", ignore_errors=True)
subprocess.run([ORCA_BIN, "--load-settings", "machine.json;process.json",
                "--load-filaments", "filament.json", "--arrange", "0", "--orient", "0",
                "--slice", "0", "--outputdir", "out", f"{KIND}.stl"], cwd=WORK, check=True)
sliced = open(f"{WORK}/out/plate_1.gcode").read()
if KIND in ("temp", "retract"):
    # the model starts at the first layer after the raft: the Z of the first non-support feature
    zs, model_z = None, None
    for l in sliced.splitlines():
        if l.startswith(";Z:"):
            zs = float(l[3:])
        elif l.startswith(";TYPE:") and zs is not None and "upport" not in l and "aft" not in l and model_z is None:
            model_z = zs
    if model_z is None:
        sys.exit("no model layer found above the raft")
    layer = float(process.get("layer_height", "0.2"))
    header += f" raft={model_z - layer:.3f}"         # Z of the raft top + contact gap = model Z0
with open(out, "w") as o:
    o.write(f"; orca calib {KIND} {header}\n")
    o.write(sliced)
print(f"{out}: {KIND} {header}")
