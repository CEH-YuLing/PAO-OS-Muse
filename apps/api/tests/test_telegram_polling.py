"""Actual bounded polling HTTP adapter + native PostgreSQL/Channels admission.

All provider credentials are synthetic; default network transport is forbidden.
"""
import asyncio,json,logging
from uuid import uuid4
import httpx,pytest
from sqlalchemy import select,func
from pao.config import settings
from pao.db import Session
from pao.models import TelegramRuntimeProfile,TelegramRuntimeReceipt,Run,Member,ChannelInbound
from pao.modules.channels import telegram_polling as polling,telegram_runtime as rt,telegram_scoped as scoped,telegram_store as store
from test_telegram_scoped import enabled_bots,update,token


def fixture_http(pin,updates,seen,*,webhook=False,check=None):
    async def handle(request):
        method=request.url.path.rsplit('/',1)[-1]
        assert request.url.host=='api.telegram.org' and request.method=='POST'
        assert request.url.path=='/bot'+token(pin).get_secret_value()+'/'+method
        assert 'authorization' not in request.headers
        body=json.loads(request.content);seen.append((method,body))
        if method=='getWebhookInfo':
            assert body=={}
            return httpx.Response(200,json={'ok':True,'result':{'url':'https://fixture.invalid/hook' if webhook else '', 'pending_update_count':0}})
        assert method=='getUpdates' and body=={'offset':body['offset'],'timeout':5,'limit':5,'allowed_updates':['message','callback_query']}
        if check:await check(body)
        return httpx.Response(200,json={'ok':True,'result':updates})
    return httpx.MockTransport(handle)


async def snapshot(pin):
    async with Session() as db:
        profile=await db.scalar(select(TelegramRuntimeProfile).where(TelegramRuntimeProfile.connection_id==pin.connection_id))
        receipts=await db.scalar(select(func.count()).select_from(TelegramRuntimeReceipt).where(TelegramRuntimeReceipt.connection_id==pin.connection_id))
        runs=await db.scalar(select(func.count()).select_from(Run).where(Run.workspace_id==pin.workspace_id))
        return profile.next_offset,receipts,runs


async def test_two_bots_same_ids_durable_ack_and_restart_no_duplicate_run(enabled_bots):
    f=enabled_bots
    for pin in f['pins']:
        seen=[]
        result=await polling.poll_once(pin,f['redis'],transport=fixture_http(pin,[update()],seen))
        assert result==polling.PollResult(1,8) and await snapshot(pin)==(8,1,1)
        assert seen[1][1]['offset']==0
        async def committed(body):
            assert body['offset']==8 and await snapshot(pin)==(8,1,1)
        # A new invocation reopens the lease and reads DB, not a process cursor.
        result=await polling.poll_once(pin,f['redis'],transport=fixture_http(pin,[],seen,check=committed))
        assert result==polling.PollResult(0,8) and await snapshot(pin)==(8,1,1)
        assert 'Xin chào' not in repr(result)
    assert f['pins'][0].workspace_id!=f['pins'][1].workspace_id


async def test_failure_mid_batch_acks_only_committed_prefix_on_next_turn(enabled_bots,monkeypatch):
    f=enabled_bots;pin=f['pins'][0];original=scoped.ingest_update
    async def fail_second(lease,**kwargs):
        if kwargs['update']['update_id']==8:raise rt.TelegramRuntimeError('fixture_admission_failure')
        return await original(lease,**kwargs)
    monkeypatch.setattr(scoped,'ingest_update',fail_second)
    with pytest.raises(rt.TelegramRuntimeError,match='fixture_admission_failure'):
        await polling.poll_once(pin,f['redis'],transport=fixture_http(pin,[update(),update(8)],[]))
    assert await snapshot(pin)==(8,1,1)
    monkeypatch.setattr(scoped,'ingest_update',original);seen=[]
    assert (await polling.poll_once(pin,f['redis'],transport=fixture_http(pin,[update(8)],seen))).next_offset==9
    assert seen[1][1]['offset']==8 and await snapshot(pin)==(9,2,1)
    # Native Channels keeps a busy inbound rather than starting another run.
    # Both the input and receipt survive restart; active-run protection stays.
    async with Session() as db:
        receipt=await db.scalar(select(TelegramRuntimeReceipt).where(TelegramRuntimeReceipt.update_id==8))
        incoming=await db.get(ChannelInbound,receipt.inbound_id)
        assert receipt.reason=='inbound' and incoming.status=='busy' and incoming.run_id is None


