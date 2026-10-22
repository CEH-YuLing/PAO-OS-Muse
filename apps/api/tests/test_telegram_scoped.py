"""Real scoped admission/Run/accounting/outbox; never live Telegram or LLM."""
from dataclasses import replace
from datetime import timedelta
from uuid import uuid4
import asyncio,json
from unittest.mock import AsyncMock
import httpx,pytest
from cryptography.fernet import Fernet
from sqlalchemy import select,text,func
from sqlalchemy.exc import DBAPIError
from pydantic import SecretStr
from pao.config import settings
from pao.db import Session
from pao.models import (Workspace,Member,User,Brain,BrainMember,ChatSession,Run,Message,ChannelBinding,ChannelInbound,
    ChannelOutbox,TelegramConnection,TelegramPeer,TelegramRuntimeProfile,TelegramRuntimeReceipt,TelegramRuntimeAudit,LlmAttempt,TenantModelLease,now)
from pao.modules.channels import telegram_runtime as rt,telegram_store as store,telegram_identity as identities,telegram_scoped as scoped,service
from pao.runtime import execute_run
from pao.main import app
from test_memory import Gateway


def token(pin):return SecretStr(pin.bot_user_id+':'+'SYNTHETIC_EXECUTION_'*3)


def http(pin,seen=None):
    def handler(request):
        assert request.url.path.endswith('/getMe')
        if seen is not None:seen.append(request.url.path)
        return httpx.Response(200,json={'ok':True,'result':{'id':int(pin.bot_user_id),'is_bot':True}})
    return httpx.MockTransport(handler)


@pytest.fixture
async def enabled_bots(identity,monkeypatch,client):
    def no_network(*a,**k):raise AssertionError('No live Telegram/LLM in scoped tests')
    monkeypatch.setattr(httpx,'AsyncHTTPTransport',no_network)
    for name in ('telegram_scoped_runtime_enabled','channels_enabled','engine_contract_enabled','chat_features_enabled','brain_manager_enabled'):
        monkeypatch.setattr(settings(),name,True)
    monkeypatch.setattr(settings(),'telegram_enabled',False)
    monkeypatch.setattr(settings(),'integration_encryption_key',Fernet.generate_key().decode())
    async with Session.begin() as db:
        actor=await db.scalar(select(User).where(User.email=='other@example.test'))
        other=Workspace(name='Scoped SME B');db.add(other);await db.flush()
        db.add_all([Member(workspace_id=other.id,user_id=identity['user_id'],role='owner'),Member(workspace_id=other.id,user_id=actor.id,role='operator')])
        connections=[TelegramConnection(workspace_id=wid,owner_id=identity['user_id'],bot_user_id=bot)
            for wid,bot in ((identity['workspace'],'111'),(other.id,'222'))]
        db.add_all(connections);await db.flush()
        pins=[rt.RuntimePin(c.workspace_id,c.id,c.owner_id,c.version,c.bot_user_id) for c in connections]
    bindings=[]
    for pin in pins:
        async with rt.own_bot(pin) as lease:
            await identities.verify_identity(lease,token(pin),request_key=str(uuid4()),consent=True,transport=http(pin))
            await store.save_profile(lease,token(pin),expected_generation=0,request_key=str(uuid4()),consent=True)
            assert (await scoped.control_profile(lease,generation=1,request_key=str(uuid4()),action='enable',consent=True,transport=http(pin))).generation==2
        async with Session.begin() as db:
            brain=Brain(workspace_id=pin.workspace_id,owner_id=actor.id,name='Actor private');db.add(brain)
            peer=TelegramPeer(workspace_id=pin.workspace_id,user_id=actor.id,connection_id=pin.connection_id,
                telegram_user_id='777',chat_id='777',enabled=True)
            db.add(peer);await db.flush()
            binding=ChannelBinding(workspace_id=pin.workspace_id,connection_id=pin.connection_id,actor_id=actor.id,
                channel='telegram',identity_hash=service.identity('telegram','777:777',pin.connection_id),peer_id=peer.id,
                brain_id=brain.id,kind='personal',mode='auto',enabled=True,outbound_confirmed=True)
            db.add(binding);await db.flush();bindings.append(binding.id)
    return {'pins':pins,'bindings':bindings,'actor':actor.id,'owner':identity['user_id'],'redis':app.state.redis}


