import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.api.games import get_runtime
from app.services.catalogue import Catalogue
from kp_agent.gameplay.runtime import GameRuntime
from tests.test_web_game import Agent, MODULE

class HttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.runtime = GameRuntime(Catalogue(), Path(self.temp.name), Agent())
        app.dependency_overrides[get_runtime] = lambda: self.runtime
        self.client = TestClient(app); self.client.__enter__()
    def tearDown(self):
        self.client.portal.call(self.runtime.close)
        self.client.__exit__(None, None, None)
        app.dependency_overrides.clear(); self.temp.cleanup()
    def create(self):
        response = self.client.post('/api/games', json={'requestId': str(uuid.uuid4()), 'moduleId': MODULE, 'investigatorId': 'stephen'})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()
    def test_http_stream_and_assets(self):
        game = self.create(); base = '/api/games/' + game['gameId']
        with self.client.stream('POST', base + '/actions', json={'requestId': str(uuid.uuid4()), 'text': 'explore_now', 'expectedVersion': 1}) as response:
            self.assertEqual(response.status_code, 200)
            self.assertIn('text/event-stream', response.headers['content-type'])
            frames = [json.loads(line[6:]) for line in response.iter_lines() if line.startswith('data: ')]
        self.assertEqual(frames[-1]['type'], 'turn.completed')
        self.assertEqual([event['seq'] for event in frames], list(range(1, len(frames)+1)))
        fresh = self.client.get(base).json()
        self.assertEqual(fresh['scene']['id'], 'house_cellar')
        self.assertEqual(self.client.get(fresh['scene']['backgroundUrl']).status_code, 200)
        self.assertEqual(self.client.get(base+'/assets/bg_cage_area').status_code, 404)
        self.assertEqual(self.client.get(base+'/assets/story.md').status_code, 404)
        self.assertEqual(self.client.get(base+'/assets/%2e%2e%2fstory.md').status_code, 404)
        self.assertEqual(self.client.get('/api/games/../../data/modules').status_code, 404)
        stale = self.client.post(base+'/actions', json={'requestId': str(uuid.uuid4()), 'text':'question', 'expectedVersion':1})
        self.assertEqual(stale.status_code, 409)
    def test_schema_invalid_and_not_found(self):
        game = self.create(); base = '/api/games/' + game['gameId']
        for body in [{'requestId': 'bad', 'text':'x', 'expectedVersion':1}, {'requestId':str(uuid.uuid4()),'text':' ', 'expectedVersion':1}, {'requestId':str(uuid.uuid4()),'text':'x'*1001,'expectedVersion':1}, {'requestId':str(uuid.uuid4()),'text':'x','expectedVersion':True}]:
            self.assertEqual(self.client.post(base+'/actions',json=body).status_code, 422)
        self.assertEqual(self.client.get('/api/games/'+'0'*32).status_code, 404)
    def test_worker_lock_and_disk_damage_are_explicit(self):
        from kp_agent.gameplay.content import GameError
        with self.assertRaises(GameError): GameRuntime(Catalogue(), Path(self.temp.name), Agent())
        game = self.create(); path = self.runtime.store.path(game['gameId']); path.write_text('{}')
        response = self.client.get('/api/games/'+game['gameId'])
        self.assertEqual(response.status_code, 503)
        self.assertEqual(path.read_text(), '{}')

