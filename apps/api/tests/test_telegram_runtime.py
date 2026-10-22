"""S3.2A real PG scope/lease + mock HTTP boundary; never a real provider token."""
import asyncio
from dataclasses import asdict,replace,FrozenInstanceError
import json,logging,os,subprocess,sys
from uuid import uuid4
from unittest.mock import AsyncMock
import httpx,pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import select,text
from pao.config import settings
from pao.db import Session
from pao.models import Workspace,Member,User,TelegramConnection,TelegramUpdate,TelegramDelivery,ChannelOutbox
from pao.modules.channels import telegram_runtime as rt

TOKENS=('111:'+('SYNTHETIC_A_'*4),'222:'+('SYNTHETIC_B_'*4))

@pytest.fixture
async def runtime(identity,monkeypatch):
    def forbidden_network(*args,**kwargs):raise AssertionError('Unexpected live transport in isolated tests')
    monkeypatch.setattr(httpx,'AsyncHTTPTransport',forbidden_network)
    monkeypatch.setattr(settings(),'telegram_scoped_runtime_enabled',True)
    monkeypatch.setattr(settings(),'telegram_enabled',False)
    monkeypatch.setattr(settings(),'integration_encryption_key',Fernet.generate_key().decode())
    # A legacy host credential must never become a fallback for either bot.
    monkeypatch.setattr(settings(),'telegram_bot_token','333:GLOBAL_MUST_NOT_BE_READ')
    async with Session.begin() as db:
        space=Workspace(name='Runtime SME B');db.add(space);await db.flush()
        db.add(Member(workspace_id=space.id,user_id=identity['user_id'],role='owner'))
        connections=[]
        for wid,bot in ((identity['workspace'],'111'),(space.id,'222')):
            row=TelegramConnection(workspace_id=wid,owner_id=identity['user_id'],bot_user_id=bot)
            db.add(row);connections.append(row)
        await db.flush()
        pins=[rt.RuntimePin(c.workspace_id,c.id,c.owner_id,c.version,c.bot_user_id) for c in connections]
    sealed=[rt.seal_credentials(pin,SecretStr(token)) for pin,token in zip(pins,TOKENS)]
    async def loader(db,pin):return sealed[pins.index(pin)]
    return pins,sealed,loader

def transport_for(pin,seen):
    def handle(request):
        seen.append(request.url.path)
        assert request.url.host=='api.telegram.org' and request.method=='POST'
        assert request.content==b'{}' and 'authorization' not in request.headers
        return httpx.Response(200,json={'ok':True,'result':{'id':int(pin.bot_user_id),'is_bot':True,'username':'fixture_bot'}})
    return httpx.MockTransport(handle)

async def test_two_bots_scoped_native_db_metadata_and_no_receipt_writes(client,runtime):
    pins,_,loader=runtime;seen=[]
    for pin,token in zip(pins,TOKENS):
        async with rt.own_bot(pin) as lease:
            result=await rt.probe(lease,loader,transport=transport_for(pin,seen))
        assert result.bot_user_id==pin.bot_user_id and token not in repr(result)
    assert seen==['/bot'+token+'/getMe' for token in TOKENS]
    async with Session() as db:
        for model in (TelegramUpdate,TelegramDelivery,ChannelOutbox):assert await db.scalar(select(model).limit(1)) is None

async def test_one_transport_owner_per_actual_bot_and_release_after_exit(client,runtime):
    a,b=runtime[0]
    async with rt.own_bot(a):
        async with rt.own_bot(b):pass
        forged=replace(b,bot_user_id=a.bot_user_id)
        with pytest.raises(rt.TelegramRuntimeError,match='bot_busy'):
            async with rt.own_bot(forged):pytest.fail('Actual bot, not namespace, owns the lease')
    async with rt.own_bot(a) as later:assert later.active
    assert not later.active

async def test_lease_released_after_cancellation_and_never_reused_after_exit(client,runtime):
    pin=runtime[0][0];entered=asyncio.Event()
    async def hold():
        async with rt.own_bot(pin):entered.set();await asyncio.Event().wait()
    task=asyncio.create_task(hold());await entered.wait();task.cancel()
    with pytest.raises(asyncio.CancelledError):await task
    async with rt.own_bot(pin) as lease:pass
    with pytest.raises(rt.TelegramRuntimeError,match='lease_lost'):await rt.probe(lease,runtime[2])

async def test_lost_database_session_cannot_silently_reconnect_with_old_lease(client,runtime):
    pin=runtime[0][0]
    async with rt.own_bot(pin) as lease:
        await lease.connection.invalidate()
        with pytest.raises(rt.TelegramRuntimeError,match='lease_lost'):await rt.probe(lease,runtime[2])
    async with rt.own_bot(pin):pass

