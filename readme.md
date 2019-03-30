# BotW Shrine Rush

A BotW patch to add a Shrine Rush mode.

## Setup
* Download the [latest release](https://github.com/leoetlino/botw-shrine-rush/releases) for your platform (Switch or Wii U).
* Follow [*Using mods*](https://zeldamods.org/wiki/Help:Using_mods) (ZeldaMods wiki) to use the patch.

## Playing
Talk to the Goddess Statue in the Temple of Time to enter Shrine Rush.

When you enter, your inventory is temporarily replaced with a useful set of items: food (speed up, hearty, attack up, etc.), a bow, plenty of arrows, and an Ancient Shield.

The following elements are reset to ensure a consistent environment:

* Runes (the rune download terminals will give you the Lv2 variants, though)
* Shrine flags (for things like doors, treasure chests, clear status)
* Enemy scaling flags (for consistent drops regardless of game progression)

You are given 13 hearts and full stamina, again for consistency. Just like the TotS, you are not allowed to save at any point.

When you finish the run, you will be sent back to the title screen. Your save is totally untouched.

### Timed runs
For timed runs, it is recommended to enter Shrine Rush on a new save, as flags for things like item get and tutorial text windows could still make a difference as far as timing is concerned.

## Project information
### Structure
* `assets`: Game content files, with archives as directories. BYML and AAMP files may be stored in their human readable format.
* `build`: Build directory.
  * `assets_{platform}`: Intermediate patch for use with [botw-patcher](https://github.com/zeldamods/botwfstools).
  * `patch_{platform}`: Final patch ready to be distributed and used on console.
  * `botw_shrine_rush_{version}_{platform}.7z`: Final patch as a 7z archive.

### Tools
* `build_release.sh`: Run to make a release build.
* `build_dev.sh`: Run to make a development build (same as release but skips making the final archive).
* `generate_shrine_list.py`: Run to generate the Shrine Rush shrine list.

#### Building
Dependencies:

* Python 3.6+
* Python lib: yaml
* Python lib: aamp
* Python lib: byml-v2
* Python lib: evfl
* Python lib: wszst_yaz0
* botwfstools (botw-overlayfs, botw-contentfs, botw-patcher must be in PATH)

Paths:

* Switch content view must be mounted at `~/botw/switch-view`.
* Switch extracted romfs must be at `~/botw/romfs-1.5.0`.
* Wii U base content directory must be at `~/botw/wiiu-base`.
* Wii U update content directory must be at `~/botw/wiiu-upd`.

When making a dev build, an instance of botw-edit is expected to be running. botw-patcher will automatically be called after the intermediate patch is generated.

### Configuration
* `inventory_items.yml` is a list of items that should be added to the temporary inventory.
* `shrine_list.csv` is a list of all shrines in BotW.
* `shrine_rush_order.csv` is an ordered list of shrines that will be used for Shrine Rush.