class SecondModuleHttpTests(unittest.TestCase):
    def setUp(self):
        from tests.test_module_runtime import fixture_catalogue, ToolAgent
        self.temp = TemporaryDirectory()
        root = Path(self.temp.name)
        self.runtime = GameRuntime(fixture_catalogue(root/'data'), root/'saves', ToolAgent())
        app.dependency_overrides[get_runtime] = lambda: self.runtime
        self.client = TestClient(app); self.client.__enter__()
    def tearDown(self):
        self.client.portal.call(self.runtime.close)
        self.client.__exit__(None, None, None)
        app.dependency_overrides.clear(); self.temp.cleanup()
    def test_data_only_module_uses_same_http_sse_and_assets(self):
        from tests.test_module_runtime import MODULE as OTHER, call
        response = self.client.post('/api/games', json={'requestId':str(uuid.uuid4()),'moduleId':OTHER,'investigatorId':'jessica'})
        self.assertEqual(response.status_code, 200, response.text)
        game=response.json();base='/api/games/'+game['gameId']
        self.assertEqual(game['module']['englishTitle'], 'The Silent Observatory')
        self.assertEqual(self.client.get(game['scene']['backgroundUrl']).status_code,200)
        self.assertEqual(self.client.get(base+'/assets/bg-vault').status_code,404)
        plan=call('take','key')
        response=self.client.post(base+'/actions',json={'requestId':str(uuid.uuid4()),'text':json.dumps(plan),'expectedVersion':game['version']})
        frames=[json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
        self.assertEqual(frames[-1]['type'],'turn.completed')
        self.assertIn('brass_key',[i['id'] for i in frames[-1]['state']['inventory']])
        self.assertEqual(self.client.get(base).json(),frames[-1]['state'])
        self.assertNotIn('hatch_open',json.dumps(frames,ensure_ascii=False))

    def test_expanded_library_scene_uses_real_asset_and_same_event_contract(self):
        from tests.test_module_runtime import DARKNESS, call
        response=self.client.post('/api/games',json={'requestId':uuid.uuid4().hex,'moduleId':DARKNESS,'investigatorId':'jessica'})
        self.assertEqual(response.status_code,200,response.text)
        game=response.json();base='/api/games/'+game['gameId']
        self.assertEqual(self.client.get(base+'/assets/bg_john_hay_library').status_code,404)
        response=self.client.post(base+'/actions',json={'requestId':uuid.uuid4().hex,'text':json.dumps(call('move','john_hay_library')),'expectedVersion':game['version']})
        frames=[json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
        self.assertEqual(frames[-1]['type'],'turn.completed')
        state=frames[-1]['state'];self.assertEqual(state['scene']['id'],'john_hay_library')
        self.assertEqual(self.client.get(state['scene']['backgroundUrl']).status_code,200)
        self.assertEqual(self.client.get(base).json(),state)
        self.assertNotIn('harper_testament',json.dumps(frames,ensure_ascii=False))
        self.assertEqual(self.runtime.read(game['gameId'])['profile']['version'],'4.0.0')

    def test_damage_confirmation_http_recovery_and_request_identity(self):
        from tests.test_module_runtime import DARKNESS, call
        game=self.client.post('/api/games',json={'requestId':str(uuid.uuid4()),'moduleId':DARKNESS,'investigatorId':'chris'}).json()
        base='/api/games/'+game['gameId'];hp=game['investigator']['resources']['hp']
        raw=self.runtime.read(game['gameId'])
        machete=next(key for key,item in raw['mechanics']['items'].items() if item['sourceId']=='machete')
        request={'requestId':str(uuid.uuid4()),'text':json.dumps(call('use_item','self','harm',item=machete)),'expectedVersion':game['version']}
        with patch('kp_agent.gameplay.engine.roll',side_effect=AssertionError('confirmation first')):
            response=self.client.post(base+'/actions',json=request)
        frames=[json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
        self.assertEqual(frames[-1]['type'],'turn.completed')
        state=self.client.get(base).json();confirmation=state['pendingAction']['id']
        self.assertEqual(state['investigator']['resources']['hp'],hp)
        decision={'requestId':str(uuid.uuid4()),'text':'确认执行','expectedVersion':state['version'],'confirmationId':confirmation}
        self.runtime.agent.fail=True
        with patch('kp_agent.gameplay.engine.roll',return_value=SimpleNamespace(total=3)):
            response=self.client.post(base+'/actions',json=decision)
        frames=[json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
        self.assertEqual(frames[-1]['type'],'turn.failed')
        self.assertEqual(len([f for f in frames if f['type']=='effect.resolved']),1)
        fresh=self.client.get(base).json()
        self.assertIsNone(fresh['pendingAction']);self.assertEqual(fresh['pendingTurn']['confirmationId'],confirmation)
        self.assertEqual(fresh['investigator']['resources']['hp'],hp-3)
        without_id={k:v for k,v in decision.items() if k!='confirmationId'}
        self.assertEqual(self.client.post(base+'/actions',json=without_id).status_code,409)
        self.runtime.agent.fail=False
        with patch('kp_agent.gameplay.engine.roll',side_effect=AssertionError('must not reroll')):
            response=self.client.post(base+'/actions',json=decision)
        self.assertIn('event: turn.completed',response.text)
        state=self.client.get(base).json();self.assertIsNone(state['pendingTurn'])
        self.assertEqual(len([m for m in state['messages'] if m['kind']=='effect']),1)
        self.assertEqual(state['investigator']['resources']['hp'],hp-3)
        decision['requestId']=str(uuid.uuid4());decision['expectedVersion']=state['version']
        rejected=self.client.post(base+'/actions',json=decision)
        self.assertEqual(rejected.status_code,409)
        self.assertEqual(rejected.json()['detail']['code'],'confirmation_expired')
