# Voron 2.4 (300) Klipper configuration

Klipper config, macros, firmware build settings and OrcaSlicer profiles for a
Voron 2.4 300mm with a BTT SKR Pro v1.2 mainboard (USB), a BTT EBB toolhead board
and a BTT Eddy Duo probe (both on a 1 Mbit CAN bus via a candleLight USB-CAN adapter),
running Klipper v0.13.

## About this config

This is the working configuration of my own Voron 2.4, and it represents a lot of
evenings at the printer. Very little of it is stock: almost every value was measured,
printed, broken and re-measured on this machine, and the commit history records why
each one changed. Some of the work behind it:

- moving the toolhead from USB to CAN, drawing the wiring, and then tracking down
  intermittent "Timer too close" shutdowns to a missing terminator and, later, a CAN-L
  pin pulled half out of its connector by a strain relief
- fitting the Eddy Duo probe: tap homing, drift calibration across the probe's
  temperature range, and comparing 9×9, 15×15 and 21×21 scans against each other,
  then moving to 31×31, which made the biggest difference to large first layers
- a heat soak that remembers how long the bed has been warm, and recovers if a start
  step fails, instead of a fixed wait
- a one-plate filament calibration suite (`tools/calsuite.py`) that prints Orca's own
  test models one after another, with Mainsail questions in between
- chasing wood-filled PLA jams down to a hot nozzle idling during the heat soak

If it saves you some of that time, good. Please read the notes in each file before
copying values: they are tuned for this machine, and the reasons matter more than the
numbers.

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
  - the nozzle stays **cold through the soak**: the first homing sets Z with the Eddy
    contactless (good enough to park for the soak); if the gantry needs leveling, the
    QGL (also contactless) runs **during the soak, after its first minute at
    temperature**, and the soak clock counts the leveling time; the nozzle starts
    warming ~90 s before the soak ends, and the only nozzle tap is the final `G28 Z`
    right before the mesh; then print temperature and purge. Holding it at 150°C through the soak heat-crept
    wood-filled PLA into the heatbreak and jammed prints
  - console messages, e.g. `Running PETG heat soak: bed 80C for 10 min`
- **START_HEAT_SOAK** manual soak macro (`TEMP=`, `MINUTES=`, `FILAMENT=`).
- **Firmware retraction** (`[firmware_retraction]`), with per-filament
  `SET_RETRACTION` / `SET_PRESSURE_ADVANCE` in the slicer's filament start G-code.
- Input shaper and accelerometer `axes_map` corrected for an EBB mounted at an angle.

## Using the OrcaSlicer profiles

The `orca/` folder holds OrcaSlicer 2.4 user presets: one printer, the processes, the
filaments, and the base templates they inherit from.

