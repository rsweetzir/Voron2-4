#!/bin/sh
# Copy the OrcaSlicer user presets in orca/ into this Mac's OrcaSlicer (one way:
# repo -> Mac). Presets that exist only on the Mac are left alone; edits made in
# Orca to a repo preset are overwritten the next time that preset changes here.
# Run automatically by the com.voron.orca-preset-sync launch agent
# (tools/orca-preset-sync.plist) whenever orca/ changes; restart Orca to load.
set -e
cd "$(dirname "$0")/.."
dest="$HOME/Library/Application Support/OrcaSlicer/user/default"
for kind in machine process filament; do
    mkdir -p "$dest/$kind"
    rsync -rtc --itemize-changes "orca/$kind/" "$dest/$kind/"
done
