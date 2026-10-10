# Roadmap

- [x] Per-game cards for MAME (MAME 2003-Plus) on a 2-player, 6-button + coin/start cabinet
- [x] Browse / in-game / menu phases driven by EmulationStation events
- [x] Consoles and ports, auto-discovered from Batocera/RetroArch/evmapy config
- [x] Wizard that runs on the cabinet itself and detects the encoder automatically
- [x] Other layouts (any rows/columns) and keyboard encoders like I-PAC *(keyboard path tested by simulation only)*
- [x] Per-cabinet controls in panel.json; `playable.py` hides/un-hides games by required control
- [ ] **Trackball, spinner, wheel and yoke cabinets** — test on a real trackball cabinet; draw the extra controls on the cards
- [x] Cross-check labels against MAME (by hardware bit) and Arcade History (`tools/crosscheck_labels.py`)
- [ ] More verified button names (see CONTRIBUTING.md) - 616 rows still `knowledge`
- [ ] Newer Batocera versions (v39+ add a built-in "backglass" web view that could host the cards)
