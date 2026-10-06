#!/bin/sh
# Pull the current Klipper config and firmware build settings from the printer
# (yeg2-4, see ~/.ssh/config) and the OrcaSlicer user profiles from this Pi.
set -e
cd "$(dirname "$0")/.."
rsync -a yeg2-4:printer_data/config/printer.cfg yeg2-4:printer_data/config/macros.cfg yeg2-4:printer_data/config/calibration.cfg \
      yeg2-4:printer_data/config/ebb_extruder.cfg yeg2-4:printer_data/config/KAMP_Settings.cfg klipper/
rsync -a yeg2-4:fw/skrpro.config yeg2-4:fw/ebb.config firmware/
rsync -a --exclude 'base/' --exclude '*.bak-*' "$HOME/snap/orcaslicer/current/.config/OrcaSlicer/user/default/" orca/
# Keep MCU serial IDs out of the public repo.
sed -i -E 's#(/dev/serial/by-id/usb-Klipper_stm32[a-z0-9]+_)[0-9A-F]{24}(-if00)#\1<MCU_SERIAL>\2#' \
    klipper/printer.cfg klipper/ebb_extruder.cfg
echo "Synced. Review 'git diff' before committing."
