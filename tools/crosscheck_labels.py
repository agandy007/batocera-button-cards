#!/usr/bin/env python3
"""Cross-check button labels for MAME 2003-Plus games against official sources, by HARDWARE BIT.

  python3 tools/crosscheck_labels.py <mame2003-plus checkout> <mame checkout> [--history history-buttons.json] [--apply]

Why by bit: a button's meaning is fixed by the PCB wire it sits on (port + bit mask). MAME 2003-Plus and current MAME
often number the same wire differently (Mortal Kombat II is an example), but both describe it with the same port/mask.
So: take MAME 2003-Plus's button NUMBER for a wire (that is what the cabinet's RetroArch core uses) and current MAME's
PORT_NAME for the SAME wire -> an exact label for the number the cabinet actually sends.

Writes a report; with --apply, updates data/community-labels.csv (source = mame-source, or arcade-history-confirmed
when Arcade History agrees with an existing label). Never invents an order from Arcade History.
"""
import csv, glob, json, os, re, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(HERE, "data", "community-labels.csv")
args = [a for a in sys.argv[1:] if not a.startswith("--")]
M2P, MAME = args[0], args[1]
APPLY = "--apply" in sys.argv
HIST = sys.argv[sys.argv.index("--history") + 1] if "--history" in sys.argv else None

PORTS = re.compile(r"INPUT_PORTS_START\(\s*(\w+)\s*\)(.*?)INPUT_PORTS_END", re.S)
GAME = re.compile(r"^\s*GAME\w*\s*\(\s*\w+\s*,\s*(\w+)\s*,\s*(\w+)\s*,\s*\w+\s*,\s*(\w+)\s*,", re.M)


def parse_m2p():
    """input-ports name -> list of ports; port = {mask: button_number} for player-1 buttons."""
    ports, games = {}, {}
    for path in glob.glob(os.path.join(M2P, "src", "drivers", "*.c")):
        t = open(path, encoding="latin-1").read()
        for m in PORTS.finditer(t):
            plist, cur = [], None
            for line in m.group(2).splitlines():
                s = line.strip()
                if s.startswith("/*") or s.startswith("//"):
                    continue
                if s.startswith("PORT_START"):
                    cur = {}; plist.append(cur); continue
                b = re.search(r"PORT_BITX?\(\s*(0x[0-9a-fA-F]+|\d+)\s*,[^,]*,\s*IPT_BUTTON(\d+)\s*\|\s*IPF_PLAYER1\b", s)
                if b and cur is not None:
                    cur[int(b.group(1), 0)] = b.group(2)
            ports[m.group(1)] = plist
        for m in GAME.finditer(t):
            games[m.group(1)] = m.group(3)
    return ports, games


def parse_mame():
    """input-ports name -> ordered list of (tag, {mask: name}) for player-1 named buttons, PORT_INCLUDE/MODIFY resolved."""
    raw, games = {}, {}
    for path in glob.glob(os.path.join(MAME, "src", "mame", "**", "*.cpp"), recursive=True):
        t = open(path, encoding="utf-8", errors="replace").read()
        for m in PORTS.finditer(t):
            ops = []
            for line in m.group(2).splitlines():
                s = line.strip()
                if s.startswith("//"):
                    continue
                inc = re.match(r"PORT_INCLUDE\(\s*(\w+)\s*\)", s)
                st = re.match(r'PORT_(START|MODIFY)\(\s*"([^"]+)"\s*\)', s)
                b = re.search(r"PORT_BIT\(\s*(0x[0-9a-fA-F]+|\d+)\s*,[^,]*,\s*IPT_BUTTON(\d+)\s*\)", s)
                if inc:
                    ops.append(("inc", inc.group(1)))
                elif st:
                    ops.append((st.group(1).lower(), st.group(2)))
                elif b:
                    n = re.search(r'PORT_NAME\(\s*"([^"]+)"\s*\)', s)
                    pl = re.search(r"PORT_PLAYER\(\s*(\d+)\s*\)", s)
                    player = int(pl.group(1)) if pl else 1
                    ops.append(("bit", int(b.group(1), 0), b.group(2), n.group(1) if n else None, player))
            raw[m.group(1)] = ops
        for m in GAME.finditer(t):
            games[m.group(1)] = m.group(3)

    def build(name, seen=()):
        order, tags = [], {}
        if name not in raw or name in seen:
            return order, tags
        cur = None
        for op in raw[name]:
            if op[0] == "inc":
                o2, t2 = build(op[1], seen + (name,))
                for tg in o2:
                    if tg not in tags:
                        order.append(tg)
                    tags[tg] = dict(t2[tg])
            elif op[0] in ("start", "modify"):
                cur = op[1]
                if cur not in tags:
                    order.append(cur); tags[cur] = {}
                elif op[0] == "start":
                    tags[cur] = {}
            elif op[0] == "bit" and cur is not None:
                _, mask, num, pname, player = op
                tags[cur][mask] = (num, pname, player)
        return order, tags
    return build, games


