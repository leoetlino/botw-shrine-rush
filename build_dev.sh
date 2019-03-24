#!/bin/sh

set -e

rm -r build/assets_wiiu || true
env PATCHER_PID=$(pgrep botw-edit) ./build.py -t wiiu --gamedata-dir ~/botw/wiiu-view/Pack/Bootup.pack/GameData/gamedata.ssarc/

rm -r build/assets_switch || true
./build.py -t switch --gamedata-dir ~/botw/switch-view/Pack/Bootup.pack/GameData/gamedata.ssarc
botw-patcher -t switch ~/botw/romfs-1.5.0/ build/assets_switch/ build/patch_switch
