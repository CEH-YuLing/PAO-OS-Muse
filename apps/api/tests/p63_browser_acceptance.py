"""Explicit local UI acceptance, not repeated in backend-only CI.

Real HTTP/Temporal/ARQ with fixed Echo on pao_test and Redis15 only.
"""
import asyncio,json,os,socket,subprocess
from contextlib import contextmanager
from uuid import uuid4
import uvicorn
from sqlalchemy import select,func
from pao.main import app
from pao.config import ROOT,settings
from pao.db import Session
from pao.models import GoalExecution,GoalEvent,TaskAttempt,Run,Goal
from pao.modules.goals import runner
from pao.modules.studio import arq_bridge as bridge
from test_goal_runner import stack,runner_gates,temporal
from test_goal_admission import draft,goal_gates
from test_goal_iterations import iteration_gates

class OwnedServer(uvicorn.Server):
    @contextmanager
    def capture_signals(self):yield

async def test_goal_browser_two_rounds_retry_replan_cancel_and_gate_rollback(client,identity,runner_gates,temporal,monkeypatch):
    assert os.environ['DATABASE_URL'].endswith('/pao_test')
    goal,p,_,_=await draft(client,identity)
    workflow=p['snapshot']['workflow'];base='/v1/studio/definitions/'+workflow['definition_id']
    body={'version_id':workflow['version_id'],'request_key':str(uuid4()),'input':{'text':'Target reached'}}
    preview=await client.post(base+'/plan-preview',headers=identity['owner'],json=body)
    saved=await client.post(base+'/plans',headers=identity['owner'],json={**body,'confirmation_hash':preview.json()['sha256']})
    assert saved.status_code==201,saved.text
    body={**body,'request_key':str(uuid4()),'input':{'text':'Cancel fixture'}}
    preview=await client.post(base+'/plan-preview',headers=identity['owner'],json=body)
    response=await client.post(base+'/plans',headers=identity['owner'],json={**body,'confirmation_hash':preview.json()['sha256']})
    assert response.status_code==201
    cancel_plan=response.json()
    response=await client.post('/v1/goals',headers=identity['owner'],json={
        'workspace_id':identity['workspace'],'title':'Browser cancellation fixture','success_criteria':['Review dry-run.']})
    assert response.status_code==201
    cancel_goal=response.json()
    directory=ROOT/'.runtime'/('goal-browser-'+uuid4().hex);directory.mkdir()
    env,_=temporal
    async with stack(env,monkeypatch) as (worker,redis):
        async with worker():
            async def health():
                while True:
                    await redis.set('pao:studio:temporal:health',bridge.worker_marker(),ex=20)
                    await bridge.dispatch_studio({'redis':redis})
                    await asyncio.sleep(1)
            health_task=asyncio.create_task(health())
            sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            server=OwnedServer(uvicorn.Config(app,host='127.0.0.1',port=port,lifespan='off',access_log=False,log_level='error'))
            api_task=asyncio.create_task(server.serve(sockets=[sock]))
            try:
                for _ in range(100):
                    if server.started:break
                    if api_task.done():await api_task
                    await asyncio.sleep(.1)
                assert server.started
                fixture={'api':f'http://127.0.0.1:{port}','goal':goal['id'],'plan':p['plan_id'],
                    'replan':saved.json()['plan_id'],'cancelGoal':cancel_goal['id'],'cancelPlan':cancel_plan['plan_id'],
                    'screenshot':str(directory/'goal-mobile.png'),'mode':'enabled'}
                async def browser():
                    child={**os.environ,'PAO_GOAL_BROWSER_FIXTURE':json.dumps(fixture)}
                    result=await asyncio.to_thread(subprocess.run,['node','scripts/verify_goal_runner_browser.cjs'],
                        env=child,cwd=ROOT,capture_output=True,text=True,timeout=180)
                    # Never dump browser request call logs containing auth headers.
                    reason=next((line for line in result.stderr.splitlines() if line.startswith('Goal browser failed at ')),'Browser subprocess failed')
                    assert result.returncode==0,reason
                    report=json.loads(result.stdout.strip());assert report['pass'] and report['real_http']
                    return report
                report=await browser();fixture['cancelled']=report['cancelled']
                async with Session() as db:
                    rows=list(await db.scalars(select(GoalExecution)))
                    assert len(rows)==2 and {r.status for r in rows}=={'completed','cancelled'}
                    for row in rows:await runner.reconstruct(db,row)
                    assert await db.scalar(select(func.count(GoalEvent.id)).where(GoalEvent.action=='runner_launch'))==3
                    assert await db.scalar(select(func.count(TaskAttempt.id)))==4
                    assert await db.scalar(select(func.count(Run.id)))==0
                    assert (await db.get(Goal,goal['id'])).status=='draft'
                settings().goal_runner_enabled=False;settings().goal_admission_enabled=False
                fixture['mode']='disabled';disabled=await browser()
                (directory/'browser.json').write_text(json.dumps({'enabled':report,'disabled':disabled}),encoding='utf-8')
            finally:
                server.should_exit=True;await asyncio.wait_for(api_task,10);sock.close()
                health_task.cancel();await asyncio.gather(health_task,return_exceptions=True)
                await redis.delete('pao:studio:temporal:health','pao:studio:arq:health')
