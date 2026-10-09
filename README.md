# Voron 2.4 (300) Klipper configuration

Klipper config, macros, firmware build settings and OrcaSlicer profiles for a
Voron 2.4 300mm with a BTT SKR Pro v1.2 mainboard (USB), a BTT EBB toolhead board
and a BTT Eddy Duo probe (both on a 1 Mbit CAN bus via a candleLight USB-CAN adapter),
running Klipper v0.13.

## Highlights

- **Sensorless XY homing** via `[homing_override]`: homing current 0.8A, 2s stall
  flag settle, back-off from the XY end stops before homing (a carriage resting on
  the frame false-triggers X) and between axes, Z lift only on a full `G28`.
  `driver_SGTHRS: 45` on X and Y. `PARK` stays 10mm off the rear frame.
- **Eddy Duo probe** (`eddy.cfg`): Z homing by nozzle tap, `SET_Z_FROM_PROBE`
  homing correction, rapid-scan adaptive bed mesh.
- **PRINT_START** with conditional heat soak:
  - re-homes only Z when X/Y are still homed (Klipper un-homes when the motors turn
    off); run `G28` by hand after a crash or layer shift
  - bed waits only for *at least* the target, never cools a hotter bed
  - the soak is non-blocking (print paused, 10 s timer; Cancel works,
    `HEAT_SOAK_SKIP` ends it): 10 min below 100°C, 20 min at 100°C+
  - a per-minute bed temperature history (last 60 min) shortens it: if the bed has
    been ≥ 80% of the target for the whole soak time, it soaks just 1 min; time
    already at the target counts towards the soak
  - if a start step fails (e.g. the Eddy scan), the print stays paused and
    `RESUME` re-runs mesh, nozzle heat and purge before printing
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
| `klipper/` | `printer.cfg`, `macros.cfg`, `calibration.cfg`, `ebb_extruder.cfg`, `eddy.cfg`, `KAMP_Settings.cfg` |
| `firmware/` | Klipper `make menuconfig` settings for the SKR Pro (F407, 32KiB bootloader, USB) and EBB (G0B1, no bootloader): `ebb.config` USB, `ebb-can.config` CAN on PB0/PB1 at 1 Mbit/s (switch-over steps in `ebb-can.md`) |
| `firmware/candlelight/` | candleLight build, flashing steps and `can0` network config for the USB-CAN adapter (STM32F072) |
| `orca/` | OrcaSlicer 2.4 user presets (machine / filament / process). Processes and filaments inherit from the templates in `orca/*/base/`, which must be installed with them; the printer `Voron 2.4 300 0.4 FW Retraction` holds all its settings itself, with Orca's stock `Voron 2.4 300 0.4 nozzle` as its parent (Orca's GUI drops a printer with no parent) |
| `docs/` | Calibration suite previews; `can_wiring.svg/.png` CAN wiring for the adapter, EBB and (later) Eddy Duo |
| `tools/` | `sync-from-printer.sh` pulls the live Klipper and firmware files into this repo; `install-orca-presets.sh` copies `orca/` into a Mac's OrcaSlicer (one way, repo → Orca), run on every change by the `orca-preset-sync.plist` launch agent |

## Using this config

- MCU serial paths are shown as `<MCU_SERIAL>`; find yours with
  `ls /dev/serial/by-id/`. `tools/sync-from-printer.sh` masks them automatically.
- The probe test scripts in `tools/` read the printer address from `PRINTER_HOST`
  (default `printer.local`).
- The `SAVE_CONFIG` block at the end of `printer.cfg` is machine-specific
  (probe offset, mesh, input shaper).
- CAN bus termination: 120R at the USB-CAN adapter and on the EBB (jumper fitted),
  Eddy 120R off. Without the EBB terminator the bus logged errors and the EBB shut
  down with "Timer too close".