def update(ident=7,body='Xin chào'):
    return {'update_id':ident,'message':{'from':{'id':777,'is_bot':False},'chat':{'id':777,'type':'private'},'text':body}}


async def receive(f,index=0,value=None,generation=2,offset=0):
    async with rt.own_bot(f['pins'][index]) as lease:
        return await scoped.ingest_update(lease,generation=generation,expected_offset=offset,
            update=update() if value is None else value,redis=f['redis'])


async def completed(f,index=0):
    result=await receive(f,index)
    assert result.disposition=='accepted',result
    await execute_run({'gateway':Gateway()},result.run_id)
    async with Session() as db:assert (await db.get(Run,result.run_id)).status=='completed'
    async with rt.own_bot(f['pins'][index]) as lease:
        assert await scoped.collect_results(lease,generation=2)==1
        assert await scoped.collect_results(lease,generation=2)==0
    async with Session() as db:
        return await db.scalar(select(ChannelOutbox.id).where(ChannelOutbox.connection_id==f['pins'][index].connection_id))


async def test_two_bots_same_sender_update_ids_use_native_run_and_accounting(client,enabled_bots):
    f=enabled_bots
    first=await receive(f);second=await receive(f,1)
    assert first.disposition==second.disposition=='accepted' and first.run_id!=second.run_id
    assert (await receive(f,offset=8)).disposition=='duplicate'
    with pytest.raises(rt.TelegramRuntimeError,match='update_conflict'):await receive(f,value=update(body='Khác'),offset=8)
    async with Session() as db:
        runs=list(await db.scalars(select(Run)));assert len(runs)==2
        assert {r.workspace_id for r in runs}=={p.workspace_id for p in f['pins']}
        for run in runs:
            assert run.engine_snapshot and run.channel_context['telegram']['actor_id']==f['actor']
            assert run.channel_context['telegram']['generation']==2
        assert await db.scalar(select(func.count()).select_from(Message))==2
        assert all(r.reason=='inbound' and r.inbound_id for r in await db.scalars(select(TelegramRuntimeReceipt)))
        assert f['redis']


async def test_end_to_end_fixture_run_collect_claim_preflight_and_confirmed_receipt(client,enabled_bots):
    f=enabled_bots;outbox=await completed(f)
    async with rt.own_bot(f['pins'][0]) as lease:
        claim=await scoped.claim_delivery(lease,generation=2,outbox_id=outbox)
        payload=await scoped.preflight_delivery(lease,generation=2,claim=claim)
        assert payload['chat_id']=='777' and payload['text'] and payload['link_preview_options']['is_disabled']
        await scoped.finish_delivery(lease,claim=claim,outcome='sent',remote_id='123')
        assert await scoped.claim_delivery(lease,generation=2,outbox_id=outbox) is None
    async with Session() as db:
        row=await db.get(ChannelOutbox,outbox)
        assert row.status=='sent' and row.attempts==1 and row.remote_id=='123'
        attempt=await db.scalar(select(LlmAttempt))
        assert attempt.workspace_id==f['pins'][0].workspace_id and attempt.user_id==f['actor']
        assert await db.scalar(select(func.count()).select_from(TenantModelLease).where(TenantModelLease.status=='active'))==0


@pytest.mark.parametrize('change',['viewer','membership','inactive','peer','binding','destination','brain','session','version','generation'])
async def test_queued_output_rechecks_fresh_authority_and_cancels(client,enabled_bots,change):
    f=enabled_bots;outbox=await completed(f);pin=f['pins'][0]
    if change=='generation':
        async with rt.own_bot(pin) as lease:
            await store.save_profile(lease,token(pin),expected_generation=2,request_key=str(uuid4()),consent=True)
    else:
        async with Session.begin() as db:
            binding=await db.get(ChannelBinding,f['bindings'][0])
            if change=='viewer':(await db.get(Member,(pin.workspace_id,f['actor']))).role='viewer'
            elif change=='membership':await db.delete(await db.get(Member,(pin.workspace_id,f['actor'])))
            elif change=='inactive':(await db.get(User,f['actor'])).active=False
            elif change=='peer':(await db.get(TelegramPeer,binding.peer_id)).enabled=False
            elif change=='binding':binding.enabled=False
            elif change=='destination':binding.outbound_confirmed=False
            elif change=='brain':(await db.get(Brain,binding.brain_id)).owner_id=f['owner']
            elif change=='session':(await db.get(ChatSession,binding.session_id)).memory_enabled=True
            else:binding.version+=1
    async with rt.own_bot(pin) as lease:assert await scoped.claim_delivery(lease,generation=2,outbox_id=outbox) is None
    async with Session() as db:assert (await db.get(ChannelOutbox,outbox)).status=='cancelled'


