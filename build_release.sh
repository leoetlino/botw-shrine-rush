#!/bin/bash

set -e

PATCH_DIR_SWITCH=build/patch_switch
PATCH_DIR_WIIU=build/patch_wiiu
ASSETS_DIR_SWITCH=build/assets_switch
ASSETS_DIR_WIIU=build/assets_wiiu

# Switch
rm -r $ASSETS_DIR_SWITCH
./build.py -t switch --gamedata-dir ~/botw/switch-view/Pack/Bootup.pack/GameData/gamedata.ssarc
botw-patcher -t switch ~/botw/romfs-1.5.0/ $ASSETS_DIR_SWITCH $PATCH_DIR_SWITCH

# Wii U
mkdir build/mnt-overlay || true
mkdir build/mnt-content || true
botw-overlayfs ~/botw/wiiu-base ~/botw/wiiu-upd build/mnt-overlay &
OVERLAYFS_PID=$!
botw-contentfs ~/botw/wiiu-base ~/botw/wiiu-upd build/mnt-content &
CONTENTFS_PID=$!

rm -r $ASSETS_DIR_WIIU
./build.py -t wiiu --gamedata-dir build/mnt-content/Pack/Bootup.pack/GameData/gamedata.ssarc
botw-patcher -t wiiu build/mnt-overlay $ASSETS_DIR_WIIU $PATCH_DIR_WIIU
cp $PATCH_DIR_WIIU/Pack/Bootup_EUen.pack $PATCH_DIR_WIIU/Pack/Bootup_USen.pack

kill $OVERLAYFS_PID
kill $CONTENTFS_PID

# Pack archives.
VERSION=$(git describe --tags --dirty --always --long --match '*')
rm build/botw_shrine_rush_*.7z || true
pushd $PATCH_DIR_WIIU
7z a ../botw_shrine_rush_${VERSION}_wiiu.7z .
popd
pushd $PATCH_DIR_SWITCH
7z a ../botw_shrine_rush_${VERSION}_switch.7z .
popd
