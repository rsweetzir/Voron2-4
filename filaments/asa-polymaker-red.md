# Polymaker ASA (Red), 1.75mm

Box: print 230–260°C, bed 75–95°C, up to 200 mm/s, fan off. Dried 4 h before use.
Calibration in progress (calibration suite v5, profile `ASA`); values marked *pending*
are placeholders until the suite finishes. Answers are saved on the printer as
`cal_polymaker_asa_red_*`.

| Setting | Value | How it was found |
|---|---|---|
| Nozzle temperature | 240°C (245°C first layer) | Temp tower 260→230°C: 240/245 cleanest overhangs and holes; 250+ droops, 230–235 fuzzy overhang tips |
| Bed temperature | 105°C | At the box's 95°C the tower's brim cooled and curled; flat at 105°C |
| Part fan | Off; 40% on bridges and overhangs past 50%; off for the first 3 layers | Box says off; bridges and overhangs printed cleanly with the overhang fan |
| Brim | Auto, 15mm (process) | Small, tall ASA parts lift without it |
| Bridges / overhangs | 25 mm/s; overhangs 25/15/10 mm/s by steepness | Tower bridges clean at these speeds |
| Max volumetric speed | 12 mm³/s *(pending)* | Max-flow test |
| Pressure advance | 0.04 *(pending)* | PA triangles |
| Flow ratio | 100% *(pending)* | Flow blocks |
| Retraction (firmware) | 0.5mm @ 40mm/s *(pending)* | Retraction tower |

ASA notes: print enclosed (doors and lid closed); a longer heat soak helps (at a 100°C+
bed PRINT_START soaks 20 min).

OrcaSlicer presets: `Voron ASA Polymaker Red` (filament, only listed with the ASA
process) and `Voron 0.20mm ASA` (process).
