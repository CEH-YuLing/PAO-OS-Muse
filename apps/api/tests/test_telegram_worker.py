"""Real isolated Redis/ARQ + PG + HTTP fixtures; never real Telegram/LLM."""
import asyncio,json,signal
from dataclasses import asdict
from datetime import timedelta
from uuid import uuid4
import httpx,pytest
from arq import create_pool
from arq.connections import RedisSettings
from arq.jobs import Job
from arq.worker import create_worker
from sqlalchemy import select,func,text
from pao.config import settings
from pao.db import Session,engine
from pao.models import (Run,Member,ChannelBinding,ChannelOutbox,TelegramRuntimeProfile,
    TelegramRuntimeReceipt,TelegramConnection,TelegramPeer,Brain,now)
from pao.skills import execution_binding
from pao.modules.channels import telegram_worker as worker,telegram_runtime as rt,telegram_store as store,telegram_scoped as scoped,service
from test_telegram_scoped import enabled_bots,update,token,http,receive,Gateway,execute_run,identities
from test_telegram_sender import queued,state,success


@pytest.fixture
async def queue(enabled_bots,monkeypatch):
    config=RedisSettings.from_dsn(settings().redis_url);assert config.database==15
    prefix='pao-test:telegram-worker:'+uuid4().hex+':'
    monkeypatch.setattr(worker,'PREFIX',prefix);monkeypatch.setattr(worker,'QUEUE',prefix+'queue')
    redis=await create_pool(config)
    try:yield redis
    finally:
        keys=[]
        for pattern in (prefix+'*','arq:*'+prefix+'*'):
            keys.extend([key async for key in redis.scan_iter(match=pattern)])
        if keys:await redis.delete(*keys)
        await redis.aclose()


async def jobs(redis):
    return [Job(value.decode(),redis,_queue_name=worker.QUEUE) for value in await redis.zrange(worker.QUEUE,0,-1)]


async def run_queue(redis,factory,*,timeout=30,job_timeout=20):
    class IsolatedWorker(worker.WorkerSettings):
        functions=[worker.telegram_turn]
        redis_settings=RedisSettings.from_dsn(settings().redis_url)
        max_jobs=1
        max_tries=1
        retry_jobs=False
        keep_result=0
        queue_name=worker.QUEUE
        health_check_key=worker.PREFIX+'health'
        on_startup=None
        cron_jobs=[]
        burst=True
        max_burst_jobs=8
        poll_delay=.02
        handle_signals=False
        ctx={'telegram_transport_factory':factory}
    IsolatedWorker.job_timeout=job_timeout
    runner=create_worker(IsolatedWorker)
    try:
        await asyncio.wait_for(runner.async_run(),timeout)
        return runner.jobs_complete,runner.jobs_failed
    finally:
        if not hasattr(signal,'SIGUSR1'):
            runner.handle_sig(signal.SIGTERM);runner._handle_signals=True
        await runner.close()


def fixture_http(updates,seen,*,hook=None):
    def factory(pin):
        async def handle(request):
            method=request.url.path.rsplit('/',1)[-1];payload=json.loads(request.content)
            assert request.url.path=='/bot'+token(pin).get_secret_value()+'/'+method
            # Worker owns one DB slot, including HTTP, not one slot per phase.
            assert engine.pool.checkedout()==1
            seen.append((pin.connection_id,method,payload))
            if hook:
                response=await hook(pin,method,payload)
                if response is not None:return response
            if method=='getWebhookInfo':return httpx.Response(200,json={'ok':True,'result':{'url':'','pending_update_count':0}})
            if method=='getUpdates':return httpx.Response(200,json={'ok':True,'result':updates})
            assert method=='sendMessage'
            return httpx.Response(200,json=success(pin,payload))
        return httpx.MockTransport(handle)
    return factory


