"""LangGraph orchestration, per-game serialization and detachable event streams."""
from __future__ import annotations
import asyncio
import copy
import uuid
from collections import defaultdict
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from .agent import DeepSeekAgent
from .content import Content, GameError
from .engine import event_choices, execute, projection, scene_description
from .store import JsonStore

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

    async def action(self, game_id, request_id, text, expected_version):
        async with self.locks[game_id]:
            game = self.read(game_id)
            turn = next((t for t in game['turns'] if t['id'] == request_id), None)
            if turn:
                if turn['text'] != text: raise GameError('request_conflict', '相同请求 ID 的行动内容不能改变。')
                job = self.jobs.get((game_id, request_id))
                if job and not job.done: return job
                if turn['stage'] == 'completed':
                    job = EventJob(request_id)
                    job.emit('state.updated', state=projection(self.content, game))
                    job.emit('turn.completed', state=projection(self.content, game)); job.done = True
                    return job
            else:
                if any(t['stage'] != 'completed' for t in game['turns']):
                    raise GameError('turn_pending', '上一行动尚未确认，请先恢复原回合。')
                if game['ending']: raise GameError('game_ended', '本次调查已结束。')
                if expected_version != game['version']: raise GameError('version_conflict', '游戏状态已经更新，请重新读取后再行动。')
                turn = {'id': request_id, 'text': text, 'stage': 'accepted', 'plan': None, 'rolls': [], 'committed': False,
                        'results': [], 'metrics': [], 'messageId': request_id + ':keeper'}
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
            scene = self.content.profile['scenes'][game['sceneId']]
            context = {'input': turn['text'], 'scene': {**scene, 'public': scene_description(self.content, game), 'id': game['sceneId']},
                       'legalEvents': event_choices(self.content, game), 'facts': game['facts'],
                       'resources': game['investigator']['resources'], 'inventory': [i['name'] for i in game['inventory']],
                       'timeline': game['flags']['timeline'], 'exitPending': game['flags'].get('exit_pending', False),
                       'recent': game['messages'][-12:]}
            turn['plan'] = await self.agent.plan(context, lambda metric: self._metric(state, metric))
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
        job.emit('state.updated', state=projection(self.content, state['game']))
        return state

    async def _narrate(self, state):
        game, turn = state['game'], state['turn']
        job = self._job(state)
        turn['stage'] = 'narrating'; self._save(state)
        job.emit('turn.status', stage='narrating')
        job.emit('message.started', message={'id': turn['messageId'], 'kind': 'keeper', 'speaker': '守秘人', 'text': ''})
        public = projection(self.content, game)
        context = {'input': turn['text'], 'kind': turn['plan']['kind'], 'results': turn['results'],
                   'scene': scene_description(self.content, game), 'facts': game['facts'],
                   'currentResources': game['investigator']['resources'], 'npcs': public['npcs'],
                   'joshStatus': game['npcs']['josh']['stage'], 'timeline': game['flags']['timeline'],
                   'ending': game['ending'], 'committedProgress': {key: game['flags'].get(key, False) for key in ('threat_passed', 'cage_open', 'final_solved', 'exit_pending', 'force_offered')}, 'legalNextActions': public['suggestions'], 'recent': game['messages'][-12:]}
        event_id = turn.get('executedEvent', turn['plan'].get('eventId'))
        # These prompts seek authorization for a later action. A deterministic
        # confirmation cannot accidentally narrate that future action as done.
        if event_id == 'end_request' and not game['ending'] and game['flags'].get('exit_pending'):
            text = '\n'.join(turn['results']) + '\n你要确认撤离，还是继续调查？'
        elif event_id == 'force_offer' and not game['ending']:
            text = '强行通过会损失固定3点HP，目前尚未扣除。明确确认后才执行；你也可以选择其他方法，或沿来路撤离。'
        else:
            text = await self.agent.narrate(context, lambda delta: job.emit('message.delta', messageId=turn['messageId'], delta=delta), lambda metric: self._metric(state, metric))
        if event_id in ('end_request', 'force_offer') and not game['ending']:
            job.emit('message.delta', messageId=turn['messageId'], delta=text)
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
