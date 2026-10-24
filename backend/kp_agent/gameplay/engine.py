"""Generic validated tools; only configured effects can change world state."""
from __future__ import annotations
import copy
import random
from trpg.check import coc_check
from trpg.dice import roll
from .conditions import matches
from .content import attempt_key
from .common_actions import ability, carried, common_choices, public_pending, register_item


def module_content(content, game):
    return content.for_game(game) if hasattr(content, 'for_game') else content


def available_methods(game, affordance):
    challenge = affordance.get('challenge')
    if not challenge: return None
    keys = game['attempts']
    def usable(call): return affordance['repeat'] != 'method' or attempt_key(affordance, call) not in keys
    return {'skills': [s for s in challenge['skills'] if usable({'skill': s})],
            'aids': [i['id'] for i in game['inventory'] if (i['id'] in challenge['aids'] or set(ability(game, i['id']).get('tags', [])) & set(challenge.get('aidTags', []))) and usable({'item': i['id']})]}


def legal_affordances(content, game):
    content = module_content(content, game)
    if game['ending']: return []
    entities, npcs = content.entities(game), content.visible_npcs(game)
    result = []
    for a in content.affordances:
        if not ('*' in a['scenes'] or game['sceneId'] in a['scenes']) or not matches(game, a['requires']): continue
        if a['tool'] == 'talk' and a['target'] not in npcs: continue
        if a['tool'] not in ('move', 'talk') and a['target'] not in entities: continue
        if a['repeat'] == 'once' and a['id'] in game['attempts']: continue
        methods = available_methods(game, a)
        if methods and not (methods['skills'] or methods['aids']): continue
        result.append(a)
    return result


def tool_choices(content, game):
    return [{'tool': a['tool'], 'target': a['target'], 'option': a.get('option'), 'label': a['label'],
             'description': a['description'], 'methods': available_methods(game, a)} for a in legal_affordances(content, game)] + common_choices(module_content(content, game), game)


def scene_description(content, game):
    content = module_content(content, game)
    scene = content.profile['scenes'][game['sceneId']]
    text = scene['public'] + ''.join(c['text'] for c in scene['clauses'] if matches(game, c['when']))
    if game['ending']:
        ending = content.profile['endings']
        text += ending['descriptions'][game['ending']] + ''.join(c['text'] for c in ending['clauses'] if matches(game, c['when']))
    return text


def move(content, game, to):
    game['sceneId'] = to
    if to not in game['visited']: game['visited'].append(to)
    for key, npc in content.profile['npcs'].items():
        if matches(game, npc['followsWhen']): game['npcs'][key]['location'] = to


def end_game(content, game, failed=False):
    ending = content.profile['endings']
    game['ending'] = 'failed' if failed else 'completed' if matches(game, ending['completeWhen']) else 'retreated'
    game['pendingExit'] = False
    if game.get('mechanics'): game['mechanics']['pendingAction'] = None
    if not failed:
        destination = next((r['scene'] for r in ending['returnRoutes'] if matches(game, r['when'])), ending['returnScene'])
        move(content, game, destination)


def exit_response(content, game):
    return '\n'.join(c['text'] for c in content.profile['endings']['confirmation'] if matches(game, c['when'])) + '\n你要确认撤离，还是继续调查？'


