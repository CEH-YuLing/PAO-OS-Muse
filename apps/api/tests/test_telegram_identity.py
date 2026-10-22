"""Verified native/legacy bot identity, real PG + bounded HTTP fixtures only."""
import asyncio,logging
from dataclasses import asdict,replace
from uuid import uuid4
from unittest.mock import AsyncMock
import httpx,pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import select,text,func
from sqlalchemy.exc import DBAPIError
from pao.config import settings
from pao.db import Session
from pao.models import (Workspace,User,Member,TelegramConnection,TelegramBotIdentity,
    TelegramRuntimeProfile,TelegramRuntimeAudit,TelegramPeer,TelegramUpdate,TelegramDelivery,
    TelegramLegacyMapping,TelegramLegacyPeerMap,ChannelBinding,ChannelOutbox)
from pao.modules.channels import telegram_runtime as rt,telegram_store as store,telegram_identity as identity_store
from pao.modules.channels.legacy_mapping import snapshot,apply
from pao.modules.channels.legacy_mapping_api import TelegramLegacyApply
from pao.auth import Principal

TOKEN=SecretStr('111:'+'SYNTHETIC_IDENTITY_A_'*3)


@pytest.fixture
async def identities(identity,monkeypatch):
    def forbidden(*a,**k):raise AssertionError('Unexpected live Telegram call')
    monkeypatch.setattr(httpx,'AsyncHTTPTransport',forbidden)
    monkeypatch.setattr(settings(),'telegram_scoped_runtime_enabled',True)
    monkeypatch.setattr(settings(),'telegram_enabled',False)
    monkeypatch.setattr(settings(),'integration_encryption_key',Fernet.generate_key().decode())
    async with Session.begin() as db:
        other=Workspace(name='Identity SME B');db.add(other);await db.flush()
        db.add(Member(workspace_id=other.id,user_id=identity['user_id'],role='owner'))
        native=TelegramConnection(workspace_id=other.id,owner_id=identity['user_id'],bot_user_id='222')
        # Start with real legacy data. apply() creates disabled mapped peers only;
        # verification later must not repin these or import their history.
        peer=TelegramPeer(workspace_id=identity['workspace'],user_id=identity['user_id'],telegram_user_id='777',chat_id='777')
        db.add_all([native,peer]);await db.flush()
        binding=ChannelBinding(workspace_id=identity['workspace'],actor_id=identity['user_id'],channel='telegram',
            identity_hash='a'*64,peer_id=peer.id,kind='personal',mode='auto',outbound_confirmed=True)
        db.add(binding);await db.flush()
        db.add(TelegramUpdate(peer_id=peer.id,update_id=7))
        db.add(TelegramDelivery(peer_id=peer.id,dedup_key='legacy-unknown',payload={'text':'PRIVATE OLD'},status='unknown'))
        db.add(ChannelOutbox(workspace_id=identity['workspace'],binding_id=binding.id,request_key='legacy-unknown',
            content_hash='b'*64,body='PRIVATE OLD',kind='auto',status='unknown'))
    async with Session() as db:
        who=Principal(identity['user_id'],0)
        preview,_,_,_=await snapshot(db,identity['workspace'],who)
        assert preview['eligible']
        mapped=await apply(db,identity['workspace'],who,TelegramLegacyApply(request_key=uuid4(),expected_version=0,
            preview_hash=preview['preview_hash'],data_only_ack=True,no_history_replay_ack=True))
    legacy_pin=rt.RuntimePin(identity['workspace'],mapped['connection_id'],identity['user_id'],1,'111')
    native_pin=rt.RuntimePin(native.workspace_id,native.id,native.owner_id,1,'222')
    return legacy_pin,native_pin


def fixture_http(pin,seen,result=None):
    def handler(request):
        seen.append(request.url.path)
        assert request.url.host=='api.telegram.org' and request.method=='POST'
        assert request.url.path.endswith('/getMe') and request.content==b'{}'
        return httpx.Response(200,json={'ok':True,'result':result if result is not None else
            {'id':int(pin.bot_user_id),'is_bot':True,'username':'fixture_bot'}})
    return httpx.MockTransport(handler)


async def verify(pin,token=TOKEN,key=None,seen=None,transport=None,consent=True):
    seen=[] if seen is None else seen
    async with rt.own_bot(pin) as lease:
        return await identity_store.verify_identity(lease,token,request_key=key or str(uuid4()),consent=consent,
            transport=transport or fixture_http(pin,seen))