async def test_queued_run_revoked_generation_never_calls_llm(client,enabled_bots):
    f=enabled_bots;result=await receive(f);pin=f['pins'][0]
    async with rt.own_bot(pin) as lease:
        await scoped.control_profile(lease,generation=2,request_key=str(uuid4()),action='disable',consent=True)
    gateway=Gateway();gateway.stream=AsyncMock(side_effect=AssertionError('No revoked inference'))
    await execute_run({'gateway':gateway},result.run_id)
    async with Session() as db:
        run=await db.get(Run,result.run_id);assert run.status=='failed' and run.error_code=='channel_scope_revoked'
    gateway.stream.assert_not_called()


@pytest.mark.parametrize('value,reason',[
    ({'update_id':7,'callback_query':{'data':'approve'}},'unsupported'),
    ({'update_id':7,'message':{'chat':{'type':'group','id':777},'from':{'id':777,'is_bot':False},'text':'Approve'}},'unsupported'),
    ({'update_id':7,'message':{'chat':{'type':'private','id':888},'from':{'id':888,'is_bot':False},'text':'Xin chào'}},'unlinked'),
    (update(body=''),'malformed'),(update(body='x'*2001),'malformed'),
])
async def test_unknown_unlinked_nonmessage_quarantined_no_user_or_task_created(client,enabled_bots,value,reason):
    result=await receive(enabled_bots,value=value)
    assert result.disposition==reason and result.next_offset==8 and result.run_id is None
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(Run))==0
        assert await db.scalar(select(func.count()).select_from(ChannelInbound))==0


async def test_inbound_denial_rolls_back_partial_admission_but_receipt_and_cursor_commit(client,enabled_bots,monkeypatch):
    f=enabled_bots
    async with Session.begin() as db:
        brain=await db.get(Brain,(await db.get(ChannelBinding,f['bindings'][0])).brain_id);brain.owner_id=f['owner']
    result=await receive(f)
    assert result.disposition=='blocked' and result.next_offset==8
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(Run))==0
        assert await db.scalar(select(func.count()).select_from(ChannelInbound))==0


async def test_unknown_delivery_never_retried_and_stale_claim_not_accepted(client,enabled_bots):
    f=enabled_bots;outbox=await completed(f)
    async with rt.own_bot(f['pins'][0]) as lease:
        claim=await scoped.claim_delivery(lease,generation=2,outbox_id=outbox)
        await scoped.finish_delivery(lease,claim=claim,outcome='unknown')
        assert await scoped.claim_delivery(lease,generation=2,outbox_id=outbox) is None
        with pytest.raises(rt.TelegramRuntimeError,match='claim_stale'):
            await scoped.finish_delivery(lease,claim=claim,outcome='sent',remote_id='123')


async def test_crash_after_claim_reconciles_unknown_not_resend(client,enabled_bots):
    f=enabled_bots;outbox=await completed(f)
    async with rt.own_bot(f['pins'][0]) as lease:assert await scoped.claim_delivery(lease,generation=2,outbox_id=outbox)
    async with Session.begin() as db:(await db.get(ChannelOutbox,outbox)).updated_at=now()-timedelta(minutes=3)
    await service.reconcile_stale()
    async with rt.own_bot(f['pins'][0]) as lease:assert await scoped.claim_delivery(lease,generation=2,outbox_id=outbox) is None
    async with Session() as db:assert (await db.get(ChannelOutbox,outbox)).status=='unknown'


