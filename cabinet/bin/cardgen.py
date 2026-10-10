#!/usr/bin/python3
"""cardgen (v2) - draw per-game button cards for EVERY system on a Batocera cabinet. Pillow only.

  cardgen.py [--system NAME] [--only rom1,rom2] [--out DIR] [--report]

Everything cabinet-specific is DISCOVERED, not hand-entered:
  panel.json            physical position -> evdev code (from the press wizard)
  es_input.cfg          EmulationStation: ES input name -> evdev code          (menu functions)
  retroarchcustom.cfg   RetroArch: RetroPad button / hotkey -> joystick index   (in-game buttons + hotkeys)
  /usr/share/evmapy     key-mapper files for non-RetroArch ports               (port hotkeys)
  configgen defaults    which emulator/core each system uses
Curated data (shipped with the kit):
  profiles.json         per core: RetroPad -> button name on the original hardware
  gamedb.json           per game: native button -> what it does ("1": "Fire", "B": "Jump")
Writes: <out>/<system>/<rom>.png (in game), <out>/<system>/<rom>.browse.png (in menu), <out>/_default.png
"""
import argparse, glob, json, os, re, textwrap
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont

BASE = os.environ.get("CARDVIEW_BASE", "/userdata/system/cardview")
ES_INPUT = "/userdata/system/configs/emulationstation/es_input.cfg"
RA_CFG = "/userdata/system/configs/retroarch/retroarchcustom.cfg"
BATO_CONF = "/userdata/system/batocera.conf"
DEFAULTS = ["/usr/share/batocera/configgen/configgen-defaults.yml", "/usr/share/batocera/configgen/configgen-defaults-arch.yml"]
EVMAPY = "/usr/share/evmapy"
FONT_B = "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"
FONT_C = "/usr/share/fonts/dejavu/DejaVuSansCondensed-Bold.ttf"
BG, PANEL, DIM, DIMRING, YELLOW, CYAN, GREY = (11, 11, 16), (22, 22, 31), (30, 30, 38), (48, 48, 58), (255, 210, 63), (127, 224, 255), (170, 170, 170)
PADS = ["b", "a", "y", "x", "l", "r", "select", "start"]
SKIP_SYSTEMS = {"imageviewer", "kodi", "flatpak", "steam"}


# ---------------------------------------------------------------- discovery
def es_config(hint):
    """(ES input name -> evdev code, joystick index -> evdev code) for the first ES config matching `hint`."""
    names, ids = {}, {}
    if os.path.exists(ES_INPUT):
        for cfg in ET.parse(ES_INPUT).getroot().findall("inputConfig"):
            if hint.lower() in (cfg.get("deviceName") or "").lower():
                for i in cfg.findall("input"):
                    if i.get("type") == "button" and i.get("code"):
                        names.setdefault(i.get("name"), int(i.get("code")))
                        ids[int(i.get("id"))] = int(i.get("code"))
                break
    return names, ids


def ra_settings():
    out = {}
    if os.path.exists(RA_CFG):
        for line in open(RA_CFG, errors="replace"):
            m = re.match(r'\s*([a-z0-9_]+)\s*=\s*"?([^"\n]*)"?', line)
            if m:
                out[m.group(1)] = m.group(2).strip()
    return out


def system_cores():
    """system -> {emulator, core} from configgen defaults + batocera.conf overrides."""
    import yaml
    res = {}
    for p in DEFAULTS:
        if os.path.exists(p):
            for k, v in (yaml.safe_load(open(p)) or {}).items():
                if isinstance(v, dict):
                    res.setdefault(k, {}).update({x: v[x] for x in ("emulator", "core") if v.get(x)})
    if os.path.exists(BATO_CONF):
        for line in open(BATO_CONF, errors="replace"):
            m = re.match(r"^([a-z0-9_]+)\.(emulator|core)=(.+)$", line.strip())
            if m:
                res.setdefault(m.group(1), {})[m.group(2)] = m.group(3)
    return res


def evmapy_hotkeys(system, es_pos, targets):
    """Hotkey combos from /usr/share/evmapy/<system>.keys -> [(position or name, label)], or None if no file."""
    p = f"{EVMAPY}/{system}.keys"
    if not os.path.exists(p):
        return None
    items = []
    for a in json.load(open(p)).get("actions_player1", []):
        trig = a.get("trigger")
        if not isinstance(trig, list) or "hotkey" not in trig:
            continue
        other = [t for t in trig if t != "hotkey"][0]
        tgt = a.get("target")
        key = "+".join(tgt) if isinstance(tgt, list) else ("killall" if "killall" in str(tgt) else str(tgt))
        label = targets.get(key)
        if label:
            items.append((es_pos.get(other) or other.upper(), label))
    return items


