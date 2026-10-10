#!/usr/bin/python3
"""Panel wizard - run ON the cabinet. Records which key code each physical button sends and writes panel.json.

  python3 wizard.py                      # 2 rows of 3 + 2 small buttons above (coin/start)
  python3 wizard.py --rows 4,4           # 2 rows of 4 (8-button panel)
  python3 wizard.py --rows 3,3,2 --above 2
  python3 wizard.py --compare            # player 2: check its wiring against the saved panel.json (writes nothing)

Press each button of ONE player's panel once, in the order shown (row by row, left to right, top row first,
then the small buttons above). Works with joystick-type encoders (DragonRise "zero delay", Xin-Mo, ...) and
keyboard-type encoders (I-PAC, ...): the first device you press is the one recorded.
"""
import argparse, json, os, select, subprocess, sys, time
import evdev
from evdev import ecodes

BASE = os.environ.get("CARDVIEW_BASE", "/userdata/system/cardview")
PALETTE = ["#1e88e5", "#fdd835", "#f4f4f4", "#43a047", "#e53935", "#8e24aa", "#fb8c00", "#00acc1", "#6d4c41", "#d81b60"]
IGNORE = ("power button", "sleep button", "video bus", "hdmi", "hda ", "pc speaker", "wmi hotkeys", "lid switch",
          "batocera hotkeys", "evmapy", "sinden", "gun")


def names(rows, above):
    """Human position names: top-left, bottom-middle, above-right ..."""
    rn = {1: ["row"], 2: ["top", "bottom"], 3: ["top", "middle", "bottom"]}
    def cols(n):
        return {1: ["center"], 2: ["left", "right"], 3: ["left", "middle", "right"],
                4: ["left", "center-left", "center-right", "right"]}.get(n, [f"col{i + 1}" for i in range(n)])
    rnames = rn.get(len(rows), [f"row{i + 1}" for i in range(len(rows))])
    grid = [[f"{rnames[r]}-{c}" for c in cols(n)] for r, n in enumerate(rows)]
    ab = [f"above-{c}" for c in cols(above)] if above else []
    return grid, ab


def input_devices():
    devs = []
    for path in evdev.list_devices():
        try:
            d = evdev.InputDevice(path)
        except OSError:
            continue
        caps = d.capabilities().get(ecodes.EV_KEY, [])
        if not caps or any(w in d.name.lower() for w in IGNORE):
            continue
        devs.append(d)
    return devs


def second_screen():
    """(output, width, height) of a connected non-primary display, if any."""
    try:
        out = subprocess.run(["xrandr"], capture_output=True, text=True, env={**os.environ, "DISPLAY": ":0.0"}).stdout
    except OSError:
        return None
    cur = None
    for line in out.splitlines():
        if " connected" in line:
            cur = None if " primary" in line else line.split()[0]
        elif cur and line.startswith("   ") and "+" in line:   # preferred mode
            w, h = line.split()[0].split("x")
            return cur, int(w), int(h.split("i")[0])
    return None


def record(order, timeout):
    devs = input_devices()
    if not devs:
        sys.exit("No input devices with buttons found.")
    print("Listening on:", ", ".join(f"{d.path} ({d.name})" for d in devs))
    fds = {d.fd: d for d in devs}
    chosen, codes, last, t_end = None, [], None, time.time() + timeout
    print(f"\nPress each button ONCE, slowly. ({timeout}s)\n  -> {order[0]}", flush=True)
    while len(codes) < len(order) and time.time() < t_end:
        r, _, _ = select.select(list(fds), [], [], 0.5)
        for fd in r:
            d = fds[fd]
            for ev in d.read():
                if ev.type != ecodes.EV_KEY or ev.value != 1:
                    continue
                if chosen is None:
                    chosen = d
                    print(f"     (recording device: {d.name})")
                if d.fd != chosen.fd or ev.code == last:
                    continue
                last = ev.code
                codes.append(ev.code)
                name = ecodes.KEY.get(ev.code) or ecodes.BTN.get(ev.code) or ev.code
                print(f"     {order[len(codes) - 1]:16s} = {ev.code} ({name if isinstance(name, str) else name[0]})")
                if len(codes) < len(order):
                    print(f"  -> {order[len(codes)]}", flush=True)
    return chosen, codes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", default="3,3", help="buttons per row, top row first (default 3,3)")
    ap.add_argument("--above", type=int, default=2, help="small buttons above the rows (coin/start), default 2")
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--compare", action="store_true", help="compare another player's wiring with panel.json")
    ap.add_argument("--controls", default="joystick", help="controls this cabinet has, e.g. joystick,trackball,spinner")
    ap.add_argument("--out", default=f"{BASE}/panel.json")
    a = ap.parse_args()
    rows = [int(x) for x in a.rows.split(",")]
    grid, above = names(rows, a.above)
    order = [p for row in grid for p in row] + above
    dev, codes = record(order, a.timeout)
    if len(codes) < len(order):
        sys.exit(f"\nOnly {len(codes)} of {len(order)} presses recorded - nothing written. Run it again.")
    if len(set(codes)) < len(codes):
        sys.exit("\nThe same code was recorded for two positions - a button was pressed twice? Nothing written.")
    pos_codes = dict(zip(order, codes))
    if a.compare:
        ref = json.load(open(a.out))["codes"]
        diff = [p for p in order if ref.get(p) != pos_codes[p]]
        print("\nSame wiring as the saved panel." if not diff else "\nDifferent wiring at: " + ", ".join(diff))
        return
    old = json.load(open(a.out)) if os.path.exists(a.out) else {}
    colors = {p: (old.get("colors", {}).get(p) or PALETTE[i % len(PALETTE)]) for i, p in enumerate(p for row in grid for p in row)}
    scr = second_screen()
    panel = {
        "_comment": "Written by wizard.py: physical position -> key code of ONE player's panel.",
        "device_hint": dev.name.strip(),
        "device_type": "keyboard" if max(codes) < ecodes.BTN_MISC else "joystick",
        "screen": old.get("screen") or ({"width": scr[1], "height": scr[2], "output": scr[0]} if scr else {"width": 1024, "height": 600, "output": "HDMI-2"}),
        "rows": grid, "above": above, "codes": pos_codes, "colors": colors, "confirmed": True,
        "controls": [c.strip() for c in a.controls.split(",") if c.strip()],
    }
    json.dump(panel, open(a.out, "w"), indent=2)
    print(f"\nSaved {a.out}  ({panel['device_type']} encoder: {panel['device_hint']})")


if __name__ == "__main__":
    main()
