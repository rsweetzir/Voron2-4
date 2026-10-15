# PLA Wood (Oak), 1.75mm

Wood-filled PLA, oak colour. Final values from the v4 calibration plate (2026-10-06, `PLA_WOOD`
profile, 230→200°C); answers saved on the printer in variables.cfg (`cal_pla_wood_oak_*`).

| Setting | Value | How it was found |
|---|---|---|
| Nozzle temperature | 200°C, first layer too; was 205/210 | Temp tower 230→200°C gave 205; lowered 2026-10-11, at 205°C it kept jamming |
| Bed temperature | 60°C | |
| Retraction (firmware) | 0.4mm @ 30/25mm/s (was 0.7 @ 40) | Stringing pyramids gave 0.7; cut 2026-10-10 after jams from frequent retractions |
| Pressure advance | 0.05 | PA triangles 0.00→0.08 |
| Flow ratio | 1.00 | Flow blocks 92→108% |
| Max volumetric speed | 12 mm³/s (14 jammed) | 2026-10-14: a 0.8mm-wide first layer held ~11.5-14 mm³/s for 12 min at 200°C and jammed (too cold to melt that fast, pressure built up). First layer is 0.5mm wide again; keep 12 |

Note: the v4 speed wall's front labels were separate lines with a retract/hop per pixel run,
which disturbed flow; 20 mm³/s may be conservative. The labels are now part of the wall
(calsuite.py, 0eecdd4), so a re-run of the speed wall would give a cleaner reading.

Notes: wood fibres can clog small nozzles; use 0.4mm or larger and avoid long hot idle
(heat creep chars the wood). Lower temperatures give a lighter colour, higher a darker one.

OrcaSlicer preset: `Voron PLA Wood Oak` (inherits Generic PLA template).

Jamming (2026-10-09/10): swollen filament tip, then the extruder ground a flat into it, early
in prints. Cause: since 2026-10-07 PRINT_START held the nozzle at 150C for the ~10 min heat
soak (parked at Z3 over the hot bed); wood-filled PLA heat-crept into the heatbreak. Fixed by
keeping the nozzle off during the soak (warm only for the tap homings), plus 0.4mm/30mm/s
retraction, fewer retractions, a 12 mm3/s cap, SpreadCycle on the extruder and drying the
spool. Do not reintroduce a long hot idle before printing wood.
