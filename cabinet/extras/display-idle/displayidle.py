#!/usr/bin/python3
"""Batocera service: black out every display after N minutes without input, restore on the next input.

Install:  see README.md next to this file
Settings (batocera.conf, optional):  displayidle.minutes=5

Why not power the monitors off (DPMS)? Many monitors report themselves as disconnected in power-save, and Batocera's
screen hotplug handler then restarts EmulationStation - an endless off/restart/on loop. Setting each output's
brightness to 0 keeps the video signal (no hotplug) while the screen shows black.
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


def minutes():
    try:
        v = subprocess.run(["batocera-settings-get", "displayidle.minutes"], capture_output=True, text=True).stdout.strip()
        return float(v) if v else 5.0
    except Exception:
        return 5.0


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


def run(idle_seconds):
    import evdev
    from evdev import ecodes as e
    devs, rescan, last_input, blank = open_devices(evdev), time.time() + 30, time.time(), False
    absinfo = {}
    rel_acc, rel_t = 0, time.time()

    def restore(*_):
        if blank:
            set_brightness(1)
        sys.exit(0)
    signal.signal(signal.SIGTERM, restore)
    signal.signal(signal.SIGINT, restore)
    log(f"started: blank after {idle_seconds:.0f}s, watching {len(devs)} devices")
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
                set_brightness(1); blank = False
                log("input - displays restored")
        elif not blank and now - last_input >= idle_seconds:
            set_brightness(0); blank = True
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
            run(minutes() * 60)
        open("/var/run/displayidle.pid", "w").write(str(pid))
    elif cmd == "stop":
        try:
            os.kill(int(open("/var/run/displayidle.pid").read()), signal.SIGTERM)
        except Exception:
            pass
    elif cmd == "test":                                 # displayidle test <seconds>: run in the foreground
        run(float(sys.argv[2]) if len(sys.argv) > 2 else 10)
