"""Explicit paid, resumable evaluation. Run from backend with --live.
Saves and metrics (never credentials) go into ignored output/web-mvp-evaluation.
"""
import argparse
import asyncio
import json
from pathlib import Path
import sys
import time
import uuid
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.catalogue import Catalogue
from kp_agent.gameplay.runtime import GameRuntime
ROOT = Path(__file__).resolve().parents[1] / 'output/web-mvp-evaluation'
ROUTES = {
 'together': [
 ('talk_tunnel','我问乔什，你怎么发现那条隧道的？'),
 ('question','假如我现在就进去，会有什么风险？我只是想了解，先不行动。'),
 ('explore_now','我决定现在就跟乔什一起下地窖探索。'),
 ('take_rope','我带上地窖里的绳索。'), ('take_crowbar','我拿起这里的撬棍带走。'),
 ('enter_tunnel','我打开随身的手电，进入旧隧道。'), ('search_traces','我仔细侦查隧道中有没有细小的新近痕迹。'),
 ('inspect_remains','我仔细检查那些显眼的遗骸和衣物。'), ('enter_hall','我继续沿隧道走向石造大厅。'),
 ('inspect_carvings','我观察石厅里的雕刻。'), ('enter_history','我先去旁边的壁画厅。'),
 ('study_murals','我研究壁画的年代与含义。'), ('back_hall','我从壁画厅回到入口厅。'),
 ('rope_rubble','我用已经带着的绳索稳妥通过碎石地段。'), ('enter_cages','我继续进入深处的牢笼区。'),
 ('force_offer','请说明强行通过的固定代价，等我确认。'),
 ('force_pass','我明确接受损失3点HP，强行通过。'), ('open_crowbar','我用随身的撬棍打开铁笼。'),
 ('inspect_cage','我调查铁笼留下的证据。'), ('end_request','我们带着证据返回地面，结束调查。'),
 ('end_confirm','确认撤离。我和乔什一起回到地面，结束本次调查。')],
 'missing': [
 ('return_tomorrow','我和乔什约好明天再来。现在回去休息，次日返回他的宅邸。'),
 ('take_rope','我把地窖中的绳索装进包。'), ('take_crowbar','我带上地窖里的撬棍。'),
 ('enter_tunnel','我持手电走进隧道寻找乔什。'), ('enter_hall','沿着旧隧道前进到石厅。'),
 ('rope_rubble','我用绳索保护自己通过松动碎石。'), ('enter_cages','我前往深处的牢笼区域。'),
 ('force_offer','请说明强行通过的固定代价，等我确认。'), ('force_pass','我接受3点HP代价，现在强行通过。'),
 ('open_crowbar','用撬棍撬开面前的铁笼。'), ('help_josh','我扶住乔什，帮助他走出铁笼跟着我。'),
 ('end_request','我带着乔什撤离这里，结束调查。'), ('end_confirm','确认，我们一起返回地面，结束这场调查。')]
}
async def main():
 parser=argparse.ArgumentParser();parser.add_argument('--live',action='store_true');args=parser.parse_args()
 if not args.live:parser.error('Requires explicit --live (billable).')
 ROOT.mkdir(parents=True,exist_ok=True);report_path=ROOT/'report.json'
 report=json.loads(report_path.read_text()) if report_path.exists() else {'modelRequests':0,'turns':[],'games':{},'startedAt':time.time()}
 def save():report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 runtime=GameRuntime(Catalogue(),ROOT/'saves')
 class BudgetAgent:
  def __init__(self,agent):self.agent=agent
  def budget(self):
   if report['modelRequests']>=90:raise RuntimeError('Evaluation model budget reached; request not sent')
   report['modelRequests']+=1;save()
  async def plan(self,*args):self.budget();return await self.agent.plan(*args)
  async def narrate(self,*args):self.budget();return await self.agent.narrate(*args)
  async def close(self):await self.agent.close()
 runtime.agent=BudgetAgent(runtime.agent)
 try:
  for route,steps in ROUTES.items():
   if route not in report['games']:
    game=runtime.create(str(uuid.uuid4()),'darkness-beneath-the-hill','jessica');report['games'][route]=game['gameId'];save()
   game_id=report['games'][route]
   for index,(expected,text) in enumerate(steps):
    request_id=uuid.uuid5(uuid.NAMESPACE_URL,game_id+':'+str(index)).hex
    raw=runtime.read(game_id);turn=next((t for t in raw['turns'] if t['id']==request_id),None)
    if turn and turn['stage']=='completed':continue
    started=time.monotonic();job=await runtime.action(game_id,request_id,text,raw['version']);await job.task
    raw=runtime.read(game_id);turn=next(t for t in raw['turns'] if t['id']==request_id)
    entry={'route':route,'index':index,'expected':expected,'input':text,'plan':turn['plan'],'stage':turn['stage'],'durationMs':round((time.monotonic()-started)*1000),'metrics':turn['metrics'],'checks':turn['rolls'],'scene':raw['sceneId'],'ending':raw['ending'],'errorPhase':turn.get('errorPhase')}
    report['turns'].append(entry);save()
    actual=turn['plan']['eventId'] if turn['plan'] and turn['plan']['kind']=='event' else (turn['plan'] or {}).get('kind')
    print(json.dumps({'route':route,'step':index,'expected':expected,'actual':actual,'stage':turn['stage'],'ms':entry['durationMs']},ensure_ascii=False),flush=True)
    if turn['stage']!='completed':raise RuntimeError('Turn failed; inspect report, explicitly resume same request.')
    if actual!=expected:raise RuntimeError('Semantic mismatch; inspect committed facts before continuing.')
   if runtime.get(game_id)['ending']!='completed':raise RuntimeError('Route did not complete.')
  report['passed']=True;save()
 finally:await runtime.close()
if __name__=='__main__':asyncio.run(main())
