"""Expanded investigation: consequential clues, routes and frozen old games.
Only temporary saves and an offline tool agent; no paid calls.
"""
import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import patch
from pydantic import ValidationError
from app.services.catalogue import Catalogue, DATA_ROOT
from kp_agent.gameplay.content import Content, GameError, digest
from kp_agent.gameplay.runtime import GameRuntime
from kp_agent.gameplay.schema import RuntimeProfile
from tests.test_module_runtime import ToolAgent, call, fixture_catalogue, DARKNESS
from tests.runtime_helpers import HistoricalCatalogue

class InvestigationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=TemporaryDirectory();self.root=Path(self.temp.name);self.agent=ToolAgent()
        self.runtime=GameRuntime(Catalogue(),self.root/'saves',self.agent)
        self.game=self.runtime.create(uuid.uuid4().hex,DARKNESS,'jessica')
        self.good=patch('kp_agent.gameplay.engine.coc_check',return_value=SimpleNamespace(roll=1,success=True));self.good.start()
    async def asyncTearDown(self):
        self.good.stop();await self.runtime.close();self.temp.cleanup()
    def raw(self):return self.runtime.read(self.game['gameId'])
    async def act(self,name,target,option=None,skill=None,item=None,accepted=True):
        text=json.dumps(call(name,target,option,skill,item),ensure_ascii=False)
        job=await self.runtime.action(self.game['gameId'],uuid.uuid4().hex,text,self.game['version']);await job.task
        self.assertEqual(job.events[-1]['type'],'turn.completed',job.events)
        self.game=self.runtime.get(self.game['gameId'])
        self.assertEqual(self.raw()['turns'][-1]['executedTool'] is not None,accepted,(name,target,option));return job
    async def start(self,timeline='now'):
        await self.act('interact','departure',timeline)
        for id in ['flashlight','rope','crowbar']:
            if id not in [i['id'] for i in self.game['inventory']]:await self.act('take',id)
        await self.act('move','old_tunnel')
    async def hall(self):
        await self.act('move','entrance_hall');await self.act('interact','rubble',item='rope')
    async def cages(self,music=False):
        await self.hall()
        if music:
            await self.act('move','music_room');await self.act('inspect','music_device');await self.act('interact','music_device','play')
        await self.act('move','pit_corridor');await self.act('inspect','pit_edge');await self.act('interact','pit_edge','careful')
        await self.act('move','cage_area')
        if music:await self.act('interact','threat','song')
        else:await self.act('interact','threat','bypass',skill='潜行')
        await self.act('interact','cage','open',item='crowbar')
    async def research(self,failed=False):
        await self.act('move','john_hay_library');await self.act('inspect','archives')
        if failed:
            with patch('kp_agent.gameplay.engine.coc_check',return_value=SimpleNamespace(roll=99,success=False)):await self.act('inspect','letters')
            self.assertNotIn('peck_letter',[f['id'] for f in self.game['facts']])
            with patch('kp_agent.gameplay.engine.coc_check',side_effect=AssertionError('do not reroll')):await self.act('inspect','letters','fragments')
        else:await self.act('inspect','letters')
        await self.act('move','winscott_house')
    async def prepare_river(self):
        await self.act('move','river_brick_wall');await self.act('inspect','river_wall')
        with patch('kp_agent.gameplay.engine.coc_check',side_effect=AssertionError('evidence + tool bypass')):await self.act('interact','river_wall','prepare')
        await self.act('move','old_tunnel')
    async def finish(self):
        await self.act('finish','investigation','request')
        if not self.game['ended']:await self.act('finish','investigation','confirm')

    async def test_all_ten_new_templates_and_idempotent_historical_creation(self):
        self.assertEqual(self.raw()['profile']['version'],'4.0.0')
        self.assertEqual(len(self.runtime.content.for_game(self.raw()).profile['scenes']),11)
        for id in Catalogue().publication(DARKNESS).investigatorIds:
            game=self.runtime.create(uuid.uuid4().hex,DARKNESS,id);raw=self.runtime.read(game['gameId'])
            self.assertEqual(raw['profile']['version'],'4.0.0');self.assertFalse(raw['flags']['river_exit_ready'])
        old=Content(HistoricalCatalogue(self.root/'old'));request=uuid.uuid4().hex
        id=uuid.uuid5(uuid.NAMESPACE_URL,'coc-mvp:'+request).hex
        self.runtime.store.save(old.initialize(id,request,DARKNESS,'jessica'))
        path=self.runtime.store.path(id);before=path.read_bytes()
        self.assertEqual(self.runtime.create(request,DARKNESS,'jessica')['gameId'],id)
        self.assertEqual(self.runtime.content.for_game(self.runtime.read(id)).profile['version'],'2.0.0')
        self.assertEqual(path.read_bytes(),before)
        self.assertNotIn('音乐室',json.dumps(self.runtime.get(id),ensure_ascii=False))

    async def test_failed_research_has_fallback_and_letter_unlocks_real_river_exit(self):
        await self.research(failed=True)
        self.assertEqual(self.raw()['flags']['timeline'],'undecided');self.assertEqual(self.raw()['npcs']['josh']['stage'],'at_home')
        await self.start();await self.act('inspect','remains');await self.act('inspect','remains','compare')
        self.assertIn('sealed_history',[f['id'] for f in self.game['facts']])
        await self.prepare_river();self.assertTrue(self.raw()['flags']['river_exit_ready'])
        await self.act('interact','escape_plan','river');self.assertFalse(self.game['ended'])
        await self.finish();self.assertEqual(self.game['ending'],'retreated');self.assertEqual(self.game['scene']['id'],'river_brick_wall')
        scene=self.agent.narrations[-1]['scene'];self.assertIn('河岸出口返回地面',scene);self.assertIn('旧信与遗骸相互印证',scene)
        self.assertNotIn('把他留在了地下',scene)

    async def test_together_route_optional_history_and_case_evidence(self):
        await self.start();await self.hall();await self.act('inspect','carvings');await self.act('move','history_hall')
        job=await self.act('inspect','murals')
        self.assertEqual([e['check']['skill'] for e in job.events if e['type']=='check.resolved'],['EDU','SAN'])
        await self.act('inspect','murals','compare');await self.act('move','pit_corridor');await self.act('inspect','pit_edge')
        with patch('kp_agent.gameplay.engine.coc_check',side_effect=AssertionError('careful method')):await self.act('interact','pit_edge','careful')
        await self.act('move','cage_area');await self.act('interact','threat','bypass',skill='潜行')
        await self.act('interact','cage','open',item='crowbar');await self.act('inspect','evidence')
        await self.act('talk','josh','remember',accepted=False);await self.finish()
        self.assertEqual(self.game['ending'],'completed');self.assertEqual(self.game['scene']['id'],'winscott_house')
        scene=self.agent.narrations[-1]['scene'];self.assertIn('没有发生营救',scene);self.assertIn('有证据表明这些遗迹远早于人类',scene)

    async def test_full_eleven_scene_investigation_and_river_extraction_survive_restart(self):
        await self.research();await self.start('tomorrow');await self.prepare_river();await self.hall()
        await self.act('inspect','carvings');await self.act('move','history_hall');await self.act('inspect','murals')
        await self.act('inspect','murals','compare');await self.act('move','entrance_hall')
        await self.act('move','music_room');await self.act('inspect','music_device');await self.act('interact','music_device','play')
        await self.act('move','pit_corridor');await self.act('move','nest_south')
        with patch('kp_agent.gameplay.engine.coc_check',return_value=SimpleNamespace(roll=99,success=False)):await self.act('inspect','testament')
        with patch('kp_agent.gameplay.engine.coc_check',side_effect=AssertionError('no repeated search')):await self.act('inspect','testament','read')
        await self.act('move','pit_corridor');await self.act('interact','pit_edge','cross',item='rope');await self.act('move','cage_area')
        await self.act('interact','threat','song');await self.act('interact','cage','open',item='crowbar')
        self.assertEqual(set(self.raw()['visited']),{'winscott_house','john_hay_library','house_cellar','old_tunnel','river_brick_wall','entrance_hall','history_hall','music_room','pit_corridor','nest_south','cage_area'})
        self.assertEqual(self.raw()['npcs']['josh']['stage'],'missing');self.assertFalse(self.raw()['flags']['final_solved'])
        with patch('kp_agent.gameplay.engine.coc_check',side_effect=AssertionError('evidence reassurance')):await self.act('talk','josh','remember')
        await self.act('interact','escape_plan','river');before=copy.deepcopy(self.game)
        await self.runtime.close();self.runtime=GameRuntime(Catalogue(),self.root/'saves',self.agent)
        self.assertEqual(self.runtime.get(self.game['gameId']),before)
        await self.finish();self.assertEqual(self.game['ending'],'completed');self.assertEqual(self.game['scene']['id'],'river_brick_wall')
        self.assertIn('失踪的乔什',self.agent.narrations[-1]['scene']);self.assertIn('受害者证词',self.agent.narrations[-1]['scene'])

    async def test_music_is_deliberate_cost_once_and_earns_an_alternative_method(self):
        await self.start();await self.hall();await self.act('move','music_room')
        await self.act('interact','music_device','play',accepted=False);san=self.game['investigator']['resources']['san']
        await self.act('inspect','music_device');self.assertEqual(self.game['investigator']['resources']['san'],san)
        job=await self.act('interact','music_device','play');self.assertEqual(self.game['investigator']['resources']['san'],san-1)
        self.assertNotIn('check.resolved',[e['type'] for e in job.events])
        await self.act('interact','music_device','play',accepted=False);self.assertEqual(self.game['investigator']['resources']['san'],san-1)
        await self.act('move','pit_corridor');await self.act('interact','pit_edge','cross',item='rope')
        job=await self.act('move','cage_area');self.assertEqual([e['check']['skill'] for e in job.events if e['type']=='check.resolved'],['SAN'])
        with patch('kp_agent.gameplay.engine.coc_check',side_effect=AssertionError('song cover')):await self.act('interact','threat','song')
        self.assertTrue(self.raw()['flags']['threat_passed'])

    async def test_failed_calming_has_environmental_fallback(self):
        await self.start('tomorrow');await self.cages();await self.act('talk','josh','remember',accepted=False)
        with patch('kp_agent.gameplay.engine.coc_check',return_value=SimpleNamespace(roll=99,success=False)):await self.act('talk','josh','calm',skill='说服')
        await self.act('talk','josh','calm',skill='心理学',accepted=False)
        self.assertEqual(self.raw()['npcs']['josh']['stage'],'missing')
        await self.act('inspect','water');self.assertIn('尚不能确定成分',self.game['facts'][-1]['text'])
        await self.act('talk','josh','water');self.assertEqual(self.raw()['npcs']['josh']['stage'],'following')
        await self.finish();self.assertEqual(self.game['ending'],'completed')

    async def test_guiding_requires_cost_offer_and_narration_retry_never_charges_twice(self):
        await self.start('tomorrow');await self.cages();hp=self.game['investigator']['resources']['hp']
        await self.act('interact','captive','guide',accepted=False);await self.act('interact','captive','cost')
        self.assertEqual(self.game['investigator']['resources']['hp'],hp)
        request=uuid.uuid4().hex;text=json.dumps(call('interact','captive','guide'),ensure_ascii=False);self.agent.fail=True
        job=await self.runtime.action(self.game['gameId'],request,text,self.game['version']);await job.task
        self.assertEqual(job.events[-1]['type'],'turn.failed');self.game=self.runtime.get(self.game['gameId'])
        self.assertEqual(self.game['investigator']['resources']['hp'],hp-1);self.agent.fail=False
        job=await self.runtime.action(self.game['gameId'],request,text,self.game['version']);await job.task
        self.game=self.runtime.get(self.game['gameId']);self.assertEqual(self.game['investigator']['resources']['hp'],hp-1)
        self.assertEqual(self.raw()['npcs']['josh']['stage'],'following');await self.finish();self.assertEqual(self.game['ending'],'completed')

    async def test_failed_direct_crossing_progresses_and_return_is_not_finish(self):
        await self.start();await self.hall();await self.act('move','cage_area',accepted=False);await self.act('move','pit_corridor')
        await self.act('move','cage_area',accepted=False);hp=self.game['investigator']['resources']['hp']
        with patch('kp_agent.gameplay.engine.coc_check',return_value=SimpleNamespace(roll=99,success=False)),patch('kp_agent.gameplay.engine.roll',return_value=SimpleNamespace(total=2)):
            await self.act('interact','pit_edge','cross',skill='DEX')
        self.assertEqual(self.game['investigator']['resources']['hp'],hp-2);self.assertTrue(self.raw()['flags']['pit_crossed'])
        await self.act('move','cage_area');await self.act('move','pit_corridor');await self.act('move','entrance_hall');self.assertFalse(self.game['ended'])

    async def test_fresh_cigarette_trail_is_exclusive_to_missing_line_and_helps_avoid_pit(self):
        await self.start();await self.act('inspect','traces',accepted=False)
        self.assertNotIn('cigarette_butt',[f['id'] for f in self.game['facts']])
        self.game=self.runtime.create(uuid.uuid4().hex,DARKNESS,'jessica')
        await self.start('tomorrow');await self.act('inspect','traces');await self.hall();await self.act('move','pit_corridor')
        with patch('kp_agent.gameplay.engine.coc_check',side_effect=AssertionError('established tracks offer a careful route')):
            await self.act('interact','pit_edge','trail')
        self.assertTrue(self.raw()['flags']['pit_crossed'])
        self.assertIn('followed_tracks',[f['id'] for f in self.game['facts']])

    async def test_unearned_methods_future_facts_and_assets_are_not_public(self):
        initial=copy.deepcopy(self.game['facts']);await self.act('observe','winscott_house');await self.act('talk','josh')
        await self.act('inspect','testament',accepted=False);self.assertEqual(self.game['facts'],initial)
        public=json.dumps(self.game,ensure_ascii=False)
        for spoiler in ['head_chorus','harper_testament','prehuman_origin','returnRoutes','river_exit_ready']:self.assertNotIn(spoiler,public)
        for asset in ['bg_music_room','bg_nest_west','bg_john_hay_library']:
            with self.assertRaises(GameError):self.runtime.content.asset(self.raw(),asset)
        await self.start();await self.act('interact','escape_plan','river',accepted=False)
        await self.cages();await self.act('interact','threat','song',accepted=False)

    async def test_retreat_leaves_captive_and_lethal_guiding_stops_before_rescue(self):
        await self.start('tomorrow');await self.cages()
        # A deliberate withdrawal does not claim an opened cage as a rescue.
        raw=self.raw();other=copy.deepcopy(raw)
        other['gameId']=uuid.uuid4().hex;other['creation']['requestId']=uuid.uuid4().hex
        self.runtime.store.save(other)
        await self.finish();self.assertEqual(self.game['ending'],'retreated')
        self.assertIn('把他留在了地下',self.agent.narrations[-1]['scene'])
        self.game=self.runtime.get(other['gameId'])
        raw=self.raw();raw['investigator']['resources']['hp']=1;self.runtime.store.save(raw)
        await self.act('interact','captive','cost');await self.act('interact','captive','guide')
        self.assertEqual(self.game['ending'],'failed')
        self.assertEqual(self.raw()['npcs']['josh']['stage'],'missing')
        self.assertNotIn('josh_rescued',[f['id'] for f in self.game['facts']])

    async def test_saved_expanded_roll_restarts_without_double_damage(self):
        await self.start();await self.hall();await self.act('move','pit_corridor')
        hp=self.game['investigator']['resources']['hp'];request=uuid.uuid4().hex
        text=json.dumps(call('interact','pit_edge','cross',skill='DEX'),ensure_ascii=False)
        save=self.runtime.store.save
        def fail_commit(game):
            if game['turns'][-1]['committed']:raise OSError('injected disk fault')
            save(game)
        with patch.object(self.runtime.store,'save',side_effect=fail_commit),patch('kp_agent.gameplay.engine.coc_check',return_value=SimpleNamespace(roll=99,success=False)),patch('kp_agent.gameplay.engine.roll',return_value=SimpleNamespace(total=2)):
            job=await self.runtime.action(self.game['gameId'],request,text,self.game['version']);await job.task
        self.assertEqual(job.events[-1]['type'],'turn.failed');raw=self.raw()
        recorded=copy.deepcopy(raw['turns'][-1]['rolls']);self.assertEqual(len(recorded),1)
        self.assertEqual(raw['investigator']['resources']['hp'],hp)
        await self.runtime.close();self.runtime=GameRuntime(Catalogue(),self.root/'saves',self.agent)
        with patch('kp_agent.gameplay.engine.coc_check',side_effect=AssertionError('saved result must be used')):
            job=await self.runtime.action(self.game['gameId'],request,text,raw['version']);await job.task
        self.assertEqual(job.events[-1]['type'],'turn.completed');self.game=self.runtime.get(self.game['gameId'])
        self.assertEqual(self.game['investigator']['resources']['hp'],hp-2)
        self.assertTrue(self.raw()['flags']['pit_crossed']);self.assertEqual(self.raw()['turns'][-1]['rolls'],recorded)
        self.assertEqual(len([m for m in self.game['messages'] if m['kind']=='check']),1)

