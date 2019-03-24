#!/usr/bin/env python3
import argparse
import contextlib
import csv
import os
from pathlib import Path
import signal
import typing
import yaml

from builder import Builder, root
import byml
import evfl
from evfl.entry_point import EntryPoint
from evfl.common import IdGenerator, make_index, make_rindex
from generate_shrine_list import Shrine

class FlagToReset(typing.NamedTuple):
    name: str
    val: typing.Union[bool, int, float]

class ShrineRushBuilder(Builder):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._bfevfl_path = self.build_assets_dir/'Event'/'ShrineRush.sbeventpack'/'EventFlow'/'ShrineRush.bfevfl'
        self._evfl_id_generator = IdGenerator()
        self.flags_to_reset = self.generate_flags_to_reset()

    def _build_project(self) -> None:
        self._generate_event_next()
        self._generate_event_enter_reset_flag()
        self._generate_event_enter_edit_inventory()
        self._generate_gamedata_config()

    def generate_flags_to_reset(self) -> typing.List[FlagToReset]:
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

        for flag in self.gamedata_flags['bool']:
            name: str = flag['DataName']
            if name.startswith('CDungeon_'):
                l.append(FlagToReset(name=name, val=False))

        for flag in self.gamedata_flags['s32']:
            name = flag['DataName']
            if name.startswith('Defeated_'):
                l.append(FlagToReset(name=name, val=0))

        for i in range(136):
            l.append(FlagToReset(name='Open_Dungeon%03d' % i, val=True))
            l.append(FlagToReset(name='Enter_Dungeon%03d' % i, val=False))
            l.append(FlagToReset(name='Clear_Dungeon%03d' % i, val=False))
            for data_type in self.gamedata_flags:
                for flag in self.gamedata_flags[data_type]:
                    name = flag['DataName']
                    if name.startswith('Dungeon%03d' % i):
                        initial_val = flag['InitValue']
                        if data_type == 'bool':
                            initial_val = initial_val != 0
                        l.append(FlagToReset(name=name, val=initial_val))

        return l

    @contextlib.contextmanager
    def _get_main_event_flow(self) -> typing.Iterator[evfl.EventFlow]:
        event_flow = evfl.EventFlow()
        with self._bfevfl_path.open('rb') as f:
            event_flow.read(f.read())
        try:
            yield event_flow
        finally:
            with self._bfevfl_path.open('wb') as f:
                event_flow.write(f) # type: ignore

    def _generate_event_next(self) -> None:
        print('[ShrineRush] generating ShrineRush<Next>')
        with (root/'shrine_rush_order.csv').open('r') as f:
            shrines = [Shrine(row['map_name'], row['title'], row['sub']) for row in csv.DictReader(f)]

        with self._get_main_event_flow() as event_flow:
            flowchart = event_flow.flowchart
            assert flowchart

            EventSystemActor = flowchart.find_actor(evfl.ActorIdentifier('EventSystemActor'))
            ChangeScene = EventSystemActor.find_action('Demo_ChangeScene')
            CheckCurrentMap = EventSystemActor.find_query('CheckCurrentMap')
            FlagOFF = EventSystemActor.find_action('Demo_FlagOFF')

            def generate_chain(entry_name: str, shrines: typing.List[Shrine]):
                # generate events
                # CheckCurrentMap (current shrine)
                #   -> 1: Warp to next shrine
                #   -> 0: CheckCurrentMap (next shrine) etc.
                assert flowchart
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
                        flowchart.add_event(scene_evt, self._evfl_id_generator)
                        next_evt.data.nxt = make_index(scene_evt)
                        scene_evt.data = evfl.ActionEvent()
                        scene_evt.data.actor = make_rindex(EventSystemActor)
                        scene_evt.data.actor_action = make_rindex(ChangeScene)
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
                    e.data.actor = make_rindex(EventSystemActor)
                    e.data.actor_query = make_rindex(CheckCurrentMap)
                    e.data.params = evfl.Container()
                    e.data.params.data['MapName'] = shrine.map_name
                    e.data.cases[1] = make_rindex(next_evt)
                    if is_last:
                        e.data.cases[0] = make_rindex(next_evt)
                    flowchart.add_event(e, self._evfl_id_generator)
                    flowchart.add_event(next_evt, self._evfl_id_generator)
                    if previous_switch_evt:
                        previous_switch_evt.data.cases[0] = make_index(e)
                    previous_switch_evt = e

                    if i == 0:
                        first_event = e

                # add the entry point
                entry_point = EntryPoint(entry_name)
                assert first_event
                entry_point.main_event = make_rindex(first_event)
                flowchart.entry_points.append(entry_point)

            generate_chain('Next_All', shrines)
            generate_chain('Next_WithoutBlessings', [s for s in shrines if not s.sub.endswith(' Blessing')])
            generate_chain('Next_WithoutTestsOfStrength', [s for s in shrines if not s.sub.endswith(' Test of Strength')])
            generate_chain('Next_WithoutBlessingsOrTestsOfStrength', [s for s in shrines if not s.sub.endswith(' Test of Strength') and not s.sub.endswith(' Blessing')])

    def _generate_gamedata_config(self) -> None:
        print('[ShrineRush] generating GameData configuration')
        flags_to_reset_set: typing.Set[str] = set(f.name for f in self.flags_to_reset)
        gdt_dest_dir = self.build_assets_dir/'Pack'/'Bootup.pack'/'GameData'/'gamedata.ssarc'
        for bgdata_name, bgdata in self.gamedata_bgdata.items():
            is_edited = False
            for data_type_key, flags in bgdata.items():
                for flag in flags:
                    if flag['DataName'] in flags_to_reset_set:
                        flag['IsOneTrigger'] = False
                        is_edited = True
            if not is_edited:
                continue
            with (gdt_dest_dir/(bgdata_name)).open('wb') as f:
                writer = byml.Writer(bgdata, be=self.wiiu, version=2)
                writer.write(f) # type: ignore

    def _generate_event_enter_reset_flag(self) -> None:
        print('[ShrineRush] generating ShrineRush<Enter_ResetFlag>')
        with self._get_main_event_flow() as event_flow:
            flowchart = event_flow.flowchart
            assert flowchart

            EventSystemActor = flowchart.find_actor(evfl.ActorIdentifier('EventSystemActor'))
            FlagON = EventSystemActor.find_action('Demo_FlagON')
            FlagOFF = EventSystemActor.find_action('Demo_FlagOFF')
            SetGameDataInt = EventSystemActor.find_action('Demo_SetGameDataInt')
            SetGameDataFloat = EventSystemActor.find_action('Demo_SetGameDataFloat')

            events: typing.List[evfl.Event] = []
            for flag in self.flags_to_reset:
                evt = evfl.Event()
                evt.data = evfl.ActionEvent()
                evt.data.actor = make_rindex(EventSystemActor)
                evt.data.params = evfl.Container()
                if isinstance(flag.val, bool):
                    evt.data.actor_action = make_rindex(FlagON if flag.val else FlagOFF)
                    evt.data.params.data['IsWaitFinish'] = True
                    evt.data.params.data['FlagName'] = flag.name
                elif isinstance(flag.val, int):
                    evt.data.actor_action = make_rindex(SetGameDataInt)
                    evt.data.params.data['IsWaitFinish'] = True
                    evt.data.params.data['GameDataIntName'] = flag.name
                    evt.data.params.data['Value'] = flag.val
                elif isinstance(flag.val, float):
                    evt.data.actor_action = make_rindex(SetGameDataFloat)
                    evt.data.params.data['IsWaitFinish'] = True
                    evt.data.params.data['GameDataFloatName'] = flag.name
                    evt.data.params.data['Value'] = flag.val
                events.append(evt)

            flowchart.botw_add_action_chain_and_entry('Enter_ResetFlag', events, self._evfl_id_generator)

    def _generate_event_enter_edit_inventory(self) -> None:
        print('[ShrineRush] generating ShrineRush<Enter_EditInventory>')
        with self._get_main_event_flow() as event_flow:
            flowchart = event_flow.flowchart
            assert flowchart

            EventSystemActor = flowchart.find_actor(evfl.ActorIdentifier('EventSystemActor'))
            IncreasePorchItem = EventSystemActor.find_action('Demo_IncreasePorchItem')
            SetCookItem = EventSystemActor.find_action('Demo_SetCookItem')

            events: typing.List[evfl.Event] = []
            with (root/'inventory_items.yml').open('r') as f:
                inventory = yaml.load(f, Loader=yaml.CSafeLoader)
            for item in inventory['food']:
                evt = evfl.Event()
                evt.data = evfl.ActionEvent()
                evt.data.actor = make_rindex(EventSystemActor)
                evt.data.actor_action = make_rindex(SetCookItem)
                evt.data.params = evfl.Container()
                evt.data.params.data['IsWaitFinish'] = True
                evt.data.params.data['SetNum'] = item['num']
                for i in range(5):
                    evt.data.params.data['PorchItemName%02d' % (i+1)] = ''
                for i, ingredient in enumerate(item['ingredients'][:5]):
                    evt.data.params.data['PorchItemName%02d' % (i+1)] = ingredient
                events.append(evt)
            for item in inventory['items']:
                evt = evfl.Event()
                evt.data = evfl.ActionEvent()
                evt.data.actor = make_rindex(EventSystemActor)
                evt.data.actor_action = make_rindex(IncreasePorchItem)
                evt.data.params = evfl.Container()
                evt.data.params.data['IsWaitFinish'] = True
                evt.data.params.data['Value'] = item['num']
                evt.data.params.data['PorchItemName'] = item['name']
                events.append(evt)

            flowchart.botw_add_action_chain_and_entry('Enter_EditInventory', events, self._evfl_id_generator)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('-t', '--target', choices=['wiiu', 'switch'], help='Target platform', required=True)
    parser.add_argument('--gamedata-dir', help='Path to GameData archive directory', required=True)
    args = parser.parse_args()
    target = args.target
    wiiu = target == 'wiiu'
    gamedata_dir = Path(args.gamedata_dir)

    builder = ShrineRushBuilder(wiiu=wiiu, gamedata_dir=gamedata_dir, build_assets_dir=root/'build'/f'assets_{target}')
    builder.build()

    patcher_pid = os.environ.get('PATCHER_PID', None)
    if patcher_pid is not None:
        os.kill(int(patcher_pid), signal.SIGUSR1)

if __name__ == '__main__':
    main()
