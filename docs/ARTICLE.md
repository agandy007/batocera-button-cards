# A per-game button guide for your Batocera arcade cabinet — built with an LLM over SSH

Every arcade cabinet owner knows the moment: a friend walks up, picks a game, and asks *"what do the buttons do?"*.
This project puts the answer on a small second screen. While you browse the menu it shows how to launch the
highlighted game and drive the menu; the moment the game starts it switches to that game's controls — drawn in
**your** panel's real layout — plus the combos to exit, pause, save and load.

![browse card](images/browse-card.png)
![in-game card](images/game-card.png)

It was built on a real 2-player cabinet (Batocera v38, Intel N95 mini PC, two "zero delay" USB encoders, 2 rows of 3
buttons + coin/start per player) by the owner and an AI assistant working together over SSH. This write-up walks
through the whole thing so you can do the same — on your own layout and your own encoder, ideally with your own LLM
doing the SSH legwork. Everything is in the repo: <https://github.com/agandy007/batocera-button-cards>.

---

## 1. What you need

- **A Batocera cabinet** with SSH enabled (built and tested on v38, x86_64; see *Other Batocera versions* below).
- **A spare video output** on the cabinet PC (most mini PCs have two HDMI ports).
- **A small screen.** We used a 7" 1024×600 HDMI panel. Touch is not needed — if yours is a touch model, leave its
  touch USB cable unplugged (otherwise a tap on it acts as a mouse click on the main screen), and power it from a USB
  charger if that cable also carries power. *Many of these panels have a backlight switch — if it stays black, check it.*
  5" 800×480 panels work too (the cards scale; below ~4" the labels get too small).
- **A computer with SSH**, and optionally an LLM assistant that can run commands for you (Claude Code, etc.).

Nothing needs to be rewired and no extra controller board is needed. (If your buttons have LEDs, they keep doing
whatever they do now — lighting individual buttons per game needs an LED controller such as an Ultimarc PacLED64 and
LEDSpicer, which is out of scope here.)

## 2. Get SSH working (and safe)

1. In Batocera: **Main Menu → System Settings → Security** → enable SSH. The default root password is `linux`.
2. Find the cabinet's IP: **Main Menu → Network Settings**. Give it a **DHCP reservation** in your router so it keeps
   that address (our cabinets moved addresses after reboots until we did).
3. Use a key instead of the password — and **type the password yourself**; don't hand passwords to an LLM:
   ```bash
   ssh-copy-id root@<cabinet-ip>
   # Batocera's SSH server (Dropbear) ignores keys if the folder is too open:
   ssh root@<cabinet-ip> 'chmod go-w $HOME; chmod 700 $HOME/.ssh; chmod 600 $HOME/.ssh/authorized_keys'
   ```
4. Hostnames may not contain `_` — use `batocera-2player`, not `batocera_2player`.

**Working with an LLM over SSH — ground rules that saved us:**
- Read before changing; back up every file before editing it (all our edits left a `.orig`/`.before-…` copy).
- Never restart the menu (EmulationStation) or rebuild devices **while a game is running** — check first:
  `pgrep -f "emulatorlauncher -"`.
- Mute before launching test games from SSH, and export `XDG_RUNTIME_DIR=/run` — otherwise audio bypasses the mute.
- Never `pkill -f` a pattern that also appears in your own SSH command line (it kills your session).
- Don't run standalone MAME with `-video none` to "just read something": Batocera's build switches the display mode.
- Ask before anything public or irreversible; let the human press the buttons and confirm what the screen shows.

## 3. Connect the second screen (and three Batocera v38 surprises)

Plug the small screen into the free HDMI port. Then:

1. **Batocera may move the menu onto the new screen** and switch the main monitor off. Pin the main screen:
   ```bash
   batocera-settings-set global.videooutput HDMI-1        # your main output; list them with: DISPLAY=:0 xrandr
   ```
2. **v38 assumes a single screen when sizing games.** `batocera-resolution currentResolution` returns the *last*
   active output — the small screen — so games get laid out at 1024×600 in the corner of the main monitor. Fix: make it
   use the first (main) output, then persist the change:
   ```bash
   cp -p /usr/bin/batocera-resolution /userdata/system/batocera-resolution.orig
   sed -i -e 's#CURRENT_RESOLUTION=$(xrandr --currentResolution)#CURRENT_RESOLUTION=$(xrandr --currentResolution | head -n1)#' \
          -e "s#xrandr --currentResolution | tail -n1#xrandr --currentResolution | head -n1#" /usr/bin/batocera-resolution
   batocera-save-overlay
   batocera-settings-set global.retroarch.video_monitor_index 1
   ```
   (Also add `| head -n1` after `grep -E '\*$'` in the `CURRENTRATE=` line.) A Batocera update replaces this file —
   re-apply afterwards.
