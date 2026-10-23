"""Private module configuration and an explicit player projection."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import yaml
from trpg.rules import DEFAULT_SKILLS, skill_default

PROFILE_FILE = Path(__file__).resolve().parents[2] / 'data/runtime/darkness-solo-mvp-v1.json'

class GameError(Exception):
    def __init__(self, code: str, message: str, status: int = 409):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


class Content:
    def __init__(self, catalogue):
        self.catalogue = catalogue
        self.profile = json.loads(PROFILE_FILE.read_text())
        self.fingerprint = digest(self.profile)
        self.events = {e['id']: e for e in self.profile['events']}
        publication = catalogue.publication(self.profile['moduleId'])
        self.root = catalogue.subroot('modules') / publication.directory
        self.manifest = yaml.safe_load((self.root / 'manifest.yaml').read_text())
        self.module_fingerprint = digest(self.manifest)
        index = yaml.safe_load((self.root / 'assets/index.yaml').read_text())
        self.assets = index['assets']

    def initialize(self, game_id, request_id, module_id, investigator_id):
        if module_id != self.profile['moduleId']:
            raise GameError('module_unavailable', '该模组尚未绑定可游玩配置。', 404)
        publication = self.catalogue.publication(module_id)
        if publication.runtimeProfile != self.profile['id']:
            raise GameError('module_unavailable', '该模组尚未发布可游玩配置。', 404)
        _, raw = self.catalogue.character(module_id, investigator_id)
        detail = self.catalogue.investigator(module_id, investigator_id).model_dump()
        attributes = detail['attributes']
        if any(v is None for v in attributes.values()):
            raise GameError('template_invalid', '人物基础属性不完整。', 503)
        resources = detail['resources']
        for key in ('hp', 'hpMax', 'san', 'mp', 'mpMax', 'luck'):
            if resources[key] is None:
                raise GameError('template_invalid', '人物资源不完整。', 503)
        known = {s['name']: s['value'] for s in detail['skills'] if s['value'] is not None}
        detail['skills'] = [{'name': k, 'value': known.get(k, skill_default(k, attributes)), 'highlighted': False}
                            for k in sorted(set(DEFAULT_SKILLS) | set(known))]
        inventory = []
        for n, item in enumerate(detail['equipment']):
            if item['kind'] != 'carried':
                continue
            key = next((key for word, key in [('手电', 'flashlight'), ('绳', 'rope'), ('撬棍', 'crowbar')] if word in item['name']), f'template_{n}')
            inventory.append({'id': key, **copy.deepcopy(item)})
        game = {'schemaVersion': 1, 'gameId': game_id, 'creation': {'requestId': request_id, 'moduleId': module_id, 'investigatorId': investigator_id},
                'profile': {'id': self.profile['id'], 'version': self.profile['version'], 'hash': self.fingerprint},
                'moduleVersion': self.manifest['content_version'], 'moduleHash': self.module_fingerprint,
                'templateVersion': raw['version'], 'templateHash': digest(raw), 'initialInvestigator': copy.deepcopy(detail),
                'investigator': detail, 'module': {'id': module_id, 'title': self.manifest['title']}, 'version': 1,
                'sceneId': 'winscott_house', 'visited': ['winscott_house'], 'flags': {'timeline': 'undecided'},
                'npcs': {'josh': {'stage': 'at_home', 'location': 'winscott_house', 'topics': []}},
                'inventory': inventory, 'facts': [], 'attempts': [], 'messages': [], 'turns': [], 'ending': None}
        game['messages'] = [
            {'id': 'opening', 'kind': 'keeper', 'speaker': '守秘人', 'text': self.profile['scenes']['winscott_house']['public']},
            {'id': 'josh-opening', 'kind': 'npc', 'speaker': '乔什·文斯考特', 'text': '地窖下面似乎藏着一条真正的旧隧道。我还没进去太远。你愿意陪我看看吗？我们现在出发，还是明天再来？'}]
        return game

    def validate(self, game):
        try:
            compatible = (game['schemaVersion'] == 1 and game['profile']['hash'] == self.fingerprint
                          and game['moduleHash'] == self.module_fingerprint)
            assert game['sceneId'] in self.profile['scenes']
            assert isinstance(game['turns'], list) and isinstance(game['messages'], list)
            assert isinstance(game['version'], int) and isinstance(game['investigator']['resources']['hp'], int)
        except (KeyError, TypeError, AssertionError):
            raise GameError('save_invalid', '游戏文件结构损坏；原文件已保留。', 503) from None
        if not compatible:
            raise GameError('version_incompatible', '游戏与当前运行配置版本不兼容；原文件已保留。', 409)

    def allowed_assets(self, game):
        result = {self.profile['scenes'][scene]['background'] for scene in game['visited']}
        result.add('sprite_josh_base')  # Met in the opening; this is an explicit profile grant.
        # Entering this profile's final room always reveals the figure, even
        # when that first SAN check immediately ends the game.
        if 'cage_area' in game['visited']:
            result.add('sprite_ssyaa_hrisss_base')
        return result

    def asset(self, game, asset_id):
        if asset_id not in self.allowed_assets(game):
            raise GameError('asset_unavailable', '素材尚不可见。', 404)
        asset = self.assets.get(asset_id, {})
        media = asset.get('media_type')
        path = (self.root / 'assets' / asset.get('file', '')).resolve()
        if media not in ('image/png', 'image/webp') or not path.is_relative_to((self.root / 'assets').resolve()) or not path.is_file():
            raise GameError('asset_invalid', '素材不可用。', 503)
        return path, media
