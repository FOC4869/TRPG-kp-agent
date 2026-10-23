"""Playable routes, durable idempotency, fault recovery and public boundaries."""
import asyncio
import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import uuid
from unittest.mock import patch
from app.services.catalogue import Catalogue
from kp_agent.gameplay.content import GameError
from kp_agent.gameplay.runtime import GameRuntime

MODULE = 'darkness-beneath-the-hill'
class Agent:
    def __init__(self): self.calls = []; self.fail_narration = False; self.wait = None
    async def plan(self, context, metric):
        self.calls.append('plan')
        if self.wait: await self.wait.wait()
        text = context['input']
        return {'kind': 'event' if text != 'question' else 'question', 'eventId': text if text != 'question' else None}
    async def narrate(self, context, emit, metric):
        self.calls.append('narrate')
        if self.fail_narration: raise TimeoutError()
        text = '已记录：' + '；'.join(context['results'])
        emit(text[:5]); emit(text[5:]); return text
    async def close(self): pass

class WebGameTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = TemporaryDirectory(); self.agent = Agent()
        self.runtime = GameRuntime(Catalogue(), Path(self.temp.name), self.agent)
        self.game = self.runtime.create(str(uuid.uuid4()), MODULE, 'jessica')
    async def asyncTearDown(self):
        await self.runtime.close(); self.temp.cleanup()
    async def act(self, text, request_id=None, version=None):
        job = await self.runtime.action(self.game['gameId'], request_id or str(uuid.uuid4()), text, self.game['version'] if version is None else version)
        if job.task: await job.task
        self.game = self.runtime.get(self.game['gameId'])
        self.assertNotEqual(job.events[-1]['type'], 'turn.failed', job.events)
        return job
    async def route(self, timeline):
        for e in [timeline, 'take_rope', 'take_crowbar', 'enter_tunnel', 'enter_hall', 'rope_rubble', 'enter_cages', 'force_offer', 'force_pass', 'open_crowbar']: await self.act(e)
    async def test_all_ten_templates_isolation_and_creation_idempotence(self):
        ids = Catalogue().publication(MODULE).investigatorIds
        self.assertEqual(len(ids), 10)
        for investigator in ids:
            request = str(uuid.uuid4()); game = self.runtime.create(request, MODULE, investigator)
            self.assertGreater(game['investigator']['resources']['hp'], 0)
            self.assertEqual(game, self.runtime.create(request, MODULE, investigator))
            self.assertIn('侦查', {s['name'] for s in game['investigator']['skills']})
            with self.assertRaises(GameError): self.runtime.create(request, MODULE, 'jessica' if investigator != 'jessica' else 'stanley')
        before = Catalogue().investigator(MODULE, 'jessica').model_dump()
        other = self.runtime.create(str(uuid.uuid4()), MODULE, 'jessica')
        await self.act('return_tomorrow')
        self.assertEqual(self.runtime.get(other['gameId'])['scene']['id'], 'winscott_house')
        self.assertEqual(Catalogue().investigator(MODULE, 'jessica').model_dump(), before)
    async def test_both_timelines_complete_and_repeat_methods_no_double_cost(self):
        for timeline in ['explore_now', 'return_tomorrow']:
            self.game = self.runtime.create(str(uuid.uuid4()), MODULE, 'jessica')
            await self.route(timeline); hp = self.game['investigator']['resources']['hp']
            await self.act('force_pass'); self.assertEqual(self.game['investigator']['resources']['hp'], hp)
            await self.act('inspect_cage' if timeline == 'explore_now' else 'help_josh')
            await self.act('end_request'); self.assertFalse(self.game['ended'])
            await self.act('end_confirm'); self.assertEqual(self.game['ending'], 'completed')
            self.assertTrue(self.game['endingSummary'])
            with self.assertRaises(GameError): await self.runtime.action(self.game['gameId'], str(uuid.uuid4()), 'question', self.game['version'])
    async def test_retreated_and_failed(self):
        await self.act('end_request'); self.assertEqual(self.game['ending'], 'retreated')
        self.game = self.runtime.create(str(uuid.uuid4()), MODULE, 'jessica')
        for e in ['explore_now', 'take_rope', 'enter_tunnel', 'enter_hall', 'rope_rubble', 'enter_cages', 'force_offer']: await self.act(e)
        saved = self.runtime.read(self.game['gameId']); saved['investigator']['resources']['hp'] = 3; self.runtime.store.save(saved)
        await self.act('force_pass'); self.assertEqual(self.game['ending'], 'failed')
    async def test_committed_narration_failure_retry_does_not_repeat(self):
        self.agent.fail_narration = True; request = str(uuid.uuid4())
        job = await self.runtime.action(self.game['gameId'], request, 'explore_now', self.game['version']); await job.task
        self.assertEqual(job.events[-1]['type'], 'turn.failed')
        saved = self.runtime.read(self.game['gameId']); self.assertTrue(saved['turns'][-1]['committed']); version = saved['version']
        with self.assertRaises(GameError): await self.runtime.action(self.game['gameId'], str(uuid.uuid4()), 'question', version)
        with self.assertRaises(GameError): await self.runtime.action(self.game['gameId'], request, 'return_tomorrow', version)
        self.agent.fail_narration = False; await self.act('explore_now', request)
        self.assertEqual(self.game['version'], version); self.assertEqual(self.agent.calls, ['plan', 'narrate', 'narrate'])
        again = await self.act('explore_now', request, version=1)
        self.assertEqual(again.events[-1]['type'], 'turn.completed')
        self.assertEqual(len([m for m in self.game['messages'] if m['kind'] == 'player']), 1)
    async def test_roll_durable_before_commit_crash_and_restart(self):
        for e in ['explore_now', 'enter_tunnel']: await self.act(e)
        real_save = self.runtime.store.save
        def fail_commit(game):
            if game['turns'][-1]['committed']: raise OSError('simulated disk failure')
            real_save(game)
        request = str(uuid.uuid4())
        with patch.object(self.runtime.store, 'save', side_effect=fail_commit):
            job = await self.runtime.action(self.game['gameId'], request, 'search_traces', self.game['version']); await job.task
        saved = self.runtime.read(self.game['gameId']); original_roll = copy.deepcopy(saved['turns'][-1]['rolls'])
        self.assertEqual(len(original_roll), 1); self.assertFalse(saved['turns'][-1]['committed'])
        await self.runtime.close(); self.runtime = GameRuntime(Catalogue(), Path(self.temp.name), self.agent)
        with patch('kp_agent.gameplay.engine.coc_check', side_effect=AssertionError('must not reroll')): job = await self.act('search_traces', request)
        self.assertEqual(self.runtime.read(self.game['gameId'])['turns'][-1]['rolls'], original_roll)
        self.assertEqual(len([m for m in self.game['messages'] if m['kind'] == 'check']), 1)
        types = [e['type'] for e in job.events]; self.assertLess(types.index('check.resolved'), types.index('message.delta'))
    async def test_concurrent_dedup_and_pending(self):
        self.agent.wait = asyncio.Event(); request = str(uuid.uuid4())
        first = await self.runtime.action(self.game['gameId'], request, 'question', 1)
        second = await self.runtime.action(self.game['gameId'], request, 'question', 1); self.assertIs(first, second)
        self.agent.wait.set(); await first.task
        with self.assertRaises(GameError): await self.runtime.action(self.game['gameId'], str(uuid.uuid4()), 'question', 1)
    async def test_public_assets_versions_and_corruption(self):
        content = self.runtime.content; saved = self.runtime.read(self.game['gameId'])
        for asset in ['bg_cage_area', '../story.md', 'sprite_ssyaa_hrisss_base']:
            with self.assertRaises(GameError): content.asset(saved, asset)
        self.assertTrue(content.asset(saved, 'bg_winscott_house')[0].is_file())
        serialized = json.dumps(self.game, ensure_ascii=False)
        for private in ['profile', 'templateHash', 'effects', 'legalEvents', 'attempts', 'moduleHash']: self.assertNotIn('"' + private + '"', serialized)
        saved['profile']['hash'] = 'old'; self.runtime.store.save(saved)
        with self.assertRaisesRegex(GameError, '版本'): self.runtime.get(self.game['gameId'])
        path = self.runtime.store.path(self.game['gameId']); path.write_text('{broken')
        with self.assertRaises(GameError): self.runtime.get(self.game['gameId'])
        self.assertTrue(path.with_suffix('.json.bak').exists())
    async def test_return_is_not_end(self):
        await self.act('return_tomorrow'); await self.act('back_house'); self.assertFalse(self.game['ended'])
        await self.act('end_request'); self.assertEqual(self.game['ending'], 'retreated')
    async def test_failed_optional_check_no_soft_lock_and_two_checks_ordered(self):
        from types import SimpleNamespace
        for e in ['explore_now', 'enter_tunnel']: await self.act(e)
        with patch('kp_agent.gameplay.engine.coc_check', return_value=SimpleNamespace(roll=99, success=False)):
            await self.act('search_traces')
        self.assertNotIn('cigarette_butt', [f['id'] for f in self.game['facts']])
        with patch('kp_agent.gameplay.engine.coc_check', side_effect=AssertionError('attempt exhausted')):
            await self.act('search_traces')
        for e in ['enter_hall', 'enter_history']: await self.act(e)
        with patch('kp_agent.gameplay.engine.coc_check', side_effect=[SimpleNamespace(roll=1,success=True), SimpleNamespace(roll=99,success=False)]), patch('kp_agent.gameplay.engine.roll',return_value=SimpleNamespace(total=3)):
            job = await self.act('study_murals')
        checks=[e['check'] for e in job.events if e['type']=='check.resolved']
        self.assertEqual([c['skill'] for c in checks], ['EDU','SAN'])
        self.assertEqual(checks[1]['details'], [{'resource':'san','dice':'1D3','amount':3}])
        self.assertEqual(self.game['investigator']['resources']['san'], 62)
        await self.act('back_hall')
        with patch('kp_agent.gameplay.engine.coc_check', return_value=SimpleNamespace(roll=99,success=False)), patch('kp_agent.gameplay.engine.roll',return_value=SimpleNamespace(total=2)):
            await self.act('cross_rubble')
        await self.act('enter_cages')
        self.assertEqual(self.game['scene']['id'],'cage_area')
    async def test_subscriber_disconnect_does_not_cancel_and_active_dedup(self):
        self.agent.wait=asyncio.Event();request=str(uuid.uuid4())
        job=await self.runtime.action(self.game['gameId'],request,'explore_now',1)
        subscriber=job.stream();await anext(subscriber);await subscriber.aclose()
        self.assertIs(job, await self.runtime.action(self.game['gameId'],request,'explore_now',1))
        with self.assertRaises(GameError): await self.runtime.action(self.game['gameId'],str(uuid.uuid4()),'question',1)
        self.agent.wait.set();await job.task
        self.assertEqual(self.runtime.get(self.game['gameId'])['scene']['id'],'house_cellar')
    async def test_first_sight_fatal_san_check_keeps_revealed_asset_available(self):
        from types import SimpleNamespace
        for e in ['explore_now','take_rope','enter_tunnel','enter_hall','rope_rubble']: await self.act(e)
        saved=self.runtime.read(self.game['gameId']);saved['investigator']['resources']['san']=1;self.runtime.store.save(saved)
        with patch('kp_agent.gameplay.engine.coc_check',return_value=SimpleNamespace(roll=99,success=False)), patch('kp_agent.gameplay.engine.roll',return_value=SimpleNamespace(total=6)):
            await self.act('enter_cages')
        self.assertEqual(self.game['ending'],'failed')
        self.assertTrue(self.runtime.content.asset(self.runtime.read(self.game['gameId']),'sprite_ssyaa_hrisss_base')[0].is_file())
    async def test_narration_context_projects_current_threat_and_josh(self):
        from kp_agent.gameplay.engine import scene_description
        await self.route('explore_now')
        raw=self.runtime.read(self.game['gameId'])
        description=scene_description(self.runtime.content,raw)
        self.assertIn('已经通过',description);self.assertIn('乔什始终与你同行',description)
        self.assertNotIn('阻挡着',description)
        await self.act('inspect_cage');await self.act('end_request')
        results=self.runtime.read(self.game['gameId'])['turns'][-1]['results']
        self.assertTrue(any('与你安全返回' in r for r in results))
        self.assertFalse(any('留在地下' in r for r in results))
    async def test_confirmations_cannot_narrate_future_actions_as_completed(self):
        await self.route('explore_now')
        calls=len(self.agent.calls)
        await self.act('end_request')
        self.assertEqual(len(self.agent.calls),calls+1)  # planner only; fixed authorization prompt
        self.assertIn('尚未撤离',self.game['messages'][-1]['text'])
        self.assertIn('确认撤离',self.game['messages'][-1]['text'])
        self.assertFalse(self.game['ended'])