async def test_lease_identity_frozen_and_forged_scope_has_no_server_lock(client,runtime):
    a,b=runtime[0];loader=AsyncMock()
    async with rt.own_bot(a) as lease:
        with pytest.raises(FrozenInstanceError):lease.pin=b
        forged=rt.BotLease(b,lease.connection,lease.backend_pid)
        with pytest.raises(rt.TelegramRuntimeError,match='lease_lost'):await rt.probe(forged,loader)
    loader.assert_not_awaited()

@pytest.mark.parametrize('during_load',[False,True])
async def test_manually_unlocked_pg_lease_denied_before_http(client,runtime,during_load):
    pin=runtime[0][0];seen=[]
    async def unlock(db):
        assert await db.scalar(text('SELECT pg_advisory_unlock(hashtextextended(:key,0))'),{'key':'pao-telegram-bot-v1:'+pin.bot_user_id})
    async def loader(db,pin):
        if during_load:await unlock(db)
        return runtime[1][0]
    async with rt.own_bot(pin) as lease:
        if not during_load:await unlock(lease.connection)
        with pytest.raises(rt.TelegramRuntimeError,match='lease_lost'):
            await rt.probe(lease,loader,transport=transport_for(pin,seen))
    assert not seen
    async with rt.own_bot(pin):pass

@pytest.mark.parametrize('change',['workspace','owner','version','bot','revoked','inactive','role','missing_member'])
async def test_fresh_scope_rejects_before_credential_loader_or_http(client,runtime,change):
    pin=runtime[0][0]
    if change=='workspace':pin=replace(pin,workspace_id=runtime[0][1].workspace_id)
    elif change=='owner':pin=replace(pin,owner_id=str(uuid4()))
    elif change=='version':pin=replace(pin,connection_version=2)
    elif change=='bot':pin=replace(pin,bot_user_id='999')
    else:
        async with Session.begin() as db:
            if change=='revoked':
                row=await db.get(TelegramConnection,pin.connection_id);row.status='revoked';row.version+=1
            elif change=='inactive':(await db.get(User,pin.owner_id)).active=False
            elif change=='role':(await db.get(Member,(pin.workspace_id,pin.owner_id))).role='operator'
            else:await db.delete(await db.get(Member,(pin.workspace_id,pin.owner_id)))
    loader=AsyncMock();seen=[]
    async with rt.own_bot(pin) as lease:
        with pytest.raises(rt.TelegramRuntimeError,match='scope_changed|owner_unavailable'):
            await rt.probe(lease,loader,transport=transport_for(pin,seen))
    loader.assert_not_awaited();assert not seen

async def test_gate_and_missing_store_never_use_host_token(client,runtime,monkeypatch):
    pin=runtime[0][0];seen=[]
    async with rt.own_bot(pin) as lease:
        monkeypatch.setattr(settings(),'telegram_scoped_runtime_enabled',False)
        with pytest.raises(rt.TelegramRuntimeError,match='runtime_disabled'):await rt.probe(lease,runtime[2])
        monkeypatch.setattr(settings(),'telegram_scoped_runtime_enabled',True);monkeypatch.setattr(settings(),'telegram_enabled',True)
        with pytest.raises(rt.TelegramRuntimeError,match='legacy_conflict'):await rt.probe(lease,runtime[2])
        monkeypatch.setattr(settings(),'telegram_enabled',False)
        with pytest.raises(rt.TelegramRuntimeError,match='store_pending'):await rt.probe(lease,transport=transport_for(pin,seen))
    assert not seen

@pytest.mark.parametrize('method',['getUpdates','sendMessage','answerCallbackQuery','setWebhook','deleteWebhook','getMe/../../sendMessage'])
async def test_read_metadata_does_not_grant_polling_or_delivery(client,runtime,method):
    loader=AsyncMock();pin=runtime[0][0]
    async with rt.own_bot(pin) as lease:
        with pytest.raises(rt.TelegramRuntimeError,match='method_denied'):await rt.probe(lease,loader,method=method)
    loader.assert_not_awaited()

@pytest.mark.parametrize('fault',['swapped','tampered','wrong_key','missing_key','missing_capsule'])
async def test_envelope_scope_version_and_key_bound_no_fallback(client,runtime,monkeypatch,fault):
    pin=runtime[0][0];capsule=runtime[1][0];seen=[]
    if fault=='swapped':capsule=runtime[1][1]
    elif fault=='tampered':capsule=rt.SealedCredential(SecretStr('gAAAA-invalid'))
    elif fault=='wrong_key':monkeypatch.setattr(settings(),'integration_encryption_key',Fernet.generate_key().decode())
    elif fault=='missing_key':monkeypatch.setattr(settings(),'integration_encryption_key','')
    else:capsule=None
    async def loader(db,pin):return capsule
    async with rt.own_bot(pin) as lease:
        with pytest.raises(rt.TelegramRuntimeError):await rt.probe(lease,loader,transport=transport_for(pin,seen))
    assert not seen and TOKENS[0] not in repr(runtime[1][0])

