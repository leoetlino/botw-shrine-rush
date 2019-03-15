#!/usr/bin/env python3
import argparse
import aamp
import aamp.yaml_util
import byml
import byml.yaml_util
from collections import defaultdict
import csv
import evfl
from evfl.common import RequiredIndex
from evfl.entry_point import EntryPoint
import os
from pathlib import Path
import shutil
import signal
import typing
import yaml
import wszst_yaz0
from generate_shrine_list import Shrine

parser = argparse.ArgumentParser()
parser.add_argument('-t', '--target', choices=['wiiu', 'switch'], help='Target platform', required=True)
parser.add_argument('--gamedata-dir', help='Path to GameData archive directory', required=True)
args = parser.parse_args()
target = args.target
wiiu = target == 'wiiu'
gamedata_dir = Path(args.gamedata_dir)

root = Path(__file__).parent
assets_dir = root / 'assets'
build_dir = root / 'build'
build_assets_dir = build_dir / ('assets_' + target)

print('loading GameData flags')
def load_gamedata_flags() -> typing.Tuple[typing.Dict[str, dict], typing.Dict[str, list]]:
    all_bgdata: typing.Dict[str, dict] = dict()
    all_flags: typing.DefaultDict[str, list] = defaultdict(list)
    for bgdata_path in gamedata_dir.glob('*.bgdata'):
        with bgdata_path.open('rb') as f:
            bgdata: typing.Dict[str, typing.Any] = byml.Byml(f.read()).parse()
            all_bgdata[bgdata_path.name] = bgdata
        for data_type_key, flags in bgdata.items():
            data_type = data_type_key[:-5]
            all_flags[data_type] += flags
    return (all_bgdata, all_flags)
gamedata_bgdata_list, gamedata_flags = load_gamedata_flags()

print('copying assets')
build_dir.mkdir(exist_ok=True)
if build_assets_dir.is_dir():
    shutil.rmtree(build_assets_dir)
shutil.copytree(assets_dir, build_assets_dir, symlinks=True)

LANGUAGES = (
    'CNzh',
    'EUde',
    #'EUen' (Source language)
    'EUes',
    'EUfr',
    'EUit',
    'EUnl',
    'EUru',
    'JPja',
    'KRko',
    'TWzh',
    'USen',
    'USes',
    'USfr',
)
if not wiiu:
    print('copying messages')
    source_lang_file_dir = build_assets_dir/'Pack'/'Bootup_EUen.pack'/'Message'/'Msg_EUen.product.ssarc'
    for lang in LANGUAGES:
        lang_message_dir = build_assets_dir/'Pack'/f'Bootup_{lang}.pack'/'Message'
        lang_message_dir.mkdir(parents=True)
        shutil.copytree(source_lang_file_dir, lang_message_dir/f'Msg_{lang}.product.ssarc', symlinks=True)

if not wiiu:
    print('preparing Switch specific resources')
    for path in build_assets_dir.glob('**/*.nx'):
        path.rename(str(path)[:-3])

bfevfl_path = build_assets_dir/'Event'/'ShrineRush.sbeventpack'/'EventFlow'/'ShrineRush.bfevfl'
class IdGenerator:
    def __init__(self):
        self._id = 0
    def gen_id(self):
        r = self._id
        self._id += 1
        return r
evfl_id_generator = IdGenerator()
# These should probably be added to evfl.util to make manipulating event flows easier...
def evfl_make_index(v):
    idx = RequiredIndex()
    idx.v = v
    return idx
def evfl_add_event(flowchart, event):
    event.name = 'AutoEvent%d' % evfl_id_generator.gen_id()
    flowchart.events.append(event)
def evfl_find_actor(flowchart, identifier: evfl.ActorIdentifier) -> evfl.Actor:
    for actor in flowchart.actors:
        if actor.identifier == identifier:
            return actor
    raise ValueError(identifier)
def evfl_find_actor_action_or_query(l: list, name: str):
    for x in l:
        if x.v == name:
            return x
    raise ValueError(name)