async def test_cancel_after_fetch_before_admission_has_no_ack_and_releases_lease(enabled_bots,monkeypatch):
    f=enabled_bots;pin=f['pins'][0];entered=asyncio.Event();original=scoped.ingest_update
    async def pause(*args,**kwargs):entered.set();await asyncio.Event().wait()
    monkeypatch.setattr(scoped,'ingest_update',pause)
    task=asyncio.create_task(polling.poll_once(pin,f['redis'],transport=fixture_http(pin,[update()],[])))
    try:
        await asyncio.wait_for(entered.wait(),5);task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
    finally:
        if not task.done():task.cancel()
        await asyncio.gather(task,return_exceptions=True)
    assert await snapshot(pin)==(0,0,0)
    monkeypatch.setattr(scoped,'ingest_update',original)
    assert (await polling.poll_once(pin,f['redis'],transport=fixture_http(pin,[update()],[]))).next_offset==8


@pytest.mark.parametrize('change',['disable','rotate','owner','actor','flag'])
async def test_authority_rechecked_between_http_fetch_and_admission(enabled_bots,monkeypatch,change):
    f=enabled_bots;pin=f['pins'][0];original=scoped.ingest_update
    async def changing(lease,**kwargs):
        if change=='disable':
            await scoped.control_profile(lease,generation=2,request_key=str(uuid4()),action='disable',consent=True)
        elif change=='rotate':
            await store.save_profile(lease,token(pin),expected_generation=2,request_key=str(uuid4()),consent=True)
        elif change=='flag':monkeypatch.setattr(settings(),'telegram_scoped_runtime_enabled',False)
        else:
            async with Session.begin() as db:
                member=await db.get(Member,(pin.workspace_id,f['owner'] if change=='owner' else f['actor']))
                member.role='viewer'
        return await original(lease,**kwargs)
    monkeypatch.setattr(scoped,'ingest_update',changing)
    if change=='actor':
        result=await polling.poll_once(pin,f['redis'],transport=fixture_http(pin,[update()],[]))
        assert result.next_offset==8 and await snapshot(pin)==(8,1,0)
        async with Session() as db:assert (await db.scalar(select(TelegramRuntimeReceipt))).reason=='blocked'
    else:
        with pytest.raises(rt.TelegramRuntimeError):
            await polling.poll_once(pin,f['redis'],transport=fixture_http(pin,[update()],[]))
        assert await snapshot(pin)==(0,0,0)


async def test_one_active_poll_owner_per_actual_bot_other_sme_not_blocked(enabled_bots):
    f=enabled_bots;a,b=f['pins'];entered=asyncio.Event();release=asyncio.Event()
    async def hold(body):entered.set();await release.wait()
    task=asyncio.create_task(polling.poll_once(a,f['redis'],transport=fixture_http(a,[],[],check=hold)))
    try:
        await asyncio.wait_for(entered.wait(),5);seen=[]
        with pytest.raises(rt.TelegramRuntimeError,match='bot_busy'):
            await polling.poll_once(a,f['redis'],transport=fixture_http(a,[],seen))
        assert seen==[]
        assert (await polling.poll_once(b,f['redis'],transport=fixture_http(b,[update()],[]))).next_offset==8
    finally:release.set();await task
    async with rt.own_bot(a):pass


async def test_inflight_fetch_serializes_owner_revoke_next_turn_denied(enabled_bots):
    f=enabled_bots;pin=f['pins'][0];entered=asyncio.Event();release=asyncio.Event()
    async def hold(body):entered.set();await release.wait()
    async def revoke():
        async with Session.begin() as db:
            member=await db.get(Member,(pin.workspace_id,f['owner']),with_for_update=True);member.role='viewer'
    task=asyncio.create_task(polling.poll_once(pin,f['redis'],transport=fixture_http(pin,[],[],check=hold)))
    changing=None
    try:
        await asyncio.wait_for(entered.wait(),5);changing=asyncio.create_task(revoke())
        await asyncio.sleep(.1);assert not changing.done()
        release.set();await task;await changing
        seen=[]
        with pytest.raises(rt.TelegramRuntimeError,match='owner_unavailable'):
            await polling.poll_once(pin,f['redis'],transport=fixture_http(pin,[],seen))
        assert not seen
    finally:
        release.set();await asyncio.gather(task,*([] if changing is None else [changing]),return_exceptions=True)


