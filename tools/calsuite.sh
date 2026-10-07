#!/bin/sh
# Build the filament calibration suite: slice the OrcaSlicer models (orca_calib.py), then
# write the one-plate G-code (calsuite.py) and upload it to the printer (not started).
#   tools/calsuite.sh MATERIAL NAME [FROM=pa TEMP=210 MAX_FLOW=14 ...]
#     e.g. tools/calsuite.sh PLA_PLUS Duramic_PLA_Plus
#     FROM= resumes at a later test with the earlier answers (see calsuite.py)
# MATERIAL is a calsuite.py PROFILES key. Needs the OrcaSlicer snap and a Python with
# DracoPy, manifold3d and numpy ($CALSUITE_PYTHON, default ~/.venvs/calsuite; set it up with
#   python3 -m venv ~/.venvs/calsuite && ~/.venvs/calsuite/bin/pip install DracoPy manifold3d numpy)
set -e
MAT=$1 NAME=$2
shift 2 2>/dev/null || true
[ -n "$MAT" ] && [ -n "$NAME" ] || { sed -n '2,8p' "$0"; exit 1; }
PY=${CALSUITE_PYTHON:-$HOME/.venvs/calsuite/bin/python}
cd "$(dirname "$0")"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

# temperature range and top speed come from the calsuite.py profile
eval "$(python3 - "$MAT" <<'EOF'
import re, sys
src = open("calsuite.py").read()
prof = re.search(r'"%s":\s*dict\((.*?)\),\n' % sys.argv[1].upper(), src, re.S)
if not prof:
    sys.exit(f"no profile {sys.argv[1]} in calsuite.py")
temps = [int(t) for t in re.search(r"temps=\[([^\]]*)\]", prof.group(1)).group(1).split(",")]
vmax = int(re.search(r"vmax=(\d+)", prof.group(1)).group(1))
print(f"HIGH={temps[0]} LOW={temps[-1]} VMAX={vmax}")
EOF
)"
SPEED_H=30.72                               # 12 bands x 2.56mm
"$PY" orca_calib.py temp "$HIGH" "$LOW" "$VMAX" "$WORK/temp.gcode"
"$PY" orca_calib.py speed "$SPEED_H" 0.6 "$WORK/speed.gcode"
"$PY" orca_calib.py retract 11.4 "$VMAX" "$WORK/retract.gcode"
"$PY" orca_calib.py tolerance "$VMAX" "$WORK/tolerance.gcode"
FROM=$(printf '%s\n' "$@" | sed -n 's/^FROM=//p' | tr 'A-Z' 'a-z')
OUT="$WORK/${NAME}_calibration_suite_v5${FROM:+_from_$FROM}.gcode"
python3 calsuite.py "$MAT" "$OUT" "$NAME" "$WORK" "$@"
curl -sf -F "file=@$OUT" http://192.168.5.240/server/files/upload > /dev/null
echo "Uploaded $(basename "$OUT") to the printer (not started)."
