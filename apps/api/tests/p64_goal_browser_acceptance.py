"""Real HTTP Goal schedules UI: isolated pao_test; no worker/provider approval."""
import asyncio,json,os,socket,subprocess
from datetime import timedelta
from uuid import uuid4
import uvicorn
from sqlalchemy import select,func
from pao.config import ROOT,settings
from pao.main import app
from pao.db import Session
from pao.models import StudioSchedule,GoalScheduleSlot,GoalExecution,StudioExecution,Goal
from pao.modules.schedules import store,dispatcher
from test_goal_schedules import template,schedule_gates
from test_goal_runner import runner_gates
from test_goal_iterations import iteration_gates
from test_goal_admission import goal_gates
from p63_browser_acceptance import OwnedServer

async def test_goal_schedule_browser_lifecycle_retry_and_actual_slot(client,identity,schedule_gates):
    assert os.environ['DATABASE_URL'].endswith('/pao_test')
    goal,p,_=await template(client,identity)
    directory=ROOT/'.runtime'/('goal-schedule-browser-'+uuid4().hex);directory.mkdir()
    marker=directory/'dispatch.ready';rollback=directory/'rollback.ready'
    async def tick():
        for _ in range(600):
            if marker.exists():
                async with Session() as db:
                    row=await db.scalar(select(StudioSchedule).where(StudioSchedule.status=='enabled'))
                    assert row and row.spec['kind']=='bounded_goal';stamp=row.next_at+timedelta(seconds=1)
                value=await dispatcher.dispatch_studio_schedules(stamp=stamp)
                assert value['admitted']==1,value
                break
            await asyncio.sleep(.5)
        else:raise AssertionError('Browser did not reach dispatch handshake')
        for _ in range(200):
            if rollback.exists():
                for key in ('studio_schedule_manager_enabled','studio_schedule_dispatch_enabled','goal_runner_enabled'):
                    settings().__setattr__(key,False)
                return
            await asyncio.sleep(.5)
        raise AssertionError('Browser did not reach rollback handshake')
    web=None;sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    server=OwnedServer(uvicorn.Config(app,host='127.0.0.1',port=port,lifespan='off',access_log=False,log_level='error'))
    api=asyncio.create_task(server.serve(sockets=[sock]));clock=asyncio.create_task(tick())
    try:
        for _ in range(100):
            if server.started:break
            await asyncio.sleep(.1)
        assert server.started
        web_url=os.environ.get('PAO_FRONTEND_URL','http://127.0.0.1:3200')
        with (directory/'web.log').open('w',encoding='utf-8') as log:
            if os.environ.get('PAO_SCHEDULE_START_WEB')=='1':
                probe=socket.socket();probe.bind(('127.0.0.1',3201));probe.close()
                web=subprocess.Popen(['node','node_modules/next/dist/bin/next','dev','apps/web','--hostname','127.0.0.1','--port','3201'],
                    cwd=ROOT,env={**os.environ,'PAO_BUILD_CHECK':'1'},stdout=log,stderr=log)
                web_url='http://127.0.0.1:3201'
                import httpx
                async with httpx.AsyncClient(timeout=3) as http:
                    for _ in range(80):
                        assert web.poll() is None
                        try:
                            if (await http.get(web_url)).status_code==200:break
                        except httpx.HTTPError:pass
                        await asyncio.sleep(.5)
                    else:raise AssertionError('Owned Web did not become ready')
            fixture={'api':f'http://127.0.0.1:{port}','web':web_url,'goal':goal['id'],'plan':p['plan_id'],
                'dispatchMarker':str(marker),'rollbackMarker':str(rollback),'screenshot':str(directory/'goal-schedule-mobile.png')}
            result=await asyncio.to_thread(subprocess.run,['node','scripts/verify_goal_schedule_browser.cjs'],cwd=ROOT,
                env={**os.environ,'PAO_GOAL_SCHEDULE_BROWSER_FIXTURE':json.dumps(fixture)},capture_output=True,text=True,timeout=240)
            reason=next((s for s in result.stderr.splitlines() if s.startswith('Goal schedule browser failed at ')),'Browser subprocess failed')
            assert result.returncode==0,reason
            await asyncio.wait_for(clock,10)
            report=json.loads(result.stdout.strip());assert report['pass'] and report['real_http']
            (directory/'browser.json').write_text(json.dumps(report),encoding='utf-8')
        async with Session() as db:
            rows=list(await db.scalars(select(StudioSchedule)));assert len(rows)==2
            assert {r.status for r in rows}=={'archived','completed'}
            for row in rows:await store.verify(db,row)
            assert await db.scalar(select(func.count()).select_from(GoalScheduleSlot))==1
            assert await db.scalar(select(func.count()).select_from(GoalExecution))==1
            assert await db.scalar(select(func.count()).select_from(StudioExecution))==0
            assert (await db.get(Goal,goal['id'])).status=='draft'
    finally:
        clock.cancel();await asyncio.gather(clock,return_exceptions=True)
        server.should_exit=True;await asyncio.wait_for(api,10);sock.close()
        if web and web.poll() is None:
            await asyncio.to_thread(subprocess.run,['taskkill.exe','/PID',str(web.pid),'/T','/F'],capture_output=True,timeout=10)
            await asyncio.to_thread(web.wait,10)