1. **Quit OrcaSlicer** (it only reads presets at start-up).
2. **Copy the three folders**, *including their `base/` subfolders*, into Orca's user
   preset folder:
   - macOS: `~/Library/Application Support/OrcaSlicer/user/default/`
   - Windows: `%APPDATA%\OrcaSlicer\user\default\`
   - Linux: `~/.config/OrcaSlicer/user/default/` (snap:
     `~/snap/orcaslicer/current/.config/OrcaSlicer/user/default/`)

   ```
   cp -R orca/machine orca/process orca/filament "<user preset folder>/"
   ```
   The processes and filaments inherit from the templates in `base/`; without them
   they do not show up. (On a Mac, `tools/install-orca-presets.sh` does this, and
   `tools/orca-preset-sync.plist` keeps it in sync when the repo changes.)
3. **Start Orca** and pick:
   - printer `Voron 2.4 300 0.4 FW Retraction` (needs Orca's stock Voron profiles,
     which ship with Orca)
   - a `Voron 0.20mm ...` process
   - a `Voron ...` filament (`Voron PLA Wood Oak` only appears with the
     `Voron 0.20mm PLA Wood` process, which has the slow first layer it needs)
4. **Set your own print host** in the printer's settings (it is this printer's LAN IP).

What the printer side must provide, or the presets will not print correctly:

- a `PRINT_START` macro taking `EXTRUDER=`, `BED=` and `FILAMENT=` (see below), and
  `PRINT_END`
- `[firmware_retraction]`: the printer preset uses firmware retraction (`G10`/`G11`);
  each filament's start G-code sets its own `SET_RETRACTION` and
  `SET_PRESSURE_ADVANCE`, so retraction and pressure advance live in the filament,
  not the printer

Things that caught me out:

- **Project files keep their own copy of the settings.** Opening an older `.3mf`
  brings back the settings it was saved with, not your updated presets. After
  updating the presets, re-select the printer, process and filament in the project,
  discard the project's changes, and save it.
- The temperatures, flow limits and retraction in the filament presets come from my
  calibration prints of my spools (`filaments/` has the notes). Calibrate yours.

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
| `filaments/` | Per-spool notes: the calibrated values, how each was found, and what went wrong on the way |
| `docs/` | Calibration suite previews; `can_wiring.svg/.png` CAN wiring for the adapter, EBB and (later) Eddy Duo |
| `tools/` | `sync-from-printer.sh` pulls the live Klipper and firmware files into this repo; `install-orca-presets.sh` copies `orca/` into a Mac's OrcaSlicer (one way, repo → Orca), run on every change by the `orca-preset-sync.plist` launch agent |
| `dollhouse/` | 1:12 scale dollhouse: dimensional lumber sizes, wood-grain boards from Blender, printing thin boards on edge |

## Dollhouse (1:12 scale)

A current project on this printer is a 1:12 scale dollhouse; its notes are in
[`dollhouse/`](dollhouse/README.md). At 1:12 one real foot is one scale inch
(1 real inch = 2.117 mm). Dimensional lumber, by its actual (planed) size and its
nominal size:

| Nominal | Actual real-world | 1:12 (actual) | 1:12 (nominal) |
|---|---|---|---|
| 2" (1x2, 2x2) | 1.5 in (38 mm) | 3.18 mm | 4.23 mm |
| 3" (1x3, 2x3) | 2.5 in (64 mm) | 5.29 mm | 6.35 mm |
| 4" (1x4, 2x4) | 3.5 in (89 mm) | 7.41 mm | 8.47 mm |
| 6" (1x6, 2x6) | 5.5 in (140 mm) | 11.64 mm | 12.70 mm |
| 8" (1x8, 2x8) | 7.25 in (184 mm) | 15.35 mm | 16.93 mm |
| 10" (1x10, 2x10) | 9.25 in (235 mm) | 19.58 mm | 21.17 mm |
| 12" (1x12, 2x12) | 11.25 in (286 mm) | 23.81 mm | 25.40 mm |
| thickness 1x | 0.75 in (19 mm) | 1.59 mm | 2.12 mm |
| thickness 2x | 1.5 in (38 mm) | 3.18 mm | 4.23 mm |

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

## Credits and references

None of this was built in a vacuum. The documentation, projects and people below
are what this configuration leans on; thank you to all of them.

**Firmware and host software**
- [Klipper](https://www.klipper3d.org/) by Kevin O'Connor and contributors, in particular:
  [Eddy current probe](https://www.klipper3d.org/Eddy_Probe.html) (calibration, tap
  homing, thermal drift calibration),
  [TMC drivers / sensorless homing](https://www.klipper3d.org/TMC_Drivers.html),
  [CAN bus](https://www.klipper3d.org/CANBUS.html) and
  [CAN bus troubleshooting](https://www.klipper3d.org/CANBUS_Troubleshooting.html),
  [Bed mesh](https://www.klipper3d.org/Bed_Mesh.html) and the
  [Config reference](https://www.klipper3d.org/Config_Reference.html)
- [Moonraker](https://github.com/Arksine/moonraker) by Arksine and
  [Mainsail](https://docs.mainsail.xyz/) (its `mainsail.cfg` client macros, prompts and
  `user_resume_macro` hook)
- [KAMP: Klipper Adaptive Meshing & Purging](https://github.com/kyleisah/Klipper-Adaptive-Meshing-Purging)
  by Kyleisah (the Voron purge)
- [candleLight firmware](https://github.com/candle-usb/candleLight_fw) for the USB-CAN adapter

**Hardware**
- [Voron Design](https://docs.vorondesign.com/): the Voron 2.4 build guide, sample
  configuration, Clockwork 2 and Stealthburner
- BIGTREETECH documentation for the [EBB toolhead boards](https://github.com/bigtreetech/EBB)
  and the [Eddy probe](https://github.com/bigtreetech/Eddy)

**Slicer and calibration models**
- [OrcaSlicer](https://github.com/OrcaSlicer/OrcaSlicer) by SoftFever and contributors
  (AGPL-3.0), and its [calibration guide](https://github.com/OrcaSlicer/OrcaSlicer/wiki/calibration_guide).
  `tools/orca_calib.py` slices Orca's own calibration models straight from your Orca
  installation; they are not copied into this repository. As credited in Orca's guide:
  - temperature tower: remixed from the "Smart compact temperature calibration tower"
    by gaaZolee
  - max volumetric speed test: remixed from CNC Kitchen's (Stefan Hermann) Extrusion
    Test Structure
  - flow and retraction tests: inspired by SuperSlicer (by supermerill)
  - tolerance test (`OrcaToleranceTest`): ships with OrcaSlicer
- [CNC Kitchen](https://cnckitchen.com/) for the extrusion-limit testing approach

**Dollhouse**
- [Blender](https://www.blender.org/) (Displace modifier, procedural Wood texture)
- Free CC0 wood textures with displacement maps: [ambientCG](https://ambientcg.com/) and
  [Poly Haven](https://polyhaven.com/textures)

**This repository**
- Built and tuned by the repository owner on this machine. Claude (Anthropic) helped with
  much of the diagnosis, scripting and documentation from October 2026; the commits
  co-authored by it say so.

## License

The original work here (scripts in `tools/`, macros and notes written for this
printer, the OrcaSlicer presets and the documentation) is released under the
[MIT License](LICENSE): use it, change it, share it, no strings attached beyond
keeping the notice. Files that started from someone else's work keep that work's
license: the Voron and BIGTREETECH sample configurations behind `printer.cfg` and
`ebb_extruder.cfg`, KAMP's `KAMP_Settings.cfg`, the candleLight firmware build, and
OrcaSlicer's calibration models (not included; read from your own Orca install). See
[LICENSE](LICENSE) for the details.
