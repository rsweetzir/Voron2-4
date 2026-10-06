# Elegoo PLA Marble Filled (Marble Brick Red), 1.75mm

Label: 190–220°C, max print speed 150mm/s. Final values from the v2 calibration plate (2026-10-06); answers saved on the printer in variables.cfg (`cal_pla_marble_*`).

| Setting | Value | How it was found |
|---|---|---|
| Nozzle temperature | 195°C (200°C first layer) | E temp tower 220→190°C |
| Bed temperature | 60°C | |
| Retraction (firmware) | 0.8mm @ 40mm/s | Stringing pyramids 0.2→1.2mm |
| Pressure advance | 0.05 | PA triangles 0.00→0.08 |
| Flow ratio | 1.00 | Flow blocks 92→108% |
| Max volumetric speed | 13.5 mm³/s | Speed wall delaminated; capped at the label's 150mm/s × 0.45mm line × 0.2mm layer |

Earlier v1 plate gave 220°C / 0.4mm / PA 0.06 / flow 96% (superseded).

Notes: marble filler is mildly abrasive and can clog at high flow; a hardened nozzle is recommended for regular use.

OrcaSlicer preset: `Voron PLA Marble` (inherits Generic PLA template). Only this preset carries the 13.5 mm³/s cap.
