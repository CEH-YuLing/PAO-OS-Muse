"""Fenced sender uses native DB/outbox and HTTP fixtures only, never real bots."""
import asyncio,json,logging
from datetime import timedelta
from uuid import uuid4
import httpx,pytest
from sqlalchemy import select
from pao.config import settings
from pao.db import Session
from pao.models import (ChannelBinding,ChannelOutbox,TelegramRuntimeProfile,TelegramPeer,Member,User,Brain,
    BrainMember,ChatSession,Run,RunKnowledge,KnowledgeSource,BrainFile,BrainNote,now)
from pao.modules.channels import telegram_sender as sender,telegram_runtime as rt,telegram_scoped as scoped,telegram_store as store,service
from test_telegram_scoped import enabled_bots,completed,token,receive,update,Gateway,execute_run


async def queued(f,index=0,body='Kết quả riêng',key=None):
    async with Session.begin() as db:
        binding=await db.get(ChannelBinding,f['bindings'][index])
        return (await service.queue(db,binding,key or 'manual:'+str(uuid4()),body,'manual')).id


async def state(ident):
    async with Session() as db:
        row=await db.get(ChannelOutbox,ident)
        return row.status,row.attempts,row.remote_id,row.error_code


def success(pin,payload):
    return {'ok':True,'result':{'message_id':123,'chat':{'id':int(payload['chat_id']),'type':'private'},
        'from':{'id':int(pin.bot_user_id),'is_bot':True},'text':payload['text']}}


def transport(pin,seen,*,handler=None):
    async def send(request):
        assert request.method=='POST' and request.url.host=='api.telegram.org'
        assert request.url.path=='/bot'+token(pin).get_secret_value()+'/sendMessage'
        assert 'authorization' not in request.headers
        payload=json.loads(request.content);seen.append(payload)
        assert set(payload)=={'chat_id','text','link_preview_options'}
        assert payload['chat_id']=='777' and payload['link_preview_options']=={'is_disabled':True}
        if handler:return await handler(request,payload)
        return httpx.Response(200,json=success(pin,payload))
    return httpx.MockTransport(send)


async def expire_cooldown(pin,ident):
    async with Session.begin() as db:
        row=await db.get(ChannelOutbox,ident);row.available_at=now()-timedelta(seconds=1)
        profile=await db.scalar(select(TelegramRuntimeProfile).where(TelegramRuntimeProfile.connection_id==pin.connection_id))
        profile.cooldown_until=now()-timedelta(seconds=1)


async def test_two_bots_same_chat_and_request_key_durable_claim_before_http_no_resend(enabled_bots):
    f=enabled_bots;ids=[]
    for i,pin in enumerate(f['pins']):
        ident=await queued(f,i,body='Riêng doanh nghiệp '+str(i),key='same-key');ids.append(ident);seen=[]
        async def committed(request,payload):
            assert (await state(ident))[:2]==('sending',1)
            return httpx.Response(200,json=success(pin,payload))
        result=await sender.send_once(pin,ident,transport=transport(pin,seen,handler=committed))
        assert result.disposition=='sent' and await state(ident)==('sent',1,'123',None)
        assert (await sender.send_once(pin,ident,transport=transport(pin,seen))).disposition=='noop'
        assert len(seen)==1 and seen[0]['text']=='Riêng doanh nghiệp '+str(i)
        assert 'Riêng' not in repr(result)
    assert ids[0]!=ids[1]
    with pytest.raises(rt.TelegramRuntimeError,match='not_found'):
        await sender.send_once(f['pins'][1],ids[0],transport=transport(f['pins'][1],[]))


async def test_native_run_collect_result_uses_same_sender_and_receipt(enabled_bots):
    f=enabled_bots;ident=await completed(f);pin=f['pins'][0];seen=[]
    assert (await sender.send_once(pin,ident,transport=transport(pin,seen))).disposition=='sent'
    assert len(seen)==1 and (await state(ident))[:3]==('sent',1,'123')


@pytest.mark.parametrize('fault',['timeout','connect','redirect','mime','json','large','echo','500',
    'wrong_chat','wrong_bot','bad_mid','bool_mid','wrong_text','no_result','429_bad','400_mismatch'])