async def test_real_arq_two_smes_receive_native_run_then_restart_collect_send(queue,enabled_bots):
    f=enabled_bots;seen=[]
    assert await worker.dispatch({'redis':queue})=={'enqueued':2}
    assert await worker.dispatch({'redis':queue})=={'enqueued':0}
    for job in await jobs(queue):
        info=await job.info();assert info.function=='telegram_turn' and len(info.args)==3
        assert all(token(pin).get_secret_value() not in repr(info.args) for pin in f['pins'])
    assert await run_queue(queue,fixture_http([update()],seen))==(2,0)
    async with Session() as db:
        runs=list(await db.scalars(select(Run)));assert len(runs)==2 and len({r.workspace_id for r in runs})==2
        assert await db.scalar(select(func.count()).select_from(TelegramRuntimeReceipt))==2
    for run in runs:await execute_run({'gateway':Gateway()},run.id)
    assert await worker.dispatch({'redis':queue})=={'enqueued':2}
    assert await run_queue(queue,fixture_http([],seen))==(2,0)
    async with Session() as db:
        deliveries=list(await db.scalars(select(ChannelOutbox)));assert len(deliveries)==2
        assert all(row.status=='sent' and row.remote_id=='123' and row.attempts==1 for row in deliveries)
    assert sorted(payload['offset'] for _,method,payload in seen if method=='getUpdates')==[0,0,8,8]
    assert len([m for _,m,_ in seen if m=='sendMessage'])==2


@pytest.mark.parametrize('loss',['owner','actor','rotate','disable','ticket'])
async def test_queued_epoch_rechecks_scope_and_other_sme_continues(queue,enabled_bots,loss):
    f=enabled_bots;a,b=f['pins'];seen=[]
    await worker.dispatch({'redis':queue})
    if loss in ('owner','actor'):
        async with Session.begin() as db:(await db.get(Member,(a.workspace_id,f[loss]))).role='viewer'
    elif loss in ('rotate','disable'):
        async with rt.own_bot(a) as lease:
            if loss=='rotate':await store.save_profile(lease,token(a),expected_generation=2,request_key=str(uuid4()),consent=True)
            else:await scoped.control_profile(lease,generation=2,request_key=str(uuid4()),action='disable',consent=True)
    else:await queue.set(worker._ticket(a.workspace_id),'replacement-owner',ex=60)
    assert await run_queue(queue,fixture_http([update()],seen))==(2,0)
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(Run).where(Run.workspace_id==a.workspace_id))==0
        assert await db.scalar(select(func.count()).select_from(Run).where(Run.workspace_id==b.workspace_id))==1
    if loss!='actor':assert all(cid!=a.connection_id for cid,_,_ in seen)
    if loss=='ticket':assert await queue.get(worker._ticket(a.workspace_id))==b'replacement-owner'


async def test_stale_source_binding_is_not_repinned_or_called(queue,enabled_bots,monkeypatch):
    monkeypatch.setattr(worker,'execution_binding',lambda:{'policy':'exact-backend-source-v1','sha256':'0'*64})
    await worker.dispatch({'redis':queue});seen=[]
    assert await run_queue(queue,fixture_http([update()],seen))==(2,0)
    assert not seen
    async with Session() as db:assert await db.scalar(select(func.count()).select_from(Run))==0
    assert not any([await queue.exists(worker._ticket(p.workspace_id)) for p in enabled_bots['pins']])


@pytest.mark.parametrize('flag',['telegram_scoped_runtime_enabled','telegram_enabled','channels_enabled'])
async def test_disabled_worker_dispatch_does_not_read_profiles_or_call_provider(queue,enabled_bots,monkeypatch,flag):
    monkeypatch.setattr(settings(),flag,flag=='telegram_enabled')
    assert await worker.dispatch({'redis':queue})=={'enqueued':0}
    assert await queue.zcard(worker.QUEUE)==0


async def test_queue_capacity_and_workspace_rotation_are_bounded(queue,enabled_bots,monkeypatch):
    monkeypatch.setattr(worker,'CAPACITY',1);seen=[]
    assert await worker.dispatch({'redis':queue})=={'enqueued':1}
    first=(await (await jobs(queue))[0].info()).args[0]['workspace_id']
    assert await worker.dispatch({'redis':queue})=={'enqueued':0}
    assert await run_queue(queue,fixture_http([],seen))==(1,0)
    assert await worker.dispatch({'redis':queue})=={'enqueued':1}
    second=(await (await jobs(queue))[0].info()).args[0]['workspace_id']
    assert first!=second


