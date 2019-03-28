import abc
from collections import defaultdict
import contextlib
from pathlib import Path
import shutil
import typing
import yaml

import aamp
import aamp.yaml_util
import byml
import byml.yaml_util
import evfl
from evfl.common import RequiredIndex, Index
import wszst_yaz0

root = Path(__file__).parent
assets_dir = root / 'assets'

class Builder(metaclass=abc.ABCMeta):
    def __init__(self, wiiu: bool, gamedata_dir: Path, build_assets_dir: Path):
        self.wiiu = wiiu
        self.gamedata_dir = gamedata_dir
        self.build_assets_dir = build_assets_dir
        self._load_gamedata_flags()

    def build(self) -> None:
        self._copy_assets()
        self._copy_language_packs()
        self._prepare_platform_specific_resources()

        self._build_project()

        self._generate_byml()
        self._generate_aamp()
        self._compress_assets()

    @abc.abstractmethod
    def _build_project(self) -> None:
        pass

    def _load_gamedata_flags(self) -> None:
        print('loading GameData flags')
        self.gamedata_bgdata: typing.Dict[str, dict] = dict()
        self.gamedata_flags: typing.DefaultDict[str, list] = defaultdict(list)
        for bgdata_path in self.gamedata_dir.glob('*.bgdata'):
            with bgdata_path.open('rb') as f:
                bgdata = byml.Byml(f.read()).parse()
                assert isinstance(bgdata, dict)
                self.gamedata_bgdata[bgdata_path.name] = bgdata
            for data_type_key, flags in bgdata.items():
                data_type = data_type_key[:-5]
                self.gamedata_flags[data_type] += flags
        if not self.gamedata_flags:
            raise Exception(f'No bgdata was found in {self.gamedata_dir}')

    def _copy_assets(self) -> None:
        print('copying assets')
        self.build_assets_dir.parent.mkdir(exist_ok=True)
        if self.build_assets_dir.is_dir():
            raise ValueError(f'{self.build_assets_dir} already exists')
        shutil.copytree(assets_dir, self.build_assets_dir, symlinks=True)

    def _copy_language_packs(self) -> None:
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
        if self.wiiu:
            return
        print('copying messages')
        source_lang_file_dir = self.build_assets_dir/'Pack'/'Bootup_EUen.pack'/'Message'/'Msg_EUen.product.ssarc'
        for lang in LANGUAGES:
            lang_message_dir = self.build_assets_dir/'Pack'/f'Bootup_{lang}.pack'/'Message'
            lang_message_dir.mkdir(parents=True)
            shutil.copytree(source_lang_file_dir, lang_message_dir/f'Msg_{lang}.product.ssarc', symlinks=True)

    def _prepare_platform_specific_resources(self) -> None:
        if not self.wiiu:
            print('preparing Switch specific resources')
            for path in self.build_assets_dir.glob('**/*.nx'):
                path.rename(str(path)[:-3])

    def _generate_byml(self) -> None:
        print('generating BYMLs')
        byml.yaml_util.add_constructors(yaml.CSafeLoader)
        for path in self.build_assets_dir.glob('**/*.yml'):
            with path.open('r') as f:
                data = yaml.load(f, Loader=yaml.CSafeLoader)
            writer = byml.Writer(data, be=self.wiiu, version=2)
            with Path(str(path)[:-4]).open('wb') as f:
                writer.write(f) # type: ignore
            path.unlink()

    def _generate_aamp(self) -> None:
        print('generating AAMPs')
        aamp.yaml_util.register_constructors(yaml.CSafeLoader)
        for path in self.build_assets_dir.glob('**/*.aampyml'):
            with path.open('r') as f:
                data = yaml.load(f, Loader=yaml.CSafeLoader)
            writer = aamp.Writer(data)
            with Path(str(path)[:-8]).open('wb') as f:
                writer.write(f) # type: ignore
            path.unlink()

    def _compress_assets(self) -> None:
        print('compressing assets')
        for path in self.build_assets_dir.glob('**/*.s*'):
            if path.is_dir():
                continue
            tmp_path = path.with_suffix('.tmp')
            path.rename(tmp_path)
            with tmp_path.open('rb') as srcf, path.open('wb') as destf:
                destf.write(wszst_yaz0.compress(srcf.read()))
            tmp_path.unlink()
