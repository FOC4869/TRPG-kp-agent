"""Independent data-only module, tool boundaries and explicit v1 migrations."""
import copy
import json
import os
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
import uuid
from unittest.mock import patch
import yaml
from pydantic import ValidationError
from app.services.catalogue import Catalogue, DATA_ROOT
from kp_agent.gameplay.agent import Plan
from kp_agent.gameplay.content import Content, GameError, digest
from kp_agent.gameplay.engine import tool_choices
from kp_agent.gameplay.runtime import GameRuntime
from kp_agent.gameplay.schema import RuntimeProfile

MODULE = 'silent-observatory'
DARKNESS = 'darkness-beneath-the-hill'
FIXTURE = Path(__file__).parent / 'fixtures/runtime/observatory-v1.json'


def call(name, target, option=None, skill=None, item=None, approach=''):
    return {'kind':'tool','tool':{'name':name,'target':target,'option':option,'skill':skill,'item':item,'approach':approach}}


class ToolAgent:
    def __init__(self): self.plans=[]; self.narrations=[]; self.fail=False
    async def plan(self, context, metric):
        self.plans.append(copy.deepcopy(context))
        return json.loads(context['input'])
    async def narrate(self, context, emit, metric):
        self.narrations.append(copy.deepcopy(context))
        if self.fail: raise TimeoutError('injected')
        text='；'.join(context['results']) or context['scene']
        emit(text); return text
    async def close(self): pass


def fixture_catalogue(root):
    """Only data differs. Art is hardlinked read-only into a temporary root."""
    shutil.copytree(DATA_ROOT/'runtime', root/'runtime')
    shutil.copytree(DATA_ROOT/'characters', root/'characters')
    original = DATA_ROOT/'modules'/DARKNESS
    module = root/'modules'/DARKNESS
    (module/'assets').mkdir(parents=True)
    shutil.copy2(original/'manifest.yaml', module/'manifest.yaml')
    shutil.copy2(original/'assets/index.yaml', module/'assets/index.yaml')
    assets=yaml.safe_load((original/'assets/index.yaml').read_text())['assets']
    profiles=[json.loads(f.read_text()) for f in (DATA_ROOT/'runtime').glob('darkness-solo-mvp-v[23].json')]
    ids={s['background'] for p in profiles for s in p['scenes'].values()} | {n['sprite'] for p in profiles for n in p['npcs'].values()} | {'module_cover'}
    for id in ids: os.link(original/'assets'/assets[id]['file'], module/'assets'/assets[id]['file'])
    registry=json.loads((DATA_ROOT/'module-catalogue.json').read_text())
    pub=copy.deepcopy(registry['modules'][0]);pub.update(id=MODULE,directory=MODULE,manifestId='silent_observatory',caseNumber='999',runtimeProfile='observatory-solo',investigatorIds=['jessica'])
    registry['modules'].append(pub);(root/'module-catalogue.json').write_text(json.dumps(registry))
    other=root/'modules'/MODULE;(other/'assets').mkdir(parents=True)
    art={'bg-lobby':'bg_winscott_house','bg-vault':'bg_cage_area','sprite-curator':'sprite_josh_base','module_cover':'module_cover'}
    index={id:{'file':id+Path(assets[source]['file']).suffix,'media_type':assets[source]['media_type'],'kind':'module_cover' if id=='module_cover' else 'test'} for id,source in art.items()}
    for id,source in art.items(): os.link(original/'assets'/assets[source]['file'], other/'assets'/index[id]['file'])
    (other/'assets/index.yaml').write_text(yaml.safe_dump({'path_base':'assets/','assets':index}))
    (other/'manifest.yaml').write_text(yaml.safe_dump({'id':'silent_observatory','title':'沉寂天文台','original_title':'The Silent Observatory','content_version':'1.0.0','files':{'assets':'assets/index.yaml'},'presentation':{'cover':'module_cover'}}))
    shutil.copy2(FIXTURE, root/'runtime/observatory-v1.json')
    index=json.loads((root/'runtime/index.json').read_text());index['profiles'].append({'id':'observatory-solo','moduleId':MODULE,'current':'observatory-v1.json'})
    (root/'runtime/index.json').write_text(json.dumps(index))
    return Catalogue(root)


class ModuleRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=TemporaryDirectory();self.root=Path(self.temp.name)
        self.catalogue=fixture_catalogue(self.root/'data');self.agent=ToolAgent()
        self.runtime=GameRuntime(self.catalogue,self.root/'saves',self.agent)
        self.game=self.runtime.create(str(uuid.uuid4()),MODULE,'jessica')
    async def asyncTearDown(self): await self.runtime.close();self.temp.cleanup()
    async def act(self, plan, request=None):
        job=await self.runtime.action(self.game['gameId'],request or uuid.uuid4().hex,json.dumps(plan,ensure_ascii=False),self.game['version'])
        await job.task
        self.assertEqual(job.events[-1]['type'],'turn.completed',job.events)
        self.game=self.runtime.get(self.game['gameId']);return job
    async def unlock_and_enter(self):
        await self.act(call('take','key'));await self.act(call('interact','hatch',item='brass_key'))
        with patch('kp_agent.gameplay.engine.coc_check',return_value=SimpleNamespace(roll=1,success=True)):await self.act(call('move','vault'))
    async def test_second_module_data_only_end_to_end_and_restart(self):
        dark=self.runtime.create(str(uuid.uuid4()),DARKNESS,'jessica')
        self.assertEqual(self.game['module']['englishTitle'],'The Silent Observatory');self.assertEqual(self.game['scene']['region'],'北部山地')
        await self.act(call('talk','curator',option='work',approach='询问失物在哪里'))
        await self.unlock_and_enter();await self.act(call('inspect','journal'))
        self.assertEqual([f['id'] for f in self.game['facts']],['request','coordinates'])
        await self.act(call('finish','investigation',option='request'));self.assertFalse(self.game['ended'])
        await self.act(call('finish','investigation',option='confirm'));self.assertEqual(self.game['ending'],'completed')
        self.assertEqual(self.game['scene']['id'],'lobby');game_id=self.game['gameId'];snapshot=copy.deepcopy(self.game)
        await self.runtime.close();self.runtime=GameRuntime(self.catalogue,self.root/'saves',self.agent)
        self.assertEqual(self.runtime.get(game_id),snapshot);self.assertEqual(self.runtime.get(dark['gameId'])['scene']['id'],'winscott_house')
        self.assertNotIn('josh',self.runtime.read(game_id)['npcs'])
        self.assertTrue(self.runtime.content.asset(self.runtime.read(game_id),'bg-vault')[0].is_file())
        with self.assertRaises(GameError):self.runtime.content.asset(self.runtime.read(dark['gameId']),'bg-vault')
    async def test_ordinary_observation_dialogue_and_knowledge_boundary(self):
        before=copy.deepcopy(self.game)
        await self.act(call('observe','lobby',approach='我慢慢环顾门厅，不碰任何物品'))
        await self.act(call('talk','curator',approach='他觉得今天的天气如何？'))
        self.assertEqual(self.game['facts'],before['facts']);self.assertEqual(self.game['inventory'],before['inventory'])
        context=self.agent.narrations[-1];self.assertEqual(context['npcs'][0]['id'],'curator')
        self.assertNotIn('坐标与',json.dumps(context,ensure_ascii=False))
        for key in ['keeper','flags','profile','affordances']:self.assertNotIn(key,context)
        await self.act({'kind':'question','tool':None});self.assertEqual(self.game['scene']['id'],'lobby')
    async def test_invalid_targets_methods_hidden_items_and_unauthorized_finish(self):
        plans=[call('move','vault'),call('take','journal'),call('observe','journal'),call('talk','curator',option='secret'),call('finish','investigation',option='confirm'),call('interact','hatch',item='brass_key'),call('interact','hatch',skill='潜行'),call('interact','hatch',skill='STR',item='brass_key')]
        for plan in plans:
            with self.subTest(plan=plan),patch('kp_agent.gameplay.engine.coc_check',side_effect=AssertionError('invalid tool must not roll')):await self.act(plan)
            self.assertEqual(self.game['scene']['id'],'lobby');self.assertFalse(self.game['ended']);self.assertEqual(self.runtime.read(self.game['gameId'])['attempts'],[])
        with self.assertRaises(GameError):self.runtime.content.asset(self.runtime.read(self.game['gameId']),'bg-vault')
    async def test_alternative_strategy_repeat_limit_and_aid(self):
        with patch('kp_agent.gameplay.engine.coc_check',return_value=SimpleNamespace(roll=99,success=False)),patch('kp_agent.gameplay.engine.roll',return_value=SimpleNamespace(total=2)):
            job=await self.act(call('interact','hatch',skill='机械维修',approach='用随身细针调整锁簧的位置'))
        self.assertEqual([e['check']['skill'] for e in job.events if e['type']=='check.resolved'],['机械维修']);hp=self.game['investigator']['resources']['hp']
        with patch('kp_agent.gameplay.engine.coc_check',side_effect=AssertionError('same method')):await self.act(call('interact','hatch',skill='机械维修',approach='换一种说法，再调整一次'))
        self.assertEqual(hp,self.game['investigator']['resources']['hp'])
        raw=self.runtime.read(self.game['gameId']);methods=next(c for c in tool_choices(self.runtime.content,raw) if c['target']=='hatch')['methods']
        self.assertEqual(methods['skills'],['STR']);await self.act(call('take','key'))
        with patch('kp_agent.gameplay.engine.coc_check',side_effect=AssertionError('aid bypass')):await self.act(call('interact','hatch',item='brass_key'))
        self.assertTrue(self.runtime.read(self.game['gameId'])['flags']['hatch_open'])
    async def test_second_module_narration_retry_and_return_not_finish(self):
        await self.unlock_and_enter();await self.act(call('move','lobby'));self.assertFalse(self.game['ended'])
        self.agent.fail=True;request=uuid.uuid4().hex;plan=call('talk','curator',option='work');text=json.dumps(plan,ensure_ascii=False)
        job=await self.runtime.action(self.game['gameId'],request,text,self.game['version']);await job.task
        self.assertEqual(job.events[-1]['type'],'turn.failed');version=self.runtime.get(self.game['gameId'])['version']
        self.agent.fail=False;await self.act(plan,request);self.assertEqual(self.game['version'],version)
        self.assertEqual(len([f for f in self.game['facts'] if f['id']=='request']),1)
    async def test_bad_other_module_is_lazy_and_paths_rejected(self):
        (self.root/'data/runtime/darkness-solo-mvp-v4.json').write_text('{bad');other=Content(self.catalogue)
        self.assertEqual(other.for_module(MODULE).profile['id'],'observatory-solo')
        with self.assertRaisesRegex(GameError,'配置无效'):other.for_module(DARKNESS)
        registry=json.loads((self.root/'data/runtime/index.json').read_text());registry['profiles'][1]['current']='../module-catalogue.json'
        (self.root/'data/runtime/index.json').write_text(json.dumps(registry))
        with self.assertRaisesRegex(GameError,'配置无效'):Content(self.catalogue).for_module(MODULE)
    async def test_game_projection_excludes_module_secrets(self):
        public=json.dumps(self.game,ensure_ascii=False)
        for field in ['completeWhen','knowledge','challenge','profile','flags','initial','effects','坐标与天文台']:self.assertNotIn(field,public)