async def test_webhook_conflict_never_polls_or_changes_provider_mode(enabled_bots):
    f=enabled_bots;pin=f['pins'][0];seen=[]
    with pytest.raises(rt.TelegramRuntimeError,match='webhook_conflict'):
        await polling.poll_once(pin,f['redis'],transport=fixture_http(pin,[update()],seen,webhook=True))
    assert [m for m,_ in seen]==['getWebhookInfo'] and await snapshot(pin)==(0,0,0)


@pytest.mark.parametrize('batch',[
    {},[None],[{'update_id':True}],[{'update_id':-1}],[{'update_id':1.5}],
    [{}],[{'update_id':2**63-1}],[update(8),update(7)],[update(),update()],
    [update(i) for i in range(6)],
])
async def test_malformed_batch_rejected_whole_before_admission(enabled_bots,batch):
    f=enabled_bots;pin=f['pins'][0]
    with pytest.raises(rt.TelegramRuntimeError):
        await polling.poll_once(pin,f['redis'],transport=fixture_http(pin,batch,[]))
    assert await snapshot(pin)==(0,0,0)


@pytest.mark.parametrize('fault',['timeout','redirect','rate_limit','mime','large','json','echo','not_ok'])
async def test_poll_failures_bounded_no_ack_no_retry_no_secret_logs(enabled_bots,caplog,fault):
    f=enabled_bots;pin=f['pins'][0];seen=[];caplog.set_level(logging.DEBUG)
    def handle(request):
        method=request.url.path.rsplit('/',1)[-1];seen.append(method)
        logging.getLogger('httpcore.http11').debug('protected %s',request.url)
        if method=='getWebhookInfo':return httpx.Response(200,json={'ok':True,'result':{'url':'','pending_update_count':0}})
        if fault=='timeout':raise httpx.ReadTimeout('private '+str(request.url),request=request)
        if fault=='redirect':return httpx.Response(307,headers={'Location':'https://fixture.invalid/'+token(pin).get_secret_value()})
        if fault=='rate_limit':return httpx.Response(429,json={'ok':False,'parameters':{'retry_after':1}})
        if fault=='mime':return httpx.Response(200,text='private')
        if fault=='large':return httpx.Response(200,content=b' '*(polling.MAX_POLL_BYTES+1),headers={'content-type':'application/json'})
        if fault=='json':return httpx.Response(200,content=b'{',headers={'content-type':'application/json'})
        if fault=='echo':return httpx.Response(200,json={'ok':True,'result':[],'echo':token(pin).get_secret_value()})
        return httpx.Response(200,json={'ok':False,'description':'PRIVATE'})
    with pytest.raises(rt.TelegramRuntimeError) as error:
        await polling.poll_once(pin,f['redis'],transport=httpx.MockTransport(handle))
    assert seen==['getWebhookInfo','getUpdates'] and await snapshot(pin)==(0,0,0)
    assert token(pin).get_secret_value() not in caplog.text+str(error.value)
    assert 'PRIVATE' not in str(error.value)


@pytest.mark.parametrize('gate',['scoped_off','host_on','disabled','missing_queue'])
async def test_gates_deny_before_any_http_or_host_token_fallback(enabled_bots,monkeypatch,gate):
    f=enabled_bots;pin=f['pins'][0];seen=[]
    monkeypatch.setattr(settings(),'telegram_bot_token','999:HOST_MUST_NEVER_BE_USED')
    if gate=='scoped_off':monkeypatch.setattr(settings(),'telegram_scoped_runtime_enabled',False)
    elif gate=='host_on':monkeypatch.setattr(settings(),'telegram_enabled',True)
    elif gate=='disabled':
        async with rt.own_bot(pin) as lease:
            await scoped.control_profile(lease,generation=2,request_key=str(uuid4()),action='disable',consent=True)
    with pytest.raises(rt.TelegramRuntimeError):
        await polling.poll_once(pin,None if gate=='missing_queue' else f['redis'],transport=fixture_http(pin,[update()],seen))
    assert not seen and await snapshot(pin)==(0,0,0)