class RetainedProfileTests(unittest.TestCase):
    def test_retained_corruption_never_silently_upgrades_the_story(self):
        with TemporaryDirectory() as temp:
            catalogue=fixture_catalogue(Path(temp)/'data');content=Content(catalogue)
            game=Content(HistoricalCatalogue(Path(temp)/'old')).initialize(uuid.uuid4().hex,uuid.uuid4().hex,DARKNESS,'jessica')
            self.assertEqual(content.for_game(game).profile['version'],'2.0.0')
            path=Path(temp)/'data/runtime/darkness-solo-mvp-v2.json';raw=json.loads(path.read_text());raw['scenes']['winscott_house']['public']+=' changed';path.write_text(json.dumps(raw))
            with self.assertRaisesRegex(GameError,'配置无效'):Content(catalogue).for_game(game)
            self.assertEqual(Content(catalogue).for_module(DARKNESS).profile['version'],'4.0.0')
    def test_invalid_new_release_does_not_break_retained_games_and_unknown_routes_fail(self):
        with TemporaryDirectory() as temp:
            catalogue=fixture_catalogue(Path(temp)/'data');game=Content(HistoricalCatalogue(Path(temp)/'old')).initialize(uuid.uuid4().hex,uuid.uuid4().hex,DARKNESS,'jessica')
            (Path(temp)/'data/runtime/darkness-solo-mvp-v4.json').write_text('{broken');content=Content(catalogue);content.validate(game)
            self.assertEqual(game['profile']['version'],'2.0.0')
            with self.assertRaises(GameError):content.for_module(DARKNESS)
        raw=json.loads((DATA_ROOT/'runtime/darkness-solo-mvp-v3.json').read_text());raw['endings']['returnRoutes'][0]['scene']='unknown'
        with self.assertRaises(ValidationError):RuntimeProfile.model_validate(raw)
    def test_frozen_v2_digest_matches_the_explicit_migration_target(self):
        root=DATA_ROOT/'runtime';entry=json.loads((root/'index.json').read_text())['profiles'][0]
        frozen=digest(json.loads((root/'darkness-solo-mvp-v2.json').read_text()))
        self.assertEqual(entry['retained'][0]['hash'],frozen);self.assertEqual(entry['compatible'][0]['targetHash'],frozen)