async def test_uncertain_outcomes_terminal_unknown_no_retry_no_private_logs(enabled_bots,fault,caplog):
    f=enabled_bots;pin=f['pins'][0];ident=await queued(f);seen=[];caplog.set_level(logging.DEBUG)
    async def fail(request,payload):
        logging.getLogger('httpcore.http11').debug('private %s',request.url)
        if fault in ('timeout','connect'):
            kind=httpx.ReadTimeout if fault=='timeout' else httpx.ConnectError
            raise kind('private '+str(request.url),request=request)
        if fault=='redirect':return httpx.Response(307,headers={'location':'https://fixture.invalid/'+token(pin).get_secret_value()})
        if fault=='mime':return httpx.Response(200,text='PRIVATE')
        if fault=='json':return httpx.Response(200,content=b'{',headers={'content-type':'application/json'})
        if fault=='large':return httpx.Response(200,content=b' '*(rt.MAX_BYTES+1),headers={'content-type':'application/json'})
        if fault=='500':return httpx.Response(500,json={'ok':False,'error_code':500,'description':'PRIVATE'})
        if fault=='429_bad':return httpx.Response(429,json={'ok':False,'error_code':429,'parameters':{'retry_after':True}})
        if fault=='400_mismatch':return httpx.Response(400,json={'ok':False,'error_code':403})
        data=success(pin,payload)
        if fault=='echo':data['echo']=token(pin).get_secret_value()
        elif fault=='wrong_chat':data['result']['chat']['id']=888
        elif fault=='wrong_bot':data['result']['from']['id']=222
        elif fault=='bad_mid':data['result']['message_id']=0
        elif fault=='bool_mid':data['result']['message_id']=True
        elif fault=='wrong_text':data['result']['text']='OTHER'
        else:data['result']=None
        return httpx.Response(200,json=data)
    result=await sender.send_once(pin,ident,transport=transport(pin,seen,handler=fail))
    assert result.disposition=='unknown' and await state(ident)==('unknown',1,None,'provider_delivery_uncertain')
    assert (await sender.send_once(pin,ident,transport=transport(pin,seen))).disposition=='noop'
    assert len(seen)==1 and token(pin).get_secret_value() not in caplog.text+repr(result)


@pytest.mark.parametrize('code',[400,401,403,404])
async def test_positive_provider_rejection_fails_without_retry_or_redirect(enabled_bots,code):
    f=enabled_bots;pin=f['pins'][0];ident=await queued(f);seen=[]
    async def reject(request,payload):return httpx.Response(code,json={'ok':False,'error_code':code,'description':'PRIVATE'})
    assert (await sender.send_once(pin,ident,transport=transport(pin,seen,handler=reject))).disposition=='rejected'
    assert await state(ident)==('failed',1,None,'provider_rejected')
    assert (await sender.send_once(pin,ident,transport=transport(pin,seen))).disposition=='noop' and len(seen)==1


async def test_429_has_per_bot_backoff_max_three_claims_other_sme_continues(enabled_bots):
    f=enabled_bots;a,b=f['pins'];ident=await queued(f);other=await queued(f,1);seen=[]
    async def limited(request,payload):return httpx.Response(429,json={'ok':False,'error_code':429,'parameters':{'retry_after':30}})
    for attempt in range(1,4):
        result=await sender.send_once(a,ident,transport=transport(a,seen,handler=limited))
        assert result.disposition=='retryable' and (await state(ident))[:2]==('queued' if attempt<3 else 'failed',attempt)
        assert (await sender.send_once(a,ident,transport=transport(a,seen))).disposition=='noop'
        if attempt==1:assert (await sender.send_once(b,other,transport=transport(b,[]))).disposition=='sent'
        await expire_cooldown(a,ident)
    assert len(seen)==3 and (await state(ident))[0]=='failed'


