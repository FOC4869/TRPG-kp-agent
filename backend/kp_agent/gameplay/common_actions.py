"""Versioned item abilities and durable common actions, independent of module plot."""
from __future__ import annotations
import copy
import re
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from .schema import ToolCall

TAGS = {'light', 'rope', 'pry', 'cut', 'key'}

class ItemAbility(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    sourceId: str
    tags: list[Literal['light', 'rope', 'pry', 'cut', 'key']]
    damage: str | None = None

class PendingAction(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    id: str
    sceneId: str
    call: ToolCall
    prompt: str

class StoredItem(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    quantity: int | None
    kind: Literal['carried', 'owned']
    note: str

class GroundItem(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    sceneId: str
    item: StoredItem

class Mechanics(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    version: Literal[1]
    rulesVersion: Literal['1.0.0']
    rulesHash: str = Field(pattern=r'^[a-f0-9]{64}$')
    items: dict[str, ItemAbility]
    groundItems: list[GroundItem]
    npcItems: dict[str, list[StoredItem]]
    entityStates: dict[str, dict[str, bool]]
    activeItems: list[str]
    pendingAction: PendingAction | None


def initial_mechanics(catalogue, content, game):
    from .content import digest, read_json, GameError
    _, raw = catalogue.character(game['creation']['moduleId'], game['creation']['investigatorId'])
    if digest(raw) != game['templateHash']:
        raise GameError('version_incompatible', '人物模板已经变化，无法安全补充本局物品能力；原存档已保留。')
    rules = read_json(catalogue.subroot('runtime'), 'common-actions-v1.json')
    if set(rules) != {'version', 'adaptation', 'items'} or rules['version'] != '1.0.0':
        raise ValueError('Unknown item rules')
    for key, item in rules['items'].items():
        ability = ItemAbility.model_validate({'sourceId': key, **item})
        if ability.damage and not re.fullmatch(r'1D[36]', ability.damage):
            raise ValueError('Invalid simple damage')
    source_items = []
    def flatten(items):
        for item in items:
            source_items.append(item)
            flatten(item.get('contents', []))
    flatten(raw.get('starting_equipment', []))
    # Catalogue flattens in the same order. Preserve historical template_N IDs.
    mapping = {}
    for index, source in enumerate(source_items):
        item_id = next((key for key, aliases in content.profile['itemAliases'].items()
                        if any(word in source['name'] for word in aliases)), f'template_{index}')
        source_id = source['id']
        if source_id in rules['items'] and any(i['id'] == item_id for i in game['inventory']):
            mapping[item_id] = {'sourceId': source_id, **copy.deepcopy(rules['items'][source_id])}
    # Explicit module item aliases also cover items picked up after initialization.
    for item in game['inventory']:
        if item['id'] in rules['items'] and item['id'] not in mapping:
            mapping[item['id']] = {'sourceId': item['id'], **copy.deepcopy(rules['items'][item['id']])}
    return {'version': 1, 'rulesVersion': rules['version'], 'rulesHash': digest(rules),
            'items': mapping, 'groundItems': [], 'npcItems': {}, 'activeItems': [],
            'entityStates': {key: copy.deepcopy(entity.get('initialState', {})) for key, entity in content.profile['entities'].items()},
            'pendingAction': None,
            # Module pickup abilities are also frozen, so a config edit cannot change a running game.
            'catalogue': copy.deepcopy(rules['items'])}


def validate_mechanics(content, game):
    from .content import GameError
    try:
        value = game['mechanics']
        Mechanics.model_validate({k: v for k, v in value.items() if k != 'catalogue'})
        assert set(value) == set(Mechanics.model_fields) | {'catalogue'}
        for key, item in value['catalogue'].items():
            ItemAbility.model_validate({'sourceId': key, **item})
        for ability in list(value['items'].values()) + list(value['catalogue'].values()):
            assert ability.get('damage') is None or re.fullmatch(r'1D[36]', ability['damage'])
        for item in value['items'].values():
            assert item == {'sourceId': item['sourceId'], **value['catalogue'][item['sourceId']]}
        assert all(g['sceneId'] in content.profile['scenes'] and isinstance(g['item']['name'], str) for g in value['groundItems'])
        assert set(value['npcItems']) <= set(game['npcs'])
        owned = game['inventory'] + [g['item'] for g in value['groundItems']] + [i for items in value['npcItems'].values() for i in items]
        for item in owned: StoredItem.model_validate(item)
        assert len({i['id'] for i in owned}) == len(owned)
        assert set(value['items']) <= {i['id'] for i in owned}
        assert set(value['entityStates']) == set(content.profile['entities'])
        for key, states in value['entityStates'].items():
            assert set(states) == set(content.profile['entities'][key].get('initialState', {}))
        assert set(value['activeItems']) <= {i['id'] for i in game['inventory']}
        pending = value['pendingAction']
        assert pending is None or (pending['sceneId'] == game['sceneId'] and not game['pendingExit'] and not game['ending'])
    except (KeyError, TypeError, ValueError, AssertionError):
        raise GameError('save_invalid', '本局行动能力或确认状态无效；原存档已保留。', 503) from None


def register_item(game, item_id):
    m = game.get('mechanics')
    if m and item_id not in m['items'] and item_id in m['catalogue']:
        m['items'][item_id] = {'sourceId': item_id, **copy.deepcopy(m['catalogue'][item_id])}


def carried(game, item_id):
    return next((i for i in game['inventory'] if i['id'] == item_id), None)


def ability(game, item_id):
    return game.get('mechanics', {}).get('items', {}).get(item_id, {}) if carried(game, item_id) else {}


def public_pending(game):
    pending = game.get('mechanics', {}).get('pendingAction')
    return {'id': pending['id'], 'prompt': pending['prompt']} if pending else None


def common_choices(content, game):
    m = game.get('mechanics')
    if not m or game['ending']: return []
    result = []
    def add(tool, target, option, label, item=None):
        result.append({'tool': tool, 'target': target, 'option': option, 'label': label,
                       'description': label, 'methods': None, 'item': item})
    for item in game['inventory']:
        add('drop', item['id'], None, '放下' + item['name'])
        a = ability(game, item['id'])
        if 'light' in a.get('tags', []): add('use_item', game['sceneId'], 'illuminate', '用' + item['name'] + '照明', item['id'])
        if a.get('damage'): add('use_item', 'self', 'harm', '以' + item['name'] + '伤害自己（先确认后果）', item['id'])
        for npc_id, npc in content.visible_npcs(game).items():
            add('give', npc_id, None, '把' + item['name'] + '交给' + npc['name'], item['id'])
    for entry in m['groundItems']:
        if entry['sceneId'] == game['sceneId']: add('take', entry['item']['id'], None, '重新拿起' + entry['item']['name'])
    add('interact', 'self', 'harm', '以徒手伤害自己（先确认后果）')
    if m['pendingAction']:
        for option, label in [('confirm', '确认执行'), ('cancel', '取消这次行动')]:
            add('confirm_action', m['pendingAction']['id'], option, label)
    return result
