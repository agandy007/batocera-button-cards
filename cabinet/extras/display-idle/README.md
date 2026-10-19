# display-idle

Puts every screen to sleep after N minutes with no input from any controller, gun, trackball or keyboard, in the menu
**and** during games, and lights them again on the next press. Default 5 minutes.

```bash
mkdir -p /userdata/system/displayidle
cp displayidle.py /userdata/system/displayidle/
cp displayidle /userdata/system/services/ && chmod +x /userdata/system/services/displayidle
batocera-settings-set displayidle.minutes 5      # optional
batocera-services enable displayidle && batocera-services start displayidle
tail /var/log/displayidle.log
```

It puts the monitors into power-save (real sleep). With DPMS off, many monitors look unplugged, and Batocera's hotplug
handler would restart EmulationStation every minute or so. The handler skips an event while `/tmp/no-hotplug` exists,
so the service keeps that file in place while the screens sleep and for 20 seconds after they wake, then removes it.
`batocera-settings-set displayidle.mode black` dims the screens to black instead of sleeping them.
