"""Explicit browser acceptance (not a dependency of backend-only CI).

Run via scripts/test_backend.py --browser, with the local Web server running.
Browser -> real isolated HTTP API -> outbox -> Temporal -> ARQ -> DB.
"""
import asyncio
import os
import signal
import socket
import subprocess
import sys
import json
from uuid import uuid4
from datetime import timedelta
import httpx
from arq import create_pool
from arq.connections import RedisSettings
from arq.worker import create_worker
from sqlalchemy import select, func
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker
from pao.config import ROOT, settings
from pao.db import Session
from pao.models import Run, Task, TaskAttempt, StudioExecution
from pao.modules.studio import durable, arq_bridge as bridge
from pao.modules.studio.durable_workflow import PaoPlannedDryRunWorkflow as W
from test_durable_admission import plan, gates
from test_studio_arq_bridge import close_worker
from test_workflow_planning import definitions, preview


async def test_real_browser_approve_reject_cancel(client, identity, gates, monkeypatch):
    monkeypatch.setattr(settings(), 'workflow_worker_enabled', True)
    monkeypatch.setattr(durable.gateway, 'deliver', durable.Gateway.deliver.__get__(durable.gateway))
    config=RedisSettings.from_dsn(settings().redis_url); assert config.database==15
    queue='pao-test:p62-ui:'+uuid4().hex
    redis=await create_pool(config,default_queue_name=queue)
    class EchoWorker:
        functions=[bridge.execute_studio_echo]
        redis_settings=config
        queue_name=queue
        health_check_key=queue+':health'
        handle_signals=False
        max_jobs=1
        keep_result=0
        max_tries=1
        poll_delay=.05
        job_timeout=20
    runner=create_worker(EchoWorker); running=asyncio.create_task(runner.async_run())
    directory=ROOT/'.runtime'/('p62-browser-'+uuid4().hex); directory.mkdir()
    from temporal_fixture import cached_binary
    cached=[cached_binary(ROOT)]
    assert cached
    tq='p62-ui-'+uuid4().hex
    monkeypatch.setattr(settings(),'workflow_temporal_task_queue',tq)
    api=None; pump=None; values=[]
    try:
        async with await WorkflowEnvironment.start_local(ui=False,dev_server_existing_path=str(cached[-1]),
                dev_server_database_filename=str(directory/'temporal.sqlite')) as env:
            monkeypatch.setattr(durable.gateway,'client',env.client)
            activity_bridge=bridge.DryRunBridge(redis)
            async with Worker(env.client,task_queue=tq,workflows=[W],
                    activities=[durable.project_state,activity_bridge.step],graceful_shutdown_timeout=timedelta(seconds=2)):
                workflow,_,_=await definitions(client,identity)
                for _ in range(3):
                    base,body,response=await preview(client,identity,workflow)
                    body['confirmation_hash']=response.json()['sha256']
                    saved=await client.post(base+'/plans',json=body,headers=identity['owner'])
                    assert saved.status_code==201,saved.text
                    values.append(saved.json())
                async def dispatch():
                    while True:
                        await redis.set('pao:studio:temporal:health',bridge.worker_marker(),ex=20)
                        await bridge.dispatch_studio({'redis':redis})
                        await asyncio.sleep(.2)
                pump=asyncio.create_task(dispatch())
                with socket.socket() as sock:
                    sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
                child=os.environ.copy();child.update({
                    'STUDIO_ENABLED':'true','WORKFLOW_PLANNING_ENABLED':'true',
                    'WORKFLOW_DURABLE_ENABLED':'true','WORKFLOW_DISPATCH_ENABLED':'true',
                    'WORKFLOW_WORKER_ENABLED':'true','WORKFLOW_TEMPORAL_TASK_QUEUE':tq,
                    'TEMPORAL_ENABLED':'true','META_ENABLED':'false','META_WRITE_ENABLED':'false'})
                assert child['DATABASE_URL'].endswith('/pao_test')
                with (directory/'api.log').open('w',encoding='utf-8') as log:
                    api=subprocess.Popen([sys.executable,'-m','uvicorn','pao.main:app','--host','127.0.0.1',
                        '--port',str(port),'--no-access-log'],env=child,cwd=ROOT,stdout=log,stderr=log)
                    url='http://127.0.0.1:'+str(port)
                    async with httpx.AsyncClient() as http:
                        for _ in range(100):
                            try:
                                if (await http.get(url+'/health')).status_code==200:break
                            except httpx.HTTPError:pass
                            await asyncio.sleep(.1)
                        else:raise AssertionError('isolated HTTP API did not start; see fixture api.log')
                    child.update({'PAO_P62_FIXTURE_API':url,'PAO_P62_PLAN_IDS':json.dumps([v['plan_id'] for v in values]),
                        'PAO_FRONTEND_URL':os.environ.get('PAO_FRONTEND_URL','http://127.0.0.1:3200')})
                    result=await asyncio.to_thread(subprocess.run,['node','scripts/verify_p62_browser.cjs'],
                        env=child,cwd=ROOT,capture_output=True,text=True,timeout=120)
                    assert result.returncode==0,result.stdout+'\n'+result.stderr
                    report=json.loads(result.stdout.strip());assert report['real_http'] and report['page_errors']==0
                    (directory/'browser.json').write_text(json.dumps(report),encoding='utf-8')
                async with Session() as db:
                    assert [ (await db.get(StudioExecution,v['plan_id'])).status for v in values ]==['completed','cancelled','cancelled']
                    assert await db.scalar(select(func.count(TaskAttempt.id)))==2
                    assert await db.scalar(select(func.count(Run.id)))==0
                    assert all(t.status=='draft' for t in await db.scalars(select(Task)))
    finally:
        if api and api.poll() is None:
            api.terminate();await asyncio.to_thread(api.wait,10)
        if pump:
            pump.cancel();await asyncio.gather(pump,return_exceptions=True)
        runner.handle_sig(signal.SIGTERM)
        try:await asyncio.wait_for(running,10)
        except asyncio.CancelledError:pass
        await close_worker(runner)
        for value in values:
            from arq.constants import job_key_prefix,in_progress_key_prefix,retry_key_prefix,result_key_prefix
            for ident in value['task_ids']:
                await redis.delete(*(p+'p62:'+ident for p in (job_key_prefix,in_progress_key_prefix,retry_key_prefix,result_key_prefix)))
        await redis.delete(queue,queue+':health','pao:studio:temporal:health','pao:studio:arq:health')
        await redis.aclose()