# ---------------------------------------------------------------- drawing helpers
def font(path, size):
    return ImageFont.truetype(path, max(8, int(size)))


def hexrgb(h):
    h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def fit(d, text, path, size, max_w, min_size=9):
    while size > min_size and d.textlength(text, font=font(path, size)) > max_w:
        size -= 0.5
    return font(path, size)


def clean_name(n):
    n = re.sub(r"\s*\((rev|revision|set|version|ver|world|us|usa|euro|europe|japan|bootleg|unl|aetherbyte|tsone|shiru)[^)]*\)", "", n or "", flags=re.I)
    return re.sub(r"\s*\([^)]*\b(set|rev|ver)\b[^)]*\)", "", n).strip()


def draw_button(d, cx, cy, r, color, face, used, s):
    d.ellipse([cx - r - 6 * s, cy - r - 6 * s, cx + r + 6 * s, cy + r + 6 * s], fill=(68, 68, 78) if used else DIMRING)
    d.ellipse([cx - r - 3 * s, cy - r - 3 * s, cx + r + 3 * s, cy + r + 3 * s], fill=(17, 17, 17))
    if used:
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
        d.chord([cx - r, cy - r, cx + r, cy + r], 20, 160, fill=tuple(max(0, c - 55) for c in color))
        d.ellipse([cx - r * 0.86, cy - r * 0.9, cx + r * 0.86, cy + r * 0.7], fill=color)
        if face:
            d.text((cx, cy - r * 0.08), str(face), font=fit(d, str(face), FONT_B, r * 0.62, r * 1.5, 8),
                   fill=tuple(int(c * 0.45) for c in color), anchor="mm")
    else:
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=DIM)


def header(d, W, s, title, meta=""):
    hh = int(60 * s)
    d.rectangle([0, 0, W, hh], fill=PANEL)
    d.rectangle([0, hh, W, hh + int(3 * s)], fill=(40, 40, 52))
    mf = font(FONT_B, 20 * s)
    mw = d.textlength(meta, font=mf) if meta else 0
    d.text((24 * s, hh / 2), title, font=fit(d, title, FONT_B, 30 * s, W - mw - 60 * s, 16), fill="white", anchor="lm")
    if meta:
        d.text((W - 24 * s, hh / 2), meta, font=mf, fill=GREY, anchor="rm")
    return hh


def panel(d, pnl, x0, x1, top, s, labels, faces, above_names, r_max=33, label_size=19):
    """Draw the control panel. labels/faces: position -> text."""
    rows = pnl["rows"]
    cols = max(len(r) for r in rows)
    colw = (x1 - x0) / cols
    centers = [x0 + colw * (i + 0.5) for i in range(cols)]
    r = int(min(r_max * s, colw * 0.21))
    pill_w, pill_h = 112 * s, 30 * s
    ax = [centers[0] + colw * 0.5, centers[-1] - colw * 0.5] if cols >= 2 else centers
    for x, name in zip(ax, above_names):
        if not name:
            continue
        d.rounded_rectangle([x - pill_w / 2, top, x + pill_w / 2, top + pill_h], radius=pill_h / 2, fill=(58, 58, 70), outline=(120, 120, 130), width=max(1, int(2 * s)))
        d.text((x, top + pill_h / 2), name, font=fit(d, name, FONT_B, 15 * s, pill_w - 10 * s), fill="white", anchor="mm")
    y = top + pill_h + 10 * s + r
    for row in rows:
        for i, pos in enumerate(row):
            used = pos in labels
            draw_button(d, centers[i], y, r, hexrgb(pnl["colors"].get(pos, "#cccccc")), faces.get(pos, ""), used, s)
            if used:
                for li, line in enumerate(textwrap.wrap(labels[pos], width=16)[:2]):
                    d.text((centers[i], y + r + 8 * s + li * label_size * s * 1.08), line,
                           font=fit(d, line, FONT_C, label_size * s, colw - 10 * s, 10), fill="white", anchor="ma")
        y += r * 2 + 40 * s