@pytest.mark.parametrize('change',['actor','owner','peer','binding','brain','session','generation','destination','tampered'])
async def test_revoked_before_invocation_never_calls_http(enabled_bots,change,monkeypatch):
    f=enabled_bots;pin=f['pins'][0];ident=await completed(f);seen=[];original=sender._invoke
    async def revoke(lease,generation,claim,http):
        if change=='generation':
            await store.save_profile(lease,token(pin),expected_generation=2,request_key=str(uuid4()),consent=True)
        else:
            async with Session.begin() as db:
                binding=await db.get(ChannelBinding,f['bindings'][0])
                if change in ('actor','owner'):(await db.get(Member,(pin.workspace_id,f[change]))).role='viewer'
                elif change=='peer':(await db.get(TelegramPeer,binding.peer_id)).enabled=False
                elif change=='binding':binding.enabled=False
                elif change=='brain':(await db.get(Brain,binding.brain_id)).owner_id=f['owner']
                elif change=='session':(await db.get(ChatSession,binding.session_id)).memory_enabled=True
                elif change=='destination':binding.outbound_confirmed=False
                else:(await db.get(ChannelOutbox,ident)).body='Corrupt'
        return await original(lease,generation,claim,http)
    monkeypatch.setattr(sender,'_invoke',revoke)
    if change=='owner':
        with pytest.raises(rt.TelegramRuntimeError,match='owner_unavailable'):
            await sender.send_once(pin,ident,transport=transport(pin,seen))
    else:assert (await sender.send_once(pin,ident,transport=transport(pin,seen))).disposition=='cancelled'
    assert not seen and (await state(ident))[0] in ('cancelled','sending')


@pytest.mark.parametrize('resource',['member','user','peer','binding','brain','session','run'])
async def test_authority_and_response_rows_remain_locked_through_actual_http(enabled_bots,resource):
    f=enabled_bots;pin=f['pins'][0];ident=await completed(f);second=await queued(f)
    async with Session() as db:
        binding=await db.get(ChannelBinding,f['bindings'][0]);run=await db.scalar(select(Run))
        model,key={
            'member':(Member,(pin.workspace_id,f['actor'])),'user':(User,f['actor']),
            'peer':(TelegramPeer,binding.peer_id),'binding':(ChannelBinding,binding.id),
            'brain':(Brain,binding.brain_id),'session':(ChatSession,binding.session_id),'run':(Run,run.id),
        }[resource]
    entered=asyncio.Event();release=asyncio.Event();changing=None
    async def hold(request,payload):entered.set();await release.wait();return httpx.Response(200,json=success(pin,payload))
    async def change():
        async with Session.begin() as db:
            row=await db.get(model,key,with_for_update=True)
            if resource=='member':row.role='viewer'
            elif resource=='user':row.active=False
            elif resource=='peer':row.enabled=False
            elif resource=='binding':row.outbound_confirmed=False
            elif resource=='brain':row.owner_id=f['owner']
            elif resource=='session':row.memory_enabled=True
            else:row.response='Changed after original admitted send'
    task=asyncio.create_task(sender.send_once(pin,ident,transport=transport(pin,[],handler=hold)))
    try:
        await asyncio.wait_for(entered.wait(),5);changing=asyncio.create_task(change())
        await asyncio.sleep(.1);assert not changing.done()
        release.set();assert (await task).disposition=='sent';await changing
        assert (await state(ident))[0]=='sent'
        if resource not in ('run',):
            assert (await sender.send_once(pin,second,transport=transport(pin,[]))).disposition=='noop'
            assert (await state(second))[0]=='cancelled'
    finally:
        release.set();await asyncio.gather(task,*([] if changing is None else [changing]),return_exceptions=True)


@pytest.mark.parametrize('resource',['member','binding','profile'])
async def test_nowait_contention_before_claim_does_not_consume_attempt_or_deadlock(enabled_bots,resource):
    f=enabled_bots;pin=f['pins'][0];ident=await queued(f);seen=[]
    async with Session.begin() as db:
        if resource=='member':await db.get(Member,(pin.workspace_id,f['actor']),with_for_update=True)
        elif resource=='binding':await db.get(ChannelBinding,f['bindings'][0],with_for_update=True)
        else:await db.scalar(select(TelegramRuntimeProfile).where(TelegramRuntimeProfile.connection_id==pin.connection_id).with_for_update())
        result=await asyncio.wait_for(sender.send_once(pin,ident,transport=transport(pin,seen)),5)
        assert result.disposition=='deferred' and not seen and (await state(ident))[:2]==('queued',0)
        # A revoke already holding member can still acquire binding immediately.
        assert await db.get(ChannelBinding,f['bindings'][0],with_for_update={'nowait':True})
    assert (await sender.send_once(pin,ident,transport=transport(pin,seen))).disposition=='sent'


