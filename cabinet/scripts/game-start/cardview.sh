#!/bin/bash
# EmulationStation event: a game is launching -> in-game card (play controls + exit/pause/save combos)
/userdata/system/cardview/bin/cardview-show --phase=game "$@" &