def execute(content, game, turn, persist_roll, rng=None, confirmed=False, confirmed_call=None):
    """Replay on a copy with saved rolls. Publish nothing before atomic commit."""
    content = module_content(content, game)
    rng = rng or random.SystemRandom()
    current = copy.deepcopy(game)
    results, checks = [], {}
    plan = {'kind': 'tool', 'tool': confirmed_call} if confirmed_call else turn['plan']
    turn['response'] = None
    turn['executedTool'] = None
    if plan['kind'] != 'tool':
        turn['outcome'] = plan['kind']
        return current, []
    call = plan['tool']
    name, target = call['name'], call['target']
    rejected = ['这个方法尚未产生效果。需要根据眼前目标、实际携带的工具和已尝试的方法重新判断。']
    turn['outcome'] = 'rejected'
    mechanics = current.get('mechanics')
    def accept():
        turn['executedTool'] = copy.deepcopy(call)
        turn['outcome'] = 'executed'
        if mechanics and not confirmed: mechanics['pendingAction'] = None
        if name != 'finish': current['pendingExit'] = False
    def confirmation(prompt):
        mechanics['pendingAction'] = {'id': turn['id'], 'sceneId': current['sceneId'], 'call': copy.deepcopy(call), 'prompt': prompt}
        current['pendingExit'] = False
        turn['outcome'] = 'confirmation'
        turn['response'] = prompt
        return current, [prompt]
    if game['ending']: return current, rejected
    if name == 'confirm_action':
        pending = mechanics and mechanics['pendingAction']
        if not pending or pending['id'] != target or call.get('item') or call.get('skill'): return current, rejected
        if call.get('option') == 'cancel':
            mechanics['pendingAction'] = None
            turn['outcome'] = 'cancelled'
            turn['response'] = '你改变了打算。眼前的调查仍在继续。'
            return current, [turn['response']]
        if call.get('option') != 'confirm' or pending['sceneId'] != current['sceneId']: return current, rejected
        result, facts = execute(content, current, turn, persist_roll, rng, confirmed=True, confirmed_call=copy.deepcopy(pending['call']))
        result['mechanics']['pendingAction'] = None
        return result, facts
    if mechanics and name in ('drop', 'give'):
        item_id = target if name == 'drop' else call.get('item')
        item = carried(current, item_id)
        if not item or call.get('skill') or call.get('option'): return current, rejected
        if name == 'drop' and call.get('item'): return current, rejected
        if name == 'give' and target not in content.visible_npcs(current): return current, rejected
        accept()
        current['inventory'].remove(item)
        if item_id in mechanics['activeItems']: mechanics['activeItems'].remove(item_id)
        if name == 'drop':
            mechanics['groundItems'].append({'sceneId': current['sceneId'], 'item': item})
            return current, ['你把' + item['name'] + '放在了这里，仍可回来拿取。']
        mechanics['npcItems'].setdefault(target, []).append(item)
        return current, ['已将' + item['name'] + '交给' + content.profile['npcs'][target]['name'] + '保管。']
    if mechanics and name == 'take' and not call.get('option') and not call.get('skill') and not call.get('item'):
        ground = next((g for g in mechanics['groundItems'] if g['sceneId'] == current['sceneId'] and g['item']['id'] == target), None)
        if ground:
            accept(); mechanics['groundItems'].remove(ground); current['inventory'].append(ground['item'])
            return current, ['你重新拿起了' + ground['item']['name'] + '。']
    if mechanics and name in ('use_item', 'interact') and target == 'self' and call.get('option') == 'harm':
        item_id = call.get('item')
        item = carried(current, item_id) if item_id else None
        damage = ability(current, item_id).get('damage') if item_id else '1D3' if name == 'interact' else None
        if not damage or call.get('skill'): return current, rejected
        title = item['name'] if item else '徒手'
        if not confirmed:
            return confirmation('你确定要用' + title + '伤害自己？这会造成实际伤害，也可能让这次调查就此结束。')
        accept()
        saved = next((r for r in turn.setdefault('damageRolls', []) if r['key'] == 'self-harm'), None)
        before = current['investigator']['resources']['hp']
        if saved is None:
            amount = roll(damage.lower(), rng).total
            saved = {'key': 'self-harm', 'effectId': turn['id'] + ':damage', 'resource': 'hp', 'dice': damage,
                     'amount': amount, 'before': before, 'after': max(0, before - amount), 'reason': '使用' + title + '造成的伤害'}
            turn['damageRolls'].append(saved); persist_roll()
        if saved['before'] != before: raise ValueError('Damage checkpoint mismatch')
        current['investigator']['resources']['hp'] = saved['after']
        current['messages'].append({'id': saved['effectId'], 'kind': 'effect', 'speaker': '行动结果', 'text': saved['reason'], 'effect': {k: v for k, v in saved.items() if k != 'key'}})
        results.append(f"实际伤害{damage}={saved['amount']}，HP从{before}变为{saved['after']}。")
        if saved['after'] == 0:
            end_game(content, current, failed=True); results.append(content.profile['endings']['descriptions']['failed'])
        return current, results
    if mechanics and name == 'use_item':
        item = carried(current, call.get('item'))
        if not item or call.get('skill'): return current, rejected
        if target == current['sceneId'] and call.get('option') == 'illuminate' and 'light' in ability(current, item['id']).get('tags', []):
            accept()
            if item['id'] not in mechanics['activeItems']: mechanics['activeItems'].append(item['id'])
            return current, ['你使用' + item['name'] + '照亮了眼前可见的区域。', scene_description(content, current)]
        name = 'interact'
    if name == 'finish':
        if target != 'investigation' or call.get('skill') or call.get('item'): return current, rejected
        option = call.get('option')
        if option == 'request':
            if current['sceneId'] in content.profile['endings']['safeScenes']: end_game(content, current)
            else:
                current['pendingExit'] = True
                turn['response'] = exit_response(content, current)
                results.append(turn['response'])
        elif option == 'confirm' and current['pendingExit']: end_game(content, current)
        elif option == 'cancel' and current['pendingExit']:
            current['pendingExit'] = False; results.append('已取消撤离，继续调查。')
        else: return current, rejected
        accept()
        if current['ending']: results.append(content.profile['endings']['descriptions'][current['ending']])
        return current, results
    if name == 'observe':
        if call.get('skill') or call.get('item') or call.get('option'): return current, rejected
        if target == current['sceneId']: results.append(scene_description(content, current))
        elif target in content.entities(current): results.append(content.entities(current)[target]['public'])
        elif target in content.visible_npcs(current): results.append(content.visible_npcs(current)[target]['public'])
        else: return current, rejected
        accept()
        return current, results
    candidates = [a for a in legal_affordances(content, current) if a['tool'] == name and a['target'] == target and a.get('option') == call.get('option')]
    # Ordinary dialogue is open-ended, but never invents clues or numeric effects.
    if name == 'talk' and not candidates and not call.get('option') and target in content.visible_npcs(current) and not call.get('skill') and not call.get('item'):
        accept()
        return current, [content.visible_npcs(current)[target]['public']]
    if len(candidates) != 1: return current, rejected
    a = candidates[0]
    challenge = a.get('challenge')
    if challenge:
        methods = available_methods(current, a)
        if call.get('item'):
            if call['item'] not in methods['aids'] or call.get('skill'): return current, rejected
        else:
            if call.get('skill') not in methods['skills']: return current, rejected
    elif call.get('skill') or call.get('item'): return current, rejected
    if a.get('dangerous') and mechanics and not confirmed:
        return confirmation(a['description'] + ' 这可能带来不可逆的变化。你确定要' + a['label'] + '吗？')
    accept()
    current['attempts'].append(attempt_key(a, call))

    def check(effect, legacy=False):
        key = turn.get('legacyRollKey', effect['key']) if legacy else effect['key']
        recorded = next((r for r in turn['rolls'] if r['key'] == key), None)
        if recorded is None:
            skill = effect['skill']; inv = current['investigator']
            value = inv['resources']['san'] if skill == 'SAN' else inv['attributes'].get(skill)
            if value is None: value = next(s['value'] for s in inv['skills'] if s['name'] == skill)
            result = coc_check(value, rng=rng)
            loss = effect.get('failureLoss') if not result.success else None
            details = [{'resource': loss['resource'], 'dice': loss['dice'], 'amount': roll(loss['dice'].lower(), rng).total}] if loss else []
            recorded = {'key': key, 'checkId': turn['id'] + ':' + key, 'skill': skill, 'target': value,
                        'roll': result.roll, 'success': result.success, 'result': '成功' if result.success else '失败',
                        'reason': effect['reason'], 'details': details}
            turn['rolls'].append(recorded)
            persist_roll()
        checks[effect['key']] = recorded['success']
        current['messages'].append({'id': recorded['checkId'], 'kind': 'check', 'speaker': '规则检定', 'text': recorded['reason'], 'check': copy.deepcopy(recorded)})
        results.append(f"{recorded['skill']}检定：{recorded['roll']}/{recorded['target']}，{recorded['result']}")
        for loss in recorded['details']:
            resource = loss['resource']
            current['investigator']['resources'][resource] = max(0, current['investigator']['resources'][resource] - loss['amount'])
            results.append(f"{resource}损失{loss['dice']}={loss['amount']}")
        return recorded['success']

    def apply(effects):
        for effect in effects:
            if current['ending']: break
            if not matches(current, effect.get('when', {}), checks): continue
            op = effect['op']
            if op == 'flag': current['flags'][effect['key']] = effect['value']
            elif op == 'move':
                move(content, current, effect['to']); results.append('到达：' + content.profile['scenes'][effect['to']]['name'])
            elif op == 'npc':
                current['npcs'][effect['id']]['stage'] = effect['stage']
                current['npcs'][effect['id']]['location'] = effect.get('location', current['sceneId'])
            elif op == 'clue':
                fact = {'id': effect['key'], 'title': effect['title'], 'text': effect['text']}
                if not any(f['id'] == fact['id'] for f in current['facts']): current['facts'].append(fact)
                results.append(fact['text'])
            elif op == 'item':
                held = carried(current, effect['key'])
                ground = next((g for g in mechanics['groundItems'] if g['item']['id'] == effect['key']), None) if mechanics else None
                owner = next((key for key, items in mechanics['npcItems'].items() if any(i['id'] == effect['key'] for i in items)), None) if mechanics else None
                if ground:
                    if ground['sceneId'] != current['sceneId']:
                        results.append(effect['name'] + '留在别处，需要回到原处拿取。'); continue
                    mechanics['groundItems'].remove(ground); current['inventory'].append(ground['item'])
                elif owner:
                    results.append(effect['name'] + '仍由' + content.profile['npcs'][owner]['name'] + '保管。'); continue
                elif not held:
                    current['inventory'].append({'id': effect['key'], 'name': effect['name'], 'quantity': 1, 'kind': 'carried', 'note': effect.get('note', '')})
                register_item(current, effect['key'])
                results.append('已带上：' + effect['name'])
            elif op == 'state':
                current['mechanics']['entityStates'][effect['target']][effect['key']] = effect['value']
            elif op == 'check': check(effect)
            elif op == 'loss':
                resource = effect['resource']
                current['investigator']['resources'][resource] = max(0, current['investigator']['resources'][resource] - effect['amount'])
                results.append(f"明确代价：{resource}减少{effect['amount']}")
            else: raise ValueError('Unknown configuration effect')
            if any(current['investigator']['resources'][r] <= 0 for r in ('hp', 'san')):
                end_game(content, current, failed=True); results.append(content.profile['endings']['descriptions']['failed'])
    if challenge:
        if call.get('item'):
            success = True
            item = next(i for i in current['inventory'] if i['id'] == call['item'])
            results.append('使用' + item['name'] + '辅助，免检定通过。')
        else:
            success = check({'key': challenge['key'], 'skill': call['skill'], 'reason': challenge['reason'], **({'failureLoss': challenge['failureLoss']} if challenge.get('failureLoss') else {})}, legacy=True)
        if any(current['investigator']['resources'][r] <= 0 for r in ('hp', 'san')):
            end_game(content, current, failed=True); results.append(content.profile['endings']['descriptions']['failed'])
        else: apply(challenge['success'] if success else challenge['failure'])
    apply(a['effects'])
    if name == 'talk' and a.get('option') and a['option'] not in current['npcs'][target]['topics']:
        current['npcs'][target]['topics'].append(a['option'])
    if not current['ending']:
        turn['response'] = a.get('response')
        if a.get('response'): results.append(a['response'])
    return current, results


