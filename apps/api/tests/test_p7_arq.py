"""Shared dispatcher + genuine ARQ/Redis15; deterministic in-process model only."""
from uuid import uuid4
import os
from arq import create_pool
from arq.connections import RedisSettings
from arq.worker import Worker
from sqlalchemy import select,func
from pao.config import settings
from pao.main import app
from pao.db import Session
from pao.models import Run,ChannelOutbox
from pao.runtime import dispatch,execute_run
from test_channels import channels_on,binding,control,inbound
from test_voice import voice
from test_voice_turns import turns,create,record
from test_memory import Gateway

async def test_shared_dispatcher_recovers_channel_and_voice_on_real_arq(client,identity,channels_on,turns):
    cfg=settings();rs=RedisSettings.from_dsn(cfg.redis_url)
    assert os.environ['DATABASE_URL'].endswith('/pao_test') and rs.database==15
    queue='pao-test:p7:'+uuid4().hex;pool=await create_pool(rs,default_queue_name=queue)
    original=app.state.redis;app.state.redis=pool;worker=None
    try:
        row,_=await binding(client,identity);row=await control(client,identity,row,'auto')
        channel=(await inbound(client,identity,row,'Channel qua hàng đợi')).json()
        value,_=await create(client,identity);turn=(await record(client,identity,value.json())).json()
        r=await client.post('/v1/voice/turns/'+turn['id']+'/submit',headers=identity['owner'],json={'version':turn['version'],'confirm_transcript':True});assert r.status_code==200
        await dispatch({'redis':pool})
        worker=Worker([execute_run],redis_pool=pool,queue_name=queue,burst=True,max_jobs=1,keep_result=0,job_timeout=30,max_tries=1,handle_signals=False,ctx={'gateway':Gateway()})
        await worker.async_run()
        assert worker.jobs_complete==2 and worker.jobs_failed==0
        await dispatch({'redis':pool})
        async with Session() as db:
            rows=list(await db.scalars(select(Run)));assert len(rows)==2 and all(run.status=='completed' for run in rows)
            assert {run.id for run in rows}=={channel['run_id'],r.json()['id']}
            assert await db.scalar(select(func.count(ChannelOutbox.id)))==1
    finally:
        app.state.redis=original
        if worker:
            import signal
            if not hasattr(signal,'SIGUSR1'):
                worker.handle_sig(signal.SIGTERM);worker._handle_signals=True
            await worker.close()
        else:await pool.aclose()
