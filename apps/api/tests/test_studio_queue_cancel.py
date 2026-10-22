"""Real isolated Redis15/ARQ abort ACK; no live business runner."""
import asyncio
import signal
from uuid import uuid4
import pytest
from arq import create_pool
from arq.connections import RedisSettings
from arq.worker import create_worker
from arq.constants import job_key_prefix,in_progress_key_prefix,retry_key_prefix,result_key_prefix,abort_jobs_ss
from sqlalchemy import select,func
from pao.config import settings
from pao.db import Session
from pao.models import StudioEvent,TaskAttempt
from pao.modules.studio import arq_bridge as bridge,queue_cancel as cancel
from test_durable_admission import gates,BASE
from test_studio_step_jobs import ready
from test_studio_arq_bridge import close_worker


async def request_cancel(client,identity,value):
    url=BASE+'/executions/'+value['plan_id']
    response=await client.post(url+'/cancel',headers=identity['owner'],json={
        'request_key':str(uuid4())})
    assert response.status_code==200,response.text


@pytest.mark.parametrize('mode',['running','queued','absent','mismatched','unserved'])
async def test_real_queue_cancel(client,identity,gates,monkeypatch,mode):
    value,ident=await ready(client,identity)
    args=(value['plan_id'],'first',ident)
    await bridge.jobs.reserve(*args)
    config=RedisSettings.from_dsn(settings().redis_url)
    assert config.database==15
    queue='pao-test:queue-cancel:'+uuid4().hex
    redis=await create_pool(config,default_queue_name=queue)
    claimed=asyncio.Event()
    original=bridge.jobs.claim
    async def paused(*args):
        result=await original(*args)
        claimed.set()
        await asyncio.Event().wait()
        return result
    monkeypatch.setattr(bridge.jobs,'claim',paused)
    class EchoWorker:
        functions=[bridge.execute_studio_echo]
        redis_settings=config
        queue_name=queue
        health_check_key=queue+':health'
        handle_signals=False
        allow_abort_jobs=True
        max_jobs=1
        keep_result=30
        max_tries=1
        poll_delay=.05
        job_timeout=20
    runner=None;running=None
    job_id='p62:'+ident
    try:
        if mode!='absent':
            await redis.enqueue_job('execute_studio_echo',*(args if mode!='mismatched' else (args[0],'second',args[2])),
                _job_id=job_id,_defer_by=60 if mode=='queued' else None)
        if mode=='running':
            runner=create_worker(EchoWorker)
            running=asyncio.create_task(runner.async_run())
            await asyncio.wait_for(claimed.wait(),10)
        await request_cancel(client,identity,value)
        if mode=='queued':
            runner=create_worker(EchoWorker)
            running=asyncio.create_task(runner.async_run())
        result=await cancel.cancel_queue_step(redis,*args,timeout_seconds=3)
        if mode in ('absent','mismatched','unserved'):
            assert result['status']=='unknown' and result['queue_ack_verified'] is False
            async with Session() as db:assert await db.get(StudioEvent,cancel.ack_id(ident)) is None
        else:
            assert result['queue_ack_verified'] is True,result
            async with Session() as db:
                event=await db.get(StudioEvent,cancel.ack_id(ident))
                assert event.data['ack']=='arq_aborted'
                assert event.data['queue_drained'] is True
                assert await db.scalar(select(func.count(TaskAttempt.id)))==(1 if mode=='running' else 0)
            assert await redis.zscore(queue,job_id) is None
            assert not await redis.exists(in_progress_key_prefix+job_id)
            # Retained Redis result is not necessary after the immutable ACK.
            await redis.delete(result_key_prefix+job_id)
            assert await cancel.cancel_queue_step(redis,*args)==result
            if mode=='running':
                async with Session() as db:
                    claim=await db.get(StudioEvent,bridge.jobs.event_id(ident,'claimed'))
                    attempt=await db.get(TaskAttempt,ident)
                    token=claim.data['token'];input_value=attempt.input
                assert (await bridge.jobs.finish(*args,token,input_value))['status']=='cancelled'
            async with Session() as db:
                assert await db.scalar(select(func.count(StudioEvent.id)).where(
                    StudioEvent.action=='p62_step_queue_cancel_ack'))==1
    finally:
        if runner:
            runner.handle_sig(signal.SIGTERM)
            try:await asyncio.wait_for(running,10)
            except asyncio.CancelledError:pass
            await close_worker(runner)
        await redis.delete(*(prefix+job_id for prefix in (
            job_key_prefix,in_progress_key_prefix,retry_key_prefix,result_key_prefix)))
        await redis.zrem(abort_jobs_ss,job_id)
        await redis.delete(queue,queue+':health')
        await redis.aclose()