async def test_dispatcher_lock_does_not_publish_a_second_batch(queue,enabled_bots):
    async with Session.begin() as db:
        assert await db.scalar(text("SELECT pg_try_advisory_xact_lock(hashtextextended('pao-telegram-dispatch-v1',0))"))
        assert await worker.dispatch({'redis':queue})=={'enqueued':0}
    assert await worker.dispatch({'redis':queue})=={'enqueued':2}


async def test_ticket_lost_after_fetch_does_not_ack_unadmitted_update(queue,enabled_bots):
    f=enabled_bots;a=f['pins'][0];seen=[];await worker.dispatch({'redis':queue})
    async def lose(pin,method,payload):
        if pin==a and method=='getUpdates':await queue.set(worker._ticket(a.workspace_id),'new-owner',ex=60)
    await run_queue(queue,fixture_http([update()],seen,hook=lose))
    async with Session() as db:
        profile=await db.scalar(select(TelegramRuntimeProfile).where(TelegramRuntimeProfile.connection_id==a.connection_id))
        assert profile.next_offset==0
        assert await db.scalar(select(func.count()).select_from(TelegramRuntimeReceipt).where(TelegramRuntimeReceipt.connection_id==a.connection_id))==0
    assert await queue.get(worker._ticket(a.workspace_id))==b'new-owner'


async def test_webhook_conflict_backoff_is_per_bot_and_never_deletes_hook(queue,enabled_bots):
    f=enabled_bots;a=f['pins'][0];seen=[]
    async def conflict(pin,method,payload):
        if pin==a and method=='getWebhookInfo':
            return httpx.Response(200,json={'ok':True,'result':{'url':'https://fixture.invalid/hook','pending_update_count':0}})
    await worker.dispatch({'redis':queue});await run_queue(queue,fixture_http([update()],seen,hook=conflict))
    assert [(cid,m) for cid,m,_ in seen if cid==a.connection_id]==[(a.connection_id,'getWebhookInfo')]
    assert await queue.exists(worker._backoff(a,2))
    assert await worker.dispatch({'redis':queue})=={'enqueued':1}


async def test_real_arq_timeout_does_not_retry_unknown_send_on_next_epoch(queue,enabled_bots):
    f=enabled_bots;a,b=f['pins'];ident=await queued(f);seen=[]
    async def hang(pin,method,payload):
        if pin==a and method=='sendMessage':await asyncio.Event().wait()
    await worker.dispatch({'redis':queue})
    complete,failed=await run_queue(queue,fixture_http([],seen,hook=hang),job_timeout=2)
    assert (complete,failed)==(1,1) and (await state(ident))[:2]==('sending',1)
    assert not await queue.exists(worker._ticket(a.workspace_id))
    await worker.dispatch({'redis':queue});await run_queue(queue,fixture_http([],seen))
    assert len([m for cid,m,_ in seen if cid==a.connection_id and m=='sendMessage'])==1
    async with Session.begin() as db:(await db.get(ChannelOutbox,ident)).updated_at=now()-timedelta(minutes=3)
    await service.reconcile_stale(connection_id=a.connection_id)
    assert (await state(ident))[0]=='unknown'


async def test_actor_lock_contention_rolls_back_receipt_cursor_then_retry_succeeds(queue,enabled_bots):
    f=enabled_bots;pin=f['pins'][0]
    async with Session.begin() as db:
        await db.get(Member,(pin.workspace_id,f['actor']),with_for_update=True)
        with pytest.raises(rt.TelegramRuntimeError,match='store_unavailable'):
            await asyncio.wait_for(receive(f),2)
        assert await db.get(ChannelBinding,f['bindings'][0],with_for_update={'nowait':True})
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(TelegramRuntimeReceipt))==0
        assert (await db.scalar(select(TelegramRuntimeProfile).where(TelegramRuntimeProfile.connection_id==pin.connection_id))).next_offset==0
    assert (await receive(f)).disposition=='accepted'


async def test_stop_lock_contention_does_not_drop_stop_or_cancel_twice(queue,enabled_bots):
    f=enabled_bots;received=await receive(f)
    async with Session.begin() as db:
        await db.get(Run,received.run_id,with_for_update=True)
        with pytest.raises(rt.TelegramRuntimeError,match='store_unavailable'):
            await asyncio.wait_for(receive(f,value=update(8,'/stop'),offset=8),2)
    assert (await receive(f,value=update(8,'/stop'),offset=8)).disposition=='command'
    assert (await receive(f,value=update(8,'/stop'),offset=9)).disposition=='duplicate'
    async with Session() as db:assert (await db.get(Run,received.run_id)).status=='cancelled'


