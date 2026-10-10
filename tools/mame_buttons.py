"""Extract player-1 button names per game from the MAME source tree (src/mame/**/*.cpp).

  python3 mame_buttons.py <path-to-mame-checkout> [out.json]

MAME drivers name many buttons, e.g.
    PORT_BIT( 0x0040, IP_ACTIVE_LOW, IPT_BUTTON1 ) PORT_NAME("P1 Turbo") PORT_PLAYER(1)
Games are tied to input definitions by the GAME() macro:
    GAME( 1993, nbajam, 0, nbajam, nbajam, midtunit_state, init_nbajam, ROT0, "Midway", "NBA Jam", ... )
Output: {"nbajam": {"1": "Turbo", "2": "Shoot / Block", "3": "Pass / Steal"}, ...}
Only names MAME itself defines are emitted; unnamed buttons are left out.
"""
import glob, json, os, re, sys

SRC = sys.argv[1] if len(sys.argv) > 1 else "mame"
OUT = sys.argv[2] if len(sys.argv) > 2 else "mame-button-names.json"

PORTS_RE = re.compile(r"INPUT_PORTS_START\(\s*(\w+)\s*\)(.*?)INPUT_PORTS_END", re.S)
GAME_RE = re.compile(r"^\s*(?:GAME|GAMEL)\s*\(\s*\w+\s*,\s*(\w+)\s*,\s*(\w+)\s*,\s*\w+\s*,\s*(\w+)\s*,", re.M)
BIT_RE = re.compile(r"IPT_BUTTON(\d+)\b(.*)")
NAME_RE = re.compile(r'PORT_NAME\(\s*"([^"]+)"\s*\)')
PLAYER_RE = re.compile(r"PORT_PLAYER\(\s*(\d+)\s*\)")
INCLUDE_RE = re.compile(r"PORT_INCLUDE\(\s*(\w+)\s*\)")


def clean(name):
    name = re.sub(r"^(P1|1P|Player 1)\s*", "", name).strip(" -:")
    return name


ports = {}      # input-ports name -> {"own": {btn: name}, "include": [names]}
games = {}      # game shortname -> (parent, input-ports name)
for path in glob.glob(os.path.join(SRC, "src", "mame", "**", "*.cpp"), recursive=True):
    text = open(path, encoding="utf-8", errors="replace").read()
    for m in PORTS_RE.finditer(text):
        own, inc = {}, INCLUDE_RE.findall(m.group(2))
        for line in m.group(2).splitlines():
            b = BIT_RE.search(line)
            n = NAME_RE.search(line)
            if not b or not n:
                continue
            pl = PLAYER_RE.search(line)
            player = int(pl.group(1)) if pl else (2 if re.match(r"^(P2|2P)\b", n.group(1)) else 1)
            if player == 1:
                own.setdefault(b.group(1), clean(n.group(1)))
        ports[m.group(1)] = {"own": own, "include": inc}
    for m in GAME_RE.finditer(text):
        games[m.group(1)] = (m.group(2), m.group(3))


def resolve(pname, seen=()):
    """Buttons of an input definition, following PORT_INCLUDE (own definitions win)."""
    if pname not in ports or pname in seen:
        return {}
    out = {}
    for inc in ports[pname]["include"]:
        out.update(resolve(inc, seen + (pname,)))
    out.update(ports[pname]["own"])
    return out


result = {}
for g, (parent, pname) in games.items():
    btns = resolve(pname)
    if btns:
        result[g] = dict(sorted(btns.items(), key=lambda kv: int(kv[0])))
json.dump(result, open(OUT, "w"), indent=0, sort_keys=True)
print(f"games: {len(games)}  with named P1 buttons: {len(result)}  -> {OUT}")