def clean(n):
    n = re.sub(r"^(P1|1P|Player 1)\s+", "", n).strip()
    return re.sub(r"^(Block|Fire|Shoot|Punch|Kick)\s+\d$", r"\1", n)   # "Block 2" -> "Block"


# internal / technical names that mean nothing to a player - keep the existing label instead
NOT_PLAYER_FACING = re.compile(r"(?i)^([A-Z] Button|Menu|Button \d+|IN \d.*|\d+)$")


m2p_ports, m2p_games = parse_m2p()
mame_build, mame_games = parse_mame()
rows = list(csv.DictReader(open(CSV, newline="", encoding="utf-8")))
mine = {}
for r in rows:
    if r["system"] == "mame" and r["button"].isdigit():
        mine.setdefault(r["rom"], {})[r["button"]] = r
hist = json.load(open(HIST)) if HIST else {}

exact, changed, confirmed, report = {}, 0, 0, []
for rom in sorted(mine):
    pname2003, pnamenew = m2p_games.get(rom), mame_games.get(rom)
    if not pname2003 or not pnamenew:
        continue
    p2003 = m2p_ports.get(pname2003, [])
    order, tags = mame_build(pnamenew)
    names = {}
    for idx, port in enumerate(p2003):
        if idx >= len(order):
            break
        newport = tags[order[idx]]
        for mask, num in port.items():
            hit = newport.get(mask)
            if hit and hit[1] and hit[2] == 1 and not re.search(r"(?i)unknown|unused|\?", hit[1]) \
                    and not NOT_PLAYER_FACING.match(clean(hit[1])):
                names[num] = clean(hit[1])
    if names:
        exact[rom] = names
        for num, label in names.items():
            r = mine[rom].get(num)
            if r is None or r["label"].lower() != label.lower():
                report.append(f"{rom:10s} button {num}: '{r['label'] if r else '-'}' -> '{label}'  (MAME, by wire)")
                changed += 1

# Arcade History: confirm existing labels when the SET of functions agrees (order is not trusted)
def words(t):
    return set(re.findall(r"[a-z]+", t.lower())) - {"the", "a", "button", "and", "p"}
SYN = [{"fire", "shoot", "shot", "zap"}, {"jump"}, {"bomb"}, {"punch", "blow"}, {"kick"}, {"attack", "stab"},
       {"shield", "force", "field"}, {"loop", "roll"}, {"magic"}, {"pass"}, {"turbo"}]
def fnset(labels):
    out = set()
    for l in labels:
        w = words(l)
        out |= {i for i, s in enumerate(SYN) if w & s} or {"?" + l.lower()}
    return out
hist_ok = set()
for rom, h in hist.items():
    if rom in exact or rom not in mine or not h.get("names"):
        continue
    my = [mine[rom][k]["label"] for k in sorted(mine[rom], key=int)]
    if len(h["names"]) == len(my) and fnset(h["names"]) == fnset(my):
        hist_ok.add(rom); confirmed += 1

print(f"games with exact wire-matched names: {len(exact)} | label changes: {changed} | Arcade History confirms: {confirmed}")
for line in report:
    print("  " + line)

if APPLY:
    for r in rows:
        if r["system"] != "mame":
            continue
        if r["rom"] in exact and r["button"] in exact[r["rom"]] and r["source"] != "play-tested":
            r["label"], r["source"] = exact[r["rom"]][r["button"]], "mame-source"
        elif r["rom"] in hist_ok and r["button"].isdigit() and r["source"] == "knowledge":
            r["source"] = "arcade-history-confirmed"
    for rom, names in exact.items():   # buttons MAME names that we had no row for
        for num, label in names.items():
            if num not in mine.get(rom, {}):
                rows.append({"system": "mame", "rom": rom, "button": num, "label": label, "source": "mame-source"})
    rows.sort(key=lambda r: (r["system"], r["rom"], (0, int(r["button"])) if r["button"].isdigit() else (1, r["button"])))
    with open(CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["system", "rom", "button", "label", "source"])
        w.writeheader(); w.writerows(rows)
    print("data/community-labels.csv updated")
