#!/bin/sh
# Restart Klipper without losing the bed state:
#   - refuses while a print is printing or paused
#   - saves the bed target and the _SOAK_TRACKER bed history (one sample/min)
#   - RESTART (or FIRMWARE_RESTART with -f), waits for ready
#   - re-heats the bed to the same target (only if it was on) and restores the
#     history, so PRINT_START's soak still knows how long the bed has been warm
# Usage: tools/klipper-restart.sh [-f]     (PRINTER_HOST overrides 192.168.5.240)
set -e
H="http://${PRINTER_HOST:-192.168.5.240}:7125"
EP=restart; [ "$1" = "-f" ] && EP=firmware_restart
q() { curl -s -m 5 "$H/printer/objects/query?$1"; }
gcode() { curl -s -m 30 -X POST -G "$H/printer/gcode/script" --data-urlencode "script=$1" >/dev/null; }

state=$(q "print_stats=state" | python3 -c 'import sys,json;print(json.load(sys.stdin)["result"]["status"]["print_stats"]["state"])')
case "$state" in printing|paused) echo "Not restarting: print is $state"; exit 1;; esac

saved=$(q "heater_bed=target&gcode_macro%20_SOAK_TRACKER=history" | python3 -c '
import sys,json; s=json.load(sys.stdin)["result"]["status"]
h=s.get("gcode_macro _SOAK_TRACKER",{}).get("history",[])
print("%d %s" % (round(s["heater_bed"]["target"]), ",".join(str(int(x)) for x in h)))')
bed=${saved%% *}; hist=${saved#* }; [ "$hist" = "$saved" ] && hist=""
echo "saved: bed target ${bed}C, $(echo "$hist" | tr ',' '\n' | grep -c . ) min of bed history"

curl -s -m 10 -X POST "$H/printer/$EP" >/dev/null
for i in $(seq 1 30); do
    sleep 2
    s=$(curl -s -m 5 "$H/printer/info" | python3 -c 'import sys,json;print(json.load(sys.stdin)["result"]["state"])' 2>/dev/null || true)
    [ "$s" = ready ] && break
done
[ "$s" = ready ] || { echo "Klipper not ready after restart ($s); bed NOT re-heated"; exit 1; }

gcode "SET_GCODE_VARIABLE MACRO=_SOAK_TRACKER VARIABLE=history VALUE=[$hist]"
[ "$bed" -gt 0 ] && gcode "M140 S$bed"
echo "restarted ($EP); bed target ${bed}C restored; history restored"