async def test_worker_policy_is_separate_and_does_not_retry_or_use_chat_queue():
    assert worker.WorkerSettings.queue_name=='pao:telegram:scoped:queue'
    assert worker.WorkerSettings.max_jobs==worker.WorkerSettings.max_tries==1
    assert worker.WorkerSettings.retry_jobs is False
    assert worker.WorkerSettings.functions==[worker.telegram_turn]
    assert worker.WorkerSettings.job_timeout<120
    assert worker.WorkerSettings.on_startup is worker.startup
    assert worker.WorkerSettings.on_shutdown is worker.shutdown
    assert worker.WorkerSettings.cron_jobs==[]


async def add_bot(f,kind=None):
    pin=f['pins'][0]
    async with Session.begin() as db:
        connection=TelegramConnection(workspace_id=pin.workspace_id,owner_id=f['owner'],bot_user_id='333')
        db.add(connection);await db.flush()
        other=rt.RuntimePin(connection.workspace_id,connection.id,connection.owner_id,connection.version,'333')
    async with rt.own_bot(other) as lease:
        await identities.verify_identity(lease,token(other),request_key=str(uuid4()),consent=True,transport=http(other))
        await store.save_profile(lease,token(other),expected_generation=0,request_key=str(uuid4()),consent=True)
        await scoped.control_profile(lease,generation=1,request_key=str(uuid4()),action='enable',consent=True,transport=http(other))
    if kind is None:return other,None
    async with Session.begin() as db:
        brain=Brain(workspace_id=pin.workspace_id,owner_id=f['actor'],name='Customer private');db.add(brain)
        peer=TelegramPeer(workspace_id=pin.workspace_id,user_id=f['actor'],connection_id=other.connection_id,
            telegram_user_id='777',chat_id='777',enabled=True);db.add(peer);await db.flush()
        binding=ChannelBinding(workspace_id=pin.workspace_id,connection_id=other.connection_id,actor_id=f['actor'],
            channel='telegram',identity_hash=service.identity('telegram','777:777',other.connection_id),peer_id=peer.id,
            brain_id=brain.id,kind=kind,mode='auto',enabled=True,outbound_confirmed=True)
        db.add(binding);await db.flush();bid=binding.id
    return other,bid


async def test_multiple_bots_in_one_sme_rotate_without_extra_sme_slots(queue,enabled_bots):
    f=enabled_bots;other,_=await add_bot(f);seen=[]
    for _ in range(2):
        assert await worker.dispatch({'redis':queue})=={'enqueued':2}
        infos=[await j.info() for j in await jobs(queue)]
        assert len({info.args[0]['workspace_id'] for info in infos})==2
        assert await run_queue(queue,fixture_http([],seen))==(2,0)
    same_sme={cid for cid,method,_ in seen if method=='getUpdates' and cid in (other.connection_id,f['pins'][0].connection_id)}
    assert len(same_sme)==2


async def test_expired_reservation_is_replaced_old_job_cannot_delete_new_ticket(queue,enabled_bots):
    f=enabled_bots;await worker.dispatch({'redis':queue});old=[await j.info() for j in await jobs(queue)]
    # Simulate TTL expiry, not a data/credential reset. Old queue entries remain.
    await queue.delete(worker._ticket(f['pins'][0].workspace_id))
    assert await worker.dispatch({'redis':queue})=={'enqueued':1}
    ticket=await queue.get(worker._ticket(f['pins'][0].workspace_id));seen=[]
    stale=next(info for info in old if info.args[0]['workspace_id']==f['pins'][0].workspace_id)
    result=await worker.telegram_turn({'redis':queue,'job_id':stale.job_id,'telegram_transport_factory':fixture_http([],seen)},*stale.args)
    assert result['status']=='deferred' and not seen
    assert await queue.get(worker._ticket(f['pins'][0].workspace_id))==ticket


