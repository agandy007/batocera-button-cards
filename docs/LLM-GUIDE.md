# Briefing for an AI assistant

*Give this file to your LLM (Claude Code, etc.) along with your cabinet's IP address. It describes the goal, the
rules, and a step-by-step procedure, including every pitfall the original build ran into.*

## Goal

Install **batocera-button-cards** on the user's Batocera cabinet: a second screen that shows how to use the menu while
browsing and each game's controls (in the cabinet's real button layout) while playing. Repo:
<https://github.com/agandy007/batocera-button-cards>. Read `docs/ARTICLE.md` for background.

## Rules

1. **You run commands over SSH; the human handles anything physical** (pressing buttons, plugging cables, looking at
   screens) and anything involving passwords. Never ask for, type or store a password; have the user run
   `ssh-copy-id` themselves.
2. **Read before you change.** Back up every file you edit (`cp -p file file.orig`) and keep a running log of changes
   (we used `/userdata/system/claude-admin/README.txt` on the cabinet).
3. **Check for a running game before** restarting EmulationStation, rebooting, rebuilding input devices or editing
   files ES rewrites (`gamelist.xml`, `es_input.cfg`, `es_settings.cfg`):
   `pgrep -f "emulatorlauncher -"` must return nothing. Edit those files only while ES is stopped:
   `/etc/init.d/S31emulationstation stop` … edit … `start`.
4. **Changes under `/usr` are lost on reboot** unless saved with `batocera-save-overlay`, and lost again on a Batocera
   update. Prefer `/userdata`. Tell the user which changes an update would undo.
5. **Don't launch games or emulators "to look at something"** without asking. If you must, mute first
   (`XDG_RUNTIME_DIR=/run batocera-audio setSystemVolume mute`) and export `XDG_RUNTIME_DIR=/run` for the launch;
   never run standalone MAME with `-video none` (it changes the display mode).
6. **Never `pkill -f` a pattern that also appears in your own command line** — you'll kill your SSH session.
7. Recording button presses: start the recording **in the background**, then tell the user to press. Messages reach
   them only after your tool call returns, so a foreground recording finishes before they see "go".
8. **Ask before anything public or irreversible** (publishing, deleting ROMs, overwriting someone else's file).
9. Don't guess button meanings the user will rely on — use the sources in `data/` and say what is unverified.

## Procedure

### 0. Connect
```bash
ssh -o BatchMode=yes root@<ip> 'hostname; cat /usr/share/batocera/batocera.version; uname -m'
```
If key login fails on a fresh cabinet: user runs `ssh-copy-id root@<ip>` (password `linux` by default), then
`ssh root@<ip> 'chmod go-w $HOME; chmod 700 $HOME/.ssh; chmod 600 $HOME/.ssh/authorized_keys'` (Dropbear is strict).

### 1. Survey (read-only)
```bash
lsusb; grep -E "^N:" /proc/bus/input/devices          # encoders: DragonRise/Xin-Mo = joystick, I-PAC = keyboard
DISPLAY=:0 xrandr | grep connected                     # main screen + the small one
grep -c "<game" /userdata/roms/*/gamelist.xml          # what systems have games
python3 -c "import evdev, PIL; print('ok')"            # both ship with Batocera
```

### 2. Second screen
- Pin the main output: `batocera-settings-set global.videooutput <MAIN>`.
- **v38 only:** check `batocera-resolution currentResolution` — if it prints the *small* screen's size, apply the
  `head -n1` fix from ARTICLE §3 and `batocera-save-overlay`, plus `global.retroarch.video_monitor_index=1`.
  Verify with a game launch: the picture must fill the main screen.

### 3. Copy and record the panel
```bash
python3 tools/build_gamedb.py
scp -r . root@<ip>:/userdata/system/batocera-button-cards
# background recording, then tell the user: "press player 1's buttons once each, row by row, top first, left to right,
# then the small buttons above"
ssh root@<ip> 'python3 /userdata/system/batocera-button-cards/cabinet/bin/wizard.py --rows 3,3 --above 2 \
   --controls joystick --timeout 120 --out /userdata/system/cardview/panel.json'
```
Ask the user for their layout first (`--rows`, `--above`) and any extra controls (`--controls joystick,trackball`).
For player 2 use `--compare`.

### 4. Verify discovery
```bash
CARDVIEW_BASE=/userdata/system/cardview python3 .../cabinet/bin/cardgen.py --report
```
(after install; before install point `CARDVIEW_BASE` at a temp dir with `panel.json`, `gamedb.json`,
`data/profiles.json`). Every position should appear in *menu functions* and *retroarch pads*.
- `l: None` / `r: None` → look for duplicate `<inputConfig>` entries for the encoder in `es_input.cfg`; the one
  without `pageup`/`pagedown` is what games use. Add the missing lines (ES stopped).
- Keyboard encoders: RetroArch's built-in keyboard defaults are assumed when `retroarchcustom.cfg` doesn't override them.

### 5. Install, then let the user test the three phases
```bash
ssh root@<ip> /userdata/system/batocera-button-cards/cabinet/install.sh
ssh root@<ip> python3 /userdata/system/cardview/bin/playable.py           # preview hiding of unplayable games
```
Ask the user to: browse to a system (menu card), highlight a game (browse card), launch it (in-game card), exit with
the shown combo (browse card again). Capture the small screen to check yourself:
`DISPLAY=:0 ffmpeg -loglevel error -y -f x11grab -video_size <WxH> -i :0.0+<x>,0 -frames:v 1 /tmp/s.png`.

### 6. Verify labels the cheap way
Pick 2–3 games with several buttons; ask the user what each physical button does and compare with the card. Record
results in `data/community-labels.csv` with source `play-tested`. If a whole *mapping* is off (not just one game),
fix `data/profiles.json` for that core rather than individual games.

### 7. Reboot test
Reboot (no game running), wait, then check: both screens active at the right sizes, `pgrep -f mpv.*cardview`, menu
running, and the network. If Wi-Fi sometimes doesn't come back, install `cabinet/extras/wifiwatchdog`.

## Known pitfalls (all hit on the original build)

- The menu (EmulationStation) and RetroArch can number the small coin/start buttons differently; the cards read both
  configs, don't "fix" one to match the other.
- `game-start` passes shell-escaped, space-split ROM paths; `game-end` passes nothing. `cardview-show` handles both.
- After an ES/X restart, the second output is off; `cardview-show` restarts the viewer. Don't toggle the output with
  `xrandr --off/--auto` yourself while the viewer runs — its window jumps onto the main screen.
- mpv on v38: no `--no-osc` (exits), no `--ontop`.
- Panels with a backlight switch look "dead" when it's off.
- Batocera seller images may run their own boot services that overwrite files in `/usr` — check
  `/userdata/system/services` before patching anything there.
