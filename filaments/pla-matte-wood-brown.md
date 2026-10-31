# Panchroma PLA Matte, Wood Brown (SKU CA04077), 1.75mm, 1kg

Matte PLA in a wood colour, not wood-filled: no wood-fibre clog or heat-creep handling
needed. Panchroma Matte runs roughly 190–230°C.

Status: **partly calibrated** (v5 plate, 2026-10-30): temperature, pressure advance, max
volumetric speed and flow read; retraction still to read. Answers are saved on the printer in
variables.cfg as `cal_pla_matte_woodbrown_*`.

| Setting | Value | How it was found |
|---|---|---|
| Nozzle temperature | 210°C (215°C first layer) | Temp tower 230→195°C picked 210 |
| Bed temperature | 60°C | |
| Retraction (firmware) | 0.8mm @ 40mm/s | Starting value (from Marble) |
| Pressure advance | 0.05 | PA triangles 0.00→0.08 |
| Flow ratio | 1.04 | Flow blocks 92→108% picked 104%. Read before the extruder check; if that finds the extruder under-feeding, fix rotation_distance and drop this back toward 1.00 |
| Max volumetric speed | 14 mm³/s at 210°C | Speed wall 6→28 (2 mm³/s bands, 2.56mm tall): picked 14 (Z 10.56–13.12) at the prompt and kept it, as saved in variables.cfg (`cal_pla_matte_woodbrown_max_flow`). The wall roughened around 12mm high, inside that band, so drop to 12 if long solid fills under-extrude |

Calibration plate: `PLA_Matte_WoodBrown_calibration_suite_v5.gcode`, built with
`OUT_DIR=~/Downloads tools/calsuite.sh PLA_MATTE PLA_Matte_WoodBrown` (profile `PLA_MATTE`:
temperature tower 230→195°C in 5°C steps, speed wall 6→28 mm³/s, PA 0.00→0.08, flow
92→108%, retraction 0.2→1.2mm, tolerance).

## Extruder check before the suite (Clockwork 2 gear just refitted, 2026-10-30)

The flow blocks only mean something if the extruder pushes what it is told. Current
`rotation_distance: 22.6789511` (`klipper/ebb_extruder.cfg`, gear_ratio 50:10). Klipper's
default `max_extrude_only_distance` is 50mm, so the 100mm goes in two moves.

1. Heat: `M109 S210`. Filament loaded through the extruder.
2. Mark the filament exactly 120mm above the extruder inlet (fine marker, steel rule).
3. `M83`, then `G1 E50 F60` twice (1mm/s, ~2.4 mm³/s, slow enough that the hotend
   doesn't limit it). Wait for it to finish.
4. Measure inlet to mark again. Extruded = 120 − remaining (should be 100).
5. If it's off by more than ~1mm: new rotation_distance = 22.6789511 × extruded / 100.
   Set it in `[extruder]`, restart, repeat once to confirm.
6. Listen for clicks while it runs; the 2026-10-18 clicks matched motor turns (22.7mm of
   filament per turn).

OrcaSlicer preset: `Voron PLA Matte Wood Brown` (inherits Generic PLA template), drafted in
`orca/drafts/` because Orca was open; move it to `orca/filament/` to sync it into Orca.