async def test_cancel_during_http_leaves_durable_sending_then_unknown_not_resend(enabled_bots):
    f=enabled_bots;pin=f['pins'][0];ident=await queued(f);seen=[];entered=asyncio.Event()
    async def hold(request,payload):entered.set();await asyncio.Event().wait()
    task=asyncio.create_task(sender.send_once(pin,ident,transport=transport(pin,seen,handler=hold)))
    try:
        await asyncio.wait_for(entered.wait(),5);task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
    finally:
        if not task.done():task.cancel()
        await asyncio.gather(task,return_exceptions=True)
    assert (await state(ident))[:2]==('sending',1)
    assert (await sender.send_once(pin,ident,transport=transport(pin,seen))).disposition=='noop'
    async with Session.begin() as db:(await db.get(ChannelOutbox,ident)).updated_at=now()-timedelta(minutes=3)
    await service.reconcile_stale()
    assert (await state(ident))[:2]==('unknown',1)
    assert (await sender.send_once(pin,ident,transport=transport(pin,seen))).disposition=='noop' and len(seen)==1


@pytest.mark.parametrize('gate',['scoped_off','host_on','disabled','channels_off'])
async def test_flags_and_profile_never_fall_back_to_host_token(enabled_bots,gate,monkeypatch):
    f=enabled_bots;pin=f['pins'][0];ident=await queued(f);seen=[]
    monkeypatch.setattr(settings(),'telegram_bot_token','999:HOST_MUST_NOT_BE_USED')
    if gate=='scoped_off':monkeypatch.setattr(settings(),'telegram_scoped_runtime_enabled',False)
    elif gate=='host_on':monkeypatch.setattr(settings(),'telegram_enabled',True)
    elif gate=='channels_off':monkeypatch.setattr(settings(),'channels_enabled',False)
    else:
        async with rt.own_bot(pin) as lease:await scoped.control_profile(lease,generation=2,request_key=str(uuid4()),action='disable',consent=True)
    with pytest.raises(rt.TelegramRuntimeError):await sender.send_once(pin,ident,transport=transport(pin,seen))
    assert not seen and (await state(ident))[:2]==('queued',0)


async def test_success_throttles_next_message_for_this_bot_only(enabled_bots):
    f=enabled_bots;pin=f['pins'][0];first=await queued(f);second=await queued(f);seen=[]
    assert (await sender.send_once(pin,first,transport=transport(pin,seen))).disposition=='sent'
    assert (await sender.send_once(pin,second,transport=transport(pin,seen))).disposition=='noop'
    assert len(seen)==1 and (await state(second))[:2]==('queued',0)
    await expire_cooldown(pin,second)
    assert (await sender.send_once(pin,second,transport=transport(pin,seen))).disposition=='sent'


async def grounded(client,identity,f,monkeypatch,kind):
    from pao.modules.knowledge import worker,index
    for name in ('knowledge_sources_enabled','knowledge_enabled','channel_autoreply_enabled'):
        monkeypatch.setattr(settings(),name,True)
    monkeypatch.setattr(settings(),'knowledge_embeddings_enabled',False)
    async with Session.begin() as db:
        binding=await db.get(ChannelBinding,f['bindings'][0]);bid=binding.brain_id
        await service.ensure_session(db,binding)
        chat=await db.get(ChatSession,binding.session_id);chat.knowledge_enabled=True
    # Explicit test setup before any inbound pin exists. Session policy changes
    # revoke the binding, so re-enable deliberately; never bypass the DB trigger.
    async with Session.begin() as db:
        binding=await db.get(ChannelBinding,f['bindings'][0]);binding.enabled=True;binding.outbound_confirmed=True
    headers=identity['other'];root='/v1/brains/'+bid
    if kind=='file':
        response=await client.post(root+'/files',params={'name':'source.md'},headers={**headers,'content-type':'text/markdown'},content=b'Doi tra trong 7 ngay.')
    else:response=await client.post(root+'/notes',headers=headers,json={'title':'SOP','content':'Doi tra trong 7 ngay.'})
    assert response.status_code==201,response.text
    origin=response.json()['id']
    response=await client.post(root+'/sources',headers=headers,json={'kind':kind,'origin_id':origin})
    assert response.status_code==200,response.text
    source=response.json();await worker.ingest_source({},source['job_id'])
    async with Session.begin() as db:
        from pao.models import KnowledgeVersion
        value=await db.get(KnowledgeVersion,source['version_id']);job=await index.ensure_job(db,value,f['actor']);jid=job.id
    await index.index_source({},jid)
    incoming=await receive(f,value=update(body='Doi tra trong may ngay?'));await execute_run({'gateway':Gateway()},incoming.run_id)
    async with Session() as db:
        run=await db.get(Run,incoming.run_id);assert run.status=='completed'
        evidence=await db.scalar(select(RunKnowledge).where(RunKnowledge.run_id==run.id));assert evidence.evidence
    async with rt.own_bot(f['pins'][0]) as lease:assert await scoped.collect_results(lease,generation=2)==1
    async with Session() as db:ident=await db.scalar(select(ChannelOutbox.id))
    return ident,source['id'],origin