print('[ShrineRush] generating ShrineRush<Next>')
def shrinerush_generate_next():
    with (root/'shrine_rush_order.csv').open('r') as f:
        shrines = [Shrine(row['map_name'], row['title'], row['sub']) for row in csv.DictReader(f)]

    event_flow = evfl.EventFlow()
    with bfevfl_path.open('rb') as f:
        event_flow.read(f.read())

    flowchart = event_flow.flowchart

    EventSystemActor = evfl_find_actor(flowchart, evfl.ActorIdentifier('EventSystemActor'))
    ChangeScene = evfl_find_actor_action_or_query(EventSystemActor.actions, 'Demo_ChangeScene')
    CheckCurrentMap = evfl_find_actor_action_or_query(EventSystemActor.queries, 'CheckCurrentMap')
    FlagOFF = evfl_find_actor_action_or_query(EventSystemActor.actions, 'Demo_FlagOFF')

    # generate events
    # CheckCurrentMap (current shrine)
    #   -> 1: Warp to next shrine
    #   -> 0: CheckCurrentMap (next shrine) etc.
    first_event = None
    previous_switch_evt = None
    for i in range(len(shrines)):
        shrine = shrines[i]
        is_last = i == len(shrines) - 1

        next_evt = evfl.Event()
        if is_last:
            next_evt.data = evfl.SubFlowEvent()
            next_evt.data.entry_point_name = 'Exit'
        else:
            # Clear the IsInside_Dungeon flag to ensure the dungeon entrance demo works correctly
            # (otherwise the entrance elevator actor gets signalled too early).
            next_evt.data = evfl.SubFlowEvent()
            next_evt.data.entry_point_name = 'Next_BeforeSceneChange'
            scene_evt = evfl.Event()
            evfl_add_event(flowchart, scene_evt)
            next_evt.data.nxt = evfl_make_index(scene_evt)
            scene_evt.data = evfl.ActionEvent()
            scene_evt.data.actor = evfl_make_index(EventSystemActor)
            scene_evt.data.actor_action = evfl_make_index(ChangeScene)
            scene_evt.data.params = evfl.Container()
            scene_evt.data.params.data['IsWaitFinish'] = True
            scene_evt.data.params.data['WarpDestMapName'] = 'CDungeon/' + shrines[i+1].map_name
            scene_evt.data.params.data['WarpDestPosName'] = 'Entrance_1'
            scene_evt.data.params.data['FadeType'] = 2
            scene_evt.data.params.data['StartType'] = 0
            scene_evt.data.params.data['EvflName'] = 'Demo008_2'
            scene_evt.data.params.data['EntryPointName'] = 'Demo008_2'

        e = evfl.Event()
        e.data = evfl.SwitchEvent()
        e.data.actor = evfl_make_index(EventSystemActor)
        e.data.actor_query = evfl_make_index(CheckCurrentMap)
        e.data.params = evfl.Container()
        e.data.params.data['MapName'] = shrine.map_name
        e.data.cases[1] = evfl_make_index(next_evt)
        if is_last:
            e.data.cases[0] = evfl_make_index(next_evt)
        evfl_add_event(flowchart, e)
        evfl_add_event(flowchart, next_evt)
        if previous_switch_evt:
            previous_switch_evt.data.cases[0] = evfl_make_index(e)
        previous_switch_evt = e

        if i == 0:
            first_event = e

    # add the entry point
    entry_point = EntryPoint('Next')
    entry_point.main_event = RequiredIndex()
    entry_point.main_event.v = first_event
    flowchart.entry_points.append(entry_point)

    with bfevfl_path.open('wb') as f:
        event_flow.write(f)
shrinerush_generate_next()

class FlagToReset(typing.NamedTuple):
    name: str
    val: typing.Union[bool, int, float]

def shrinerush_generate_flags_to_reset() -> typing.List[FlagToReset]:
    l = []

    l.append(FlagToReset(name='IsGet_Obj_IceMaker', val=False))
    l.append(FlagToReset(name='IsGet_Obj_Magnetglove', val=False))
    l.append(FlagToReset(name='IsGet_Obj_RemoteBomb', val=False))
    l.append(FlagToReset(name='IsGet_Obj_RemoteBombLv2', val=True))
    l.append(FlagToReset(name='IsGet_Obj_StopTimer', val=False))
    l.append(FlagToReset(name='IsGet_Obj_StopTimerLv2', val=True))
    l.append(FlagToReset(name='CurrentHart', val=52))
    l.append(FlagToReset(name='MaxHartValue', val=52))
    l.append(FlagToReset(name='StaminaCurrentMax', val=3000.0))
    l.append(FlagToReset(name='StaminaMax', val=3000.0))

    for flag in gamedata_flags['bool']:
        name: str = flag['DataName']
        if name.startswith('CDungeon_'):
            l.append(FlagToReset(name=name, val=False))

    for flag in gamedata_flags['s32']:
        name = flag['DataName']
        if name.startswith('Defeated_'):
            l.append(FlagToReset(name=name, val=0))

    for i in range(136):
        l.append(FlagToReset(name='Open_Dungeon%03d' % i, val=True))
        l.append(FlagToReset(name='Enter_Dungeon%03d' % i, val=False))
        l.append(FlagToReset(name='Clear_Dungeon%03d' % i, val=False))
        for data_type in gamedata_flags:
            for flag in gamedata_flags[data_type]:
                name = flag['DataName']
                if name.startswith('Dungeon%03d' % i):
                    initial_val = flag['InitValue']
                    if data_type == 'bool':
                        initial_val = initial_val != 0
                    l.append(FlagToReset(name=name, val=initial_val))

    return l

print('[ShrineRush] generating flags to reset')
flags_to_reset = shrinerush_generate_flags_to_reset()

print('[ShrineRush] generating GameData configuration')
def shrinerush_generate_gamedata_config():
    flags_to_reset_set: typing.Set[str] = set(f.name for f in flags_to_reset)
    gdt_dest_dir = build_assets_dir/'Pack'/'Bootup.pack'/'GameData'/'gamedata.ssarc'
    for bgdata_name, bgdata in gamedata_bgdata_list.items():
        is_edited = False
        for data_type_key, flags in bgdata.items():
            for flag in flags:
                if flag['DataName'] in flags_to_reset_set:
                    flag['IsOneTrigger'] = False
                    is_edited = True
        if not is_edited:
            continue
        with (gdt_dest_dir/(bgdata_name)).open('wb') as f:
            writer = byml.Writer(bgdata, be=wiiu, version=2)
            writer.write(f)
