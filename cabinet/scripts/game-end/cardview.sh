#!/bin/bash
# EmulationStation event: back from a game -> browse card of that game again
/userdata/system/cardview/bin/cardview-show --phase=browse "$@" &