async def test_retryable_cooldown_is_bot_scoped_and_attempt_is_pinned(client,enabled_bots):
    f=enabled_bots;a=await completed(f);b=await completed(f,1)
    async with rt.own_bot(f['pins'][0]) as lease:
        claim=await scoped.claim_delivery(lease,generation=2,outbox_id=a)
        await scoped.finish_delivery(lease,claim=claim,outcome='retryable',retry_after=30)
        assert await scoped.claim_delivery(lease,generation=2,outbox_id=a) is None
    async with rt.own_bot(f['pins'][1]) as lease:assert await scoped.claim_delivery(lease,generation=2,outbox_id=b)
    async with Session.begin() as db:
        (await db.get(ChannelOutbox,a)).available_at=now()-timedelta(seconds=1)
        (await db.scalar(select(TelegramRuntimeProfile).where(TelegramRuntimeProfile.connection_id==f['pins'][0].connection_id))).cooldown_until=now()-timedelta(seconds=1)
    async with rt.own_bot(f['pins'][0]) as lease:
        newer=await scoped.claim_delivery(lease,generation=2,outbox_id=a);assert newer.attempt==2
        with pytest.raises(rt.TelegramRuntimeError,match='claim_stale'):await scoped.preflight_delivery(lease,generation=2,claim=claim)


async def test_cross_bot_claim_and_pin_rewrite_denied(client,enabled_bots):
    f=enabled_bots;outbox=await completed(f)
    async with rt.own_bot(f['pins'][1]) as lease:
        with pytest.raises(rt.TelegramRuntimeError,match='not_found'):await scoped.claim_delivery(lease,generation=2,outbox_id=outbox)
    for table in ('channel_inbounds','channel_outbox'):
        with pytest.raises(DBAPIError,match='pin_immutable'):
            async with Session.begin() as db:
                await db.execute(text("UPDATE "+table+" SET telegram_context=jsonb_set(telegram_context,'{generation}','999') WHERE telegram_context IS NOT NULL"))


async def test_native_management_and_public_fake_sender_still_denied(client,identity,enabled_bots):
    f=enabled_bots;bid=f['bindings'][0]
    response=await client.post('/v1/channels/bindings/'+bid+'/inbound',headers=identity['owner'],json={'message_key':'fake','text':'fake'})
    assert response.status_code==503
    assert (await client.post('/v1/channels/bindings/'+bid+'/control',headers=identity['owner'],json={
        'request_key':str(uuid4()),'version':1,'action':'auto'})).status_code==503


async def test_activation_consent_and_cas_and_key_rotation_disable_again(client,enabled_bots):
    f=enabled_bots;pin=f['pins'][0];key=str(uuid4())
    async with rt.own_bot(pin) as lease:
        with pytest.raises(rt.TelegramRuntimeError,match='consent_required'):
            await scoped.control_profile(lease,generation=2,request_key=key,action='disable')
        disabled=await scoped.control_profile(lease,generation=2,request_key=key,action='disable',consent=True)
        assert disabled.generation==3 and disabled.status=='disabled'
        assert await scoped.control_profile(lease,generation=2,request_key=key,action='disable',consent=True)==disabled
        seen=[]
        enabled=await scoped.control_profile(lease,generation=3,request_key=str(uuid4()),action='enable',consent=True,transport=http(pin,seen))
        assert enabled.generation==4 and len(seen)==1
        rotated=await store.save_profile(lease,token(pin),expected_generation=4,request_key=str(uuid4()),consent=True)
        assert rotated.generation==5 and rotated.status=='disabled'


@pytest.mark.parametrize('fault',['denied','unexpected'])
async def test_partial_native_run_and_session_rollback_before_receipt(client,enabled_bots,monkeypatch,fault):
    from fastapi import HTTPException
    original=service.admit_run
    async def fail_after_admission(*args,**kwargs):
        await original(*args,**kwargs)
        if fault=='denied':raise HTTPException(503,'synthetic admission denial')
        raise RuntimeError('synthetic infrastructure failure')
    monkeypatch.setattr(service,'admit_run',fail_after_admission)
    if fault=='denied':assert (await receive(enabled_bots)).disposition=='blocked'
    else:
        with pytest.raises(rt.TelegramRuntimeError):await receive(enabled_bots)
    async with Session() as db:
        for model in (Run,Message,ChatSession,ChannelInbound):assert await db.scalar(select(func.count()).select_from(model))==0
        assert await db.scalar(select(func.count()).select_from(TelegramRuntimeReceipt))==(1 if fault=='denied' else 0)
        profile=await db.scalar(select(TelegramRuntimeProfile).where(TelegramRuntimeProfile.connection_id==enabled_bots['pins'][0].connection_id))
        assert profile.next_offset==(8 if fault=='denied' else 0)


