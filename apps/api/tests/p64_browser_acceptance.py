"""Explicit genuine HTTP lifecycle/UI acceptance on pao_test only."""
import asyncio,json,os,socket,subprocess
from uuid import uuid4
from sqlalchemy import select,func
from pao.config import ROOT
from pao.main import app
from pao.db import Session
from pao.models import StudioSchedule,StudioExecution
from pao.modules.schedules import store
from test_studio_schedules import schedule_gates
from test_durable_admission import gates,plan
from p63_browser_acceptance import OwnedServer
import uvicorn

async def test_actual_browser_schedule_lifecycle(client,identity,schedule_gates):
    assert os.environ['DATABASE_URL'].endswith('/pao_test')
    p=await plan(client,identity)
    directory=ROOT/'.runtime'/('schedule-browser-'+uuid4().hex);directory.mkdir()
    web=None;sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    server=OwnedServer(uvicorn.Config(app,host='127.0.0.1',port=port,lifespan='off',access_log=False,log_level='error'))
    api=asyncio.create_task(server.serve(sockets=[sock]))
    try:
        for _ in range(100):
            if server.started:break
            await asyncio.sleep(.1)
        assert server.started
        web_url=os.environ.get('PAO_FRONTEND_URL','http://127.0.0.1:3200')
        with (directory/'web.log').open('w',encoding='utf-8') as log:
            if os.environ.get('PAO_SCHEDULE_START_WEB')=='1':
                # Isolated owner; no main process records or database changed.
                probe=socket.socket();probe.bind(('127.0.0.1',3201));probe.close()
                web=subprocess.Popen(['node','node_modules/next/dist/bin/next','dev','apps/web','--hostname','127.0.0.1','--port','3201'],
                    cwd=ROOT,env=os.environ.copy(),stdout=log,stderr=log)
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
            fixture={'api':f'http://127.0.0.1:{port}','web':web_url,'plan':p['plan_id'],'screenshot':str(directory/'schedule-mobile.png')}
            result=await asyncio.to_thread(subprocess.run,['node','scripts/verify_schedule_browser.cjs'],cwd=ROOT,
                env={**os.environ,'PAO_SCHEDULE_BROWSER_FIXTURE':json.dumps(fixture)},capture_output=True,text=True,timeout=150)
            reason=next((s for s in result.stderr.splitlines() if s.startswith('Schedule browser failed at ')),'Browser subprocess failed')
            assert result.returncode==0,reason
            report=json.loads(result.stdout.strip());assert report['pass'] and report['real_http']
            (directory/'browser.json').write_text(json.dumps(report),encoding='utf-8')
        async with Session() as db:
            row=await db.scalar(select(StudioSchedule));await store.verify(db,row)
            assert row.status=='archived' and row.spec['cron']=='0 10 * * *'
            assert await db.scalar(select(func.count()).select_from(StudioExecution))==0
    finally:
        server.should_exit=True;await asyncio.wait_for(api,10);sock.close()
        if web and web.poll() is None:
            # Popen owns the live process handle, so this PID cannot be a stale record.
            await asyncio.to_thread(subprocess.run,['taskkill.exe','/PID',str(web.pid),'/T','/F'],capture_output=True,timeout=10)
            await asyncio.to_thread(web.wait,10)
