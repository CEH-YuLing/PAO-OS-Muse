"""Goal terminal -> actual HTTP inbox/delivery UI on pao_test, no external send."""
import asyncio,json,os,socket,subprocess
from uuid import uuid4
import uvicorn,httpx
from sqlalchemy import select,func
from pao.config import ROOT,settings
from pao.main import app
from pao.db import Session
from pao.models import GoalResultReceipt,GoalResultDelivery
from test_goal_runner import stack,admission,approve,approve_steps,wait,runner_gates
from test_goal_iterations import iteration_gates
from test_goal_admission import goal_gates
from test_goal_temporal_kernel import temporal
from p63_browser_acceptance import OwnedServer

async def test_actual_goal_inbox_and_delivery_browser(client,identity,runner_gates,temporal,monkeypatch):
    assert os.environ['DATABASE_URL'].endswith('/pao_test')
    monkeypatch.setattr(settings(),'result_inbox_enabled',True)
    env,_=temporal
    async with stack(env,monkeypatch) as (worker,_):
        async with worker():
            _,plan,row,_=await admission(client,identity,target='Fixture planning')
            await approve(client,identity,row);await approve_steps(client,identity,plan['plan_id']);await wait(client,identity,row,'completed')
    directory=ROOT/'.runtime'/('result-browser-'+uuid4().hex);directory.mkdir()
    sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    server=OwnedServer(uvicorn.Config(app,host='127.0.0.1',port=port,lifespan='off',access_log=False,log_level='error'))
    task=asyncio.create_task(server.serve(sockets=[sock]));web=None
    try:
        for _ in range(100):
            if server.started:break
            await asyncio.sleep(.1)
        assert server.started
        with (directory/'web.log').open('w',encoding='utf-8') as log:
            probe=socket.socket();probe.bind(('127.0.0.1',3201));probe.close()
            web=subprocess.Popen(['node','node_modules/next/dist/bin/next','dev','apps/web','--hostname','127.0.0.1','--port','3201'],cwd=ROOT,env={**os.environ,'PAO_BUILD_CHECK':'1'},stdout=log,stderr=log)
            async with httpx.AsyncClient(timeout=3) as http:
                for _ in range(80):
                    assert web.poll() is None
                    try:
                        if (await http.get('http://127.0.0.1:3201/')).status_code==200:break
                    except httpx.HTTPError:pass
                    await asyncio.sleep(.5)
                else:raise AssertionError('Owned test Web not ready')
            fixture={'api':f'http://127.0.0.1:{port}','web':'http://127.0.0.1:3201','parent':row['execution_id'],'screenshot':str(directory/'result-mobile.png')}
            result=await asyncio.to_thread(subprocess.run,['node','scripts/verify_result_browser.cjs'],cwd=ROOT,env={**os.environ,'PAO_RESULT_BROWSER_FIXTURE':json.dumps(fixture)},capture_output=True,text=True,timeout=150)
            reason=next((s for s in result.stderr.splitlines() if s.startswith('Result browser failed at ')),'Result browser subprocess failed')
            assert result.returncode==0,reason
            report=json.loads(result.stdout);assert report['pass'];(directory/'browser.json').write_text(json.dumps(report),encoding='utf-8')
        async with Session() as db:
            assert await db.scalar(select(func.count(GoalResultReceipt.id)))==1
            assert await db.scalar(select(func.count(GoalResultDelivery.id)))==1
            d=await db.scalar(select(GoalResultDelivery));assert d.status=='delivered' and d.attempts==1
    finally:
        server.should_exit=True;await asyncio.wait_for(task,10);sock.close()
        if web and web.poll() is None:
            await asyncio.to_thread(subprocess.run,['taskkill.exe','/PID',str(web.pid),'/T','/F'],capture_output=True,timeout=10)
            await asyncio.to_thread(web.wait,10)
