#!/usr/bin/python3
"""Batocera service: put every display to sleep after N minutes without input, wake it on the next input.

Install:  see README.md next to this file
Settings (batocera.conf, optional):  displayidle.minutes=5

Monitors are put in power-save (DPMS off; displayidle.mode=black only dims them to black instead). Many monitors report
themselves as disconnected in power-save, and Batocera's hotplug handler (batocera-switch-screen-checker) would restart
EmulationStation. That handler skips an event when /tmp/no-hotplug exists, so we keep that file in place while the
screens sleep and for a while after they wake.
Why read input devices directly? X's idle timer ignores joysticks, and EmulationStation's screensaver doesn't run
while a game is open. Reading the encoders/guns/keyboards catches everything, in the menu and in games.
"""
import os, select, signal, subprocess, sys, time

IGNORE = ("power button", "sleep button", "video bus", "hdmi", "hda ", "pc speaker", "wmi hotkeys", "lid switch")
LOG = "/var/log/displayidle.log"
ENV = {**os.environ, "DISPLAY": ":0.0"}


def log(msg):
    with open(LOG, "a") as f:
        f.write(time.strftime("%H:%M:%S ") + msg + "\n")


def setting(key, default):
    try:
        v = subprocess.run(["batocera-settings-get", key], capture_output=True, text=True, timeout=10).stdout.strip()
        return v or default
    except Exception:
        return default


_outputs = []


def outputs():
    global _outputs
    try:
        out = subprocess.run(["xrandr", "--listactivemonitors"], capture_output=True, text=True, timeout=5, env=ENV).stdout
        found = [l.split()[-1] for l in out.splitlines()[1:] if l.strip()]
        if found:
            _outputs = found
    except Exception:
        pass
    return _outputs                                    # last known list if X is busy


def set_brightness(value):
    for o in outputs():
        try:
            subprocess.run(["xrandr", "--output", o, "--brightness", str(value)], env=ENV,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
        except Exception as ex:
            log(f"xrandr {o} failed: {ex}")


GUARD = "/tmp/no-hotplug"
_guard_until = 0.0


def guard_loop():
    """Keep the hotplug handler's skip file present while needed (the handler deletes it each time it is used)."""
    held = False
    while True:
        if time.time() < _guard_until:
            if not os.path.exists(GUARD):
                open(GUARD, "w").close()
            held = True
        elif held:                                      # done: let real plug/unplug events through again
            try:
                os.remove(GUARD)
            except OSError:
                pass
            held = False
        time.sleep(0.2)


def xset(*args):
    try:
        subprocess.run(["xset", *args], env=ENV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
    except Exception as ex:
        log(f"xset {' '.join(args)} failed: {ex}")


def screens(on, mode):
    global _guard_until
    if mode == "black":
        set_brightness(1 if on else 0)
        return
    _guard_until = float("inf")
    if on:
        xset("dpms", "force", "on")
        xset("-dpms")
        _guard_until = time.time() + 20                 # monitors re-announce themselves while waking
    else:
        xset("dpms", "0", "0", "0")                     # no X timers: X ignores joysticks
        xset("+dpms")
        xset("dpms", "force", "off")


def open_devices(evdev):
    devs = {}
    for path in evdev.list_devices():
        try:
            d = evdev.InputDevice(path)
        except OSError:
            continue
        if any(w in d.name.lower() for w in IGNORE):
            continue
        caps = d.capabilities()
        if evdev.ecodes.EV_KEY in caps or evdev.ecodes.EV_ABS in caps or evdev.ecodes.EV_REL in caps:
            devs[d.fd] = d
    return devs


def run(idle_seconds, mode):
    import evdev, threading
    threading.Thread(target=guard_loop, daemon=True).start()
    from evdev import ecodes as e
    devs, rescan, last_input, blank = open_devices(evdev), time.time() + 30, time.time(), False
    absinfo = {}
    rel_acc, rel_t = 0, time.time()

    def restore(*_):
        if blank:
            screens(True, mode)
            time.sleep(21)                              # guard_loop removes the skip file after its 20 s
        sys.exit(0)
    signal.signal(signal.SIGTERM, restore)
    signal.signal(signal.SIGINT, restore)
    log(f"started: {mode} after {idle_seconds:.0f}s, watching {len(devs)} devices")
    while True:
        r, _, _ = select.select(list(devs), [], [], 1.0)
        active = False
        for fd in r:
            d = devs.get(fd)
            try:
                for ev in d.read():
                    if ev.type == e.EV_KEY and ev.value == 1:
                        active = True
                    elif ev.type == e.EV_ABS:          # sticks/guns: a real move, not sensor jitter
                        key = (fd, ev.code)
                        if key not in absinfo:
                            try:
                                ai = d.absinfo(ev.code); span = max(1, ai.max - ai.min)
                            except Exception:
                                span = 2
                            absinfo[key] = [span, ev.value]
                        span, last = absinfo[key]
                        if abs(ev.value - last) > 0.25 * span:
                            active = True
                            absinfo[key][1] = ev.value
                        elif abs(ev.value - last) > 0:
                            absinfo[key][1] = last  # keep the reference point; slow drift doesn't count
                    elif ev.type == e.EV_REL:          # guns/trackballs/mice: ignore tiny jitter
                        if time.time() - rel_t > 1:
                            rel_acc, rel_t = 0, time.time()
                        rel_acc += abs(ev.value)
                        if rel_acc > 40:
                            active = True
            except OSError:                            # device unplugged / recreated
                devs.pop(fd, None)
        now = time.time()
        if active:
            last_input = now
            if blank:
                screens(True, mode); blank = False
                log("input - displays restored")
        elif not blank and now - last_input >= idle_seconds:
            screens(False, mode); blank = True
            log("idle - displays blanked")
        if now >= rescan:                              # pick up re-plugged/recreated devices (e.g. Sinden guns)
            for fd, d in open_devices(evdev).items():
                if all(x.path != d.path for x in devs.values()):
                    devs[fd] = d
            rescan = now + 30


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "start":
        pid = os.fork()
        if pid == 0:
            os.setsid()
            time.sleep(20)                              # let X/EmulationStation come up first
            run(float(setting("displayidle.minutes", "5")) * 60, setting("displayidle.mode", "dpms"))
        open("/var/run/displayidle.pid", "w").write(str(pid))
    elif cmd == "stop":
        try:
            os.kill(int(open("/var/run/displayidle.pid").read()), signal.SIGTERM)
        except Exception:
            pass
    elif cmd == "test":                                 # displayidle test <seconds>: run in the foreground
        run(float(sys.argv[2]) if len(sys.argv) > 2 else 10, sys.argv[3] if len(sys.argv) > 3 else "dpms")
