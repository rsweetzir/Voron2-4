# Transparent PETG (PolyLite-style clear)

| Setting | Value | How it was found |
|---|---|---|
| Nozzle temperature | 235°C | Temp tower 248→230°C in 2°C steps (2026-10-05): heavy stringing at 238°C and above, clean from 236°C down, walls clear throughout |
| Bed temperature | 80°C | |
| Retraction (firmware) | 0.4mm @ 60mm/s | Length: dried filament (14% RH) with PA 0.04 was clean at every band, so the lowest reliable length was chosen (undried test was inconclusive). Speed: tower 35→60mm/s, only 60mm/s free of visible strings. |
| Pressure advance | 0.04 | PA tower 0→0.10 (Klipper method, 100mm/s, accel 500, SCV 1): bulge below 0.03, gaps above 0.06 |
| Flow ratio | 0.96 | Flow squares 92/96/100/104/108%: little visible difference on top surfaces; 96% had the cleanest corners |
| Max volumetric speed | 16 mm³/s (functional), 8 mm³/s (Cosmetic preset) | Single-wall ramp 8→24 mm³/s: fails from ~19 mm³/s (loops/strings); clearest at the lowest bands |

Dry at 65°C for 4–6 h before tuning; wet PETG strings regardless of settings.

## OrcaSlicer presets

- `Voron PETG Clear` (functional, default): settings above, max volumetric 16 mm³/s.
- `Voron PETG Clear - Cosmetic`: identical but max volumetric 8 mm³/s for best clarity.
- Process preset `Voron 0.20mm PETG`: accel ≤4000 (outer 3000), inner-first walls, aligned seam, wipe on loops, scarf seam on outer walls.
