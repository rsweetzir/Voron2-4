# Working in this repo

Klipper config, tools and OrcaSlicer presets for two Voron 2.4 printers: **Edmonton**
(`klipper/`, ssh `voron`) and **Las Vegas** (`vegas/klipper/`, ssh `voron-vegas`).
Read `docs/printer-parity.md` before changing any Klipper macro or printer config.

## Printer parity (do not skip)

- Print flow, homing helpers, QGL, soak, park, cancel, filament park, eddy tap macros and the
  calibration suite macros are **shared**: `klipper/shared/`. Change them there, for both printers.
- Printer-specific numbers go in each printer's `printer_settings.cfg` (`_PRINTER_SETTINGS`). A new
  setting is added to **both** printers' files in the same change.
- Never put a copy or a variant of a shared macro in a printer file, and never edit `shared/`
  on a printer.
- Deploy with `tools/deploy_config.py <printer> --dry-run`, then `--restart` when the printer is
  idle (it refuses while printing, keeps the printer's SAVE_CONFIG block, fills in MCU serials,
  backs up what it replaces). Deploy a shared change to both printers; if one is offline, say so
  in the commit message and deploy when it is back.
- Pull printer-side changes (SAVE_CONFIG) with `tools/sync-from-printer.sh` (`PRINTER=vegas` for
  Las Vegas) before editing, so a deploy never undoes them.
- Slicer start/end G-code is only `PRINT_START EXTRUDER=... BED=... FILAMENT=...` / `PRINT_END`.

## Repo conventions

- Public repo: MCU serials stay masked (`<MCU_SERIAL>`), no personal names; author
  `rsweetzir`, copyright "The Voron2-4 authors" (SPDX headers on scripts).
- Comments explain *why* (what went wrong without it, with the date), as in the existing files.
- Klipper on these printers: `[gcode_arcs]` is required (Orca arc fitting), Mainsail
  "Save Z offset" must not be used (eddy probe: it shifts the calibration table).

## Gridfinity prints (rule set by the repository owner, 2026-11-09)

- Slice with mouse ears (`brim_type: brim_ears`): each Gridfinity foot is its own small pad on the bed
  and its corners lift. Process presets: `Vegas 0.20mm ASA Gridfinity 0.6`, `Vegas 0.20mm TPU 0.6`.
- The floor above the tapered feet spans the gaps between them: it must print as a bridge across
  the gap the short way (Orca bridge detection, `bridge_angle` 0 = auto, thick bridges), never as
  solid infill running the long way over air. Check the slice: the first layer over the gaps has
  `;TYPE:Bridge` / `Internal Bridge`, and its lines cross the channels.
- Upload to the printer's `Gridfinity/` folder (Moonraker upload with `path=Gridfinity`).
- Light by default: 2 walls (about 1.25 mm with the 0.6 nozzle) and 10% gyroid; walls and solid floors
  are most of a bin's weight, infill the least (set in the Gridfinity process preset).
