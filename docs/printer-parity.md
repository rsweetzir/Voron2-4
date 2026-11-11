# Keeping the two printers the same

Two Voron 2.4s run from this repo: **Edmonton** (300 mm, 0.4 mm nozzle, EBB36 + Eddy Duo on CAN)
and **Las Vegas** (350 mm, 0.6 mm nozzle, Octopus + Eddy Duo on USB, TFT24). The hardware differs;
the way they *behave* must not. A print, a cancel, a G32 or a heat soak should do the same moves
in the same order on both, so a problem found (and fixed) on one is fixed on the other, and nobody
has to remember which printer does what.

## What lives where

| Where | What | Source of truth |
|---|---|---|
| `klipper/shared/print_flow.cfg` | PRINT_START / _PRINT_START_FINISH / PRINT_END, heat soak, CANCEL_PRINT, PARK, SMART_HOME, SMART_QGL, QGL, G32, the QUAD_GANTRY_LEVEL wrapper, BED_LVL_MESH, eddy homing correction and tap (`_EDDY`, `SET_Z_FROM_PROBE`, `_TAP_Z`), FILAMENT_PARK / FILAMENT_LOADED, print bounds check | **repo** |
| `klipper/shared/calsuite.cfg` | calibration suite prompts (`_CAL*`), `[save_variables]` | **repo** |
| `<printer>/printer_settings.cfg` | `_PRINTER_SETTINGS`: bed centre, skew, filament park length, chamber target, saved mesh name, tap temperatures, soak park height, fine QGL height, Z method (`tap` or `contactless`) and the contactless offset, soak bed boost (extra bed heat while waiting for the chamber). Las Vegas also: `_CLIENT_VARIABLE`, `[firmware_retraction]` | repo |
| everything else in `klipper/` (Edmonton) or `vegas/klipper/` (Las Vegas) | hardware: MCUs, steppers, TMC, homing override (sensorless currents), probe, QGL points/corners, bed mesh area, extras only one printer has (wood grain, drift tests, TFT24 menu) | repo, but `SAVE_CONFIG` results live on the printer |

The `#*# SAVE_CONFIG` block at the end of each `printer.cfg` (PID, eddy calibration, tap
threshold, meshes) belongs to the printer. `tools/deploy_config.py` always keeps the printer's own
block; `tools/sync-from-printer.sh` brings it back into the repo.

## Rules

1. **Behaviour goes in `shared/`, values go in `printer_settings.cfg`.** If a macro needs a
   number that differs between the printers, add a `variable_` to `_PRINTER_SETTINGS` on *both*
   printers and read it from the shared macro. Never copy a shared macro into a printer file to
   tweak it.
2. **Never edit `shared/` on a printer.** Edit it in the repo and deploy to both. An edit made in
   Mainsail on one printer is lost at the next deploy and splits the printers in the meantime.
3. **A fix for one printer is a fix for both.** If it is a print-flow problem, fix it in `shared/`.
   If it is hardware, fix it in that printer's files and say in the commit why the other printer
   does not need it.
4. **Hardware differences stay in hardware sections.** Homing overrides (sensorless currents,
   back-off positions), probe sections, QGL points and corners, mesh area, MCU serials and
   firmware differ and stay per printer, but follow the same structure: the homing override ends
   with `G28 Z` + `SET_Z_FROM_PROBE` (contactless if `_EDDY.skip_tap`, tap otherwise) and one lift.
5. **Include order** in `printer.cfg`: `mainsail.cfg` before `shared/print_flow.cfg` (its
   CANCEL_PRINT wraps Mainsail's), then `printer_settings.cfg`, `shared/print_flow.cfg`,
   `shared/calsuite.cfg`. Printer-only macro files may come before or after.
6. **Slicer presets call the same start:** `PRINT_START EXTRUDER=... BED=... FILAMENT=...` and
   `PRINT_END`, nothing else, and `support_air_filtration` off (Orca's `M106 P3` at the end of a
   print turns the part fan on: Klipper has no fan P3).
7. **Mainsail "Save Z offset" is not used** on these printers: with an eddy probe it shifts the
   probe calibration table instead of saving an offset, and homing then fails ("Invalid
   probe_eddy_current height"). Babystep during a print, then put the value into the config.

## The print flow (both printers)

```
PRINT_START  heat bed (nozzle off) -> SET_SKEW CLEAR -> G28 (Z contactless) -> park over bed centre
             at soak_park_z -> wait for bed -> non-blocking soak (QGL half-way through, nozzle
             warms to the tap temperature for the last 90 s)
_PRINT_START_FINISH  QGL if not applied -> Z0 at the bed centre (_TAP_Z: a tap, or the eddy
             reading + contactless_z_offset when z_method is "contactless") -> SET_SKEW ->
             adaptive rapid_scan mesh -> nozzle to print temp -> KAMP purge -> print continues
             from the purge (no move back to the soak position)
PRINT_END    retract, filament park (if enabled), heaters off, move off the part, mesh and skew
             cleared, speed factor 100%, PARK
```
Z is homed once (contactless) and set once more at the bed centre per print: by a tap (Edmonton,
`z_method: "tap"`) or by the eddy reading (Las Vegas since 2026-11-08, `z_method: "contactless"`:
its taps moved 0.15-0.3 mm with nozzle residue and tap temperature). QGL runs coarse + fine with no G28 Z in
between (the fine pass probes from `qgl_fine_z`, 10 mm).

## Making a change

1. `git pull`, then `tools/sync-from-printer.sh` (Edmonton) or `PRINTER=vegas ...` to bring in
   anything saved on the printers (SAVE_CONFIG). Review `git diff`.
2. Edit the repo. Shared behaviour in `klipper/shared/`, values in both `printer_settings.cfg`.
3. Preview: `tools/deploy_config.py vegas --dry-run` and `tools/deploy_config.py edmonton --dry-run`.
4. Deploy to **both** printers when idle: `tools/deploy_config.py <printer> --restart`. If a printer
   is offline, note it in the commit and deploy as soon as it is back; until then the printers
   differ.
5. Run one print (or `G32` + a heat soak) on each and check the console.
6. Commit with what changed and why.

## Current state

- 2026-11-04: shared macros created. Las Vegas: deploy after the current print. Edmonton is
  offline until about 2026-11-25; its `klipper/` files in the repo are already restructured for
  `shared/`, so when it is back **deploy first** (step 3 then 4), and only then use
  `sync-from-printer.sh` again: a sync before the deploy would pull the old, unshared
  `macros.cfg` over the restructured one. The deploy keeps the printer's SAVE_CONFIG block, so
  nothing saved on the printer meanwhile is lost.