shrinerush_generate_gamedata_config()

print('[ShrineRush] generating ShrineRush<Enter_ResetFlag>')
def shrinerush_generate_flag_reset_event():
    event_flow = evfl.EventFlow()
    with bfevfl_path.open('rb') as f:
        event_flow.read(f.read())

    flowchart = event_flow.flowchart

    EventSystemActor = evfl_find_actor(flowchart, evfl.ActorIdentifier('EventSystemActor'))
    FlagON = evfl_find_actor_action_or_query(EventSystemActor.actions, 'Demo_FlagON')
    FlagOFF = evfl_find_actor_action_or_query(EventSystemActor.actions, 'Demo_FlagOFF')
    WaitFrame = evfl_find_actor_action_or_query(EventSystemActor.actions, 'Demo_WaitFrame')
    SetGameDataInt = evfl_find_actor_action_or_query(EventSystemActor.actions, 'Demo_SetGameDataInt')
    SetGameDataFloat = evfl_find_actor_action_or_query(EventSystemActor.actions, 'Demo_SetGameDataFloat')

    first_evt = None
    previous_evt = None
    for i, flag in enumerate(flags_to_reset):
        evt = evfl.Event()
        evt.data = evfl.ActionEvent()
        evt.data.actor = evfl_make_index(EventSystemActor)
        evt.data.params = evfl.Container()
        if isinstance(flag.val, bool):
            evt.data.actor_action = evfl_make_index(FlagON if flag.val else FlagOFF)
            evt.data.params.data['IsWaitFinish'] = True
            evt.data.params.data['FlagName'] = flag.name
        elif isinstance(flag.val, int):
            evt.data.actor_action = evfl_make_index(SetGameDataInt)
            evt.data.params.data['IsWaitFinish'] = True
            evt.data.params.data['GameDataIntName'] = flag.name
            evt.data.params.data['Value'] = flag.val
        elif isinstance(flag.val, float):
            evt.data.actor_action = evfl_make_index(SetGameDataFloat)
            evt.data.params.data['IsWaitFinish'] = True
            evt.data.params.data['GameDataFloatName'] = flag.name
            evt.data.params.data['Value'] = flag.val

        evfl_add_event(flowchart, evt)
        if previous_evt:
            previous_evt.data.nxt = evfl_make_index(evt)
        previous_evt = evt
        if i == 0:
            first_evt = evt

        if i != 0 and i % 10 == 0:
            # Give the event system a chance to clean up event action contexts.
            wait_evt = evfl.Event()
            wait_evt.data = evfl.ActionEvent()
            wait_evt.data.actor = evfl_make_index(EventSystemActor)
            wait_evt.data.actor_action = evfl_make_index(WaitFrame)
            wait_evt.data.params = evfl.Container()
            wait_evt.data.params.data['IsWaitFinish'] = True
            wait_evt.data.params.data['Frame'] = 1
            evfl_add_event(flowchart, wait_evt)
            if previous_evt:
                previous_evt.data.nxt = evfl_make_index(wait_evt)
            previous_evt = wait_evt

    # add the entry point
    entry_point = EntryPoint('Enter_ResetFlag')
    entry_point.main_event = evfl_make_index(first_evt)
    flowchart.entry_points.append(entry_point)

    with bfevfl_path.open('wb') as f:
        event_flow.write(f)
shrinerush_generate_flag_reset_event()

print('generating BYMLs')
byml.yaml_util.add_constructors(yaml.CSafeLoader)
for path in build_assets_dir.glob('**/*.yml'):
    with path.open('r') as f:
        data = yaml.load(f, Loader=yaml.CSafeLoader)
    writer = byml.Writer(data, be=wiiu, version=2)
    with Path(str(path)[:-4]).open('wb') as f:
        writer.write(f)
    path.unlink()

print('generating AAMPs')
aamp.yaml_util.register_constructors(yaml.CSafeLoader)
for path in build_assets_dir.glob('**/*.aampyml'):
    with path.open('r') as f:
        data = yaml.load(f, Loader=yaml.CSafeLoader)
    writer = aamp.Writer(data)
    with Path(str(path)[:-8]).open('wb') as f:
        writer.write(f)
    path.unlink()

# compress files
print('compressing assets')
for path in build_assets_dir.glob('**/*.s*'):
    if path.is_dir():
        continue
    tmp_path = path.with_suffix('.tmp')
    path.rename(tmp_path)
    with tmp_path.open('rb') as srcf, path.open('wb') as destf:
        destf.write(wszst_yaz0.compress(srcf.read()))
    tmp_path.unlink()

# trigger patcher
patcher_pid = os.environ.get('PATCHER_PID', None)
if patcher_pid is not None:
    os.kill(int(patcher_pid), signal.SIGUSR1)