3. Restarting the menu restarts the display server and switches the second screen off again — the viewer notices and
   turns it back on by itself (see *How it works*).

## 4. Get the scripts onto the cabinet

```bash
git clone https://github.com/agandy007/batocera-button-cards.git
cd batocera-button-cards
python3 tools/build_gamedb.py                       # data/community-labels.csv -> cabinet/gamedb.json
scp -r . root@<cabinet-ip>:/userdata/system/batocera-button-cards
```

## 5. Teach it your panel — the wizard

Physical button positions can't be detected; the encoder only reports "button 5 pressed". So you press each button
once and the wizard records which code each position sends. Run it **on the cabinet** (stand at player 1's controls):

```bash
ssh -t root@<cabinet-ip> python3 /userdata/system/batocera-button-cards/cabinet/bin/wizard.py \
    --out /userdata/system/cardview/panel.json
```

Press, slowly, row by row from the top, left to right, then the small buttons above (coin/start). Options:

| option | for |
|---|---|
| `--rows 4,4` | 8-button panels (2 rows of 4); `--rows 3,3,2` etc. for anything else |
| `--above 2` | number of small buttons above the rows (0 if none) |
| `--controls joystick,trackball` | what else the cabinet has (trackball, spinner, wheel …) |
| `--compare` | run at player 2's controls: reports any wiring difference instead of saving |

The wizard records whichever device you press first, so it works with joystick-type encoders (DragonRise "zero delay",
Xin-Mo, …) and keyboard-type encoders (I-PAC, …) alike. It also finds the second screen.

On our cabinet, player 2's six buttons matched player 1 exactly; only coin and start were swapped. Both encoders share
one configuration in Batocera (same USB ID), so a per-player swap isn't possible in software — swap two wires, or live
with it.

## 6. Check your encoder configuration (we found a real bug here)

```bash
ssh root@<cabinet-ip> python3 /userdata/system/batocera-button-cards/cabinet/bin/cardgen.py --report
```
prints, per panel position: the menu function, the RetroArch button and the hotkeys. **Every position should show up.**
Ours had `l: None, r: None`: the encoder had **two** EmulationStation configs with the same ID — the menu used the
complete one, games used one *without* page-up/page-down, so the top-right and bottom-right buttons did nothing in
every game. Adding the two missing `<input>` lines to the second `<inputConfig>` in
`/userdata/system/configs/emulationstation/es_input.cfg` (with the menu stopped: `/etc/init.d/S31emulationstation stop`)
fixed six-button games. RetroArch picks up the change at the next game launch.

## 7. Install

```bash
ssh root@<cabinet-ip> /userdata/system/batocera-button-cards/cabinet/install.sh
```

This copies the scripts to `/userdata/system/cardview`, renders a browse card and an in-game card for every game on
every system (276 games took about 70 seconds on an Intel N95), installs EmulationStation event hooks and enables the
`cardview` service. Everything lives in `/userdata` — it survives reboots and Batocera updates.
`cabinet/uninstall.sh` removes it all.

## 8. Hide the games your cabinet can't play

```bash
ssh root@<cabinet-ip> python3 /userdata/system/cardview/bin/playable.py          # preview
ssh root@<cabinet-ip> python3 /userdata/system/cardview/bin/playable.py --apply  # do it (gamelist backup kept)
```

Games built around a wheel, flight yoke, twin joysticks, spinner, trackball or periscope are **hidden** (not deleted)
unless your panel lists that control. Add `trackball` to `controls` in `panel.json` and run it again — the trackball
games come back.

## 9. How it works

```
EmulationStation event          card shown                         made from
-----------------------------   --------------------------------   ------------------------------------------
system-selected                 "How to use the menu"              es_input.cfg (menu functions per position)
game-selected (highlighted)     browse card: screenshot, facts,     + gamelist.xml (name, year, players, image)
                                "PRESS ● TO PLAY", menu buttons
game-start                      in-game card: controls + combos     retroarchcustom.cfg (RetroPad + hotkeys),
                                                                    profiles.json (per core), gamedb.json (per game)
game-end (no game in args!)     browse card of the last game        remembered in /var/run/cardview.last
```

- **cardgen.py** draws the PNGs with Pillow on the cabinet itself. Every cabinet-specific detail is *discovered*:
  `panel.json` gives position → key code; `es_input.cfg` gives the menu's mapping; `retroarchcustom.cfg` gives
  RetroArch's (joystick indexes are translated to codes through the same ES config; keyboard encoders use SDL keycodes
  in ES and key names / built-in defaults in RetroArch); `/usr/share/evmapy/<system>.keys` gives the hotkeys of ports
  that don't run in RetroArch; Batocera's configgen defaults say which core each system uses.
