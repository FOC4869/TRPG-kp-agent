"""Validated event tools. Only this module applies configured world effects."""
from __future__ import annotations
import copy
import random
from trpg.check import coc_check
from trpg.dice import roll
from .content import GameError


def matches(game, condition, checks=None):
    for key, value in condition.items():
        if key == 'all': actual = all(matches(game, c, checks) for c in value); value = True
        elif key == 'any': actual = any(matches(game, c, checks) for c in value); value = True
        elif key == 'not': actual = not matches(game, value, checks); value = True
        elif key.startswith('flag:'): actual = game['flags'].get(key[5:], False)
        elif key.startswith('item:'): actual = any(i['id'] == key[5:] for i in game['inventory'])
        elif key.startswith('check:'): actual = (checks or {}).get(key[6:])
        else: raise ValueError('Unknown configuration condition')
        if actual != value: return False
    return True


def legal_events(content, game):
    if game['ending']: return []
    return [e for e in content.events.values()
            if ('*' in e['scenes'] or game['sceneId'] in e['scenes'])
            and (e['repeat'] == 'always' or e['id'] not in game['attempts'])
            and matches(game, e['requires'])]


def event_choices(content, game):
    return [{'id': e['id'], 'label': e['label'], 'description': e['description']} for e in legal_events(content, game)]


def scene_description(content, game):
    """Initial scene prose must not override later committed facts."""
    scene_id, flags = game['sceneId'], game['flags']
    josh = game['npcs']['josh']['stage']
    text = content.profile['scenes'][scene_id]['public']
    if scene_id == 'cage_area':
        text = '阴冷的石室内排列着锈蚀铁笼。'
        text += ('你已经通过蛇形生物的威胁，可以接近铁笼，不需要再次突破。' if flags.get('threat_passed')
                 else '一个尚未完全清醒的蛇形身影阻挡着通往铁笼的路。')
        text += '铁笼已经打开。' if flags.get('cage_open') else '铁笼尚未打开。'
        if flags['timeline'] == 'together':
            text += '乔什始终与你同行，没有被囚禁，无需营救。'
        elif josh == 'following':
            text += '你已经救出乔什，他现在跟随你，需要你照顾。'
        else:
            text += '失踪的乔什就在铁笼中，尚未被你帮助离开。'
        text += '退回入口厅的来路始终畅通，撤离不需要再次通过威胁。'
    if scene_id == 'house_cellar' and flags['timeline'] == 'missing' and josh == 'missing':
        text += '乔什不在这里，足迹通向地下；他目前仍失踪。'
    if game['ending']:
        text += {'completed': '调查完成，调查员与乔什均已安全返回地面。',
                 'retreated': '调查尚未完成，但玩家已明确结束并返回地面。',
                 'failed': '调查员HP或SAN已归零，调查失败。'}[game['ending']]
    return text


def end_game(game, failed=False):
    completed = (game['flags'].get('final_solved') and game['npcs']['josh']['stage'] == 'following')
    game['ending'] = 'failed' if failed else 'completed' if completed else 'retreated'
    if not failed:
        game['sceneId'] = 'winscott_house'
        if 'winscott_house' not in game['visited']:
            game['visited'].append('winscott_house')
        game['npcs']['josh']['location'] = 'winscott_house' if game['npcs']['josh']['stage'] == 'following' else game['npcs']['josh']['location']


