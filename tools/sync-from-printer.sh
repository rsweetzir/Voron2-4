#!/bin/sh
# SPDX-License-Identifier: MIT  (c) 2026 The Voron2-4 authors, see LICENSE
# Pull the current Klipper config and firmware build settings from a printer into this repo
# (printer -> repo), e.g. after SAVE_CONFIG. Deploying the other way: tools/deploy_config.py.
#   tools/sync-from-printer.sh                 Edmonton (ssh alias 'voron') -> klipper/, firmware/
#   PRINTER=vegas tools/sync-from-printer.sh   Las Vegas ('voron-vegas') -> vegas/klipper/, vegas/firmware/
# PRINTER_SSH=... overrides the ssh alias. klipper/shared/ is never pulled: the repo is its
# source (docs/printer-parity.md); this only warns if a printer's copy differs.
# OrcaSlicer presets are not pulled: orca/ is their source, and
# tools/install-orca-presets.sh installs them into this Mac's OrcaSlicer.
set -e
cd "$(dirname "$0")/.."
case "${PRINTER:-edmonton}" in
    edmonton)
        P="${PRINTER_SSH:-voron}"
        rsync -a "$P:printer_data/config/printer.cfg" "$P:printer_data/config/macros.cfg" "$P:printer_data/config/calibration.cfg" \
              "$P:printer_data/config/ebb_extruder.cfg" "$P:printer_data/config/KAMP_Settings.cfg" "$P:printer_data/config/eddy.cfg" \
              "$P:printer_data/config/printer_settings.cfg" klipper/
        rsync -a "$P:fw/skrpro.config" "$P:fw/ebb.config" "$P:fw/ebb-can.config" "$P:fw/eddy-can.config" firmware/
        DIR=klipper ;;
    vegas)
        P="${PRINTER_SSH:-voron-vegas}"
        for f in printer.cfg eddy.cfg qgl.cfg bed_mesh.cfg KAMP_Settings.cfg menu.cfg calibration.cfg \
                 printer_settings.cfg purge.cfg calibrate.cfg; do
            rsync -a "$P:printer_data/config/$f" vegas/klipper/
        done
        rsync -a "$P:printer_data/config/firmware-eddy-usb.config" "$P:printer_data/config/firmware-octopus-usbcan.config" vegas/firmware/
        DIR=vegas/klipper ;;
    *) echo "unknown PRINTER=$PRINTER (edmonton or vegas)"; exit 1 ;;
esac
# Keep MCU serial IDs out of the public repo (perl: same on macOS and Linux).
perl -i -pe 's#(/dev/serial/by-id/usb-Klipper_(?:stm32[a-z0-9]+|rp2040)_)[0-9A-F]{12,24}(-if00)#$1<MCU_SERIAL>$2#' "$DIR"/*.cfg
for f in klipper/shared/*.cfg; do
    if ! ssh -o BatchMode=yes "$P" "cat printer_data/config/shared/$(basename "$f")" 2>/dev/null | cmp -s - "$f"; then
        echo "WARNING: $P's shared/$(basename "$f") differs from the repo (not deployed yet, or edited on the printer)"
    fi
done
echo "Synced. Review 'git diff' before committing."