@pytest.mark.parametrize('kind',['file','note'])
@pytest.mark.parametrize('revoke_before',[False,True])
async def test_grounded_evidence_source_and_origin_fenced_through_http(client,identity,enabled_bots,monkeypatch,kind,revoke_before):
    f=enabled_bots;pin=f['pins'][0];ident,sid,oid=await grounded(client,identity,f,monkeypatch,kind);seen=[]
    async def trash():
        async with Session.begin() as db:
            origin=await db.get(BrainFile if kind=='file' else BrainNote,oid,with_for_update=True);origin.trashed_at=now()
    if revoke_before:
        await trash()
        assert (await sender.send_once(pin,ident,transport=transport(pin,seen))).disposition=='noop'
        assert (await state(ident))[0]=='cancelled' and not seen
        return
    entered=asyncio.Event();release=asyncio.Event();changing=None
    async def hold(request,payload):entered.set();await release.wait();return httpx.Response(200,json=success(pin,payload))
    task=asyncio.create_task(sender.send_once(pin,ident,transport=transport(pin,seen,handler=hold)))
    try:
        await asyncio.wait_for(entered.wait(),5);changing=asyncio.create_task(trash());await asyncio.sleep(.1)
        assert not changing.done();release.set();assert (await task).disposition=='sent';await changing
    finally:
        release.set();await asyncio.gather(task,*([] if changing is None else [changing]),return_exceptions=True)


async def test_after_claim_lock_contention_is_known_no_send_and_bounded_retry(enabled_bots,monkeypatch):
    f=enabled_bots;pin=f['pins'][0];ident=await queued(f);original=sender._invoke;seen=[]
    async def busy(lease,generation,claim,http):
        async with Session.begin() as db:
            await db.get(ChannelBinding,f['bindings'][0],with_for_update=True)
            return await original(lease,generation,claim,http)
    monkeypatch.setattr(sender,'_invoke',busy)
    assert (await sender.send_once(pin,ident,transport=transport(pin,seen))).disposition=='deferred'
    assert not seen and (await state(ident))[:2]==('queued',1)
    monkeypatch.setattr(sender,'_invoke',original);await expire_cooldown(pin,ident)
    assert (await sender.send_once(pin,ident,transport=transport(pin,seen))).disposition=='sent'
    assert len(seen)==1 and (await state(ident))[:2]==('sent',2)


@pytest.mark.parametrize('loss',['disconnect','unlock'])
async def test_lost_bot_lease_after_claim_cannot_send_with_stale_authority(enabled_bots,monkeypatch,loss):
    from sqlalchemy import text
    f=enabled_bots;pin=f['pins'][0];ident=await queued(f);original=sender._invoke;seen=[]
    async def lose(lease,generation,claim,http):
        if loss=='disconnect':await lease.connection.invalidate()
        else:
            assert await lease.connection.scalar(text('SELECT pg_advisory_unlock(hashtextextended(:key,0))'),{'key':'pao-telegram-bot-v1:'+pin.bot_user_id})
            await lease.connection.commit()
        return await original(lease,generation,claim,http)
    monkeypatch.setattr(sender,'_invoke',lose)
    with pytest.raises(rt.TelegramRuntimeError,match='lease_lost'):
        await sender.send_once(pin,ident,transport=transport(pin,seen))
    assert not seen and (await state(ident))[:2]==('sending',1)
    monkeypatch.setattr(sender,'_invoke',original)
    assert (await sender.send_once(pin,ident,transport=transport(pin,seen))).disposition=='noop'