def execute(content, game, turn, persist_roll, rng=None):
    """Replay effects on a copy, using durable rolls, then commit the whole copy."""
    rng = rng or random.SystemRandom()
    plan = turn['plan']
    current = copy.deepcopy(game)
    results = []
    if plan['kind'] != 'event':
        return current, ['本轮未执行世界行动，也未改变资源或剧情。']
    event = content.events.get(plan['eventId'])
    if not event or event not in legal_events(content, current):
        turn['executedEvent'] = None
        return current, ['该行动当前不可执行：目标、前提不满足或已尝试。请根据目前可见信息选择下一步。']
    turn['executedEvent'] = event['id']
    current['attempts'].append(event['id'])
    checks = {}
    for effect in event['effects']:
        if not matches(current, effect.get('when', {}), checks): continue
        op = effect['op']
        if op == 'flag':
            current['flags'][effect['key']] = effect['value']
            results.append(f"{effect['key']} = {effect['value']}")
        elif op == 'move':
            current['sceneId'] = effect['to']
            if effect['to'] not in current['visited']: current['visited'].append(effect['to'])
            if current['npcs']['josh']['stage'] == 'following': current['npcs']['josh']['location'] = effect['to']
            results.append('到达：' + content.profile['scenes'][effect['to']]['name'])
        elif op == 'josh':
            current['npcs']['josh']['stage'] = effect['stage']
            current['npcs']['josh']['location'] = 'cage_area' if effect['stage'] == 'missing' else current['sceneId']
            results.append('乔什状态：' + effect['stage'])
        elif op == 'clue':
            fact = {'id': effect['key'], 'title': effect['title'], 'text': effect['text']}
            if not any(f['id'] == fact['id'] for f in current['facts']): current['facts'].append(fact)
            if event['id'].startswith('talk_'): current['npcs']['josh']['topics'].append(event['id'])
            results.append(fact['text'])
        elif op == 'item':
            if not any(i['id'] == effect['key'] for i in current['inventory']):
                current['inventory'].append({'id': effect['key'], 'name': effect['name'], 'quantity': 1, 'kind': 'carried', 'note': '从宅邸地窖领取'})
            results.append('已带上：' + effect['name'])
        elif op == 'check':
            key = effect['key']
            recorded = next((r for r in turn['rolls'] if r['key'] == key), None)
            if recorded is None:
                skill = effect['skill']
                inv = current['investigator']
                target = inv['resources']['san'] if skill == 'SAN' else inv['attributes'][skill] if skill in inv['attributes'] else next(s['value'] for s in inv['skills'] if s['name'] == skill)
                result = coc_check(target, rng=rng)
                loss = effect.get('failureLoss') if not result.success else None
                details = []
                if loss:
                    amount = roll(loss['dice'].lower(), rng).total
                    details.append({'resource': loss['resource'], 'dice': loss['dice'], 'amount': amount})
                recorded = {'key': key, 'checkId': turn['id'] + ':' + key, 'skill': skill, 'target': target,
                            'roll': result.roll, 'success': result.success, 'result': '成功' if result.success else '失败',
                            'reason': effect['reason'], 'details': details}
                turn['rolls'].append(recorded)
                persist_roll()  # Must succeed before any observable effect.
            checks[key] = recorded['success']
            current['messages'].append({'id': recorded['checkId'], 'kind': 'check', 'speaker': '规则检定', 'text': recorded['reason'], 'check': copy.deepcopy(recorded)})
            results.append(f"{recorded['skill']}检定：{recorded['roll']}/{recorded['target']}，{recorded['result']}")
            for loss in recorded['details']:
                resource = loss['resource']
                current['investigator']['resources'][resource] = max(0, current['investigator']['resources'][resource] - loss['amount'])
                results.append(f"{resource}损失{loss['dice']}={loss['amount']}")
        elif op == 'loss':
            resource = effect['resource']
            current['investigator']['resources'][resource] = max(0, current['investigator']['resources'][resource] - effect['amount'])
            results.append(f"明确代价：{resource}减少{effect['amount']}")
        elif op == 'request_exit':
            if current['sceneId'] in ('winscott_house', 'house_cellar'):
                end_game(current)
            else:
                current['flags']['exit_pending'] = True
                results.append('尚未撤离。来路始终可走，无需再次突破威胁；请确认是否返回地面并结束本次调查。')
                results.append('乔什正在跟随你，确认后将与你安全返回。' if current['npcs']['josh']['stage'] == 'following'
                               else '乔什尚未获救，确认撤离将把他留在地下。')
        elif op == 'end': end_game(current)
        else: raise ValueError('Unknown configuration effect')
        resources = current['investigator']['resources']
        if resources['hp'] <= 0 or resources['san'] <= 0:
            end_game(current, failed=True)
            results.append('HP或SAN归零，调查失败。')
            break
    if event['id'] == 'force_offer': results.append('强行通过需承受固定3点HP损失；尚未扣除，请明确确认后才能执行。')
    return current, results


def projection(content, game):
    scene = content.profile['scenes'][game['sceneId']]
    base = f"/api/games/{game['gameId']}/assets/"
    npcs = []
    josh = game['npcs']['josh']
    if josh['stage'] in ('at_home', 'following') and josh['location'] == game['sceneId']:
        npcs.append({'id': 'josh', 'name': '乔什·文斯考特', 'role': '作家 · 同行者' if josh['stage'] == 'following' else '作家 · 邀请人', 'spriteUrl': base + 'sprite_josh_base'})
    if game['sceneId'] == 'cage_area':
        if not game['flags'].get('threat_passed'):
            npcs.append({'id': 'serpent', 'name': '蛇形生物', 'role': '挡住去路的身影', 'spriteUrl': base + 'sprite_ssyaa_hrisss_base'})
        elif josh['stage'] == 'missing':
            npcs.append({'id': 'josh', 'name': '乔什·文斯考特', 'role': '铁笼中的失踪者', 'spriteUrl': base + 'sprite_josh_base'})
    pending = next((t for t in reversed(game['turns']) if t['stage'] != 'completed'), None)
    ending_message = next((m['text'] for m in reversed(game['messages']) if m.get('final')), None)
    choices = event_choices(content, game)
    preferred = choices[:3]
    # Progress suggestions stay useful after optional observations have been exhausted.
    return {'gameId': game['gameId'], 'version': game['version'], 'module': game['module'], 'investigator': game['investigator'],
            'scene': {'id': game['sceneId'], 'name': scene['name'], 'region': '普罗维登斯 · 学院山', 'backgroundUrl': base + scene['background']},
            'npc': npcs[-1] if npcs else None, 'npcs': npcs, 'inventory': game['inventory'], 'facts': game['facts'], 'messages': game['messages'],
            'suggestions': [e['label'] for e in preferred], 'ended': bool(game['ending']), 'ending': game['ending'],
            'endingSummary': ending_message, 'status': 'ended' if game['ending'] else 'active',
            'pendingTurn': {'requestId': pending['id'], 'text': pending['text'], 'stage': pending['stage']} if pending else None}