async def test_verified_native_and_legacy_share_registry_no_history_repin_or_activation(client,identities):
    for pin,token in ((identities[0],TOKEN),(identities[1],SecretStr('222:'+'SYNTHETIC_IDENTITY_B_'*3))):
        seen=[];result=await verify(pin,token,seen=seen)
        assert asdict(result)=={'workspace_id':pin.workspace_id,'connection_id':pin.connection_id,
            'bot_user_id':pin.bot_user_id,'connection_version':1}
        assert seen==['/bot'+token.get_secret_value()+'/getMe'] and token.get_secret_value() not in repr(result)
        async with Session.begin() as db:assert await identity_store.resolve_identity(db,pin)==result
    async with Session() as db:
        legacy=await db.get(TelegramConnection,identities[0].connection_id)
        assert legacy.bot_user_id is None and legacy.status=='staged' and legacy.version==1
        link=await db.scalar(select(TelegramLegacyPeerMap))
        mapped_peer=await db.get(TelegramPeer,link.peer_id);mapped_binding=await db.get(ChannelBinding,link.binding_id)
        assert not mapped_peer.enabled and mapped_peer.session_id is None
        assert not mapped_binding.enabled and not mapped_binding.outbound_confirmed and mapped_binding.session_id is None
        assert await db.scalar(select(func.count()).select_from(TelegramRuntimeProfile))==0
        assert await db.scalar(select(func.count()).select_from(TelegramBotIdentity))==2
        assert (await db.scalar(select(TelegramDelivery))).status=='unknown'
        assert (await db.scalar(select(ChannelOutbox))).body=='PRIVATE OLD'
        assert (await db.scalar(select(TelegramUpdate))).connection_id is None


async def test_verified_legacy_can_store_disabled_scoped_token_and_probe_not_send(client,identities):
    pin=identities[0];await verify(pin)
    async with rt.own_bot(pin) as lease:
        result=await store.save_profile(lease,TOKEN,expected_generation=0,request_key=str(uuid4()),consent=True)
    assert result.status=='disabled' and result.generation==1
    seen=[]
    async with rt.own_bot(pin) as lease:
        assert (await rt.probe(lease,store.credential_loader(1),transport=fixture_http(pin,seen))).bot_user_id=='111'
    for method in ('sendMessage','getUpdates'):
        async with rt.own_bot(pin) as lease:
            with pytest.raises(rt.TelegramRuntimeError,match='method_denied'):
                await rt.probe(lease,store.credential_loader(1),method=method,transport=fixture_http(pin,seen))
    assert len(seen)==1


async def test_unverified_native_resolver_and_legacy_metadata_fail_closed(client,identities):
    async with Session.begin() as db:
        with pytest.raises(rt.TelegramRuntimeError,match='unverified'):await identity_store.resolve_identity(db,identities[1])
    loader=AsyncMock()
    async with rt.own_bot(identities[0]) as lease:
        with pytest.raises(rt.TelegramRuntimeError,match='scope_changed'):await rt.probe(lease,loader)
    loader.assert_not_awaited()


async def test_consent_and_exact_request_retry_without_provider_replay(client,identities):
    pin=identities[0];seen=[];key=str(uuid4())
    with pytest.raises(rt.TelegramRuntimeError,match='consent_required'):await verify(pin,consent=False,seen=seen)
    first=await verify(pin,key=key,seen=seen)
    assert await verify(pin,key=key,seen=seen)==first and len(seen)==1
    with pytest.raises(rt.TelegramRuntimeError,match='request_conflict'):
        await verify(pin,SecretStr('111:'+'SYNTHETIC_OTHER_TOKEN_'*3),key,seen)
    with pytest.raises(rt.TelegramRuntimeError,match='already_bound'):await verify(pin,seen=seen)
    assert len(seen)==1


@pytest.mark.parametrize('result',[
    {'id':999,'is_bot':True}, {'id':111,'is_bot':False}, {'id':True,'is_bot':True},
    {'id':111,'is_bot':True,'username':'invalid/user'}, {'id':111,'is_bot':True,'private':TOKEN.get_secret_value()},
])
async def test_provider_identity_or_credential_echo_invalid_no_journal(client,identities,result):
    pin=identities[0];seen=[]
    with pytest.raises(rt.TelegramRuntimeError):await verify(pin,transport=fixture_http(pin,seen,result))
    assert len(seen)==1
    async with Session() as db:assert await db.scalar(select(func.count()).select_from(TelegramBotIdentity))==0


