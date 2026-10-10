# Contributing button names

All per-game button names are in `data/community-labels.csv`:

| column | meaning |
|---|---|
| `system` | Batocera system folder (`mame`, `snes`, `megadrive`, `prboom` …) |
| `rom` | game file name without extension (`mk2`, `Super Mario World (USA)`) |
| `button` | the button as the **original hardware** names it: MAME `1`–`6`; SNES `B` `A` `Y` `X` `L` `R`; Mega Drive `A` `B` `C` `X` `Y` `Z`; PC Engine `I` `II`; ports use EmulationStation names `a` `b` `x` `y`. Special rows: `stick` and `note`. |
| `label` | what the button does in that game (`Low Punch`, `Jump`, `Smart Bomb`) |
| `source` | where the label comes from — see below |

**Sources, most trusted first** (when two rows disagree, the higher one wins):

1. `play-tested` — someone pressed the button in that game on a real cabinet.
2. `mame2003-plus-source` — from MAME 2003-Plus driver code (the core most Batocera arcade games run on).
3. `mame-source` — from current MAME driver `PORT_NAME`s, matched by hardware bit.
4. `arcade-history` — from the Arcade History database (names in original cabinet order).
5. `community` — reported by a user, not yet play-tested.
6. `knowledge` — best knowledge, unverified.

**To fix or add a game:** edit the CSV (one row per button), set `source` to `play-tested` if you tested it, and open a
pull request. Please mention the emulator/core you tested with — button *order* can differ between MAME versions.
