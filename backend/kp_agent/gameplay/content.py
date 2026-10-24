"""Explicit module/profile registry, private content and versioned game snapshots."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import yaml
from pydantic import ValidationError
from trpg.rules import DEFAULT_SKILLS, skill_default
from .conditions import matches
from .schema import RuntimeProfile, entity_affordances
from .common_actions import initial_mechanics, validate_mechanics

class GameError(Exception):
    def __init__(self, code: str, message: str, status: int = 409):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def private_file(root, relative):
    path = Path(relative)
    resolved = (root / path).resolve()
    if path.is_absolute() or '..' in path.parts or not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
        raise ValueError('Invalid content path')
    return resolved


def read_json(root, relative):
    path = private_file(root, relative)
    if path.stat().st_size > 1_000_000: raise ValueError('Content file too large')
    return json.loads(path.read_text(encoding='utf-8'))


def attempt_key(affordance, call):
    if affordance['repeat'] == 'method':
        challenge = affordance['challenge']
        method = 'item:' + call['item'] if call.get('item') else 'skill:' + (call.get('skill') or challenge['skills'][0])
        return affordance['id'] + ':' + method
    return affordance['id']


class ModuleContent:
    def __init__(self, catalogue, publication, entry, source=None):
        runtime_root = catalogue.subroot('runtime')
        source = source or entry['current']
        raw = read_json(runtime_root, source)
        self.profile = RuntimeProfile.model_validate(raw).model_dump(exclude_none=True)
        self.fingerprint = digest(raw)
        if source != entry['current']:
            retained = next((r for r in entry.get('retained', []) if r['source'] == source), None)
            if retained is None or retained['hash'] != self.fingerprint: raise ValueError('Retained profile changed')
        if self.profile['moduleId'] != publication.id or self.profile['id'] != publication.runtimeProfile or entry['id'] != publication.runtimeProfile:
            raise ValueError('Module/profile binding mismatch')
        self.affordances = self.profile['affordances'] + entity_affordances(self.profile)
        self.root = private_file(catalogue.subroot('modules'), f'{publication.directory}/manifest.yaml').parent
        self.manifest = yaml.safe_load((self.root / 'manifest.yaml').read_text(encoding='utf-8'))
        if self.manifest['id'] != publication.manifestId: raise ValueError('Manifest mismatch')
        self.module_fingerprint = digest(self.manifest)
        index = yaml.safe_load(private_file(self.root, self.manifest['files']['assets']).read_text(encoding='utf-8'))
        if index['path_base'] != 'assets/': raise ValueError('Unsupported asset base')
        self.assets = index['assets']
        required = {s['background'] for s in self.profile['scenes'].values()} | {n['sprite'] for n in self.profile['npcs'].values()} | {g['asset'] for g in self.profile['assetGrants']}
        for asset_id in required:
            asset = self.assets[asset_id]
            if asset['media_type'] not in ('image/png', 'image/webp'): raise ValueError('Unsupported asset')
            private_file(self.root / 'assets', asset['file'])
        self.compatible = []
        for compatible in entry.get('compatible', []):
            if compatible['targetHash'] != self.fingerprint: continue
            source = read_json(runtime_root, compatible['source'])
            if compatible['schemaVersion'] != 1 or source['id'] != self.profile['id'] or source['moduleId'] != publication.id:
                raise ValueError('Invalid migration source')
            if not set(e['id'] for e in source['events']).issubset(self.profile['legacyActions']): raise ValueError('Missing action migration')
            self.compatible.append((digest(source), source))

    def visible_npcs(self, game):
        return {key: npc for key, npc in self.profile['npcs'].items()
                if game['npcs'][key]['location'] == game['sceneId'] and matches(game, npc['visibleWhen'])}

    def entities(self, game):
        return {key: {**entity, 'public': entity['public'] + ''.join(c['text'] for c in entity['clauses'] if matches(game, c['when']))}
                for key, entity in self.profile['entities'].items()
                if game['sceneId'] in entity['scenes'] and matches(game, entity['requires'])}

    def knowledge(self, game):
        return [{'id': key, 'name': npc['name'], 'public': npc['public'],
                 'knowledge': [clause['text'] for clause in npc['knowledge'] if matches(game, clause['when'])]}
                for key, npc in self.visible_npcs(game).items()]

    def migrate(self, game):
        if game.get('schemaVersion') == 1:
            source = next((source for fingerprint, source in self.compatible if game.get('profile') == {'id': source['id'], 'version': source['version'], 'hash': fingerprint}), None)
            if source is None: raise GameError('version_incompatible', '游戏与当前运行配置版本不兼容；原文件已保留。')
            original = copy.deepcopy(game)
            try:
                game['flags'] = {**copy.deepcopy(self.profile['initial']['flags']), **game['flags']}
                game['npcs'] = {**copy.deepcopy(self.profile['initial']['npcs']), **game['npcs']}
                game['pendingExit'] = bool(game['flags'].get('exit_pending'))
                game['attempts'] = [self.legacy_attempt(key) for key in game['attempts']]
                for key, npc in game['npcs'].items():
                    npc['topics'] = [self.profile['legacyActions'].get(topic, {}).get('option') or topic for topic in npc['topics']]
                old_events = {e['id']: e for e in source['events']}
                for turn in game['turns']:
                    plan = turn.get('plan')
                    if plan and plan['kind'] == 'event':
                        old_id = plan['eventId']
                        call = copy.deepcopy(self.profile['legacyActions'][old_id])
                        turn['plan'] = {'kind': 'tool', 'tool': call}
                        old_check = next((e['key'] for e in old_events[old_id]['effects'] if e['op'] == 'check'), None)
                        if old_check: turn['legacyRollKey'] = old_check
                    elif plan:
                        turn['plan'] = {'kind': plan['kind'], 'tool': None}
                    if turn.get('committed'):
                        # Old flag/stage diagnostics were private, never narration facts.
                        turn['results'] = [r for r in turn['results'] if not any(r.startswith(k + ' =') for k in game['flags']) and not any(r.endswith(': ' + n['stage']) for n in game['npcs'].values())]
                game['schemaVersion'] = 2
                game['profile'] = {'id': self.profile['id'], 'version': self.profile['version'], 'hash': self.fingerprint}
                game['module']['englishTitle'] = self.manifest.get('original_title')
            except (KeyError, TypeError, ValueError):
                game.clear(); game.update(original)
                raise GameError('save_invalid', '旧版游戏无法安全升级；原文件已保留。', 503) from None

    def legacy_attempt(self, old_id):
        call = self.profile['legacyActions'][old_id]
        affordance = next((a for a in self.affordances if a['tool'] == call['name'] and a['target'] == call['target'] and a.get('option') == call.get('option')), None)
        return attempt_key(affordance, call) if affordance else old_id

    def validate(self, game):
        self.migrate(game)
        try:
            compatible = (game['schemaVersion'] == 2 and game['profile'] == {'id': self.profile['id'], 'version': self.profile['version'], 'hash': self.fingerprint}
                          and game['moduleHash'] == self.module_fingerprint)
            assert game['sceneId'] in self.profile['scenes'] and all(s in self.profile['scenes'] for s in game['visited'])
            assert set(game['npcs']) == set(self.profile['npcs'])
            assert all(n['location'] in self.profile['scenes'] and isinstance(n['topics'], list) for n in game['npcs'].values())
            assert isinstance(game['turns'], list) and isinstance(game['messages'], list) and isinstance(game['attempts'], list)
            assert type(game['version']) is int and all(type(game['investigator']['resources'][k]) is int for k in ('hp', 'san'))
            assert game['ending'] in (None, 'completed', 'retreated', 'failed') and type(game['pendingExit']) is bool
            from .schema import Plan
            for turn in game['turns']:
                assert isinstance(turn['id'], str) and isinstance(turn['rolls'], list) and type(turn['committed']) is bool
                if turn['plan'] is not None: Plan.model_validate(turn['plan'])
        except (KeyError, TypeError, AssertionError, ValidationError):
            raise GameError('save_invalid', '游戏文件结构损坏；原文件已保留。', 503) from None
        if not compatible: raise GameError('version_incompatible', '游戏与当前运行配置版本不兼容；原文件已保留。')

    def allowed_assets(self, game):
        result = {self.profile['scenes'][scene]['background'] for scene in game['visited']}
        result.update(g['asset'] for g in self.profile['assetGrants'] if matches(game, g['when']))
        # Sprite grants survive leaving a scene; visible figures can always be rendered.
        result.update(n['sprite'] for n in self.visible_npcs(game).values())
        return result

    def asset(self, game, asset_id):
        if asset_id not in self.allowed_assets(game): raise GameError('asset_unavailable', '素材尚不可见。', 404)
        try:
            asset = self.assets[asset_id]
            return private_file(self.root / 'assets', asset['file']), asset['media_type']
        except (KeyError, ValueError, OSError): raise GameError('asset_invalid', '素材不可用。', 503) from None


class Content:
    """Lazy, per-module dispatch; an unrelated bad profile cannot break startup."""
    def __init__(self, catalogue):
        self.catalogue = catalogue
        self.loaded = {}

    def registration(self, module_id):
        publication = self.catalogue.publication(module_id)
        if not publication.runtimeProfile: raise GameError('module_unavailable', '该模组尚未发布可游玩配置。', 404)
        try:
            registry = read_json(self.catalogue.subroot('runtime'), 'index.json')
            entries = registry['profiles']
            if len({e['id'] for e in entries}) != len(entries) or len({e['moduleId'] for e in entries}) != len(entries): raise ValueError('Duplicate binding')
            entry = next((e for e in entries if e['moduleId'] == module_id and e['id'] == publication.runtimeProfile), None)
            if entry is None: raise GameError('module_unavailable', '该模组尚未登记可游玩配置。', 404)
            retained = entry.get('retained', [])
            if len({r['source'] for r in retained}) != len(retained) or len({r['hash'] for r in retained}) != len(retained): raise ValueError('Duplicate retained profile')
            if any(r['source'] == entry['current'] for r in retained): raise ValueError('Current profile also retained')
            return publication, entry
        except (ValueError, KeyError, TypeError, OSError, ValidationError, yaml.YAMLError):
            raise GameError('profile_invalid', '模组运行配置无效；请检查服务端内容。', 503) from None

    def load(self, publication, entry, source):
        key = (publication.id, source)
        if key in self.loaded: return self.loaded[key]
        try: content = ModuleContent(self.catalogue, publication, entry, source)
        except (ValueError, KeyError, TypeError, OSError, ValidationError, yaml.YAMLError):
            raise GameError('profile_invalid', '模组运行配置无效；请检查服务端内容。', 503) from None
        self.loaded[key] = content
        return content

    def for_module(self, module_id):
        publication, entry = self.registration(module_id)
        return self.load(publication, entry, entry['current'])

    def for_game(self, game):
        try:
            publication, entry = self.registration(game['module']['id'])
            fingerprint = game['profile']['hash']
            # Resolve historical snapshots before loading the current story. A new
            # release must not change an existing route or unfinished action.
            retained = next((r for r in entry.get('retained', []) if r['hash'] == fingerprint), None)
            if retained: return self.load(publication, entry, retained['source'])
            if game.get('schemaVersion') == 1:
                for migration in entry.get('compatible', []):
                    source = read_json(self.catalogue.subroot('runtime'), migration['source'])
                    if digest(source) == fingerprint:
                        target = next((r for r in entry.get('retained', []) if r['hash'] == migration['targetHash']), None)
                        content = self.load(publication, entry, target['source'] if target else entry['current'])
                        if content.fingerprint != migration['targetHash']: raise GameError('version_incompatible', '游戏与登记的升级目标版本不兼容；原文件已保留。')
                        return content
            return self.for_module(publication.id)
        except (KeyError, TypeError): raise GameError('save_invalid', '游戏文件结构损坏；原文件已保留。', 503) from None
        except (ValueError, OSError): raise GameError('profile_invalid', '模组运行配置无效；请检查服务端内容。', 503) from None

    def validate(self, game):
        content = self.for_game(game)
        content.validate(game)
        if 'mechanics' not in game:
            game['mechanics'] = initial_mechanics(self.catalogue, content, game)
        validate_mechanics(content, game)
    def asset(self, game, asset_id): return self.for_game(game).asset(game, asset_id)

    def initialize(self, game_id, request_id, module_id, investigator_id):
        content = self.for_module(module_id)
        _, raw = self.catalogue.character(module_id, investigator_id)
        detail = self.catalogue.investigator(module_id, investigator_id).model_dump()
        attributes, resources = detail['attributes'], detail['resources']
        if any(v is None for v in attributes.values()) or any(resources[k] is None for k in ('hp', 'hpMax', 'san', 'mp', 'mpMax', 'luck')):
            raise GameError('template_invalid', '人物属性或资源不完整。', 503)
        known = {s['name']: s['value'] for s in detail['skills'] if s['value'] is not None}
        detail['skills'] = [{'name': k, 'value': known.get(k, skill_default(k, attributes)), 'highlighted': False}
                            for k in sorted(set(DEFAULT_SKILLS) | set(known))]
        inventory = []
        for n, item in enumerate(detail['equipment']):
            if item['kind'] != 'carried': continue
            key = next((key for key, words in content.profile['itemAliases'].items() if any(word in item['name'] for word in words)), f'template_{n}')
            if not any(i['id'] == key for i in inventory): inventory.append({'id': key, **copy.deepcopy(item)})
        initial = content.profile['initial']
        game = {'schemaVersion': 2, 'gameId': game_id, 'creation': {'requestId': request_id, 'moduleId': module_id, 'investigatorId': investigator_id},
                'profile': {'id': content.profile['id'], 'version': content.profile['version'], 'hash': content.fingerprint},
                'moduleVersion': content.manifest['content_version'], 'moduleHash': content.module_fingerprint,
                'templateVersion': raw['version'], 'templateHash': digest(raw), 'initialInvestigator': copy.deepcopy(detail),
                'investigator': detail, 'module': {'id': module_id, 'title': content.manifest['title'], 'englishTitle': content.manifest.get('original_title')}, 'version': 1,
                'sceneId': initial['scene'], 'visited': [initial['scene']], 'flags': copy.deepcopy(initial['flags']), 'npcs': copy.deepcopy(initial['npcs']),
                'inventory': inventory, 'facts': [], 'attempts': [], 'messages': copy.deepcopy(content.profile['opening']), 'turns': [], 'ending': None, 'pendingExit': False}

        game['mechanics'] = initial_mechanics(self.catalogue, content, game)
        return game
