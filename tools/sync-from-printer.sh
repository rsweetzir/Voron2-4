#!/bin/sh
# Pull the current Klipper config and firmware build settings from the printer
# (ssh alias 'voron', see ~/.ssh/config; override with PRINTER_SSH=...) into this repo.
# OrcaSlicer presets are not pulled: orca/ is their source, and
# tools/install-orca-presets.sh installs them into this Mac's OrcaSlicer.
set -e
cd "$(dirname "$0")/.."
P="${PRINTER_SSH:-voron}"
rsync -a "$P:printer_data/config/printer.cfg" "$P:printer_data/config/macros.cfg" "$P:printer_data/config/calibration.cfg" \
      "$P:printer_data/config/ebb_extruder.cfg" "$P:printer_data/config/KAMP_Settings.cfg" "$P:printer_data/config/eddy.cfg" klipper/
rsync -a "$P:fw/skrpro.config" "$P:fw/ebb.config" "$P:fw/ebb-can.config" "$P:fw/eddy-can.config" firmware/
# Keep MCU serial IDs out of the public repo (perl: same on macOS and Linux).
perl -i -pe 's#(/dev/serial/by-id/usb-Klipper_stm32[a-z0-9]+_)[0-9A-F]{24}(-if00)#$1<MCU_SERIAL>$2#' \
    klipper/printer.cfg klipper/ebb_extruder.cfg
echo "Synced. Review 'git diff' before committing."