def strip(d, pnl, W, s, y, title, items):
    """One-line combo strip; items: [(position-or-text, label)]; text shrinks to fit."""
    fs = 15.0
    while True:
        tf, itf, pf = font(FONT_B, fs * s), font(FONT_C, fs * s), font(FONT_B, (fs - 3) * s)
        need = 30 * s + d.textlength(title, font=tf) + 18 * s
        for ref, label in items:
            need += (28 * s if ref in pnl["colors"] else d.textlength(str(ref), font=pf) + 20 * s) + d.textlength(label, font=itf) + 20 * s
        if need <= W - 30 * s or fs <= 10:
            break
        fs -= 0.5
    d.rounded_rectangle([16 * s, y, W - 16 * s, y + 42 * s], radius=10 * s, fill=PANEL)
    cy, x = y + 21 * s, 30 * s
    d.text((x, cy), title, font=tf, fill=YELLOW, anchor="lm")
    x += d.textlength(title, font=tf) + 18 * s
    for ref, label in items:
        if ref in pnl["colors"]:
            d.ellipse([x, cy - 11 * s, x + 22 * s, cy + 11 * s], fill=hexrgb(pnl["colors"][ref]), outline=(17, 17, 17), width=max(1, int(2 * s)))
            x += 28 * s
        else:
            pw = d.textlength(str(ref), font=pf) + 14 * s
            d.rounded_rectangle([x, cy - 11 * s, x + pw, cy + 11 * s], radius=11 * s, fill=(58, 58, 70), outline=(120, 120, 130))
            d.text((x + pw / 2, cy), str(ref), font=pf, fill="white", anchor="mm")
            x += pw + 6 * s
        d.text((x, cy), label, font=itf, fill="white", anchor="lm")
        x += d.textlength(label, font=itf) + 20 * s


def footer(d, W, H, s, text):
    if text:
        d.text((W / 2, H - 18 * s), text, font=fit(d, text, FONT_C, 18 * s, W - 40 * s, 10), fill=CYAN, anchor="mm")


# ---------------------------------------------------------------- cards
def game_card(ctx, g):
    W, H = ctx["size"]; s = min(W / 800, H / 480)
    img = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(img)
    meta = "  ·  ".join(x for x in [g["year"], (g["players"] + "P") if g["players"] else ""] if x)
    hh = header(d, W, s, g["title"], meta)
    above = [g["faces"].get(p, "") for p in ctx["panel"]["above"]]
    panel(d, ctx["panel"], 20 * s, W - 20 * s, hh + 12 * s, s, g["labels"], g["faces"], above)
    if g["hotkeys"]:
        # small buttons have no colour dot: show their name (START, COIN...) instead of the position id
        items = [(ref if ref in ctx["panel"]["colors"] else (g["faces"].get(ref) or g.get("above_names", {}).get(ref) or ref), label)
                 for ref, label in g["hotkeys"]]
        strip(d, ctx["panel"], W, s, H - 88 * s, f"IN GAME  hold {g['hotkey_name']} +", items)
    note = g["note"]
    if "made for" in note.lower():
        foot = note
    else:
        foot = "  ·  ".join(x for x in [g["stick"].upper(), note or g["menu_note"]] if x)
    footer(d, W, H, s, foot)
    return img


