# Polymaker ASA (Red), 1.75mm

Box: print 230–260°C, bed 75–95°C, up to 200 mm/s, fan off. Dried 4 h before use.
Calibrated with calibration suite v5 (profile `ASA`), 2026-10-11; answers are saved on the
printer as `cal_polymaker_asa_red_*`.

| Setting | Value | How it was found |
|---|---|---|
| Nozzle temperature | 240°C (245°C first layer) | Temp tower 260→230°C: 240/245 cleanest overhangs and holes; 250+ droops, 230–235 fuzzy overhang tips |
| Bed temperature | 105°C | At the box's 95°C the tower's brim cooled and curled; flat at 105°C |
| Part fan | Off; 40% on bridges and overhangs past 50%; off for the first 3 layers | Box says off; bridges and overhangs printed cleanly with the overhang fan |
| Brim | 8mm on every part, 0.125mm gap to the part (process) | Full plates lift without it; the gap lets the brim snap off without the whitened line ASA leaves when a fused brim is torn off. Small tall parts can get a wider brim per object in Orca |
| Travel | Avoid crossing walls; retract + 0.4mm lift on every travel and layer change | So the nozzle does not clip edges that start to lift on full plates |
| Bridges / overhangs | 25 mm/s; overhangs 25/15/10 mm/s by steepness | Tower bridges clean at these speeds |
| Max volumetric speed | 16 mm³/s | Max-flow test, last good band |
| Pressure advance | 0.05 | PA triangles |
| Flow ratio | 100% | Flow blocks |
| Retraction (firmware) | 1.0mm @ 40mm/s | Retraction tower |
| Tolerance | 0.4mm | Tolerance test: tightest hole the key fits |

ASA notes: print enclosed (doors and lid closed); a longer heat soak helps (at a 100°C+
bed PRINT_START soaks 20 min).

OrcaSlicer presets: `Voron ASA Polymaker Red` (filament, only listed with the ASA
process) and `Voron 0.20mm ASA` (process).