- **profiles.json** is the only hand-written mapping: per emulator core, which RetroPad button is which button on the
  original hardware (SNES `B/A/Y/X/L/R`, Mega Drive `A/B/C`, PC Engine `I/II`, MAME `1`–`6`).
- **cardview service** runs `mpv` full-screen on the second output and listens on a socket.
- **cardview-show** is called by the hooks. Things we learned the hard way: `game-start` passes the ROM path
  *shell-escaped and split on spaces* (`Super\ Mario\ World\ \(USA\).sfc`); `game-end` passes nothing; fast scrolling
  fires overlapping events (a sequence number makes the newest win); and after a menu/X restart the second screen is
  off — it then restarts the viewer in the background.
- mpv on Batocera v38 is built without its on-screen controller, so `--no-osc` makes it exit; and don't use
  `--ontop`: if the second screen is ever switched off, the window lands on top of the main menu.

## 10. Where the button names come from — and how much to trust them

`data/community-labels.csv` holds one row per game and button with a **source**:

| source | meaning | rows today |
|---|---|---|
| `play-tested` | pressed on a real cabinet | 12 |
| `mame-source` | MAME driver `PORT_NAME`, matched to MAME 2003-Plus **by hardware bit** | 40 |
| `arcade-history-confirmed` | our label agrees with the Arcade History database | 53 |
| `knowledge` | best knowledge, unverified | 616 |

Lessons:
- Most Batocera arcade games run on **MAME 2003-Plus** (core `mame078plus`), whose drivers mostly don't name buttons.
- Current MAME names thousands of buttons — but **numbers them differently** for some games (Mortal Kombat II's
  button 2 is *Block* in MAME and *Low Kick* in MAME 2003-Plus). Matching by the PCB wire (port + bit mask) instead of
  by number gives exact names for the core you actually run: `tools/crosscheck_labels.py`.
- Arcade History lists buttons in the original cabinet's order, which isn't always MAME's — use it to confirm, not
  to reorder.
- A quick play test settles it. Our first mapping assumption (Batocera's MAME layout) turned out correct only after
  testing two games (Punch-Out!! and NBA Jam) — trust tests over theory.

Please contribute corrections — see `CONTRIBUTING.md`.

## 11. Troubleshooting we actually hit

| symptom | cause / fix |
|---|---|
| 7" screen black | backlight switch on the panel; or power through its USB cable (use a charger, not the PC) |
| menu appears on the small screen, main screen dark | `global.videooutput=<main output>`; restart the menu |
| games squeezed into the top-left corner | v38 single-screen resolution check — section 3 |
| card covers the main menu | viewer window moved after the 2nd output was toggled — `--ontop` removed; restart service |
| card shows the wrong game | scrolling fast; fixed by the sequence check — re-enter the game list |
| no in-game card for console games | escaped paths in `game-start` — fixed in `cardview-show` |
| top-right/bottom-right dead in games | duplicate ES encoder config without page-up/page-down — section 6 |
| cabinet not on the network after reboot | Wi-Fi came up and went down at boot; `cabinet/extras/wifiwatchdog` |
| coin/start confused | the menu and RetroArch can number the two small buttons differently — the cards read both |

## 12. Adapting it

- **Other layouts:** run the wizard with `--rows`. The cards lay out any grid.
- **Keyboard encoders (I-PAC etc.):** supported by the wizard and card generator; check `cardgen.py --report`.
- **Xin-Mo and other 2-player-in-one boards:** press player 1's buttons in the wizard; it records the right codes.
- **Other systems / cores:** add an entry to `data/profiles.json` (RetroPad → native button names) and labels to the CSV.
- **Other Batocera versions:** v39+ include a built-in "backglass" web view on the second screen that could display
  the same cards; the resolution fix in section 3 may not be needed there.
- **Trackball / spinner / wheel cabinets:** next on the roadmap — panel `controls` already drive which games are shown.

## Credits

Built by the cabinet's owner with Claude (Anthropic) over SSH. Button research uses MAME and MAME 2003-Plus source
code and the Arcade History database as references. MIT licensed.
