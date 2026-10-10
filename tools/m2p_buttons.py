"""Player-1 button meanings from MAME 2003-Plus driver source comments and PORT_BITX names.

  python3 m2p_buttons.py <mame2003-plus checkout> <roms.txt> [out.json]

Uses the exact emulator the cabinet runs. Captures e.g.
  PORT_BIT( 0x0010, IP_ACTIVE_LOW, IPT_BUTTON3 | IPF_PLAYER1 ) /* HP */
  PORT_BITX(0x0010, IP_ACTIVE_LOW, IPT_BUTTON1 | IPF_PLAYER1, "Fire", ... )
Games link to input definitions through GAME( year, name, parent, machine, input, ... ).
"""
import glob, json, os, re, sys
SRC, ROMS = sys.argv[1], sys.argv[2]
OUT = sys.argv[3] if len(sys.argv) > 3 else "m2p-button-names.json"
ABBR = {"HP": "High Punch", "LP": "Low Punch", "HK": "High Kick", "LK": "Low Kick", "BL": "Block", "BLOCK2": "Block",
        "MP": "Medium Punch", "MK": "Medium Kick", "RUN": "Run"}
PORTS = re.compile(r"INPUT_PORTS_START\(\s*(\w+)\s*\)(.*?)INPUT_PORTS_END", re.S)
GAME = re.compile(r"^\s*GAME\w*\s*\(\s*\w+\s*,\s*(\w+)\s*,\s*(\w+)\s*,\s*\w+\s*,\s*(\w+)\s*,", re.M)
LINE = re.compile(r"IPT_BUTTON(\d+)\s*\|\s*IPF_PLAYER1\b[^\n]*")
COMMENT = re.compile(r"/\*\s*([^*]{1,30}?)\s*\*/")
BITX = re.compile(r'PORT_BITX\([^"]*IPT_BUTTON(\d+)\s*\|\s*IPF_PLAYER1[^"]*"([^"]+)"')
ports, games = {}, {}
for path in glob.glob(os.path.join(SRC, "src", "drivers", "*.c")):
    t = open(path, encoding="latin-1").read()
    for m in PORTS.finditer(t):
        names = {}
        for line in m.group(2).splitlines():
            if line.strip().startswith("/*"):
                continue   # commented-out port bit
            b = BITX.search(line)
            if b:
                names.setdefault(b.group(1), b.group(2)); continue
            l = LINE.search(line)
            c = COMMENT.search(line) if l else None
            if l and c and not re.search(r"(?i)unused|unknown|\?|test|service|coin|start|dip", c.group(1)):
                txt = c.group(1).strip()
                names.setdefault(l.group(1), ABBR.get(txt.upper().replace(" ", ""), txt))
        ports[m.group(1)] = names
    for m in GAME.finditer(t):
        games[m.group(1)] = m.group(3)
want = [l.strip() for l in open(ROMS) if l.strip()]
res = {g: dict(sorted(ports[games[g]].items(), key=lambda kv: int(kv[0]))) for g in want if g in games and ports.get(games[g])}
json.dump(res, open(OUT, "w"), indent=0, sort_keys=True)
print(f"cabinet games: {len(want)}  with named buttons in MAME 2003-Plus source: {len(res)}")
for g, v in res.items(): print(" ", g, v)
