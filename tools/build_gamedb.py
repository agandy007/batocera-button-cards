#!/usr/bin/env python3
"""Build cabinet/gamedb.json from data/community-labels.csv (+ MAME button counts).

  python3 tools/build_gamedb.py            -> writes cabinet/gamedb.json

community-labels.csv columns: system, rom, button, label, source
  button = the NATIVE button name for that system ("1".."6" for MAME, "B"/"Y" for SNES, "I"/"II" for PC Engine,
           ES input names "a"/"b" for ports), or the special rows "stick" and "note".
  source = where the label comes from. When the same button appears twice, the more trusted source wins:
           play-tested > mame2003-plus-source > mame-source > arcade-history > community > knowledge
"""
import csv, json, os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RANK = ["knowledge", "community", "arcade-history", "mame-source", "mame2003-plus-listxml", "mame2003-plus-source", "play-tested"]
counts = json.load(open(os.path.join(HERE, "data", "mame2003plus-controls.json")))
db, rank = {}, {}
for row in csv.DictReader(open(os.path.join(HERE, "data", "community-labels.csv"), newline="", encoding="utf-8")):
    key = f"{row['system']}/{row['rom']}"
    e = db.setdefault(key, {"labels": {}})
    r = RANK.index(row["source"]) if row["source"] in RANK else 0
    slot = (key, row["button"])
    if r < rank.get(slot, -1):
        continue
    rank[slot] = r
    if row["button"] in ("stick", "note"):
        e[row["button"]] = row["label"]
    else:
        e["labels"][row["button"]] = row["label"]
for key, e in db.items():
    system, rom = key.split("/", 1)
    m = counts.get(rom) if system == "mame" else None
    if m:
        e["mame_buttons"] = max([int(c.get("buttons") or 0) for c in m["controls"]] or [0])
    e["sources"] = sorted({s for (k, b), s in ((sl, RANK[rk]) for sl, rk in rank.items()) if k == key})
os.makedirs(os.path.join(HERE, "cabinet"), exist_ok=True)
json.dump(db, open(os.path.join(HERE, "cabinet", "gamedb.json"), "w"), indent=0, ensure_ascii=False, sort_keys=True)
print(f"gamedb.json: {len(db)} games")
