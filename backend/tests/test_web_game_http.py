import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import uuid
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