@pytest.mark.parametrize('change',['role','membership','active','peer'])
async def test_revoked_then_restored_authority_never_resurrects_old_delivery(client,enabled_bots,change):
    f=enabled_bots;outbox=await completed(f);pin=f['pins'][0]
    async with Session.begin() as db:
        binding=await db.get(ChannelBinding,f['bindings'][0]);old_version=binding.version
        if change=='role':
            member=await db.get(Member,(pin.workspace_id,f['actor']));member.role='viewer';await db.flush();member.role='operator'
        elif change=='membership':
            await db.delete(await db.get(Member,(pin.workspace_id,f['actor'])));await db.flush()
            db.add(Member(workspace_id=pin.workspace_id,user_id=f['actor'],role='operator'))
        elif change=='active':
            user=await db.get(User,f['actor']);user.active=False;await db.flush();user.active=True
        else:
            peer=await db.get(TelegramPeer,binding.peer_id);peer.enabled=False;await db.flush();peer.enabled=True
    async with Session.begin() as db:
        binding=await db.get(ChannelBinding,f['bindings'][0])
        assert not binding.enabled and not binding.outbound_confirmed and binding.version>old_version
        # Even a later explicit re-enable cannot repin an old queued body.
        binding.enabled=True;binding.outbound_confirmed=True
    async with rt.own_bot(pin) as lease:assert await scoped.claim_delivery(lease,generation=2,outbox_id=outbox) is None


async def test_mutated_run_context_cannot_repin_immutable_inbound(client,enabled_bots):
    f=enabled_bots;result=await receive(f);pin=f['pins'][0]
    async with rt.own_bot(pin) as lease:
        await scoped.control_profile(lease,generation=2,request_key=str(uuid4()),action='disable',consent=True)
        await scoped.control_profile(lease,generation=3,request_key=str(uuid4()),action='enable',consent=True,transport=http(pin))
    async with Session.begin() as db:
        run=await db.get(Run,result.run_id);binding=await db.get(ChannelBinding,f['bindings'][0])
        # 0064 revokes grants on generation changes. Simulate a later explicit
        # regrant, then forge *both* mutable Run pins; immutable ingress must
        # still prevent repinning the historical message to current authority.
        binding.enabled=True;binding.outbound_confirmed=True;await db.flush();await db.refresh(binding)
        run.channel_context={**run.channel_context,'version':binding.version,'telegram':await scoped.context(db,binding)}
    await execute_run({'gateway':Gateway()},result.run_id)
    async with Session() as db:assert (await db.get(Run,result.run_id)).error_code=='channel_scope_revoked'


async def test_after_claim_revocation_preflight_returns_no_payload(client,enabled_bots):
    f=enabled_bots;outbox=await completed(f);pin=f['pins'][0]
    async with rt.own_bot(pin) as lease:claim=await scoped.claim_delivery(lease,generation=2,outbox_id=outbox)
    async with Session.begin() as db:(await db.get(Member,(pin.workspace_id,f['actor']))).role='viewer'
    async with rt.own_bot(pin) as lease:assert await scoped.preflight_delivery(lease,generation=2,claim=claim) is None
    async with Session() as db:assert (await db.get(ChannelOutbox,outbox)).status=='cancelled'


async def test_commands_share_stop_boundary_but_cannot_approve_or_shell(client,enabled_bots):
    f=enabled_bots;first=await receive(f)
    assert (await receive(f,value=update(8,'/stop'),offset=8)).disposition=='command'
    assert (await receive(f,value=update(9,'/approve'),offset=9)).disposition=='command'
    async with Session() as db:
        assert (await db.get(Run,first.run_id)).status=='cancelled'
        assert await db.scalar(select(func.count()).select_from(Run))==1
        assert any('không được phép' in r.body for r in await db.scalars(select(ChannelOutbox)))


