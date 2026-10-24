"""Small, non-executable predicates shared by content and tools."""
def matches(game, condition, checks=None):
    for key, value in condition.items():
        if key == 'all': actual = all(matches(game, c, checks) for c in value); value = True
        elif key == 'any': actual = any(matches(game, c, checks) for c in value); value = True
        elif key == 'not': actual = not matches(game, value, checks); value = True
        elif key == 'scene': actual = game['sceneId']
        elif key == 'ending': actual = game['ending']
        elif key.startswith('flag:'): actual = game['flags'].get(key[5:], False)
        elif key.startswith('item:'): actual = any(i['id'] == key[5:] for i in game['inventory'])
        elif key.startswith('clue:'): actual = any(f['id'] == key[5:] for f in game['facts'])
        elif key.startswith('visited:'): actual = key[8:] in game['visited']
        elif key.startswith('check:'): actual = (checks or {}).get(key[6:])
        elif key.startswith('entity:'):
            _, entity, field = key.split(':'); actual = game.get('mechanics', {}).get('entityStates', {}).get(entity, {}).get(field, False)
        elif key.startswith('npc:'):
            _, npc, field = key.split(':'); actual = game['npcs'][npc][field]
        else: raise ValueError('Unknown configuration condition')
        if actual != value: return False
    return True