async def test_unlinked_and_callback_are_durably_quarantined_no_new_actor_or_run(enabled_bots):
    f=enabled_bots;pin=f['pins'][0];unknown=update();unknown['message']['from']['id']=888;unknown['message']['chat']['id']=888
    result=await polling.poll_once(pin,f['redis'],transport=fixture_http(pin,[unknown,{'update_id':8,'callback_query':{'id':'untrusted'}}],[]))
    assert result==polling.PollResult(2,9) and await snapshot(pin)==(9,2,0)
    async with Session() as db:
        assert set(await db.scalars(select(TelegramRuntimeReceipt.reason)))=={'unlinked','unsupported'}


@pytest.mark.parametrize('loss',['disconnect','unlock'])
async def test_database_lease_lost_after_fetch_never_admits_and_fresh_turn_recovers(enabled_bots,monkeypatch,loss):
    from sqlalchemy import text
    f=enabled_bots;pin=f['pins'][0];original=scoped.ingest_update
    async def lose(lease,**kwargs):
        if loss=='disconnect':await lease.connection.invalidate()
        else:
            assert await lease.connection.scalar(text('SELECT pg_advisory_unlock(hashtextextended(:key,0))'),{'key':'pao-telegram-bot-v1:'+pin.bot_user_id})
            await lease.connection.commit()
        return await original(lease,**kwargs)
    monkeypatch.setattr(scoped,'ingest_update',lose)
    with pytest.raises(rt.TelegramRuntimeError,match='lease_lost'):
        await polling.poll_once(pin,f['redis'],transport=fixture_http(pin,[update()],[]))
    assert await snapshot(pin)==(0,0,0)
    monkeypatch.setattr(scoped,'ingest_update',original)
    assert (await polling.poll_once(pin,f['redis'],transport=fixture_http(pin,[update()],[]))).next_offset==8


async def test_turn_deadline_cancels_http_without_ack_and_releases_bot(enabled_bots,monkeypatch):
    f=enabled_bots;pin=f['pins'][0];seen=[]
    async def hold(body):await asyncio.Event().wait()
    monkeypatch.setattr(polling,'TURN_SECONDS',2)
    with pytest.raises(rt.TelegramRuntimeError,match='turn_timeout'):
        await polling.poll_once(pin,f['redis'],transport=fixture_http(pin,[],seen,check=hold))
    assert [m for m,_ in seen]==['getWebhookInfo','getUpdates'] and await snapshot(pin)==(0,0,0)
    async with rt.own_bot(pin):pass


async def test_old_provider_batch_cannot_rewind_committed_cursor(enabled_bots):
    f=enabled_bots;pin=f['pins'][0]
    await polling.poll_once(pin,f['redis'],transport=fixture_http(pin,[update()],[]))
    with pytest.raises(rt.TelegramRuntimeError):
        await polling.poll_once(pin,f['redis'],transport=fixture_http(pin,[update()],[]))
    assert await snapshot(pin)==(8,1,1)


async def test_maximum_batch_is_bounded_and_all_receipts_commit(enabled_bots):
    f=enabled_bots;pin=f['pins'][0]
    updates=[{'update_id':i,'callback_query':{'id':'unsupported'}} for i in range(5)]
    assert await polling.poll_once(pin,f['redis'],transport=fixture_http(pin,updates,[]))==polling.PollResult(5,5)
    assert await snapshot(pin)==(5,5,0)


async def test_large_valid_batch_does_not_hit_single_update_response_limit(enabled_bots):
    f=enabled_bots;pin=f['pins'][0]
    # Telegram may return multiple full-size messages. Bound the whole batch,
    # not all five updates combined to the single-item 64KiB budget.
    updates=[update(i,body='ữ'*4000) for i in range(5)]
    assert len(json.dumps({'ok':True,'result':updates}).encode())>rt.MAX_BYTES
    assert await polling.poll_once(pin,f['redis'],transport=fixture_http(pin,updates,[]))==polling.PollResult(5,5)
    assert await snapshot(pin)==(5,5,0)
    async with Session() as db:assert set(await db.scalars(select(TelegramRuntimeReceipt.reason)))=={'malformed'}