async def test_utf16_parts_each_keep_independent_scope_and_request_identity(client,enabled_bots):
    f=enabled_bots
    async with Session.begin() as db:
        binding=await db.get(ChannelBinding,f['bindings'][0]);await service.queue(db,binding,'manual:parts','🙂'*4000,'manual')
    async with Session() as db:
        rows=list(await db.scalars(select(ChannelOutbox).order_by(ChannelOutbox.request_key)))
        assert len(rows)==3 and ''.join(r.body for r in rows)=='🙂'*4000
        assert all(len(r.body.encode('utf-16-le'))//2<=3500 and r.telegram_context['generation']==2 for r in rows)


async def test_retryable_is_bounded_to_three_claims(client,enabled_bots):
    f=enabled_bots;outbox=await completed(f);pin=f['pins'][0]
    for attempt in range(1,4):
        async with rt.own_bot(pin) as lease:
            claim=await scoped.claim_delivery(lease,generation=2,outbox_id=outbox);assert claim.attempt==attempt
            await scoped.finish_delivery(lease,claim=claim,outcome='retryable',retry_after=1)
        async with Session.begin() as db:
            (await db.get(ChannelOutbox,outbox)).available_at=now()-timedelta(seconds=1)
            (await db.scalar(select(TelegramRuntimeProfile).where(TelegramRuntimeProfile.connection_id==pin.connection_id))).cooldown_until=now()-timedelta(seconds=1)
    async with Session() as db:assert (await db.get(ChannelOutbox,outbox)).status=='failed'
    async with rt.own_bot(pin) as lease:assert await scoped.claim_delivery(lease,generation=2,outbox_id=outbox) is None


@pytest.mark.parametrize('fault',['wrong_bot','timeout','cancel'])
async def test_failed_enable_never_commits_generation_or_approval(client,enabled_bots,fault):
    f=enabled_bots;pin=f['pins'][0]
    async with rt.own_bot(pin) as lease:
        await scoped.control_profile(lease,generation=2,request_key=str(uuid4()),action='disable',consent=True)
    async with Session() as db:before=await db.scalar(select(func.count()).select_from(TelegramRuntimeAudit))
    async def handler(request):
        if fault=='timeout':raise httpx.ReadTimeout('synthetic timeout',request=request)
        if fault=='cancel':raise asyncio.CancelledError()
        return httpx.Response(200,json={'ok':True,'result':{'id':999,'is_bot':True}})
    async with rt.own_bot(pin) as lease:
        with pytest.raises(asyncio.CancelledError if fault=='cancel' else rt.TelegramRuntimeError):
            await scoped.control_profile(lease,generation=3,request_key=str(uuid4()),action='enable',consent=True,transport=httpx.MockTransport(handler))
    async with Session() as db:
        profile=await db.scalar(select(TelegramRuntimeProfile).where(TelegramRuntimeProfile.connection_id==pin.connection_id))
        assert (profile.generation,profile.status)==(3,'disabled')
        assert await db.scalar(select(func.count()).select_from(TelegramRuntimeAudit))==before


async def test_staged_unpinned_queue_is_never_adopted_by_enabled_runtime(client,enabled_bots):
    f=enabled_bots;pin=f['pins'][0]
    async with Session.begin() as db:
        old=ChannelOutbox(workspace_id=pin.workspace_id,connection_id=pin.connection_id,binding_id=f['bindings'][0],
            request_key='staged-old',content_hash=service.digest({'body':'Old staged','kind':'manual'}),body='Old staged',kind='manual')
        db.add(old);await db.flush();ident=old.id
    async with rt.own_bot(pin) as lease:assert await scoped.claim_delivery(lease,generation=2,outbox_id=ident) is None
    async with Session() as db:assert (await db.get(ChannelOutbox,ident)).status=='cancelled'


async def test_existing_cooldown_is_rechecked_after_claim(client,enabled_bots):
    f=enabled_bots;outbox=await completed(f);pin=f['pins'][0]
    async with rt.own_bot(pin) as lease:claim=await scoped.claim_delivery(lease,generation=2,outbox_id=outbox)
    async with Session.begin() as db:
        profile=await db.scalar(select(TelegramRuntimeProfile).where(TelegramRuntimeProfile.connection_id==pin.connection_id))
        profile.cooldown_until=now()+timedelta(seconds=30)
    async with rt.own_bot(pin) as lease:assert await scoped.preflight_delivery(lease,generation=2,claim=claim) is None
    async with Session() as db:assert (await db.get(ChannelOutbox,outbox)).status=='queued'
