#!/bin/bash
# EmulationStation event: the screensaver started (no input for ScreenSaverTime).
# Turn ALL displays off once the cabinet has been idle for SLEEP_AFTER seconds in total.
# EmulationStation tracks joystick/button input (X's own idle timer does not), so this follows real activity.
SLEEP_AFTER=300
T=$(grep -oE 'name="ScreenSaverTime" value="[0-9]+"' /userdata/system/configs/emulationstation/es_settings.cfg | grep -oE "[0-9]+$")
T=$(( ${T:-300000} / 1000 ))
DELAY=$(( SLEEP_AFTER - T )); [ "$DELAY" -lt 0 ] && DELAY=0
(
  sleep "$DELAY"
  export DISPLAY=:0.0
  xset +dpms; xset dpms 0 0 0      # DPMS on, but no automatic X timeouts (X ignores joysticks)
  xset dpms force off
  echo "$(date +%T) displays off" >> /var/log/display-sleep.log
) &
echo $! > /var/run/display-sleep.pid
