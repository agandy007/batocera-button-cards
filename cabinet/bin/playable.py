#!/usr/bin/python3
"""Hide MAME games this cabinet can't play, and un-hide the ones it can - based on its controls.

  python3 playable.py            # show what would change
  python3 playable.py --apply    # stop the menu, update gamelist.xml (backup kept), start the menu again

The cabinet's controls come from panel.json -> "controls" (default ["joystick"]); e.g. a trackball cabinet:
  "controls": ["joystick", "trackball"]
Each game's required control comes from MAME's own control list (mame2003plus-controls.json: the FIRST control is
the one the game is built around) plus a short list of overrides (control-overrides.json) for games that play fine
on a joystick anyway, or that MAME lists differently.
Only games whose required control the cabinet lacks are hidden; nothing is deleted.
"""
import json, os, re, shutil, subprocess, sys, time

BASE = os.environ.get("CARDVIEW_BASE", "/userdata/system/cardview")
GAMELIST = "/userdata/roms/mame/gamelist.xml"
KIND = {"joy": "joystick", "only_buttons": "joystick", "doublejoy": "twin-joystick", "dial": "spinner",
        "trackball": "trackball", "paddle": "wheel", "pedal": "wheel", "stick": "analog-stick",
        "positional": "periscope", "lightgun": "lightgun", "gambling": "joystick", "keyboard": "keyboard"}


def required(rom, controls, overrides):
    if rom in overrides:
        return overrides[rom]
    c = controls.get(rom, {}).get("controls") or [{"type": "joy"}]
    return KIND.get(c[0].get("type"), "joystick")


def main():
    apply = "--apply" in sys.argv
    panel = json.load(open(f"{BASE}/panel.json"))
    have = set(panel.get("controls") or ["joystick"])
    controls = json.load(open(f"{BASE}/mame2003plus-controls.json"))
    overrides = {k: v for k, v in json.load(open(f"{BASE}/control-overrides.json")).items() if not k.startswith("_")}
    text = open(GAMELIST, encoding="utf-8").read()
    hide, show = [], []

    def fix(m):
        block = m.group(0)
        path = re.search(r"<path>\./([^<]+)\.(zip|7z)</path>", block)
        if not path:
            return block
        rom = path.group(1)
        need = required(rom, controls, overrides)
        hidden = "<hidden>true</hidden>" in block
        if need not in have and not hidden:
            hide.append(f"{rom} ({need})")
            return block.replace("</game>", "\t<hidden>true</hidden>\n\t</game>")
        if need in have and hidden:
            show.append(f"{rom} ({need})")
            return re.sub(r"\s*<hidden>true</hidden>", "", block)
        return block

    new = re.sub(r"<game\b.*?</game>", fix, text, flags=re.S)
    print(f"cabinet controls: {', '.join(sorted(have))}")
    print(f"hide {len(hide)}: " + ", ".join(hide) if hide else "hide: none")
    print(f"show {len(show)}: " + ", ".join(show) if show else "show: none")
    if not apply or (not hide and not show):
        return
    shutil.copy2(GAMELIST, GAMELIST + f".before-playable-{time.strftime('%Y%m%d-%H%M%S')}")
    # EmulationStation rewrites gamelists when it exits, so edit only while it is stopped
    subprocess.run(["/etc/init.d/S31emulationstation", "stop"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(4)
    open(GAMELIST, "w", encoding="utf-8").write(new)
    subprocess.run(["/etc/init.d/S31emulationstation", "start"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("gamelist updated (backup kept next to it); menu restarted")


if __name__ == "__main__":
    main()