@pytest.mark.parametrize('fault',['timeout','redirect','rate_limit','non_json','too_large','wrong_bot','not_bot','reflected','bad_count'])
async def test_response_bound_identity_and_safe_error_without_retries(client,runtime,fault,caplog):
    pin=runtime[0][0];seen=[];caplog.set_level(logging.DEBUG)
    def handle(request):
        seen.append(True)
        # Simulate standard transport diagnostic logging in its protected context.
        logging.getLogger('httpcore.http11').debug('private request %s',request.url)
        if fault=='timeout':raise httpx.ReadTimeout('private '+str(request.url),request=request)
        if fault=='redirect':return httpx.Response(307,headers={'Location':'https://untrusted.invalid/'+TOKENS[0]})
        if fault=='rate_limit':return httpx.Response(429,json={'ok':False,'parameters':{'retry_after':1}})
        if fault=='non_json':return httpx.Response(200,text='private '+TOKENS[0])
        if fault=='too_large':return httpx.Response(200,headers={'content-type':'application/json'},content=b' '*70000)
        if fault=='wrong_bot':result={'id':222,'is_bot':True}
        elif fault=='not_bot':result={'id':111,'is_bot':False}
        elif fault=='reflected':result={'id':111,'is_bot':True,'discarded':{'echo':TOKENS[0]}}
        else:result={'url':'','pending_update_count':True}
        return httpx.Response(200,json={'ok':True,'result':result})
    async with rt.own_bot(pin) as lease:
        with pytest.raises(rt.TelegramRuntimeError) as error:
            await rt.probe(lease,runtime[2],method='getWebhookInfo' if fault=='bad_count' else 'getMe',transport=httpx.MockTransport(handle))
    assert len(seen)==1 and TOKENS[0] not in str(error.value) and TOKENS[0] not in caplog.text
    logging.getLogger('httpcore.http11').warning('outside-telegram-context')
    assert 'outside-telegram-context' in caplog.text

async def test_webhook_metadata_projection_no_raw_url_or_provider_error(client,runtime):
    pin=runtime[0][0]
    def handle(request):return httpx.Response(200,json={'ok':True,'result':{'url':'https://private.invalid/hook','pending_update_count':4,'last_error_message':'PRIVATE PROVIDER ERROR'}})
    async with rt.own_bot(pin) as lease:
        result=await rt.probe(lease,runtime[2],method='getWebhookInfo',transport=httpx.MockTransport(handle))
    assert result.webhook_present is True and result.pending_update_count==4
    assert 'private.invalid' not in repr(result) and 'PRIVATE' not in repr(result)

async def test_scope_rechecked_after_store_load(client,runtime):
    pin=runtime[0][0];seen=[]
    async def loader(db,pin):
        member=await db.get(Member,(pin.workspace_id,pin.owner_id));member.role='viewer';await db.flush()
        return runtime[1][0]
    async with rt.own_bot(pin) as lease:
        with pytest.raises(rt.TelegramRuntimeError,match='owner_unavailable'):
            await rt.probe(lease,loader,transport=transport_for(pin,seen))
    assert not seen

async def test_inflight_scope_lock_serializes_revoke_and_next_request_denied(client,runtime):
    pin=runtime[0][0];entered=asyncio.Event();release=asyncio.Event()
    async def handle(request):
        entered.set();await release.wait()
        return httpx.Response(200,json={'ok':True,'result':{'id':111,'is_bot':True}})
    async def revoke():
        async with Session.begin() as db:
            member=await db.get(Member,(pin.workspace_id,pin.owner_id),with_for_update=True)
            member.role='viewer'
    async with rt.own_bot(pin) as lease:
        pending=asyncio.create_task(rt.probe(lease,runtime[2],transport=httpx.MockTransport(handle)))
        changing=None
        try:
            await asyncio.wait_for(entered.wait(),5);changing=asyncio.create_task(revoke())
            await asyncio.sleep(.1);assert not changing.done()
            release.set();await pending;await changing
            loader=AsyncMock()
            with pytest.raises(rt.TelegramRuntimeError,match='owner_unavailable'):await rt.probe(lease,loader)
            loader.assert_not_awaited()
        finally:
            release.set()
            await asyncio.gather(pending,*([] if changing is None else [changing]),return_exceptions=True)

