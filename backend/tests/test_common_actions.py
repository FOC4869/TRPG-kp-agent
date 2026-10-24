"""Common actions across modules, confirmation, durable damage and public boundaries."""
import copy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import patch
from app.services.catalogue import Catalogue, DATA_ROOT
from kp_agent.gameplay.content import Content, GameError, digest
from kp_agent.gameplay.engine import tool_choices
from kp_agent.gameplay.runtime import GameRuntime
from kp_agent.gameplay.schema import RuntimeProfile
from tests.test_module_runtime import ToolAgent, call, fixture_catalogue, MODULE

DARKNESS = 'darkness-beneath-the-hill'

class CommonActionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = TemporaryDirectory(); self.root = Path(self.temp.name)
        self.catalogue = fixture_catalogue(self.root/'data'); self.agent = ToolAgent()
        self.runtime = GameRuntime(self.catalogue, self.root/'saves', self.agent)
        self.game = self.runtime.create(uuid.uuid4().hex, DARKNESS, 'chris')
    async def asyncTearDown(self):
        await self.runtime.close(); self.temp.cleanup()
    def raw(self): return self.runtime.read(self.game['gameId'])
    def item(self, source):
        return next(key for key, item in self.raw()['mechanics']['items'].items() if item['sourceId'] == source)
    async def act(self, plan, request=None, decision=None, fail=False):
        text = decision if decision else json.dumps(plan, ensure_ascii=False)
        job = await self.runtime.action(self.game['gameId'], request or uuid.uuid4().hex, text,
                                        self.game['version'], ((self.game.get('pendingAction') or {}).get('id') or (self.game.get('pendingTurn') or {}).get('confirmationId')) if decision else None)
        await job.task
        self.assertEqual(job.events[-1]['type'], 'turn.failed' if fail else 'turn.completed', job.events)
        self.game = self.runtime.get(self.game['gameId']); return job
    async def harm(self): return await self.act(call('use_item', 'self', 'harm', item=self.item('machete')))

    async def test_ten_templates_and_frozen_abilities_do_not_rewrite_source(self):
        for id in self.catalogue.publication(DARKNESS).investigatorIds:
            game = self.runtime.create(uuid.uuid4().hex, DARKNESS, id)
            raw = self.runtime.read(game['gameId'])
            self.assertEqual(raw['mechanics']['version'], 1)
            self.assertEqual(set(raw['mechanics']['entityStates']), set(self.runtime.content.for_game(raw).profile['entities']))
        item_id = self.item('machete')
        self.assertEqual(self.raw()['mechanics']['items'][item_id]['damage'], '1D6')
        raw_character = self.catalogue.character(DARKNESS, 'chris')[1]
        self.assertIsNone(raw_character['starting_equipment'][0]['combat_profile'])
        rules = self.root/'data/runtime/common-actions-v1.json'
        value=json.loads(rules.read_text());value['items']['machete']['damage']='1D3';rules.write_text(json.dumps(value))
        self.assertEqual(self.raw()['mechanics']['items'][item_id]['damage'], '1D6')
        self.assertEqual(self.runtime.create(uuid.uuid4().hex,DARKNESS,'chris')['inventory'], self.game['inventory'])

    async def test_old_v3_save_get_upgrade_is_read_only_and_preserves_history(self):
        game=self.raw(); game.pop('mechanics')
        old=json.loads((DATA_ROOT/'runtime/darkness-solo-mvp-v3.json').read_text())
        game['profile']={'id':old['id'],'version':old['version'],'hash':digest(old)}
        self.runtime.store.save(game);path=self.runtime.store.path(game['gameId']);before=path.read_bytes()
        self.assertIsNone(self.runtime.get(game['gameId'])['pendingAction'])
        self.assertEqual(self.raw()['mechanics']['items'][self.item('machete')]['damage'],'1D6')
        self.assertEqual(path.read_bytes(),before)
        await self.harm();self.assertEqual(self.raw()['profile']['version'],'3.0.0')
        self.assertIn('mechanics',json.loads(path.read_text()))

    async def test_drop_retrieve_location_and_give_conserve_items(self):
        id=self.item('machete');original=copy.deepcopy(self.game['inventory'])
        await self.act(call('drop',id)); self.assertNotIn(id,[i['id'] for i in self.game['inventory']])
        self.assertEqual(self.game['nearbyItems'][0]['id'],id)
        await self.act(call('take',id));self.assertEqual(len(self.game['inventory']),len(original))
        await self.act(call('take',id));self.assertEqual(len(self.game['inventory']),len(original))
        await self.act(call('give','josh',item=id))
        self.assertEqual(self.raw()['mechanics']['npcItems']['josh'][0]['id'],id)
        self.assertNotIn(id,[i['id'] for i in self.game['inventory']]);self.assertEqual(self.game['facts'],[])
        await self.act(call('use_item','self','harm',item=id));self.assertIsNone(self.game['pendingAction'])
        await self.act(call('give','absent',item=self.item('rope')));self.assertNotIn('absent',self.raw()['mechanics']['npcItems'])

    async def test_light_only_changes_known_item_state_not_clues(self):
        id=self.item('flashlight');before=copy.deepcopy(self.game['facts'])
        await self.act(call('use_item','winscott_house','illuminate',item=id))
        self.assertIn(id,self.raw()['mechanics']['activeItems']);self.assertEqual(before,self.game['facts'])
        await self.act(call('drop',id));self.assertNotIn(id,self.raw()['mechanics']['activeItems'])
        await self.act(call('move','john_hay_library'));self.assertFalse(self.game['nearbyItems'])
        await self.act(call('take',id));self.assertNotIn(id,[i['id'] for i in self.game['inventory']])

    async def test_harm_confirm_cancel_actual_hp_and_event_order(self):
        hp=self.game['investigator']['resources']['hp']
        with patch('kp_agent.gameplay.engine.roll',side_effect=AssertionError('no dice before confirmation')):
            await self.harm();self.assertEqual(self.game['investigator']['resources']['hp'],hp)
            await self.act(None,decision='取消这次行动')
        self.assertIsNone(self.game['pendingAction']);await self.harm()
        with patch('kp_agent.gameplay.engine.roll',return_value=SimpleNamespace(total=3)):
            job=await self.act(None,decision='确认执行')
        self.assertEqual(self.game['investigator']['resources']['hp'],hp-3)
        self.assertIsNone(self.game['pendingAction']);self.assertEqual(self.raw()['turns'][-1]['rolls'],[])
        effects=[m for m in self.game['messages'] if m['kind']=='effect'];self.assertEqual(len(effects),1)
        self.assertEqual(effects[0]['effect']['dice'],'1D6')
        types=[e['type'] for e in job.events];self.assertLess(types.index('effect.resolved'),types.index('state.updated'))
        self.assertLess(types.index('state.updated'),types.index('message.delta'))
        for secret in ('mechanics','rulesHash','damageRolls','call'):
            self.assertNotIn('"'+secret+'"',json.dumps(self.game,ensure_ascii=False))

    async def test_questions_do_not_confirm_and_stale_buttons_are_rejected(self):
        await self.harm();pending=copy.deepcopy(self.game['pendingAction']);hp=self.game['investigator']['resources']['hp']
        await self.act({'kind':'question','tool':None});self.assertEqual(self.game['pendingAction'],pending)
        await self.act(call('observe','winscott_house'));self.assertIsNone(self.game['pendingAction'])
        with self.assertRaises(GameError):
            await self.runtime.action(self.game['gameId'],uuid.uuid4().hex,'确认执行',self.game['version'],pending['id'])
        await self.harm();self.assertNotEqual(self.game['pendingAction']['id'],pending['id'])
        with self.assertRaises(GameError):
            await self.runtime.action(self.game['gameId'],uuid.uuid4().hex,'确认执行',self.game['version'],pending['id'])
        self.assertEqual(self.game['investigator']['resources']['hp'],hp)

    async def test_roll_checkpoint_recovers_confirm_plan_after_restart_without_reroll(self):
        await self.harm();pending=self.game['pendingAction']['id'];request=uuid.uuid4().hex
        save=self.runtime.store.save
        def crash(game):
            if game['turns'][-1]['committed']:raise OSError('commit unavailable')
            save(game)
        with patch.object(self.runtime.store,'save',side_effect=crash),patch('kp_agent.gameplay.engine.roll',return_value=SimpleNamespace(total=2)):
            await self.act(None,request,decision='确认执行',fail=True)
        checkpoint=self.raw();rolls=copy.deepcopy(checkpoint['turns'][-1]['damageRolls'])
        self.assertEqual(checkpoint['turns'][-1]['plan']['tool']['name'],'confirm_action')
        self.assertEqual(self.game['pendingTurn']['confirmationId'],pending)
        await self.runtime.close();self.runtime=GameRuntime(self.catalogue,self.root/'saves',self.agent)
        with patch('kp_agent.gameplay.engine.roll',side_effect=AssertionError('must reuse saved damage')):
            await self.act(None,request,decision='确认执行')
        self.assertEqual(self.raw()['turns'][-1]['damageRolls'],rolls)
        self.assertEqual(len([m for m in self.game['messages'] if m['kind']=='effect']),1)
        self.assertEqual(self.game['investigator']['resources']['hp'],rolls[0]['before']-2)

    async def test_committed_damage_narration_retry_and_terminal_hp(self):
        await self.harm();pending=self.game['pendingAction']['id'];request=uuid.uuid4().hex
        self.agent.fail=True
        with patch('kp_agent.gameplay.engine.roll',return_value=SimpleNamespace(total=2)):
            await self.act(None,request,decision='确认执行',fail=True)
        hp=self.game['investigator']['resources']['hp'];self.agent.fail=False
        job=await self.runtime.action(self.game['gameId'],request,'确认执行',self.game['version'],pending);await job.task
        self.game=self.runtime.get(self.game['gameId']);self.assertEqual(self.game['investigator']['resources']['hp'],hp)
        self.assertEqual(len([m for m in self.game['messages'] if m['kind']=='effect']),1)
        raw=self.raw();raw['investigator']['resources']['hp']=1;self.runtime.store.save(raw)
        await self.harm()
        with patch('kp_agent.gameplay.engine.roll',return_value=SimpleNamespace(total=3)):
            await self.act(None,decision='确认执行')
        self.assertEqual(self.game['ending'],'failed');self.assertTrue(self.game['endingSummary'])

    async def test_entity_methods_aid_state_and_second_module_reuse(self):
        await self.act(call('interact','departure','now'));await self.act(call('take','crowbar'))
        choices=tool_choices(self.runtime.content,self.raw())
        method=next(a for a in choices if a['target']=='supply_case' and a['option']=='open')
        self.assertIn('crowbar',method['methods']['aids'])
        with patch('kp_agent.gameplay.engine.coc_check',side_effect=AssertionError('aid is automatic')):
            await self.act(call('use_item','supply_case','open',item='crowbar'))
        self.assertTrue(self.raw()['mechanics']['entityStates']['supply_case']['opened'])
        await self.act(call('take','supply_case','canvas'));self.assertIn('canvas',[i['id'] for i in self.game['inventory']])
        self.game=self.runtime.create(uuid.uuid4().hex,MODULE,'jessica')
        with patch('kp_agent.gameplay.engine.coc_check',return_value=SimpleNamespace(roll=99,success=False)):
            await self.act(call('interact','cabinet','open',skill='STR'))
        self.assertFalse(self.raw()['mechanics']['entityStates']['cabinet']['opened'])
        self.assertNotIn('STR',next(a for a in tool_choices(self.runtime.content,self.raw()) if a['target']=='cabinet')['methods']['skills'])
        with patch('kp_agent.gameplay.engine.coc_check',return_value=SimpleNamespace(roll=1,success=True)):
            await self.act(call('interact','cabinet','open',skill='机械维修'))
        self.assertTrue(self.raw()['mechanics']['entityStates']['cabinet']['opened'])
        await self.act(call('observe','cabinet'));self.assertIn('柜门已经打开',self.agent.narrations[-1]['results'][0])

    async def test_dangerous_object_method_waits_and_exit_cancels_pending(self):
        await self.act(call('interact','departure','now'));hp=self.game['investigator']['resources']['hp']
        await self.act(call('interact','supply_case','break',item=self.item('machete')))
        self.assertIsNotNone(self.game['pendingAction']);self.assertEqual(self.game['investigator']['resources']['hp'],hp)
        self.assertFalse(self.raw()['mechanics']['entityStates']['supply_case']['opened'])
        await self.act(None,decision='确认执行')
        self.assertTrue(self.raw()['mechanics']['entityStates']['supply_case']['broken'])
        await self.harm();await self.act(call('finish','investigation','request'))
        self.assertIsNone(self.game['pendingAction'])

    async def test_invalid_versions_and_undeclared_object_state_are_rejected(self):
        raw=self.raw();raw['mechanics']['version']=999;self.runtime.store.save(raw)
        with self.assertRaises(GameError):self.runtime.get(self.game['gameId'])
        profile=json.loads((DATA_ROOT/'runtime/darkness-solo-mvp-v4.json').read_text())
        profile['entities']['supply_case']['actions'][0]['success'][0]['key']='undeclared'
        with self.assertRaises(ValueError):RuntimeProfile.model_validate(profile)

    async def test_module_pickup_cannot_duplicate_dropped_or_given_equipment(self):
        await self.act(call('interact','departure','now'))
        id=self.item('rope');await self.act(call('drop',id))
        await self.act(call('take','rope'))
        self.assertEqual(len([i for i in self.game['inventory'] if i['id']==id]),1)
        self.assertEqual(self.game['nearbyItems'],[])
        await self.act(call('give','josh',item=self.item('flashlight')))
        await self.act(call('take','flashlight'))
        self.assertNotIn('flashlight',[i['id'] for i in self.game['inventory']])
        self.assertEqual(len(self.raw()['mechanics']['npcItems']['josh']),1)

    async def test_another_executed_action_invalidates_exit_confirmation(self):
        await self.act(call('interact','departure','now'))
        await self.act(call('move','old_tunnel'))
        await self.act(call('finish','investigation','request'))
        self.assertTrue(self.raw()['pendingExit'])
        await self.act(call('observe','old_tunnel'))
        self.assertFalse(self.raw()['pendingExit'])
        await self.act(call('finish','investigation','confirm'))
        self.assertFalse(self.game['ended'])

    async def test_corrupt_item_ownership_is_reported_without_rewriting_file(self):
        raw=self.raw();raw['mechanics']['groundItems'].append({'sceneId':raw['sceneId'],'item':copy.deepcopy(raw['inventory'][0])})
        self.runtime.store.save(raw);path=self.runtime.store.path(raw['gameId']);before=path.read_bytes()
        with self.assertRaises(GameError):self.runtime.get(raw['gameId'])
        self.assertEqual(path.read_bytes(),before)