def browse_card(ctx, g, art):
    W, H = ctx["size"]; s = min(W / 800, H / 480)
    img = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(img)
    hh = header(d, W, s, g["title"])
    lw = int(W * 0.40)
    box = (int(20 * s), int(hh + 18 * s), lw - int(10 * s), int(H - 120 * s))
    if art and os.path.exists(art):
        try:
            sh = Image.open(art).convert("RGB"); sh.thumbnail((box[2] - box[0], box[3] - box[1]))
            ox = box[0] + (box[2] - box[0] - sh.width) // 2; oy = box[1] + (box[3] - box[1] - sh.height) // 2
            d.rectangle([ox - 3, oy - 3, ox + sh.width + 2, oy + sh.height + 2], fill="white"); img.paste(sh, (ox, oy))
        except OSError:
            pass
    nb = len(g["labels"])
    facts = [x for x in [g["year"], (g["players"] + " players") if g["players"] else "", g["system_label"],
                         (f"{nb} button{'s' if nb != 1 else ''}" if nb else "joystick only"), g["stick"]] if x]
    fy = H - 108 * s
    for i in range(0, len(facts), 2):
        line = "  ·  ".join(facts[i:i + 2])
        d.text(((box[0] + box[2]) / 2, fy), line, font=fit(d, line, FONT_C, 18 * s, lw - 30 * s, 10), fill=GREY, anchor="ma")
        fy += 26 * s
    rx0, rw = lw + 10 * s, W - lw - 30 * s
    d.rounded_rectangle([rx0, hh + 16 * s, rx0 + rw, hh + 62 * s], radius=10 * s, fill=(33, 52, 33))
    bf = font(FONT_B, 20 * s); txt = "PRESS        TO PLAY"; tx = rx0 + rw / 2
    d.text((tx, hh + 39 * s), txt, font=bf, fill="white", anchor="mm")
    launch = ctx["menu_pos"].get("b")
    if launch:
        dx = tx - d.textlength(txt, font=bf) / 2 + d.textlength("PRESS   ", font=bf) + 11 * s
        d.ellipse([dx - 11 * s, hh + 28 * s, dx + 11 * s, hh + 50 * s], fill=hexrgb(ctx["panel"]["colors"].get(launch, "#e53935")),
                  outline=(17, 17, 17), width=max(1, int(2 * s)))
    above = [ctx["menu_labels"].get(p, "") for p in ctx["panel"]["above"]]
    mlabels = {p: v for p, v in ctx["menu_labels"].items() if p not in ctx["panel"]["above"]}
    panel(d, ctx["panel"], rx0, rx0 + rw, hh + 78 * s, s, mlabels, {}, above, r_max=27, label_size=16)
    footer(d, W, H, s, "Joystick: move through the list  ·  Hold the launch button for game options")
    return img


def menu_card(ctx):
    W, H = ctx["size"]; s = min(W / 800, H / 480)
    img = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(img)
    hh = header(d, W, s, "How to use the menu")
    above = [ctx["menu_labels"].get(p, "") for p in ctx["panel"]["above"]]
    mlabels = {p: v for p, v in ctx["menu_labels"].items() if p not in ctx["panel"]["above"]}
    panel(d, ctx["panel"], 20 * s, W - 20 * s, hh + 12 * s, s, mlabels, {}, above)
    footer(d, W, H, s, "Joystick: move  ·  pick a system, then a game, and launch it")
    return img