async def test_provider_429_backoff_is_not_shared_with_other_sme(queue,enabled_bots):
    f=enabled_bots;a=f['pins'][0];ident=await queued(f);seen=[]
    async def limit(pin,method,payload):
        if pin==a and method=='sendMessage':return httpx.Response(429,json={'ok':False,'error_code':429,'parameters':{'retry_after':30}})
    await worker.dispatch({'redis':queue});assert await run_queue(queue,fixture_http([],seen,hook=limit))==(2,0)
    assert (await state(ident))[:2]==('queued',1)
    assert 25<=await queue.ttl(worker._backoff(a,2))<=30
    assert await worker.dispatch({'redis':queue})=={'enqueued':1}


async def test_unknown_receipt_is_not_replayed_by_new_worker(queue,enabled_bots):
    f=enabled_bots;a=f['pins'][0];ident=await queued(f);seen=[]
    async def uncertain(pin,method,payload):
        if pin==a and method=='sendMessage':return httpx.Response(500,json={'ok':False,'error_code':500})
    await worker.dispatch({'redis':queue});await run_queue(queue,fixture_http([],seen,hook=uncertain))
    assert (await state(ident))[0]=='unknown'
    await queue.delete(worker._backoff(a,2))
    await worker.dispatch({'redis':queue});await run_queue(queue,fixture_http([],seen))
    assert len([m for cid,m,_ in seen if cid==a.connection_id and m=='sendMessage'])==1


async def test_retention_skips_locked_native_run_without_binding_run_cycle(queue,enabled_bots,monkeypatch):
    # Retention is opt-in after S6.2; this corpus exercises the legacy lock path.
    monkeypatch.setattr(settings(),'channel_retention_enabled',True)
    f=enabled_bots;pin,bid=await add_bot(f,'customer')
    for name in ('channel_autoreply_enabled','knowledge_enabled','knowledge_sources_enabled'):
        monkeypatch.setattr(settings(),name,True)
    customer={**f,'pins':[pin],'bindings':[bid]}
    result=await receive(customer);assert result.disposition=='accepted'
    await execute_run({'gateway':Gateway()},result.run_id)
    async with Session.begin() as db:
        from pao.models import ChannelInbound
        row=await db.scalar(select(ChannelInbound).where(ChannelInbound.run_id==result.run_id))
        row.created_at=now()-timedelta(days=60)
    async with Session.begin() as db:
        run=await db.get(Run,result.run_id,with_for_update=True);assert run.status=='completed'
        assert await asyncio.wait_for(service.purge_expired(bid),2)=={'purged':0}
        assert await db.get(ChannelBinding,bid,with_for_update={'nowait':True})
    assert await service.purge_expired(bid)=={'purged':1}
    async with Session() as db:assert (await db.get(Run,result.run_id)).response=='[retention purged]'


async def test_scheduler_startup_is_singleton_shutdown_releases_background_task(queue,enabled_bots):
    ctx={'redis':queue}
    await worker.startup(ctx);task=ctx['telegram_dispatch_task']
    try:
        assert ctx['telegram_last_dispatch']=={'enqueued':2}
        await worker.startup(ctx);assert ctx['telegram_dispatch_task'] is task
        assert not task.done()
        infos=[await j.info() for j in await jobs(queue)]
        assert len(infos)==2 and all(info.function=='telegram_turn' for info in infos)
    finally:await worker.shutdown(ctx)
    assert task.done() and 'telegram_dispatch_task' not in ctx


async def test_scheduler_off_creates_no_background_task_or_queue_entries(queue,enabled_bots,monkeypatch):
    monkeypatch.setattr(settings(),'telegram_scoped_runtime_enabled',False)
    ctx={'redis':queue};await worker.startup(ctx)
    assert 'telegram_dispatch_task' not in ctx and await queue.zcard(worker.QUEUE)==0
    await worker.shutdown(ctx)


async def test_periodic_scanner_does_not_enqueue_cron_or_duplicate_tickets(queue,enabled_bots):
    ctx={'redis':queue};await worker.startup(ctx)
    try:
        # Real periodic loop and Redis, not a mocked dispatch callback.
        await asyncio.sleep(5.2)
        assert ctx['telegram_last_dispatch']=={'enqueued':0}
        infos=[await j.info() for j in await jobs(queue)]
        assert len(infos)==2 and all(info.function=='telegram_turn' for info in infos)
    finally:await worker.shutdown(ctx)