def projection(content, game):
    content = module_content(content, game)
    scene = content.profile['scenes'][game['sceneId']]
    base = f"/api/games/{game['gameId']}/assets/"
    npcs = [{'id': key, 'name': npc['name'], 'role': npc['role'], 'spriteUrl': base + npc['sprite']} for key, npc in content.visible_npcs(game).items()]
    pending = next((t for t in reversed(game['turns']) if t['stage'] != 'completed'), None)
    ending_message = next((m['text'] for m in reversed(game['messages']) if m.get('final')), None)
    choices = [c for c in tool_choices(content, game) if c['target'] != 'self' and c['tool'] not in ('confirm_action', 'give', 'drop')]
    return {'gameId': game['gameId'], 'version': game['version'], 'module': game['module'], 'investigator': game['investigator'],
            'scene': {'id': game['sceneId'], 'name': scene['name'], 'region': scene['region'], 'backgroundUrl': base + scene['background']},
            'npc': npcs[-1] if npcs else None, 'npcs': npcs, 'inventory': game['inventory'], 'facts': game['facts'], 'messages': game['messages'],
            'suggestions': ['确认执行', '取消这次行动'] if public_pending(game) else [e['label'] for e in choices[:3]] if not game['pendingExit'] else ['确认撤离，结束本次调查', '继续调查，取消撤离'],
            'ended': bool(game['ending']), 'ending': game['ending'], 'endingSummary': ending_message, 'status': 'ended' if game['ending'] else 'active',
            'pendingAction': public_pending(game),
            'nearbyItems': [g['item'] for g in game.get('mechanics', {}).get('groundItems', []) if g['sceneId'] == game['sceneId']],
            'pendingTurn': {'requestId': pending['id'], 'text': pending['text'], 'stage': pending['stage'], **({'confirmationId': pending['confirmationId']} if pending.get('confirmationId') else {})} if pending else None}
