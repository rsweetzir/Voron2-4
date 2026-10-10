#!/usr/bin/env python3
"""
CAN bus monitor for the printer Pi: logs every CAN error with what the printer was doing.

Follows klippy.log (Klipper's once-a-second "Stats" line has the per-node CAN counters
canstat_<mcu> rx_error/tx_error and each MCU's bytes_retransmit/bytes_invalid), reads the
USB-CAN adapter's counters from `ip -j -s -d link show can0`, and asks Moonraker for the
toolhead position and print state. Writes to ~/printer_data/logs/can_monitor.log (shown
in Mainsail's log list):
  - a line whenever any counter changes, with the 10 s before it (position, heater and
    fan power, print state), so a failure shows the conditions that led up to it
  - Klipper shutdowns / lost communication, as they appear in klippy.log
  - a heartbeat every 10 min
Run as a systemd user service (tools/can-monitor.service) or by hand.
"""
import collections, json, os, re, subprocess, time, urllib.request

LOG_DIR = os.path.expanduser("~/printer_data/logs")
KLIPPY = os.path.join(LOG_DIR, "klippy.log")
OUT = os.path.join(LOG_DIR, "can_monitor.log")
MOONRAKER = "http://127.0.0.1:7125/printer/objects/query?print_stats=state,filename,print_duration" \
            "&toolhead=position,homed_axes&extruder=temperature,target,power&heater_bed=power&fan=speed"
MAX_BYTES = 5_000_000
HEARTBEAT = 600

NODE = re.compile(r"canstat_(\w+): bus_state=(\w+) rx_error=(\d+) tx_error=(\d+) tx_retries=(\d+)")
MCU = re.compile(r"(?:^|\s)(\w+): mcu_awake=\S+ .*?bytes_retransmit=(\d+) bytes_invalid=(\d+)")
EVENTS = re.compile(r"Timer too close|Lost communication|shutdown|Unable to connect|Transition to shutdown")


def out(msg):
    if os.path.exists(OUT) and os.path.getsize(OUT) > MAX_BYTES:
        os.replace(OUT, OUT + ".1")
    with open(OUT, "a") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")


def adapter():
    try:
        d = json.loads(subprocess.run(["ip", "-j", "-s", "-d", "link", "show", "can0"],
                                      capture_output=True, text=True, timeout=5).stdout)[0]
        x = d.get("linkinfo", {}).get("info_xstats", {})
        return {"adapter_" + k: x.get(k, 0) for k in ("error_warning", "error_passive", "bus_off", "restarts")} \
            | {"adapter_state": d.get("linkinfo", {}).get("info_data", {}).get("state", "?")}
    except Exception as e:
        return {"adapter_state": f"? ({e.__class__.__name__})"}


def printer():
    try:
        s = json.load(urllib.request.urlopen(MOONRAKER, timeout=2))["result"]["status"]
        p, t, e = s["print_stats"], s["toolhead"], s["extruder"]
        x, y, z = t["position"][:3]
        return (f"{p['state']} {os.path.basename(p['filename'] or '-')} t={p['print_duration']:.0f}s "
                f"pos=({x:.1f},{y:.1f},{z:.2f}) nozzle={e['temperature']:.0f}/{e['target']:.0f}C "
                f"heater={e['power']:.2f} bed={s['heater_bed']['power']:.2f} fan={s['fan']['speed']:.2f}")
    except Exception as e:
        return f"moonraker unavailable ({e.__class__.__name__})"


def counters(stats_line):
    c = {}
    for name, state, rx, tx, retries in NODE.findall(stats_line):
        c[f"{name}_state"] = state
        c[f"{name}_rx_error"], c[f"{name}_tx_error"] = int(rx), int(tx)
    for name, rt, inv in MCU.findall(stats_line):
        c[f"{name}_retransmit"], c[f"{name}_invalid"] = int(rt), int(inv)
    return c


def follow(path):
    """Yield new lines of path, reopening it when Klipper rotates the log."""
    f, ino = None, None
    while True:
        if f is None:
            try:
                f = open(path)
                ino = os.fstat(f.fileno()).st_ino
                f.seek(0, os.SEEK_END)
            except OSError:
                time.sleep(2)
                continue
        line = f.readline()
        if line:
            yield line
            continue
        try:
            if os.stat(path).st_ino != ino:
                f.close()
                f = None
                continue
        except OSError:
            pass
        yield None
        time.sleep(0.2)


def main():
    out("monitor started")
    history = collections.deque(maxlen=10)
    last, last_beat, last_poll = {}, 0.0, 0.0
    for line in follow(KLIPPY):
        now = time.time()
        if line and EVENTS.search(line) and not line.startswith(("Stats ", "Receive:", "Sent ")):
            out("KLIPPER: " + line.strip()[:300])
        if line is not None and not line.startswith("Stats "):
            continue
        if line is None and now - last_poll < 1.0:
            continue
        last_poll = now
        cur = (counters(line) if line else {}) | adapter()
        ctx = printer()
        if last:
            changed = {k: (last.get(k), v) for k, v in cur.items() if k in last and v != last[k]}
            if changed:
                out("CHANGE " + " ".join(f"{k}:{a}->{b}" for k, (a, b) in sorted(changed.items())))
                for t, c in history:
                    out(f"   before {time.strftime('%H:%M:%S', time.localtime(t))} {c}")
                out(f"   now    {ctx}")
        cur = {k: v for k, v in (last | cur).items()}
        history.append((now, ctx))
        last = cur
        if now - last_beat > HEARTBEAT:
            out(f"heartbeat {ctx} | " + " ".join(f"{k}={v}" for k, v in sorted(cur.items())))
            last_beat = now


if __name__ == "__main__":
    main()