# ---------------------------------------------------------------- main
def load_gamelist(system):
    """Visible games whose file exists: rom name (file name without extension) -> gamelist fields."""
    out = {}
    p = f"/userdata/roms/{system}/gamelist.xml"
    if os.path.exists(p):
        for g in ET.parse(p).getroot().findall("game"):
            path = g.findtext("path") or ""
            rom = os.path.splitext(os.path.basename(path))[0]
            if not rom or g.findtext("hidden") == "true" or not os.path.exists(os.path.join(f"/userdata/roms/{system}", path)):
                continue
            out[rom] = {k: g.findtext(k) for k in ("name", "players", "releasedate", "image")}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--system", default="")
    ap.add_argument("--only", default="")
    ap.add_argument("--out", default=f"{BASE}/cards")
    ap.add_argument("--report", action="store_true", help="print discovered mappings only")
    a = ap.parse_args()

    pnl = json.load(open(f"{BASE}/panel.json"))
    prof = json.load(open(f"{BASE}/profiles.json"))
    db = json.load(open(f"{BASE}/gamedb.json"))
    size = (pnl["screen"]["width"], pnl["screen"]["height"])
    pos_of = {code: pos for pos, code in pnl["codes"].items()}

    # menu (EmulationStation) functions -> positions
    es_names, es_ids = es_config(pnl.get("device_hint", ""))
    es_pos = {name: pos_of[c] for name, c in es_names.items() if c in pos_of}
    menu_labels = {}
    for name, label in prof["es_functions"].items():
        p = es_pos.get(name)
        if not name.startswith("_") and p and p not in menu_labels:
            menu_labels[p] = label
    menu_pos = {name: es_pos.get(name) for name in ("b", "a")}

    # RetroArch RetroPad buttons + hotkeys -> positions (RetroArch joystick index -> evdev code via the ES id table)
    ra = ra_settings()
    def ra_pos(key):
        v = ra.get(key, "")
        return pos_of.get(es_ids.get(int(v))) if v.lstrip("-").isdigit() else None
    ra_pad_pos = {pad: ra_pos(f"input_player1_{pad}_btn") for pad in PADS}
    for pad, es_name in (("l", "pageup"), ("r", "pagedown")):   # RetroArch file not refreshed yet: same codes as the menu config
        ra_pad_pos[pad] = ra_pad_pos[pad] or es_pos.get(es_name)
    ra_hot = [(p, label) for k, label in prof["retroarch_hotkeys"].items() if (p := ra_pos(f"input_{k}_btn"))]
    swap = ra.get("menu_swap_ok_cancel_buttons") == "true"
    pause_note = "Pause menu: joystick = move, " + ", ".join(
        f"{p.replace('-', ' ')} = {t}" for p, t in [(ra_pad_pos.get("b"), "OK" if swap else "back"), (ra_pad_pos.get("a"), "back" if swap else "OK")] if p)

    if a.report:
        print("menu functions   :", menu_labels)
        print("retroarch pads   :", ra_pad_pos)
        print("retroarch hotkeys:", ra_hot, "| hotkey button:", ra_pos("input_enable_hotkey_btn"))
        return

    cores = system_cores()
    ctx = {"panel": pnl, "size": size, "menu_labels": menu_labels, "menu_pos": menu_pos}
    systems = [a.system] if a.system else sorted(os.path.basename(os.path.dirname(p)) for p in glob.glob("/userdata/roms/*/gamelist.xml"))
    total, missing = 0, []
    for system in systems:
        if system in SKIP_SYSTEMS:
            continue
        gl = load_gamelist(system)
        if not gl:
            continue
        emu = cores.get(system, {})
        core = emu.get("core", "")
        cp = prof["cores"].get(core) if emu.get("emulator") == "libretro" else None
        evh = evmapy_hotkeys(system, es_pos, prof["evmapy_targets"])
        os.makedirs(f"{a.out}/{system}", exist_ok=True)
        roms = [x for x in a.only.split(",") if x] or sorted(gl)
        n = 0
        for rom in roms:
            if rom not in gl:
                continue
            e, g = db.get(f"{system}/{rom}", {}), gl[rom]
            faces, labels, game_above = {}, {}, {}
            if cp:   # RetroArch core: RetroPad -> position (RetroArch config) -> native name (core profile)
                for pad, native in cp["buttons"].items():
                    p = ra_pad_pos.get(pad)
                    if p:
                        faces[p] = native
                        if e.get("labels", {}).get(native):
                            labels[p] = e["labels"][native]
                for i in range(1, int(e.get("mame_buttons") or 0) + 1):   # arcade buttons nobody labelled yet
                    p = next((pp for pp, nat in faces.items() if nat == str(i)), None)
                    if p and p not in labels:
                        labels[p] = f"Button {i}"
                hot, hot_name, note2 = ra_hot, cp["buttons"].get("select", "SELECT"), pause_note
            else:    # port / standalone emulator: labels keyed by ES input names
                for name, lab in e.get("labels", {}).items():
                    p = es_pos.get(name)
                    if p:
                        labels[p] = lab
                        faces[p] = name.upper() if len(name) <= 2 else ""
                hot, hot_name, note2 = (evh or []), "SELECT", ""
                game_above = {es_pos[nm]: nm.upper() for nm in ("start", "select") if es_pos.get(nm)}
            game = {"title": clean_name(g.get("name") or rom), "year": (g.get("releasedate") or "")[:4], "players": g.get("players") or "",
                    "labels": labels, "faces": faces, "stick": e.get("stick", ""), "note": e.get("note", ""),
                    "hotkeys": hot, "hotkey_name": hot_name, "above_names": game_above, "system_label": (cp or {}).get("label", ""), "menu_note": note2}
            game_card(ctx, game).save(f"{a.out}/{system}/{rom}.png", optimize=True)
            art = g.get("image") or ""
            if art.startswith("./"):
                art = f"/userdata/roms/{system}/" + art[2:]
            browse_card(ctx, game, art).save(f"{a.out}/{system}/{rom}.browse.png", optimize=True)
            n += 1
            if not e:
                missing.append(f"{system}/{rom}")
        total += n
        kind = "profile" if cp else ("keymap" if evh is not None else "none")
        print(f"{system:14s} {emu.get('emulator', '?'):12s} {core:14s} {kind:8s} {n} cards")
    menu_card(ctx).save(f"{a.out}/_default.png")
    print(f"rendered {total} games at {size[0]}x{size[1]}")
    if missing:
        print("no label data:", ", ".join(missing))


if __name__ == "__main__":
    main()
