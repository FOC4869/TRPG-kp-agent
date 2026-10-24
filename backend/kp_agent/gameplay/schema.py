"""Declarative runtime format. No module names or executable expressions."""
from __future__ import annotations
from typing import Annotated, Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Id = Annotated[str, Field(pattern=r'^[a-z0-9][a-z0-9_-]{0,79}$')]

class Definition(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)

class ToolCall(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    name: Literal['move', 'observe', 'talk', 'take', 'inspect', 'interact', 'finish', 'use_item', 'drop', 'give', 'confirm_action']
    target: str = Field(min_length=1, max_length=80)
    option: str | None
    skill: str | None
    item: str | None
    approach: str = Field(max_length=500)

class Plan(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    kind: Literal['tool', 'question', 'clarify', 'unsupported']
    tool: ToolCall | None

    @model_validator(mode='after')
    def consistent(self):
        if (self.kind == 'tool') != (self.tool is not None): raise ValueError('tool/kind mismatch')
        return self

class Clause(Definition):
    when: dict[str, Any] = Field(default_factory=dict)
    text: str

class Scene(Definition):
    name: str
    background: Id
    public: str
    keeper: str = ''
    region: str = ''
    clauses: list[Clause] = Field(default_factory=list)

class Npc(Definition):
    name: str
    sprite: Id
    role: str
    public: str
    visibleWhen: dict[str, Any] = Field(default_factory=dict)
    followsWhen: dict[str, Any] = Field(default_factory=lambda: {'any': []})
    knowledge: list[Clause] = Field(default_factory=list)

class Interaction(Definition):
    id: Id
    label: str
    description: str
    skills: list[str] = Field(default_factory=list)
    aids: list[Literal['light', 'rope', 'pry', 'cut', 'key']] = Field(default_factory=list)
    requires: dict[str, Any] = Field(default_factory=dict)
    effects: list[dict[str, Any]] = Field(default_factory=list)
    success: list[dict[str, Any]] = Field(default_factory=list)
    failure: list[dict[str, Any]] = Field(default_factory=list)
    failureLoss: dict[str, str] | None = None
    dangerous: bool = False
    repeat: Literal['once', 'always', 'method'] = 'once'

class Entity(Definition):
    name: str
    scenes: list[Id]
    public: str
    requires: dict[str, Any] = Field(default_factory=dict)
    initialState: dict[str, bool] = Field(default_factory=dict)
    clauses: list[Clause] = Field(default_factory=list)
    actions: list[Interaction] = Field(default_factory=list)

class Challenge(Definition):
    key: Id
    skills: list[str]
    reason: str
    aids: list[Id] = Field(default_factory=list)
    failureLoss: dict[str, str] | None = None
    success: list[dict[str, Any]] = Field(default_factory=list)
    failure: list[dict[str, Any]] = Field(default_factory=list)

class Affordance(Definition):
    id: Id
    tool: Literal['move', 'inspect', 'talk', 'take', 'interact']
    target: Id
    option: Id | None = None
    label: str
    description: str
    scenes: list[str]
    requires: dict[str, Any] = Field(default_factory=dict)
    repeat: Literal['once', 'always', 'method'] = 'once'
    effects: list[dict[str, Any]] = Field(default_factory=list)
    challenge: Challenge | None = None
    response: str | None = None

class Initial(Definition):
    scene: Id
    flags: dict[str, Any] = Field(default_factory=dict)
    npcs: dict[str, dict[str, Any]] = Field(default_factory=dict)

class ReturnRoute(Definition):
    when: dict[str, Any]
    scene: Id

class Ending(Definition):
    returnScene: Id
    safeScenes: list[Id]
    completeWhen: dict[str, Any]
    confirmation: list[Clause]
    descriptions: dict[str, str]
    clauses: list[Clause] = Field(default_factory=list)
    returnRoutes: list[ReturnRoute] = Field(default_factory=list)

class RuntimeProfile(Definition):
    schemaVersion: Literal[2]
    id: Id
    version: str
    moduleId: Id
    adaptation: str
    initial: Initial
    opening: list[dict[str, str]]
    scenes: dict[Id, Scene]
    npcs: dict[Id, Npc] = Field(default_factory=dict)
    entities: dict[Id, Entity] = Field(default_factory=dict)
    affordances: list[Affordance]
    endings: Ending
    assetGrants: list[dict[str, Any]] = Field(default_factory=list)
    itemAliases: dict[Id, list[str]] = Field(default_factory=dict)
    # Explicit data-only compatibility map for recorded v1 event plans/attempts.
    legacyActions: dict[str, dict[str, Any]] = Field(default_factory=dict)

    @model_validator(mode='after')
    def references(self):
        try:
            validate_profile(self.model_dump(exclude_none=True))
        except (KeyError, TypeError, IndexError) as error:
            raise ValueError('Invalid runtime definition or reference') from error
        return self


def validate_profile(p):
    scenes, npcs, entities = p['scenes'], p['npcs'], p['entities']
    affordances = p['affordances'] + entity_affordances(p)
    import re
    from trpg.rules import DEFAULT_SKILLS
    flags = p['initial']['flags']
    skills = set(DEFAULT_SKILLS) | {'STR','CON','SIZ','DEX','APP','INT','POW','EDU','SAN'}
    clues = {e['key'] for a in affordances for e in all_effects(a) if e['op'] == 'clue'}
    items = set(p['itemAliases']) | {e['key'] for a in affordances for e in all_effects(a) if e['op'] == 'item'}
    def require(test):
        if not test: raise ValueError('Invalid runtime definition or reference')
    def condition(c, depth=0, check_keys=()):
        require(isinstance(c, dict) and depth < 16)
        for key, value in c.items():
            if key in ('all', 'any'):
                require(isinstance(value, list)); [condition(child, depth + 1, check_keys) for child in value]
            elif key == 'not': condition(value, depth + 1, check_keys)
            elif key == 'scene': require(value in scenes)
            elif key == 'ending': require(value in ('completed','retreated','failed'))
            elif key.startswith('flag:'): require(key[5:] in flags and isinstance(value, (str, bool, int)))
            elif key.startswith('entity:'):
                parts = key.split(':'); require(len(parts) == 3 and parts[1] in entities and parts[2] in entities[parts[1]]['initialState'] and type(value) is bool)
            elif key.startswith('npc:'):
                parts = key.split(':'); require(len(parts) == 3 and parts[1] in npcs and parts[2] in ('stage', 'location'))
                if parts[2] == 'location': require(value in scenes)
                else: require(isinstance(value, str))
            else:
                require(isinstance(value, bool))
                if key.startswith('clue:'): require(key[5:] in clues)
                elif key.startswith('item:'): require(key[5:] in items)
                elif key.startswith('visited:'): require(key[8:] in scenes)
                else: require(key.startswith('check:') and key[6:] in check_keys)
    def loss(value):
        require(set(value) == {'resource', 'dice'} and value['resource'] in ('hp', 'san'))
        require(isinstance(value['dice'], str) and re.fullmatch(r'[1-3]D(?:3|4|6|8|10)', value['dice']) is not None)
    def effect(e, check_keys):
        fields = {'flag': {'key', 'value'}, 'move': {'to'}, 'npc': {'id', 'stage', 'location'},
                  'clue': {'key', 'title', 'text'}, 'item': {'key', 'name', 'note'},
                  'state': {'target', 'key', 'value'}, 'check': {'key', 'skill', 'reason', 'failureLoss'}, 'loss': {'resource', 'amount'}}
        op = e.get('op'); require(op in fields and not set(e) - fields[op] - {'op', 'when'})
        required = {'flag': {'key','value'}, 'move': {'to'}, 'npc': {'id','stage'}, 'clue': {'key','title','text'}, 'item': {'key','name'}, 'state': {'target','key','value'}, 'check': {'key','skill','reason'}, 'loss': {'resource','amount'}}
        require(required[op].issubset(e))
        condition(e.get('when', {}), check_keys=check_keys)
        if op == 'flag': require(e['key'] in flags and isinstance(e['value'], (str, bool, int)))
        elif op == 'move': require(e['to'] in scenes)
        elif op == 'npc':
            require(e['id'] in npcs and isinstance(e['stage'], str))
            if 'location' in e: require(e['location'] in scenes)
        elif op in ('clue', 'item'):
            require(all(isinstance(e[k], str) and e[k] for k in (('key', 'title', 'text') if op == 'clue' else ('key', 'name'))))
        elif op == 'state': require(e['target'] in entities and e['key'] in entities[e['target']]['initialState'] and type(e['value']) is bool)
        elif op == 'check':
            require(e['skill'] in skills)
            require(all(isinstance(e[k], str) and e[k] for k in ('key', 'skill', 'reason')))
            if 'failureLoss' in e: loss(e['failureLoss'])
        elif op == 'loss': require(e['resource'] in ('hp', 'san') and type(e['amount']) is int and 0 <= e['amount'] <= 100)
    require(all(type(v) in (str, bool, int) for v in flags.values()))
    require(all(re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,79}', key) for key in flags))
    require(p['initial']['scene'] in scenes and set(p['initial']['npcs']) == set(npcs))
    for state in p['initial']['npcs'].values():
        require(set(state) == {'stage', 'location', 'topics'} and state['location'] in scenes and isinstance(state['stage'], str) and isinstance(state['topics'], list) and all(isinstance(t, str) for t in state['topics']))
    require(not set(entities) & (set(npcs) | set(scenes)))
    require(not set(npcs) & set(scenes))
    ids, routes = set(), {}
    for a in affordances:
        require(a['id'] not in ids); ids.add(a['id'])
        signature = (a['tool'], a['target'], a.get('option'))
        # A target/option may be reused in disjoint scenes; overlapping routes are ambiguous.
        previous = routes.setdefault(signature, set())
        require(not previous or ('*' not in previous and '*' not in a['scenes'] and not previous.intersection(a['scenes'])))
        previous.update(a['scenes'])
        require(a['scenes'] and all(s == '*' or s in scenes for s in a['scenes']))
        target = a['target']
        require(target in (scenes if a['tool'] == 'move' else npcs if a['tool'] == 'talk' else entities))
        if a['tool'] == 'move':
            destinations = [e['to'] for e in a['effects'] if e.get('op') == 'move']
            require(destinations == [a['target']])
        condition(a['requires'])
        check_keys = {e['key'] for e in all_effects(a) if e.get('op') == 'check'} | ({a['challenge']['key']} if a.get('challenge') else set())
        for e in all_effects(a): effect(e, check_keys)
        if a.get('challenge'):
            ch = a['challenge']; require((ch['skills'] or ch.get('aidTags')) and all(s in skills for s in ch['skills']) and len(set(ch['skills'])) == len(ch['skills']))
            require(all(i in items for i in ch['aids']))
            if 'failureLoss' in ch: loss(ch['failureLoss'])
    for key, aliases in p['itemAliases'].items():
        require(aliases and all(isinstance(word, str) and word for word in aliases))
    for call in p['legacyActions'].values():
        ToolCall.model_validate(call)
        targets = set(scenes) | set(entities) | set(npcs) if call['name'] == 'observe' else {'investigation'} if call['name'] == 'finish' else scenes if call['name'] == 'move' else npcs if call['name'] == 'talk' else entities
        require(call['target'] in targets)
        require(call['skill'] is None or call['skill'] in skills)
        require(call['item'] is None or call['item'] in items)
    for scene in scenes.values():
        for clause in scene['clauses']: condition(clause['when'])
    for npc in npcs.values():
        condition(npc['visibleWhen']); condition(npc['followsWhen'])
        for clause in npc['knowledge']: condition(clause['when'])
    for entity in entities.values():
        require(all(s in scenes for s in entity['scenes'])); condition(entity['requires'])
        for clause in entity['clauses']: condition(clause['when'])
        require(len({a['id'] for a in entity['actions']}) == len(entity['actions']))
    end = p['endings']; require(end['returnScene'] in scenes and all(s in scenes for s in end['safeScenes']))
    require(set(end['descriptions']) == {'completed', 'retreated', 'failed'})
    condition(end['completeWhen'])
    for clause in end['confirmation'] + end['clauses']: condition(clause['when'])
    for route in end['returnRoutes']:
        require(route['scene'] in scenes); condition(route['when'])
    for grant in p['assetGrants']:
        require(set(grant) == {'asset', 'when'} and isinstance(grant['asset'], str)); condition(grant['when'])
    require(len({m['id'] for m in p['opening']}) == len(p['opening']))
    for opening in p['opening']:
        require(set(opening) == {'id', 'kind', 'speaker', 'text'} and opening['kind'] in ('keeper', 'npc'))


def all_effects(affordance):
    challenge = affordance.get('challenge') or {}
    return affordance.get('effects', []) + challenge.get('success', []) + challenge.get('failure', [])


def entity_affordances(profile):
    """Compile declarative target methods into the existing validated executor."""
    result = []
    for target, entity in profile['entities'].items():
        for action in entity.get('actions', []):
            key = f"entity-{target}-{action['id']}"
            challenge = None
            if action['skills'] or action['aids']:
                challenge = {'key': key, 'skills': action['skills'], 'aids': [], 'aidTags': action['aids'],
                             'reason': action['description'], 'success': action['success'], 'failure': action['failure']}
                if action.get('failureLoss'): challenge['failureLoss'] = action['failureLoss']
            elif action['success'] or action['failure'] or action.get('failureLoss'):
                raise ValueError('Outcome requires a challenge')
            result.append({'id': key, 'tool': 'interact', 'target': target, 'option': action['id'],
                           'label': action['label'], 'description': action['description'], 'scenes': entity['scenes'],
                           'requires': action['requires'], 'repeat': action['repeat'], 'effects': action['effects'],
                           'challenge': challenge, 'dangerous': action['dangerous']})
    return result