class ProfileValidationTests(unittest.TestCase):
    def test_unknown_operations_bad_conditions_and_references(self):
        original=json.loads(FIXTURE.read_text())
        def bad_effect(p):p['affordances'][0]['effects'][0]['op']='exec'
        def bad_scene(p):p['initial']['scene']='missing'
        def bad_target(p):p['affordances'][0]['target']='missing'
        def bad_flag(p):p['affordances'][0]['requires']={'flag:no_such_flag':True}
        def bad_dice(p):p['affordances'][2]['challenge']['failureLoss']['dice']='100D1000'
        def duplicate(p):p['affordances'].append(copy.deepcopy(p['affordances'][0]))
        def missing_field(p):del p['affordances'][0]['effects'][0]['key']
        def unknown_skill(p):p['affordances'][2]['challenge']['skills']=['神秘技能']
        def cross_check(p):p['affordances'][0]['requires']={'check:first_sight':True}
        for change in [bad_effect,bad_scene,bad_target,bad_flag,bad_dice,duplicate,missing_field,unknown_skill,cross_check]:
            p=copy.deepcopy(original);change(p)
            with self.subTest(change=change.__name__),self.assertRaises(ValidationError):RuntimeProfile.model_validate(p)
    def test_model_cannot_return_event_id_or_arbitrary_patch(self):
        for plan in [{'kind':'event','eventId':'go_vault'},{'kind':'question','tool':call('move','vault')['tool']},{**call('move','vault'),'hp':99}]:
            with self.assertRaises(ValidationError):Plan.model_validate(plan)


class MigrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=TemporaryDirectory();self.agent=ToolAgent();self.runtime=GameRuntime(Catalogue(),Path(self.temp.name),self.agent)
        self.game=self.runtime.create(uuid.uuid4().hex,DARKNESS,'jessica');self.raw=self.runtime.read(self.game['gameId'])
        old=json.loads((DATA_ROOT/'runtime/darkness-solo-mvp-v1.json').read_text());self.raw['schemaVersion']=1
        self.raw.pop('mechanics')  # Real v1 saves predate the independent action state.
        self.raw['profile']={'id':old['id'],'version':old['version'],'hash':digest(old)};self.raw.pop('pendingExit');self.raw['npcs'].pop('serpent')
        self.raw['flags']={'timeline':'missing','rubble_crossed':True,'serpent_seen':True};self.raw['sceneId']='cage_area'
        self.raw['visited']=['winscott_house','house_cellar','old_tunnel','entrance_hall','cage_area'];self.raw['npcs']['josh'].update(stage='missing',location='cage_area')
        self.raw['attempts']=['return_tomorrow','sneak'];self.request=uuid.uuid4().hex
    async def asyncTearDown(self):await self.runtime.close();self.temp.cleanup()
    def turn(self,committed=False):
        return {'id':self.request,'text':'legacy input','stage':'failed','plan':{'kind':'event','eventId':'distract'},'rolls':[],'committed':committed,'results':[],'metrics':[],'messageId':self.request+':keeper'}
    async def resume(self):
        job=await self.runtime.action(self.game['gameId'],self.request,'legacy input',self.raw['version']);await job.task
        self.assertEqual(job.events[-1]['type'],'turn.completed',job.events);return self.runtime.read(self.game['gameId'])
    async def test_get_is_read_only_upgrade_saved_roll_and_attempts(self):
        turn=self.turn();check={'key':'distract','checkId':self.request+':distract','skill':'话术','target':5,'roll':99,'success':False,'result':'失败','reason':'旧的危险尝试','details':[{'resource':'hp','dice':'1D6','amount':2}]}
        turn['rolls']=[check];self.raw['turns']=[turn];self.raw['messages'].append({'id':self.request+':player','kind':'player','speaker':'玩家','text':'legacy input'})
        self.runtime.store.save(self.raw);path=self.runtime.store.path(self.game['gameId']);before=path.read_bytes()
        preview=self.runtime.get(self.game['gameId']);self.assertEqual(preview['pendingTurn']['stage'],'failed');self.assertEqual(path.read_bytes(),before)
        hp=self.raw['investigator']['resources']['hp'];await self.runtime.close();self.runtime=GameRuntime(Catalogue(),Path(self.temp.name),self.agent)
        with patch('kp_agent.gameplay.engine.coc_check',side_effect=AssertionError('must reuse legacy roll')):upgraded=await self.resume()
        self.assertEqual(upgraded['schemaVersion'],2);self.assertEqual(upgraded['turns'][0]['rolls'],[check]);self.assertEqual(upgraded['investigator']['resources']['hp'],hp-2)
        self.assertIn('sneak:skill:潜行',upgraded['attempts']);self.assertIn('sneak:skill:话术',upgraded['attempts'])
        self.assertEqual(len([m for m in upgraded['messages'] if m['kind']=='check']),1);self.assertEqual(self.agent.plans,[])
        self.assertTrue(path.with_suffix('.json.bak').is_file())
    async def test_committed_effects_are_never_reexecuted_on_upgrade(self):
        turn=self.turn(True);turn['results']=['alerted = True','hp损失1D6=2'];self.raw['turns']=[turn]
        hp=self.raw['investigator']['resources']['hp'];self.runtime.store.save(self.raw)
        with patch('kp_agent.gameplay.runtime.execute',side_effect=AssertionError('already committed')):upgraded=await self.resume()
        self.assertEqual(upgraded['version'],self.raw['version']);self.assertEqual(upgraded['investigator']['resources']['hp'],hp)
        self.assertEqual(self.agent.narrations[-1]['results'],['hp损失1D6=2'])
    async def test_unknown_old_fingerprint_preserves_file(self):
        self.raw['profile']['hash']='0'*64;self.runtime.store.save(self.raw);path=self.runtime.store.path(self.game['gameId']);before=path.read_bytes()
        with self.assertRaisesRegex(GameError,'不兼容'):self.runtime.get(self.game['gameId'])
        self.assertEqual(path.read_bytes(),before)
