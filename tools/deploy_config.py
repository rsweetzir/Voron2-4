#!/usr/bin/env python3
# SPDX-License-Identifier: MIT  (c) 2026 The Voron2-4 authors, see LICENSE
"""
Deploy this repo's Klipper config to one printer (repo -> printer).

  tools/deploy_config.py vegas|edmonton [--dry-run] [--restart]

Pushes the SHARED macros (klipper/shared/ -> config/shared/) and that printer's own files
(klipper/ for Edmonton, vegas/klipper/ for Las Vegas). On the way:
  - the masked MCU serials (<MCU_SERIAL>) are filled back in from the printer's current files
  - each printer.cfg keeps the printer's own SAVE_CONFIG block (#*# ...): calibrations saved on
    the printer are never overwritten by an older copy in the repo
  - every file that changes is backed up first to config/backup-<date>-deploy/, and files the
    repo no longer has (OBSOLETE) are moved there instead of deleted
  - refuses while the printer is printing or paused
--dry-run shows the diffs only. --restart restarts Klipper afterwards and reports its state.
Rules for what goes where: docs/printer-parity.md.
"""
import difflib, json, os, re, subprocess, sys, time, urllib.request

PRINTERS = {
    "edmonton": dict(ssh="voron", host="192.168.5.240", dir="klipper",
                     files=["printer.cfg", "macros.cfg", "calibration.cfg", "ebb_extruder.cfg",
                            "KAMP_Settings.cfg", "eddy.cfg", "printer_settings.cfg"],
                     obsolete=[]),
    "vegas": dict(ssh="voron-vegas", host="192.168.128.20", dir="vegas/klipper",
                  files=["printer.cfg", "eddy.cfg", "qgl.cfg", "bed_mesh.cfg", "KAMP_Settings.cfg",
                         "menu.cfg", "calibration.cfg", "printer_settings.cfg", "purge.cfg", "calibrate.cfg"],
                  obsolete=["print_macros.cfg", "calsuite.cfg", "smart_home.cfg"]),
}
SHARED = ["print_flow.cfg", "calsuite.cfg"]
REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

args = [a for a in sys.argv[1:] if not a.startswith("--")]
if len(args) != 1 or args[0] not in PRINTERS:
    sys.exit(__doc__)
P, DRY, RESTART = PRINTERS[args[0]], "--dry-run" in sys.argv, "--restart" in sys.argv

def ssh(cmd, inp=None):
    r = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", P["ssh"], cmd],
                       input=inp, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"ssh {P['ssh']}: {r.stderr.strip() or r.returncode}")
    return r.stdout

def remote(path):
    return ssh(f"cat printer_data/config/{path} 2>/dev/null || true")

def moonraker(path, method="GET"):
    req = urllib.request.Request(f"http://{P['host']}:7125{path}", method=method)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)["result"]

state = moonraker("/printer/objects/query?print_stats=state")["status"]["print_stats"]["state"]
if state in ("printing", "paused") and not DRY:
    sys.exit(f"{args[0]} is {state}: deploy after the print (--dry-run works now)")

SERIAL = re.compile(r"^(\s*serial:\s*/dev/serial/by-id/usb-Klipper_[a-z0-9]+_)<MCU_SERIAL>(-if00.*)$", re.M)
AUTOSAVE = "#*# <---------------------- SAVE_CONFIG ---------------------->"

def prepare(name, text, live):
    def fill(m):
        found = re.search(re.escape(m.group(1)) + r"([0-9A-F]{8,})" + re.escape(m.group(2).split()[0]), live)
        if not found:
            sys.exit(f"{name}: no live serial for {m.group(1).strip()}<MCU_SERIAL> on the printer")
        return m.group(1) + found.group(1) + m.group(2)
    text = SERIAL.sub(fill, text)
    if name == "printer.cfg":
        if AUTOSAVE not in live:
            sys.exit("printer.cfg on the printer has no SAVE_CONFIG block: refusing to guess")
        text = text.split(AUTOSAVE)[0].rstrip("\n") + "\n\n" + AUTOSAVE + live.split(AUTOSAVE, 1)[1]
    return text

plan = [(f"shared/{f}", open(os.path.join(REPO, "klipper/shared", f)).read()) for f in SHARED]
plan += [(f, open(os.path.join(REPO, P["dir"], f)).read()) for f in P["files"]]
changes = []
for path, text in plan:
    live = remote(path)
    new = prepare(os.path.basename(path), text, live)
    if new != live:
        changes.append((path, new))
        diff = list(difflib.unified_diff(live.splitlines(), new.splitlines(), f"printer:{path}", f"repo:{path}", lineterm="", n=1))
        print(f"== {path}: {sum(1 for l in diff if l[:1] in '+-') - 2} lines differ")
        if DRY:
            print("\n".join(diff[:200]))
gone = [f for f in P["obsolete"] if ssh(f"test -e printer_data/config/{f} && echo yes || true").strip()]
for f in gone:
    print(f"== {f}: obsolete, moves to the backup folder")
if not changes and not gone:
    print("Printer already matches the repo.")
    sys.exit(0)
if DRY:
    sys.exit(0)

backup = time.strftime("backup-%Y%m%d_%H%M%S-deploy")
ssh(f"cd printer_data/config && mkdir -p {backup}/shared shared")
for path, new in changes:
    ssh(f"cd printer_data/config && {{ [ -e {path} ] && cp {path} {backup}/{path} || true; }} && cat > {path}", new)
for f in gone:
    ssh(f"cd printer_data/config && mv {f} {backup}/")
print(f"Deployed {len(changes)} file(s); previous versions in config/{backup}/")

if RESTART:
    try:
        moonraker("/printer/restart", "POST")
    except OSError:
        pass                                   # the restart drops the request; the state poll below reports
    for _ in range(40):
        time.sleep(3)
        try:
            info = moonraker("/printer/info")
        except OSError:
            continue
        if info["state"] != "startup":
            print(f"Klipper: {info['state']}: {info['state_message'].splitlines()[0]}")
            if info["state"] != "ready":
                print(f"Roll back with: ssh {P['ssh']} 'cd printer_data/config && cp -r {backup}/* .'")
            break
