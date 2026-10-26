#!/usr/bin/env python3
"""Opt-in real narration with isolated HTTP tests, fault injection and real dice."""
import argparse
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from app.main import app
from app.services.catalogue import Catalogue
from kp_agent.web import WebKeeperService
from kp_agent.models import create_planner, ModelCallError
from tests.fixtures_common import build_fixtures


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true')
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    if not args.live:parser.error('--live is required')
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    if (out/'calls.jsonl').exists():parser.error('Choose a fresh evidence directory.')
    os.environ['KP_MODEL_METRICS_PATH']=str(out/'calls.jsonl')
    planner=create_planner('deepseek')
    service=WebKeeperService(Catalogue(),out/'saves',planner=planner)
    app.state.web_keeper=service;cases=[]
    def check(name,passed,**details):
        cases.append({'name':name,'passed':bool(passed),**details})
        (out/'results.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2)+'\n')
        print(('PASS ' if passed else 'FAIL ')+name,flush=True)
        if not passed:raise AssertionError(name)
    def new(client,fixture=None):
        g=client.post('/api/games',json={'requestId':str(uuid4()),'moduleId':'rainy-archive','investigatorId':'richard'}).json()
        if fixture:
            game=service.read(g['gameId']);campaign=service.content.for_game(game).campaign
            game['campaignState']=copy.deepcopy(build_fixtures(campaign,game['character'])[fixture])
            service.store.save(game)
            g=client.get(f"/api/games/{g['gameId']}").json()
        return g
    def act(client,g,text,*,request=None,confirmation=None,expected_failure=False):
        metrics=out/'calls.jsonl'
        if metrics.exists() and len(metrics.read_text().splitlines()) >= 12:
            raise RuntimeError('Supplement provider-call limit reached.')
        body={'requestId':request or str(uuid4()),'text':text,'expectedVersion':g['version']}
        if confirmation:body['confirmationId']=confirmation
        r=client.post(f"/api/games/{g['gameId']}/actions",json=body);r.raise_for_status()
        events=[json.loads(x[6:]) for x in r.text.splitlines() if x.startswith('data: ')]
        if not expected_failure and any(e['type']=='turn.failed' for e in events):
            raise RuntimeError('Unexpected turn.failed; retain evidence for diagnosis.')
        state=client.get(f"/api/games/{g['gameId']}").json()
        return state,events,body
    with TestClient(app) as client:
        g=new(client)
        g,events,_=act(client,g,'奖励骰和惩罚骰怎么用？')
        text=g['messages'][-1]['text']
        check('修复奖励骰解释：低值更好，无实际掷骰','奖励骰取15' in text and '惩罚骰取85' in text and not service.read(g['gameId'])['turns'][-1]['rolls'],reply=text)
        g,events,_=act(client,g,'调查壁炉')
        raw=service.read(g['gameId']);before=copy.deepcopy(raw['character']);roll=raw['turns'][-1]['rolls']
        check('真实API理智事件结算',len(roll)==1 and roll[0]['skill']=='理智' and 52<=before['san']<=55,rolls=roll,reply=g['messages'][-1]['text'])
        g,events,_=act(client,g,'调查壁炉')
        after=service.read(g['gameId'])
        check('再次查看不重掷或重复扣SAN',after['character']==before and not after['turns'][-1]['rolls'])
        injury_seen=False
        for n in range(3):
            trial=new(client,'station_start')
            trial,events,_=act(client,trial,'靠近检查松动的站台（有失足风险）')
            raw=service.read(trial['gameId']);turn=raw['turns'][-1];hp=raw['character']['hp']
            check(f'真实随机站台检定{n+1}',len(turn['rolls'])==1 and 7<=hp<=10,rolls=turn['rolls'],damage=turn['damageRolls'])
            if hp<10:
                injury_seen=True
                trial,events,_=act(client,trial,'用简易止血包处理自己的擦伤（消耗1份）')
                check('真实受伤后的物品消耗与HP恢复',trial['investigator']['resources']['hp']==min(10,hp+2) and not any(i['id']=='bandage' for i in trial['inventory']),reply=trial['messages'][-1]['text'])
                break
        if not injury_seen:
            # Never manufacture a failed live roll. Offline tests force the
            # failure branch and its exact resource arithmetic separately.
            print('NOTE 三次真实站台检定都成功；伤害失败分支由确定性离线检查覆盖。',flush=True)
        # Inject a transport failure after deterministic commit, before provider
        # narration. Restore the original request with the real provider.
        g=new(client);rid=str(uuid4())
        original=planner.stream_web_narration
        def interrupted(*args,**kwargs):
            raise ModelCallError('测试注入的叙述中断；请恢复本轮。',code='evaluation_injected')
            yield ''
        planner.stream_web_narration=interrupted
        g,events,body=act(client,g,'仔细调查书桌',request=rid,expected_failure=True)
        raw=service.read(g['gameId']);saved=copy.deepcopy(raw['campaignState']);character=copy.deepcopy(raw['character']);rolls=copy.deepcopy(raw['turns'][-1]['rolls']);version=g['version']
        check('注入故障后仍保存骰子与已提交状态',bool(g['pendingTurn']) and raw['turns'][-1]['committed'] and len(rolls)==1)
        planner.stream_web_narration=original
        # Recreate the service/store to exercise durable recovery, not just a
        # reconnect to a still-running in-memory job.
        service.store.close()
        service=WebKeeperService(Catalogue(),out/'saves',planner=planner)
        app.state.web_keeper=service
        r=client.post(f"/api/games/{g['gameId']}/actions",json=body);r.raise_for_status()
        recovered=client.get(f"/api/games/{g['gameId']}").json();raw=service.read(g['gameId'])
        check('重建服务后真实API恢复原请求，不重掷不重复结算',recovered['pendingTurn'] is None and recovered['version']==version and raw['campaignState']==saved and raw['character']==character and raw['turns'][-1]['rolls']==rolls,reply=recovered['messages'][-1]['text'])
        g=new(client,'archive_complete')
        g,_,_=act(client,g,'明确结束本次调查')
        g,_,_=act(client,g,'确认执行',confirmation=g['pendingAction']['id'])
        check('结局提示匹配页面真实入口','查看复盘' in g['messages'][-1]['text'] and '你可以问我' not in g['messages'][-1]['text'],reply=g['messages'][-1]['text'])
    rows=[json.loads(s) for s in (out/'calls.jsonl').read_text().splitlines()]
    summary={'cases':len(cases),'passed':sum(c['passed'] for c in cases),'failed':sum(not c['passed'] for c in cases),
             'provider_calls':len(rows),'total_tokens':sum(c.get('total_tokens') or 0 for c in rows),
             'provider_errors':[c.get('error_code') for c in rows if c.get('error_code')],
             'injury_seen_in_live_trials':injury_seen,'fault_injection':'local before narration; recovery used real provider',
             'fixture_setup':'station/archive fixtures constructed from original authored outcomes; checks use real system RNG'}
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
