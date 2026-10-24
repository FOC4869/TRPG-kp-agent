"""LangGraph orchestration, per-game serialization and detachable event streams."""
from __future__ import annotations
import asyncio
import copy
import uuid
from collections import defaultdict
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from .agent import DeepSeekAgent, Plan
from .content import Content, GameError
from .engine import tool_choices, execute, projection, scene_description, exit_response
from .store import JsonStore
from .common_actions import public_pending

class GraphState(TypedDict):
    game: dict
    turn: dict

class EventJob:
    def __init__(self, turn_id):
        self.turn_id = turn_id
        self.events = []
        self.changed = asyncio.Event()
        self.task = None
        self.done = False

    def emit(self, kind, **data):
        self.events.append({'type': kind, 'turnId': self.turn_id, 'seq': len(self.events) + 1, **data})
        self.changed.set()

    async def stream(self):
        index = 0
        while True:
            self.changed.clear()
            while index < len(self.events):
                yield self.events[index]
                index += 1
            if self.done: return
            try: await asyncio.wait_for(self.changed.wait(), 15)
            except TimeoutError: yield None  # heartbeat; no token event persistence required

class GameRuntime:
    def __init__(self, catalogue, root, agent=None):
        self.content = Content(catalogue)
        self.store = JsonStore(root)
        self.agent = agent or DeepSeekAgent()
        self.locks = defaultdict(asyncio.Lock)
        self.jobs = {}
        self.graph = self._graph()

    def read(self, game_id):
        game = self.store.load(game_id)
        self.content.validate(game)
        return game

    def get(self, game_id):
        return projection(self.content, self.read(game_id))

    def create(self, request_id, module_id, investigator_id):
        game_id = uuid.uuid5(uuid.NAMESPACE_URL, 'coc-mvp:' + request_id).hex
        with self.store.mutex:
            if self.store.path(game_id).exists():
                game = self.read(game_id)
                if game['creation'] != {'requestId': request_id, 'moduleId': module_id, 'investigatorId': investigator_id}:
                    raise GameError('request_conflict', '相同创建请求不能用于不同人物或案件。')
            else:
                game = self.content.initialize(game_id, request_id, module_id, investigator_id)
                self.store.save(game)
        return projection(self.content, game)

    async def action(self, game_id, request_id, text, expected_version, confirmation_id=None):
        async with self.locks[game_id]:
            game = self.read(game_id)
            turn = next((t for t in game['turns'] if t['id'] == request_id), None)
            if turn:
                if turn['text'] != text or turn.get('confirmationId') != confirmation_id: raise GameError('request_conflict', '相同请求 ID 的行动内容不能改变。')
                job = self.jobs.get((game_id, request_id))
                if job and not job.done: return job
                if turn['stage'] == 'completed':
                    job = EventJob(request_id)
                    job.emit('state.updated', state=projection(self.content, game))
                    job.emit('turn.completed', state=projection(self.content, game)); job.done = True
                    return job
            else:
                pending = public_pending(game)
                if confirmation_id and (not pending or pending['id'] != confirmation_id):
                    raise GameError('confirmation_expired', '这次确认已经失效，请重新读取当前调查。')
                if confirmation_id and text not in ('确认执行', '取消这次行动'):
                    raise GameError('confirmation_invalid', '请选择继续或取消，或直接描述新的行动。')
                if any(t['stage'] != 'completed' for t in game['turns']):
                    raise GameError('turn_pending', '上一行动尚未确认，请先恢复原回合。')
                if game['ending']: raise GameError('game_ended', '本次调查已结束。')
                if expected_version != game['version']: raise GameError('version_conflict', '游戏状态已经更新，请重新读取后再行动。')
                turn = {'id': request_id, 'text': text, 'stage': 'accepted', 'plan': None, 'rolls': [], 'committed': False,
                        'results': [], 'metrics': [], 'confirmationId': confirmation_id, 'messageId': request_id + ':keeper'}
                game['turns'].append(turn)
                game['messages'].append({'id': request_id + ':player', 'kind': 'player', 'speaker': game['investigator']['displayName'], 'text': text})
                self.store.save(game)
            job = EventJob(request_id)
            self.jobs[(game_id, request_id)] = job
            job.task = asyncio.create_task(self._run(game_id, request_id, job))
            return job

    def _graph(self):
        graph = StateGraph(GraphState)
        graph.add_node('understand', self._understand)
        graph.add_node('execute_tools', self._execute)
        graph.add_node('narrate', self._narrate)
        graph.add_edge(START, 'understand'); graph.add_edge('understand', 'execute_tools')
        graph.add_edge('execute_tools', 'narrate'); graph.add_edge('narrate', END)
        return graph.compile()

    def _job(self, state): return self.jobs[(state['game']['gameId'], state['turn']['id'])]

    def _save(self, state):
        game, turn = state['game'], state['turn']
        game['turns'] = [turn if t['id'] == turn['id'] else t for t in game['turns']]
        self.store.save(game)

    def _metric(self, state, metric):
        state['turn']['metrics'].append(metric)
        self._save(state)

    async def _understand(self, state):
        game, turn = state['game'], state['turn']
        if turn['plan'] is None:
            self._job(state).emit('turn.status', stage='understanding')
            content = self.content.for_game(game)
            scene = content.profile['scenes'][game['sceneId']]
            context = {'input': turn['text'], 'scene': {'id': game['sceneId'], 'name': scene['name'], 'public': scene_description(content, game), 'keeper': scene['keeper']},
                       'availableTools': tool_choices(content, game), 'entities': {key: {'name': e['name'], 'public': e['public']} for key, e in content.entities(game).items()}, 'npcs': content.knowledge(game),
                       'facts': game['facts'], 'resources': game['investigator']['resources'], 'inventory': game['inventory'],
                       'pendingExit': game['pendingExit'], 'pendingAction': public_pending(game), 'nearbyItems': projection(self.content, game)['nearbyItems'], 'recent': game['messages'][-12:]}
            if turn.get('confirmationId'):
                turn['plan'] = {'kind': 'tool', 'tool': {'name': 'confirm_action', 'target': turn['confirmationId'], 'option': 'confirm' if turn['text'] == '确认执行' else 'cancel', 'skill': None, 'item': None, 'approach': turn['text']}}
            else:
                turn['plan'] = Plan.model_validate(await self.agent.plan(context, lambda metric: self._metric(state, metric))).model_dump()
            turn['stage'] = 'planned'; self._save(state)
        return state

    async def _execute(self, state):
        game, turn = state['game'], state['turn']
        job = self._job(state)
        if not turn['committed']:
            job.emit('turn.status', stage='resolving')
            committed, results = execute(self.content, game, turn, lambda: self._save(state))
            committed['version'] += 1
            turn['results'], turn['committed'], turn['stage'] = results, True, 'committed'
            state['game'] = committed
            self._save(state)
        # Publish only durable checks/effects. Reconnect clients deduplicate checkId.
        for result in turn['rolls']:
            job.emit('check.started', check={k: result[k] for k in ('checkId', 'skill', 'target', 'reason')})
            job.emit('check.resolved', check=result)
        for result in turn.get('damageRolls', []):
            job.emit('effect.resolved', effect={k: v for k, v in result.items() if k != 'key'})
        job.emit('state.updated', state=projection(self.content, state['game']))
        return state

    async def _narrate(self, state):
        game, turn = state['game'], state['turn']
        job = self._job(state)
        turn['stage'] = 'narrating'; self._save(state)
        job.emit('turn.status', stage='narrating')
        job.emit('message.started', message={'id': turn['messageId'], 'kind': 'keeper', 'speaker': '守秘人', 'text': ''})
        public = projection(self.content, game)
        content = self.content.for_game(game)
        context = {'input': turn['text'], 'kind': turn['plan']['kind'], 'outcome': turn.get('outcome'), 'pendingAction': public_pending(game), 'results': turn['results'],
                   'scene': scene_description(content, game), 'facts': game['facts'], 'inventory': game['inventory'],
                   'currentResources': game['investigator']['resources'], 'npcs': content.knowledge(game),
                   'visibleEntities': [e['public'] for e in content.entities(game).values()],
                   'ending': game['ending'], 'legalNextActions': public['suggestions'], 'recent': game['messages'][-12:]}
        response = turn.get('response')
        # Compatible old committed turns may predate the saved deterministic response.
        if not response and turn.get('executedEvent') and not game['ending']:
            call = turn['plan'].get('tool') or {}
            if call.get('name') == 'finish' and call.get('option') == 'request' and game['pendingExit']:
                response = exit_response(content, game)
            else:
                response = next((a.get('response') for a in content.affordances if a['tool'] == call.get('name') and a['target'] == call.get('target') and a.get('option') == call.get('option')), None)
        if response and not game['ending']:
            text = response
            job.emit('message.delta', messageId=turn['messageId'], delta=text)
        else:
            text = await self.agent.narrate(context, lambda delta: job.emit('message.delta', messageId=turn['messageId'], delta=delta), lambda metric: self._metric(state, metric))
        message = {'id': turn['messageId'], 'kind': 'keeper', 'speaker': '守秘人', 'text': text, 'final': bool(game['ending'])}
        game['messages'].append(message)
        turn['stage'] = 'completed'
        self._save(state)
        job.emit('message.completed', message=message)
        job.emit('turn.completed', state=projection(self.content, game))
        return state

    async def _run(self, game_id, request_id, job):
        job.emit('turn.started')
        try:
            game = self.read(game_id)
            turn = next(t for t in game['turns'] if t['id'] == request_id)
            async with asyncio.timeout(120):
                await self.graph.ainvoke({'game': game, 'turn': turn})
        except (Exception, asyncio.CancelledError) as error:
            # Reload the last durable checkpoint: LangGraph may have replaced game.
            try:
                game = self.read(game_id)
                turn = next(t for t in game['turns'] if t['id'] == request_id)
                turn['errorPhase'] = turn['stage']; turn['stage'] = 'failed'
                turn['errorType'] = type(error).__name__
                turn['errorCode'] = error.code if isinstance(error, GameError) else 'turn_interrupted'
                self.store.save(game)
            except Exception:
                pass  # Preserve disk evidence; report failure, never fabricate success.
            job.emit('turn.failed', code=error.code if isinstance(error, GameError) else 'turn_interrupted',
                     message=error.message if isinstance(error, GameError) else '回应未完成。请重新读取并恢复原回合；已结算结果会保留。')
        finally:
            job.done = True; job.changed.set()
            self.jobs.pop((game_id, request_id), None)

    async def close(self):
        tasks = [j.task for j in self.jobs.values() if j.task and not j.task.done()]
        for task in tasks: task.cancel()
        if tasks: await asyncio.gather(*tasks, return_exceptions=True)
        await self.agent.close()
        self.store.close()
