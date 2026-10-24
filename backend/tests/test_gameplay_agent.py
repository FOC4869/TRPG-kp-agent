"""Exercise the real provider adapter boundary without network or credentials."""
import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import AsyncMock, patch

import httpx
from openai import APIConnectionError, APIStatusError, APITimeoutError, BadRequestError

from app.services.catalogue import Catalogue
from kp_agent.gameplay.agent import DeepSeekAgent
from kp_agent.gameplay.content import GameError
from kp_agent.gameplay.runtime import GameRuntime
from kp_agent.gameplay.schema import Plan


def response(plan):
    return SimpleNamespace(status='completed', output_text=json.dumps(plan),
                           usage=SimpleNamespace(input_tokens=10, output_tokens=5))


def status_error(status):
    request = httpx.Request('POST', 'https://api.deepseek.com/responses')
    # Deliberately sensitive provider detail must not reach logs, saves or SSE.
    return APIStatusError('private-context sk-test-secret', response=httpx.Response(status, request=request),
                          body={'message': 'private-context sk-test-secret'})


class Stream:
    def __init__(self, events): self.events = events
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass
    async def __aiter__(self):
        for event in self.events: yield event


class AgentAdapterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.create = AsyncMock()
        self.agent = DeepSeekAgent()
        self.agent.client = SimpleNamespace(responses=SimpleNamespace(create=self.create), close=AsyncMock())
        self.metrics = []

    async def asyncTearDown(self): await self.agent.close()

    async def test_request_schema_is_provider_compatible_and_plan_validated(self):
        plan = {'kind': 'tool', 'tool': {'name': 'observe', 'target': 'room', 'option': None,
                                       'skill': None, 'item': None, 'approach': '观察房间'}}
        self.create.return_value = response(plan)
        self.assertEqual(await self.agent.plan({'input': '观察房间'}, self.metrics.append), plan)
        args = self.create.call_args.kwargs
        schema = args['text']['format']['schema']
        def verify(node):
            if isinstance(node, dict):
                self.assertFalse({'$defs', '$ref', 'minLength', 'maxLength'} & node.keys())
                if 'anyOf' in node:
                    for child in node['anyOf']: self.assertIn('type', child)
                if node.get('type') == 'object':
                    self.assertFalse(node['additionalProperties'])
                    self.assertEqual(set(node['required']), set(node['properties']))
                for child in node.values(): verify(child)
            elif isinstance(node, list):
                for child in node: verify(child)
        verify(schema)
        self.assertEqual(schema['properties']['kind']['enum'], list(Plan.model_fields['kind'].annotation.__args__))
        self.assertTrue(args['text']['format']['strict'])
        self.assertEqual(args['reasoning'], {'effort': 'none'})
        self.assertTrue(self.metrics[-1]['completed'])
        self.assertIn('maxLength', Plan.model_json_schema()['$defs']['ToolCall']['properties']['target'])

    async def test_local_validation_still_rejects_invalid_plans(self):
        valid = {'kind': 'tool', 'tool': {'name': 'observe', 'target': 'room', 'option': None,
                                         'skill': None, 'item': None, 'approach': ''}}
        cases = [{'kind': 'tool', 'tool': None}, {'kind': 'question', 'tool': valid['tool']},
                 {'kind': 'question', 'tool': None, 'private': 'extra'}, {'kind': 'question'}]
        for field, value in [('target', ''), ('target', 'x'*81), ('approach', 'x'*501), ('name', 'write_save')]:
            plan = copy.deepcopy(valid); plan['tool'][field] = value; cases.append(plan)
        for plan in cases:
            with self.subTest(plan=plan):
                self.create.return_value = response(plan)
                with self.assertRaises(GameError) as caught:
                    await self.agent.plan({}, self.metrics.append)
                self.assertEqual(caught.exception.code, 'model_invalid_plan')

    async def test_provider_failures_are_categorized_without_leaking_or_retrying(self):
        for status, code in [(400, 'model_request_rejected'), (422, 'model_request_rejected'),
                             (401, 'model_authentication_failed'), (402, 'model_insufficient_balance'),
                             (429, 'model_rate_limited'), (503, 'model_unavailable')]:
            with self.subTest(status=status):
                self.create.reset_mock(); self.create.side_effect = status_error(status)
                with self.assertLogs('kp_agent.gameplay.agent', level='WARNING') as logs:
                    with self.assertRaises(GameError) as caught:
                        await self.agent.plan({}, self.metrics.append)
                self.assertEqual(caught.exception.code, code)
                self.assertEqual(self.create.await_count, 1)
                self.assertFalse(self.metrics[-1]['completed'])
                public = str(caught.exception) + str(logs.output) + json.dumps(self.metrics)
                self.assertNotIn('sk-test-secret', public)
                self.assertNotIn('private-context', public)

    async def test_connection_and_timeout_classification(self):
        request = httpx.Request('POST', 'https://api.deepseek.com/responses')
        for error, code in [(APIConnectionError(request=request), 'model_connection_failed'),
                            (APITimeoutError(request=request), 'model_timeout'),
                            (TimeoutError(), 'model_timeout')]:
            with self.subTest(code=code):
                self.create.side_effect = error
                with self.assertLogs('kp_agent.gameplay.agent', level='WARNING'):
                    with self.assertRaises(GameError) as caught:
                        await self.agent.narrate({}, lambda delta: None, self.metrics.append)
                self.assertEqual(caught.exception.code, code)

    async def test_genuine_stream_deltas_and_terminal_failure(self):
        final = SimpleNamespace(status='completed', usage=None)
        self.create.return_value = Stream([SimpleNamespace(type='response.output_text.delta', delta='门后'),
                                          SimpleNamespace(type='response.output_text.delta', delta='很安静。'),
                                          SimpleNamespace(type='response.completed', response=final)])
        chunks = []
        text = await self.agent.narrate({}, chunks.append, self.metrics.append)
        self.assertEqual(text, '门后很安静。'); self.assertEqual(chunks, ['门后', '很安静。'])
        self.assertTrue(self.create.call_args.kwargs['stream'])
        for event in ('response.failed', 'response.incomplete', 'error'):
            self.create.return_value = Stream([SimpleNamespace(type=event)])
            with self.assertRaises(GameError) as caught:
                await self.agent.narrate({}, chunks.append, self.metrics.append)
            self.assertEqual(caught.exception.code, 'model_incomplete')

    async def test_rejected_request_recovers_same_turn_without_duplicating_state(self):
        with TemporaryDirectory() as temp:
            runtime = GameRuntime(Catalogue(), Path(temp), self.agent)
            try:
                game = runtime.create(str(uuid.uuid4()), 'darkness-beneath-the-hill', 'jessica')
                request = str(uuid.uuid4())
                self.create.side_effect = BadRequestError('private-context sk-test-secret',
                    response=httpx.Response(400, request=httpx.Request('POST', 'https://api.deepseek.com/responses')),
                    body={'message': 'Invalid json schema: field anyOf: missing field type'})
                with self.assertLogs('kp_agent.gameplay.agent', level='WARNING'):
                    job = await runtime.action(game['gameId'], request, '看看房间', game['version'])
                    await job.task
                saved = runtime.read(game['gameId'])
                self.assertEqual(job.events[-1]['code'], 'model_request_rejected')
                self.assertEqual(saved['turns'][-1]['errorCode'], 'model_request_rejected')
                self.assertIsNone(saved['turns'][-1]['plan'])
                self.assertFalse(saved['turns'][-1]['committed'])
                self.assertEqual(saved['turns'][-1]['rolls'], [])
                self.assertEqual(saved['version'], game['version'])
                self.assertNotIn('sk-test-secret', json.dumps(saved) + json.dumps(job.events))
                self.create.side_effect = None
                self.create.return_value = response({'kind': 'question', 'tool': None})
                with patch.object(self.agent, 'narrate', new=AsyncMock(return_value='房间很安静。')):
                    job = await runtime.action(game['gameId'], request, '看看房间', game['version'])
                    await job.task
                self.assertEqual(job.events[-1]['type'], 'turn.completed')
                restored = runtime.get(game['gameId'])
                self.assertEqual(len([m for m in restored['messages'] if m['kind'] == 'player']), 1)
                self.assertEqual(restored['version'], game['version'] + 1)
            finally: await runtime.close()