async def test_lost_database_ack_after_provider_success_is_not_replayed(enabled_bots,monkeypatch):
    f=enabled_bots;pin=f['pins'][0];ident=await queued(f);seen=[]
    async def lost(*args,**kwargs):raise rt.TelegramRuntimeError('fixture_database_commit_lost')
    monkeypatch.setattr(scoped,'_apply_delivery_outcome',lost)
    with pytest.raises(rt.TelegramRuntimeError,match='fixture_database_commit_lost'):
        await sender.send_once(pin,ident,transport=transport(pin,seen))
    assert (await state(ident))[:2]==('sending',1)
    assert (await sender.send_once(pin,ident,transport=transport(pin,seen))).disposition=='noop' and len(seen)==1


@pytest.mark.parametrize('during',[False,True])
async def test_explicit_brain_editor_grant_revoke_serializes_with_send(enabled_bots,during):
    f=enabled_bots;pin=f['pins'][0]
    async with Session.begin() as db:
        binding=await db.get(ChannelBinding,f['bindings'][0]);bid=binding.brain_id
        (await db.get(Brain,bid)).owner_id=f['owner']
        db.add(BrainMember(brain_id=bid,workspace_id=pin.workspace_id,user_id=f['actor'],role='editor'))
    ident=await queued(f);seen=[]
    async def revoke():
        async with Session.begin() as db:await db.delete(await db.get(BrainMember,(bid,f['actor']),with_for_update=True))
    if not during:
        await revoke();assert (await sender.send_once(pin,ident,transport=transport(pin,seen))).disposition=='noop'
        assert not seen and (await state(ident))[0]=='cancelled';return
    entered=asyncio.Event();release=asyncio.Event();changing=None
    async def hold(request,payload):entered.set();await release.wait();return httpx.Response(200,json=success(pin,payload))
    task=asyncio.create_task(sender.send_once(pin,ident,transport=transport(pin,seen,handler=hold)))
    try:
        await asyncio.wait_for(entered.wait(),5);changing=asyncio.create_task(revoke());await asyncio.sleep(.1)
        assert not changing.done();release.set();assert (await task).disposition=='sent';await changing
    finally:
        release.set();await asyncio.gather(task,*([] if changing is None else [changing]),return_exceptions=True)


async def test_channel_switch_rechecked_after_durable_claim(enabled_bots,monkeypatch):
    f=enabled_bots;pin=f['pins'][0];ident=await queued(f);original=sender._invoke;seen=[]
    async def turn_off(lease,generation,claim,http):
        monkeypatch.setattr(settings(),'channels_enabled',False)
        return await original(lease,generation,claim,http)
    monkeypatch.setattr(sender,'_invoke',turn_off)
    assert (await sender.send_once(pin,ident,transport=transport(pin,seen))).disposition=='cancelled'
    assert not seen and (await state(ident))[0]=='cancelled'


async def test_credential_echo_in_queued_body_is_not_sent_to_provider(enabled_bots):
    f=enabled_bots;pin=f['pins'][0];ident=await queued(f,body=token(pin).get_secret_value());seen=[]
    assert (await sender.send_once(pin,ident,transport=transport(pin,seen))).disposition=='unknown'
    assert not seen and (await state(ident))[0]=='unknown'


async def test_source_archive_remains_locked_during_grounded_send(client,identity,enabled_bots,monkeypatch):
    f=enabled_bots;pin=f['pins'][0];ident,sid,_=await grounded(client,identity,f,monkeypatch,'file')
    entered=asyncio.Event();release=asyncio.Event();changing=None
    async def archive():
        async with Session.begin() as db:(await db.get(KnowledgeSource,sid,with_for_update=True)).archived_at=now()
    async def hold(request,payload):entered.set();await release.wait();return httpx.Response(200,json=success(pin,payload))
    task=asyncio.create_task(sender.send_once(pin,ident,transport=transport(pin,[],handler=hold)))
    try:
        await asyncio.wait_for(entered.wait(),5);changing=asyncio.create_task(archive());await asyncio.sleep(.1)
        assert not changing.done();release.set();assert (await task).disposition=='sent';await changing
    finally:
        release.set();await asyncio.gather(task,*([] if changing is None else [changing]),return_exceptions=True)