async def test_logging_suppression_does_not_hide_another_coroutine(client,runtime,caplog):
    pin=runtime[0][0];entered=asyncio.Event();release=asyncio.Event();caplog.set_level(logging.DEBUG)
    async def handle(request):
        logging.getLogger('httpcore.http11').warning('private %s',request.url)
        entered.set();await release.wait()
        return httpx.Response(200,json={'ok':True,'result':{'id':111,'is_bot':True}})
    async with rt.own_bot(pin) as lease:
        pending=asyncio.create_task(rt.probe(lease,runtime[2],transport=httpx.MockTransport(handle)))
        try:
            await asyncio.wait_for(entered.wait(),5)
            logging.getLogger('httpcore.http11').warning('other-coroutine-still-observed')
        finally:release.set();await pending
    assert 'other-coroutine-still-observed' in caplog.text and TOKENS[0] not in caplog.text

async def test_owner_lock_order_does_not_deadlock_existing_member_control(client,runtime):
    pin=runtime[0][0];seen=[];pending=None
    async with rt.own_bot(pin) as lease:
        try:
            async with Session.begin() as db:
                member=await db.get(Member,(pin.workspace_id,pin.owner_id),with_for_update=True)
                pending=asyncio.create_task(rt.probe(lease,runtime[2],transport=transport_for(pin,seen)))
                async with asyncio.timeout(5):
                    while True:
                        await db.execute(text('SELECT pg_stat_clear_snapshot()'))
                        if await db.scalar(text("SELECT wait_event_type='Lock' FROM pg_stat_activity WHERE pid=:pid"),{'pid':lease.backend_pid}):break
                        await asyncio.sleep(.02)
                # A blocked scope read must not already hold user SHARE while
                # owner control owns member UPDATE (the opposite lock order).
                assert await db.scalar(select(User).where(User.id==pin.owner_id).with_for_update(nowait=True))
                member.role='viewer'
            with pytest.raises(rt.TelegramRuntimeError,match='owner_unavailable'):await pending
        finally:
            if pending and not pending.done():pending.cancel()
            if pending:await asyncio.gather(pending,return_exceptions=True)
    assert not seen

@pytest.mark.parametrize('change',[{'workspace_id':'bad'},{'connection_id':None},{'connection_version':True},{'connection_version':0},{'bot_user_id':'../111'},{'bot_user_id':111}])
def test_closed_pin_input(change):
    base={'workspace_id':str(uuid4()),'connection_id':str(uuid4()),'owner_id':str(uuid4()),'connection_version':1,'bot_user_id':'111'}
    with pytest.raises(rt.TelegramRuntimeError,match='pin_invalid'):rt.RuntimePin(**{**base,**change})

@pytest.mark.parametrize('change',['purpose','version_bool','extra','token_bot'])
async def test_authenticated_but_malformed_envelope_denied(client,runtime,change):
    pin=runtime[0][0];seen=[];payload={'purpose':rt.PURPOSE,'pin':asdict(pin),'token':TOKENS[0]}
    if change=='purpose':payload['purpose']='some-other-feature'
    elif change=='version_bool':payload['pin']['connection_version']=True
    elif change=='extra':payload['private']='discarded unsafe field'
    else:payload['token']=TOKENS[1]
    sealed=rt.SealedCredential(SecretStr(Fernet(settings().integration_encryption_key.encode()).encrypt(json.dumps(payload).encode()).decode()))
    async def loader(db,pin):return sealed
    async with rt.own_bot(pin) as lease:
        with pytest.raises(rt.TelegramRuntimeError):await rt.probe(lease,loader,transport=transport_for(pin,seen))
    assert not seen

def test_fresh_import_opens_no_network_and_has_no_public_router():
    code="""
import socket,sys
def forbidden(*args,**kwargs):raise AssertionError('No import-time network')
socket.socket.connect=forbidden
socket.create_connection=forbidden
from pao.modules.channels import telegram_runtime as runtime
from pao.config import settings
assert settings().telegram_scoped_runtime_enabled is False
assert not hasattr(runtime,'router')
assert 'pao.telegram' not in sys.modules and 'pao.main' not in sys.modules
print('PASS isolated kernel import')
"""
    env={**os.environ,'TELEGRAM_SCOPED_RUNTIME_ENABLED':'false','PYTHONDONTWRITEBYTECODE':'1','PYTHONUTF8':'1'}
    result=subprocess.run([sys.executable,'-c',code],env=env,capture_output=True,text=True,timeout=20)
    assert result.returncode==0 and 'PASS isolated kernel import' in result.stdout
