#!/bin/bash
# Install the button-card viewer ("cardview") on a Batocera cabinet.
# Run from the repo's cabinet/ folder after copying the repo to the cabinet (see README).
set -e
cd "$(dirname "$0")"
D=/userdata/system/cardview
ES=/userdata/system/configs/emulationstation/scripts
mkdir -p "$D/bin" "$D/cards" /userdata/system/services "$ES/game-selected" "$ES/system-selected" "$ES/game-start" "$ES/game-end"
cp bin/cardview-show bin/cardgen.py "$D/bin/" && chmod +x "$D/bin/"*
[ -f "$D/layout.json" ] && [ "$(python3 -c "import json;print(json.load(open('$D/layout.json')).get('confirmed'))")" = "True" ] \
  && echo "keeping confirmed layout.json" || cp layout.json "$D/layout.json"
cp gamedb.json ../data/profiles.json "$D/"
[ -f "$D/panel.json" ] && python3 -c "import json,sys;sys.exit(0 if json.load(open('$D/panel.json')).get('confirmed') else 1)" \
  && echo "keeping confirmed panel.json" || cp panel.example.json "$D/panel.json"
cp services/cardview /userdata/system/services/cardview && chmod +x /userdata/system/services/cardview
cp scripts/game-selected/cardview.sh "$ES/game-selected/cardview.sh"
cp scripts/system-selected/cardview.sh "$ES/system-selected/cardview.sh"
cp scripts/game-start/cardview.sh "$ES/game-start/cardview.sh"
cp scripts/game-end/cardview.sh "$ES/game-end/cardview.sh"
chmod +x "$ES/game-selected/cardview.sh" "$ES/system-selected/cardview.sh" "$ES/game-start/cardview.sh" "$ES/game-end/cardview.sh"
python3 "$D/bin/cardgen.py"
batocera-services enable cardview
( batocera-services start cardview >/dev/null 2>&1 & )   # waits for HDMI-2; exits quietly if no screen
echo "cardview installed in $D"
