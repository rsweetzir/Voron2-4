# Voron 2.4 (300) Klipper configuration

Klipper config, macros, firmware build settings and OrcaSlicer profiles for a
Voron 2.4 300mm with a BTT SKR Pro v1.2 mainboard and a BTT EBB toolhead board
(USB), running Klipper v0.13.

## Highlights

- **Sensorless XY homing** via `[homing_override]`: homing current 0.8A, 2s stall
  flag settle, back-off between axes, Z lift only on a full `G28`.
  `driver_SGTHRS: 50` on X and Y (40 grinds, 60 stops early on this machine).
- **PRINT_START** with conditional heat soak:
  - bed waits only for *at least* the target, never cools a hotter bed
  - a background timer tracks how long the bed has been ≥ 78°C; the soak only
    runs for the remainder (10 min below 100°C, 20 min at 100°C+)
  - optional chamber target once `[temperature_sensor chamber]` exists
  - `SMART_QGL` only levels when motors were off since the last QGL, then re-homes Z
  - nozzle held at 150°C until right before the purge
  - console messages, e.g. `Running PETG heat soak: bed 80C for 10 min`
- **START_HEAT_SOAK** manual soak macro (`TEMP=`, `MINUTES=`, `FILAMENT=`).
- **Firmware retraction** (`[firmware_retraction]`), with per-filament
  `SET_RETRACTION` / `SET_PRESSURE_ADVANCE` in the slicer's filament start G-code.
- Input shaper and accelerometer `axes_map` corrected for an EBB mounted at an angle.

## Slicer start G-code (OrcaSlicer)

```
PRINT_START EXTRUDER=[nozzle_temperature_initial_layer] BED=[bed_temperature_initial_layer_single] FILAMENT=[filament_type]
```

Do not add `M190`/`M109` before it; `PRINT_START` handles heating.

## Layout

| Folder | Contents |
|---|---|
| `klipper/` | `printer.cfg`, `macros.cfg`, `ebb_extruder.cfg`, `KAMP_Settings.cfg` |
| `firmware/` | Klipper `make menuconfig` settings for the SKR Pro (F407, 32KiB bootloader, USB) and EBB (G0B1, no bootloader): `ebb.config` USB, `ebb-can.config` CAN on PB0/PB1 at 1 Mbit/s (switch-over steps in `ebb-can.md`) |
| `firmware/candlelight/` | candleLight build, flashing steps and `can0` network config for the USB-CAN adapter (STM32F072) |
| `orca/` | OrcaSlicer 2.4 user presets (machine / filament / process) |
| `docs/` | Calibration suite previews; `can_wiring.svg/.png` CAN wiring for the adapter, EBB and (later) Eddy Duo |
| `tools/` | `sync-from-printer.sh` pulls the live files into this repo |

## Using this config

- MCU serial paths are shown as `<MCU_SERIAL>`; find yours with
  `ls /dev/serial/by-id/`. `tools/sync-from-printer.sh` masks them automatically.
- The probe test scripts in `tools/` read the printer address from `PRINTER_HOST`
  (default `printer.local`).
- The `SAVE_CONFIG` block at the end of `printer.cfg` is machine-specific
  (probe offset, mesh, input shaper).