@pytest.mark.parametrize('fault',['timeout','429','redirect','malformed','too_large','cancel'])
async def test_failed_or_uncertain_metadata_never_commits_or_retries(client,identities,fault):
    pin=identities[0];seen=[]
    async def handler(request):
        seen.append(True)
        if fault=='timeout':raise httpx.ReadTimeout('PRIVATE TRANSPORT URL',request=request)
        if fault=='cancel':raise asyncio.CancelledError()
        if fault=='429':return httpx.Response(429,json={'retry_after':1})
        if fault=='redirect':return httpx.Response(302,headers={'location':'https://example.invalid/PRIVATE'})
        if fault=='too_large':return httpx.Response(200,content=b'x'*65537,headers={'content-type':'application/json'})
        return httpx.Response(200,json={'ok':True,'result':None})
    with pytest.raises(asyncio.CancelledError if fault=='cancel' else rt.TelegramRuntimeError):
        await verify(pin,transport=httpx.MockTransport(handler))
    assert len(seen)==1
    async with Session() as db:assert await db.scalar(select(func.count()).select_from(TelegramBotIdentity))==0


@pytest.mark.parametrize('change',['viewer','operator','inactive','membership','connection','version','workspace','bot'])
async def test_fresh_owner_scope_denied_before_http(client,identities,change):
    pin=identities[0];seen=[]
    if change in ('version','workspace','bot'):
        pin=replace(pin,**{'version':{'connection_version':2},'workspace':{'workspace_id':identities[1].workspace_id},
            'bot':{'bot_user_id':'222'}}[change])
    else:
        async with Session.begin() as db:
            if change in ('viewer','operator'):(await db.get(Member,(pin.workspace_id,pin.owner_id))).role=change
            elif change=='inactive':(await db.get(User,pin.owner_id)).active=False
            elif change=='membership':await db.delete(await db.get(Member,(pin.workspace_id,pin.owner_id)))
            else:
                row=await db.get(TelegramConnection,pin.connection_id);row.status='revoked';row.version+=1
    token=SecretStr(pin.bot_user_id+':'+'SYNTHETIC_FOR_SCOPE_'*3)
    with pytest.raises(rt.TelegramRuntimeError):await verify(pin,token,seen=seen)
    assert not seen


async def test_verified_legacy_bot_blocks_future_native_claim_and_identity_rewrites(client,identities):
    pin=identities[0];await verify(pin)
    with pytest.raises(DBAPIError,match='telegram_bot_identity_claimed'):
        async with Session.begin() as db:
            db.add(TelegramConnection(workspace_id=identities[1].workspace_id,owner_id=pin.owner_id,bot_user_id='111'))
    for sql in ('UPDATE telegram_bot_identities SET bot_user_id=bot_user_id','DELETE FROM telegram_bot_identities'):
        with pytest.raises(DBAPIError,match='identity_immutable'):
            async with Session.begin() as db:await db.execute(text(sql))
    # Same bot remains reserved after profile revoke; this is not a release/reset.
    async with rt.own_bot(pin) as lease:
        await store.save_profile(lease,TOKEN,expected_generation=0,request_key=str(uuid4()),consent=True)
        await store.revoke_profile(lease,expected_generation=1,request_key=str(uuid4()),consent=True)
    with pytest.raises(DBAPIError):
        async with Session.begin() as db:
            db.add(TelegramConnection(workspace_id=identities[1].workspace_id,owner_id=pin.owner_id,bot_user_id='111'))


async def test_existing_native_reservation_prevents_legacy_identity_claim_no_network(client,identities):
    pin=replace(identities[0],bot_user_id='222');seen=[]
    with pytest.raises(rt.TelegramRuntimeError,match='claimed'):
        await verify(pin,SecretStr('222:'+'SYNTHETIC_COLLISION_'*3),seen=seen)
    assert not seen


async def test_legacy_mapping_required_not_just_kind_or_prefix(client,identity,monkeypatch):
    monkeypatch.setattr(settings(),'telegram_enabled',False)
    monkeypatch.setattr(settings(),'telegram_scoped_runtime_enabled',True)
    monkeypatch.setattr(settings(),'integration_encryption_key',Fernet.generate_key().decode())
    async with Session.begin() as db:
        row=TelegramConnection(workspace_id=identity['workspace'],owner_id=identity['user_id'],kind='legacy',bot_user_id=None)
        db.add(row);await db.flush();pin=rt.RuntimePin(row.workspace_id,row.id,row.owner_id,1,'111')
    seen=[]
    with pytest.raises(rt.TelegramRuntimeError,match='mapping_required'):await verify(pin,seen=seen)
    assert not seen


