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

- Slice with a brim (8 mm, see placement below; mouse ears until 2026-11-16): each Gridfinity foot is
  its own small pad on the bed and its corners lift. Process presets: `Vegas 0.20mm ASA Gridfinity 0.6`, `Vegas 0.20mm TPU 0.6`.
- The floor above the tapered feet spans the gaps between them: it must print as a bridge across
  the gap the short way (Orca bridge detection, `bridge_angle` 0 = auto, thick bridges), never as
  solid infill running the long way over air. Check the slice: the first layer over the gaps has
  `;TYPE:Bridge` / `Internal Bridge`, and its lines cross the channels.
- Placement (rule updated 2026-11-16): every Gridfinity part goes centred left-right at the BACK of
  the bed, its brim edge 25 mm from the back (Y 325 on the 350 bed), with an 8 mm full brim
  (`brim_type: outer_only`, now the Gridfinity preset default) for bins AND baseplates: mouse ears
  still let a 2x4 bin warp slightly (2026-11-16). Brim/ear gap
  (`brim_object_gap`) 0.5 mm in the Gridfinity preset (0.1, 0.2 and 0.3 were hard to peel off cleanly).
  Filament: "Vegas Frucindra ASA Gridfinity" (260C since 2026-11-17, was 250C; bed 115C, part fan off on walls, 25% on
  bridges/steep overhangs, exhaust off while printing): tall bins warped and split layers at 240C,
  fan 30%, exhaust 25% (2026-11-16/17).
  Layer height 0.3 mm with max 15.5 mm3/s (2026-11-19, trial 5x5 plate fine; ~20% faster than 0.2 at
  18). The process preset keeps its old name "Vegas 0.20mm ASA Gridfinity 0.6".
  Calibration at 260C (2026-11-19, bed 115, fan off): PA 0.06 (was 0.04 at 240C), flow 100% (was 102%),
  retraction 0.2 mm @ 40 (unchanged), tolerance 0.2 mm.
  Speed model locked in 2026-11-17 (presets now default to it, no overrides needed): nozzle 260C,
  max volumetric speed 18 mm3/s (max-flow test at 260C: clean to 19, long walls gapped at 22);
  outer wall 90, inner wall 220, sparse infill 250, solid infill 125, top 120, gap 135 mm/s (solid
  160 = 18 mm3/s dropped out on long diagonal runs, Ryobi floor 2026-11-19); first layer
  30 / infill 45 mm/s (was 20/30, +50% 2026-11-18: Frucindra lays down well); machine
  limits 200 mm/s (300 skipped X/Y steps 2026-11-05 and 2026-11-18), 3400 mm/s2 in the machine
  profiles (Klipper accel_limit caps prints at 3000).
  Back of the bed + bed 110C (Frucindra ASA) stopped the warping across the front.
- Holding ribs in bins (repository owner's rule, 2026-11-17): put a rib on every grid line that meets
  a wall (positions 21/63 mm etc. from the centre), full height, ~5 mm thick, symmetrical where the
  object allows, shortened where the object sticks out (hinges, latches). Rib tops end above the
  stacking plane in a baseplate-profile ridge so bins/lids on top locate on them. Example:
  ~/voron-gcodes/LasVegas/Gridfinity/ryobi_bit_case/make_bin.py.
- Gridfinity bins (repository owner's rules, 2026-11-19): the wall thickens gradually under the
  stacking lip (SUP = 5 mm taper from the 1.2 mm wall to the 2.6 mm lip, not the 1.4 mm 45-degree step).
  Bins get their brim from ~/voron-gcodes/bin/outer_brim.py (outside of the footprint only, 8 mm,
  0.5 gap, 14 mm round corner pads) and are sliced with --set=brim_type=no_brim: Orca's brim also went
  between the feet. Baseplates keep the slicer brim (one island).
- Bins, 2026-11-20 (corners still lifted a little at bed 120): outer wall 2.4 mm in the model (4 lines,
  was 1.2) and a 6 mm square full-height post in each inside corner. Gridfinity filament bed default
  is 120C (was 115C; bed max_temp 125 / setpoint cap 120).
- Gridfinity slices use SLICER retraction with wipe (2026-11-20): the Frucindra GF filament profile has
  retraction 0.2 mm @ 40 / 30, wipe 2 mm, retract during wipe (0%); slice with
  --mset=use_firmware_retraction=0 (slice_presets.py). Orca can't wipe with Klipper firmware retraction.
- Files live in `~/gridfinity-toolbox/<LasVegas|Edmonton>/<project>/` on the Mac (old ones in `<project>/not-working/`, a
  `readme.txt` history in each folder). The LaunchAgent `com.rsweetzir.gridfinity-sync`
  (`sync_to_printer.sh`) mirrors each location folder to that printer's `gcodes/Gridfinity/<project>/`; the Mac is the
  source of truth. Never upload files straight to a printer (repository owner's rule, 2026-11-16):
  save them in that tree and let the sync (every minute) or `sync_to_printer.sh --force` copy them.
  Calibration suites (`tools/calsuite.sh`) go to `<Location>/Calibration/` -> printer `gcodes/Calibration/calsuite/`.
- Shells (2026-11-17): 2 bottom layers, 3 top layers with ironing (all top surfaces); sparse infill
  gyroid at 4.43% = 14 mm line spacing (one third of a 42 mm Gridfinity unit, 0.62 mm lines).
- Light by default: 2 walls (about 1.25 mm with the 0.6 nozzle; never a single 0.8 mm wall in ASA: a
  3x4x9 bin split between layers and the ribs scarred the outside, 2026-11-16) and gyroid infill (10% until 2026-11-17, now 4.43% / 14 mm); walls and solid floors
  are most of a bin's weight, infill the least (set in the Gridfinity process preset).
