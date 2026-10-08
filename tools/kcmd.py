#!/usr/bin/env python3
# Run G-code on the printer through Klipper's API socket and stream the console output
# until the command finishes. No web proxy, so long commands (homing, QGL, soaks) don't
# time out. Run it on the printer Pi, e.g. from this Pi:
#   scp tools/kcmd.py yeg2-4:kcmd.py   (once), then
#   ssh yeg2-4 "python3 kcmd.py 'G28' 'QUAD_GANTRY_LEVEL'"
# Each argument is one line of G-code; they run as one script. Exit code 1 on a Klipper error.
import json, socket, sys

SOCK = "/home/ross/printer_data/comms/klippy.sock"
script = "\n".join(sys.argv[1:])
s = socket.socket(socket.AF_UNIX)
s.connect(SOCK)
send = lambda obj: s.sendall(json.dumps(obj).encode() + b"\x03")
send({"id": 1, "method": "gcode/subscribe_output", "params": {"response_template": {}}})
send({"id": 2, "method": "gcode/script", "params": {"script": script}})
buf = b""
while True:
    data = s.recv(65536)
    if not data:
        sys.exit("klippy socket closed")
    buf += data
    while b"\x03" in buf:
        raw, buf = buf.split(b"\x03", 1)
        msg = json.loads(raw)
        if "params" in msg and "response" in msg["params"]:
            print(msg["params"]["response"], flush=True)
        elif msg.get("id") == 2:
            if "error" in msg:
                print("!! " + msg["error"].get("message", str(msg["error"])), flush=True)
                sys.exit(1)
            sys.exit(0)
