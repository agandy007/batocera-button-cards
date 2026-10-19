#!/bin/bash
# EmulationStation event: input arrived, the screensaver stopped -> cancel a pending sleep and wake the displays.
[ -f /var/run/display-sleep.pid ] && kill "$(cat /var/run/display-sleep.pid)" 2>/dev/null
rm -f /var/run/display-sleep.pid
export DISPLAY=:0.0
xset dpms force on
echo "$(date +%T) displays on" >> /var/log/display-sleep.log
