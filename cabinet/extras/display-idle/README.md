# display-idle

Blacks out every screen after N minutes with no input from any controller, gun, trackball or keyboard, in the menu
**and** during games, and lights them again on the next press. Default 5 minutes.

```bash
mkdir -p /userdata/system/displayidle
cp displayidle.py /userdata/system/displayidle/
cp displayidle /userdata/system/services/ && chmod +x /userdata/system/services/displayidle
batocera-settings-set displayidle.minutes 5      # optional
batocera-services enable displayidle && batocera-services start displayidle
tail /var/log/displayidle.log
```

It sets each output's brightness to 0 rather than powering the monitors off: with DPMS off, many monitors look
unplugged, and Batocera's hotplug handler restarts EmulationStation every minute or so. The screens show black but
the backlights stay on.
