#!/bin/sh
# Probe repeatability vs probing speed. Waits until no print is running, then at a clear
# spot (nozzle X60 Y60, probe 25mm behind) runs PROBE_ACCURACY with 10 samples at rising
# speeds, starting at 25% of the configured 5mm/s. Stops at the first speed that can no
# longer produce three identical consecutive readings.
H=http://${PRINTER_HOST:-printer.local}:7125
state() { curl -s -m 5 "$H/printer/objects/query?print_stats=state" | python3 -c 'import sys,json;print(json.load(sys.stdin)["result"]["status"]["print_stats"]["state"])'; }
gc() { curl -s -m 600 -X POST -H 'Content-Type: application/json' -d "{\"script\":\"$1\"}" "$H/printer/gcode/script" >/dev/null; }

while true; do s=$(state); case "$s" in printing|paused|"") sleep 30;; *) break;; esac; done
# hold the bed at printing temperature so thermal drift doesn't skew the comparison
gc "M190 S80"; gc "G4 P120000"
echo "print state: $s"
homed=$(curl -s -m 5 "$H/printer/objects/query?toolhead=homed_axes" | python3 -c 'import sys,json;print(json.load(sys.stdin)["result"]["status"]["toolhead"]["homed_axes"])')
[ "$homed" = "xyz" ] || gc "G28"
gc "G90"; gc "G1 Z50 F900"; gc "G1 X60 Y60 F6000"; gc "G1 Z10 F900"; gc "M400"

for sp in 1.25 2.5 3.75 5 6.25 7.5 10 12.5 15 20; do
  gc "PROBE_ACCURACY PROBE_SPEED=$sp SAMPLES=10 SAMPLE_RETRACT_DIST=3"
  res=$(curl -s -m 5 "$H/server/gcode_store?count=40" | python3 -c "
import sys,json,re
gs=json.load(sys.stdin)['result']['gcode_store']
i=max(k for k,g in enumerate(gs) if g['message'].startswith('PROBE_ACCURACY'))
gs=gs[i:]
z=[float(m.group(1)) for g in gs for m in [re.search(r'(?:is z=|contact at z=)(-?[0-9.]+)',g['message'])] if m]
summ=[g['message'] for g in gs if 'maximum' in g['message']]
best=run=1
for a,b in zip(z,z[1:]):
    run=run+1 if abs(a-b)<1e-6 else 1; best=max(best,run)
print(f'{best}|' + ' '.join(f'{v:.4f}' for v in z) + '|' + (summ[0].replace(chr(10),' ') if summ else ''))
")
  best=${res%%|*}
  echo "speed $sp mm/s: longest identical run=$best | ${res#*|}"
  [ "$best" -ge 3 ] || { echo "STOP: no 3 identical readings at $sp mm/s"; break; }
done
gc "G1 Z50 F900"