async def test_logs_and_response_contain_no_token_or_raw_provider_fields(client,identities,caplog):
    pin=identities[0];caplog.set_level(logging.DEBUG)
    result=await verify(pin)
    assert TOKEN.get_secret_value() not in caplog.text+repr(result)
    assert 'api.telegram.org/bot111:' not in caplog.text
    async with Session() as db:
        row=await db.scalar(select(TelegramBotIdentity))
        assert len(row.content_hash)==64 and TOKEN.get_secret_value() not in row.content_hash


@pytest.mark.parametrize('change',['workspace','owner','version','bot','connection'])
async def test_database_identity_scope_guard_rejects_forged_references(client,identities,change):
    pin=identities[1]
    fields={'workspace_id':pin.workspace_id,'connection_id':pin.connection_id,'owner_id':pin.owner_id,
        'connection_version':1,'bot_user_id':'222','request_key':str(uuid4()),'content_hash':'a'*64}
    async with Session() as db:outside=await db.scalar(select(User.id).where(User.email=='outside@example.test'))
    fields.update({'workspace':{'workspace_id':identities[0].workspace_id},'owner':{'owner_id':outside},
        'version':{'connection_version':2},'bot':{'bot_user_id':'333'},'connection':{'connection_id':identities[0].connection_id}}[change])
    with pytest.raises(DBAPIError):
        async with Session.begin() as db:db.add(TelegramBotIdentity(**fields))
    async with Session() as db:assert await db.scalar(select(func.count()).select_from(TelegramBotIdentity))==0


@pytest.mark.parametrize('change',['viewer','inactive','revoked'])
async def test_verified_identity_does_not_survive_authority_revocation_as_a_grant(client,identities,change):
    pin=identities[0];key=str(uuid4());await verify(pin,key=key)
    async with Session.begin() as db:
        if change=='viewer':(await db.get(Member,(pin.workspace_id,pin.owner_id))).role='viewer'
        elif change=='inactive':(await db.get(User,pin.owner_id)).active=False
        else:
            row=await db.get(TelegramConnection,pin.connection_id);row.status='revoked';row.version+=1
    async with Session.begin() as db:
        with pytest.raises(rt.TelegramRuntimeError):await identity_store.resolve_identity(db,pin)
    seen=[]
    with pytest.raises(rt.TelegramRuntimeError):await verify(pin,key=key,seen=seen)
    assert not seen
    async with Session() as db:assert await db.scalar(select(func.count()).select_from(TelegramBotIdentity))==1


@pytest.mark.parametrize('change',['disabled','host_conflict'])
async def test_identity_enrollment_respects_transport_gates(client,identities,monkeypatch,change):
    if change=='disabled':monkeypatch.setattr(settings(),'telegram_scoped_runtime_enabled',False)
    else:monkeypatch.setattr(settings(),'telegram_enabled',True)
    seen=[]
    with pytest.raises(rt.TelegramRuntimeError):await verify(identities[0],seen=seen)
    assert not seen


async def test_identity_enrollment_requires_actual_pg_bot_lock(client,identities):
    pin=identities[0];seen=[]
    async with rt.own_bot(pin) as lease:
        assert await lease.connection.scalar(text('SELECT pg_advisory_unlock(hashtextextended(:key,0))'),
            {'key':'pao-telegram-bot-v1:'+pin.bot_user_id})
        await lease.connection.commit()
        with pytest.raises(rt.TelegramRuntimeError,match='lease_lost'):
            await identity_store.verify_identity(lease,TOKEN,request_key=str(uuid4()),consent=True,transport=fixture_http(pin,seen))
    assert not seen


async def test_same_bot_cannot_be_registered_or_created_while_verification_holds_lease(client,identities):
    pin=identities[0];entered=asyncio.Event();release=asyncio.Event();pending=None
    async def handler(request):
        entered.set();await release.wait()
        return httpx.Response(200,json={'ok':True,'result':{'id':111,'is_bot':True}})
    try:
        pending=asyncio.create_task(verify(pin,transport=httpx.MockTransport(handler)))
        await asyncio.wait_for(entered.wait(),5)
        with pytest.raises(rt.TelegramRuntimeError,match='bot_busy'):
            async with rt.own_bot(replace(identities[1],bot_user_id='111')):pytest.fail('Same actual bot must be exclusive')
        release.set();assert (await asyncio.wait_for(pending,5)).bot_user_id=='111'
        with pytest.raises(DBAPIError,match='identity_claimed'):
            async with Session.begin() as db:
                db.add(TelegramConnection(workspace_id=identities[1].workspace_id,owner_id=pin.owner_id,bot_user_id='111'))
    finally:
        release.set()
        if pending and not pending.done():pending.cancel()
        if pending:await asyncio.gather(pending,return_exceptions=True)
