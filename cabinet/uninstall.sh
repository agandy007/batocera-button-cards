#!/bin/bash
# Remove cardview completely.
batocera-services stop cardview 2>/dev/null; batocera-services disable cardview 2>/dev/null
rm -f /userdata/system/services/cardview /userdata/system/configs/emulationstation/scripts/*/cardview.sh
rm -rf /userdata/system/cardview
echo "cardview removed"
