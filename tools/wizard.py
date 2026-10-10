"""Layout wizard: record which encoder button sits at each physical position, then write layout.json.

Run from the Mac:  python3 wizard.py [cabinet-ip] [seconds]
The user presses player 1's buttons once each, in this order:
  top row left->right, bottom row left->right, then the two buttons above left->right.
Mapping chain (from the cabinet's es_input.cfg + MAME mameControls.csv 'default'):
  encoder button id -> retropad name -> MAME button number.
"""
import json, os, re, subprocess, sys

HOST = sys.argv[1] if len(sys.argv) > 1 else "192.168.4.22"
SECS = int(sys.argv[2]) if len(sys.argv) > 2 else 180
PLAYER = int(sys.argv[3]) if len(sys.argv) > 3 else 1   # 1 = first encoder, 2 = second encoder
HERE = os.path.dirname(os.path.abspath(__file__))
POSITIONS = ["top-left", "top-middle", "top-right", "bottom-left", "bottom-middle", "bottom-right", "above-left", "above-right"]

# es_input.cfg (DragonRise): retropad name -> evdev code
PAD_CODE = {"b": 296, "a": 297, "y": 298, "x": 299, "pageup": 295, "pagedown": 294, "start": 292, "select": 293}
# MAME 2003-Plus / mameControls.csv default: MAME function -> retropad name  (VERIFY for mame078plus core)
# mame078plus core (MAME 2003-Plus): B=1 A=2 Y=3 X=4 L=5 R=6 - confirmed B1-B3 by play tests (Punch-Out, NBA Jam)
MAME_PAD = {1: "b", 2: "a", 3: "y", 4: "x", 5: "pageup", 6: "pagedown", "START": "start", "COIN": "select"}
CODE_TO_FUNC = {PAD_CODE[pad]: func for func, pad in MAME_PAD.items()}

# record presses from the first DragonRise encoder (player 1 = first device ES assigns; checked below)
cmd = ("D=$(for d in $(ls -d /sys/class/input/event* | sort -V); do n=$(cat $d/device/name); case \"$n\" in *DragonRise*) "
       f"echo /dev/input/$(basename $d);; esac; done | sed -n {PLAYER}p); echo DEVICE $D; "
       f"timeout {SECS} evtest $D 2>/dev/null | grep --line-buffered 'EV_KEY.*value 1'")
print(f"Recording {SECS}s on {HOST}. Press each player-1 button ONCE, in order:\n  " + ", ".join(POSITIONS))
out = subprocess.run(["ssh", f"root@{HOST}", cmd], capture_output=True, text=True).stdout
codes = []
for line in out.splitlines():
    m = re.search(r"code (\d+) ", line)
    if m:
        c = int(m.group(1))
        if not codes or codes[-1] != c:  # ignore double-taps
            codes.append(c)
print("device:", next((l for l in out.splitlines() if l.startswith("DEVICE")), "?"))
print("codes pressed:", codes)
if len(codes) < 8:
    sys.exit(f"Only {len(codes)} presses recorded - need 8. Nothing written.")

pos_func = {}
for pos, code in zip(POSITIONS, codes[:8]):
    func = CODE_TO_FUNC.get(code)
    pos_func[pos] = func
    print(f"  {pos:14s} -> evdev {code} -> MAME {func}")

if PLAYER != 1:
    panel = json.load(open(os.path.join(HERE, "package", "panel.json")))
    same = all(panel["codes"][p] == c for p, c in zip(POSITIONS, codes[:8]))
    print("PLAYER", PLAYER, "matches player 1 wiring" if same else "DIFFERS from player 1:")
    for p, c in zip(POSITIONS, codes[:8]):
        print(f"  {p:14s} P1={panel['codes'][p]} P{PLAYER}={c}" + ("" if panel["codes"][p] == c else "   <-- different"))
    sys.exit(0)
layout = json.load(open(os.path.join(HERE, "layout.json")))
layout["rows"] = [[pos_func[p] for p in POSITIONS[0:3]], [pos_func[p] for p in POSITIONS[3:6]]]
layout["above"] = [pos_func["above-left"], pos_func["above-right"]]
layout["confirmed"] = True
json.dump(layout, open(os.path.join(HERE, "layout.json"), "w"), indent=2)
print("layout.json updated:", layout["rows"], layout["above"])
