"""Real PG/ASGI pairing, modes and grants; synthetic credentials and HTTP only."""
import hashlib,json
from datetime import timedelta
from uuid import uuid4
import httpx,pytest
from sqlalchemy import select,func,text
from pao.auth import issue_token
from pao.db import Session
from pao.config import settings
from pao.models import (TelegramRuntimeProfile,TelegramRuntimeReceipt,TelegramPairing,TelegramPeer,
    TelegramConnection,TelegramRuntimeAudit,ChannelBinding,ChannelInbound,ChannelOutbox,Member,Run,now)
from pao.modules.channels import telegram_runtime as rt,telegram_store as store,telegram_scoped as scoped,telegram_setup as setup,telegram_transport as transport,telegram_polling as polling
from test_telegram_scoped import enabled_bots,update,receive,token
from test_telegram_polling import fixture_http,snapshot


def auth(user):return {'Authorization':'Bearer '+issue_token(user)}


async def prepare(f,user=None,tgid='888',brain=None):
    pin=f['pins'][0];user=user or f['owner']
    async with rt.own_bot(pin) as lease:
        async with store._transaction(lease) as db:
            profile=await store._profile(db,pin)
            row,code=await setup.pairing(db,pin,profile,user,tgid,brain)
            return row.id,code


async def observe(f,code,tgid=888,ident=9):
    value=update(ident,'/start pao_'+code);value['message']['from']['id']=value['message']['chat']['id']=tgid
    return await receive(f,value=value)


async def confirmed(f):
    ident,code=await prepare(f);await observe(f,code)
    pin=f['pins'][0]
    async with rt.own_bot(pin) as lease:
        async with store._transaction(lease) as db:
            profile=await store._profile(db,pin)
            peer=await setup.confirm(db,pin,profile,f['owner'],ident)
            return peer.id


async def test_pairing_observe_confirm_does_not_grant_or_store_raw_challenge(client,enabled_bots,caplog):
    f=enabled_bots;pin=f['pins'][0];headers=auth(f['owner'])
    response=await client.post('/v1/telegram/scoped/'+pin.connection_id+'/pairing',headers=headers,json={'expected_user_id':'888'})
    assert response.status_code==201,response.text
    data=response.json();code=data['command'].removeprefix('/start pao_')
    await observe(f,code)
    response=await client.post('/v1/telegram/scoped/'+pin.connection_id+'/pairing/confirm',headers=headers,json={'pairing_id':data['id'],'consent':True})
    assert response.status_code==200 and response.json()['granted'] is False
    async with Session() as db:
        pair=await db.get(TelegramPairing,data['id']);peer=await db.get(TelegramPeer,response.json()['peer_id'])
        assert pair.status=='confirmed' and code not in pair.code_hash and not peer.enabled
        assert await db.scalar(select(func.count()).select_from(ChannelBinding).where(ChannelBinding.peer_id==peer.id))==0
        assert await db.scalar(select(func.count()).select_from(ChannelInbound))==0
        assert await db.scalar(select(func.count()).select_from(Run))==0
    assert code not in caplog.text
    assert (await client.post('/v1/telegram/scoped/'+pin.connection_id+'/pairing/confirm',headers=headers,json={'pairing_id':data['id'],'consent':True})).status_code==409


@pytest.mark.parametrize('fault',['forwarded','expired','wrong_bot','wrong_account','rotated','viewer','unknown'])
async def test_pairing_challenge_never_grants_on_invalid_context(client,enabled_bots,fault):
    f=enabled_bots;pin=f['pins'][0];ident,code=await prepare(f)
    if fault=='expired':
        # Expiry is an immutable pin; advance the service clock rather than
        # weakening the DB trigger or modifying a persisted challenge.
        from unittest.mock import patch
        with patch.object(setup,'now',lambda:now()+timedelta(minutes=11)):await observe(f,code)
    elif fault=='wrong_bot':await receive(f,1,value=update(9,'/start pao_'+code))
    elif fault=='forwarded':await observe(f,code,tgid=999)
    elif fault=='unknown':await observe(f,'x'*32)
    else:await observe(f,code)
    if fault=='rotated':
        async with rt.own_bot(pin) as lease:await store.save_profile(lease,token(pin),expected_generation=2,request_key=str(uuid4()),consent=True)
    if fault=='viewer':
        async with Session.begin() as db:(await db.get(Member,(pin.workspace_id,f['owner']))).role='viewer'
    response=await client.post('/v1/telegram/scoped/'+pin.connection_id+'/pairing/confirm',headers=auth(f['actor'] if fault=='wrong_account' else f['owner']),json={'pairing_id':ident,'consent':True})
    assert response.status_code in (403,409)
    async with Session() as db:assert not await db.scalar(select(TelegramPeer.id).where(TelegramPeer.connection_id==pin.connection_id,TelegramPeer.telegram_user_id=='888'))


async def test_explicit_admin_grant_separates_chat_reports_and_revocation(client,enabled_bots):
    f=enabled_bots;pin=f['pins'][0];peer=await confirmed(f);base='/v1/telegram/scoped/'+pin.connection_id
    body={'peer_id':peer,'request_key':str(uuid4()),'version':0,'allow_reports':True,'allow_chat':False,'confirm_destination':True}
    assert (await client.post(base+'/team/grant',headers=auth(f['actor']),json=body)).status_code==403
    result=await client.post(base+'/team/grant',headers=auth(f['owner']),json=body)
    assert result.status_code==200,result.text
    binding_id=result.json()['binding_id']
    async with Session() as db:
        binding=await db.get(ChannelBinding,binding_id)
        assert binding.mode=='quiet' and binding.reports_enabled and binding.enabled
    assert (await client.post(base+'/team/grant',headers=auth(f['owner']),json=body)).status_code==200
    result=await client.post(base+'/team/grant',headers=auth(f['owner']),json={**body,'request_key':str(uuid4()),'version':result.json()['version'],'allow_reports':False,'confirm_destination':False})
    assert result.status_code==200,result.text
    async with Session() as db:
        binding=await db.get(ChannelBinding,binding_id);assert not binding.enabled and not binding.outbound_confirmed and not binding.reports_enabled


async def test_setup_list_cross_sme_and_token_validation_no_echo(client,enabled_bots):
    f=enabled_bots;pin=f['pins'][0]
    response=await client.get('/v1/telegram/scoped',params={'workspace_id':pin.workspace_id},headers=auth(f['owner']))
    assert response.status_code==200 and len(response.json()['connections'])==1
    assert token(pin).get_secret_value() not in response.text and 'ciphertext' not in response.text
    invalid='111:'+('PRIVATE_VALUE'*5)
    response=await client.post('/v1/telegram/scoped/'+pin.connection_id+'/credential',headers=auth(f['owner']),json={'generation':2,'request_key':'invalid','token':invalid,'consent':True})
    assert response.status_code==422 and invalid not in response.text and response.headers['cache-control']=='no-store'
    assert (await client.get('/v1/telegram/scoped',params={'workspace_id':pin.workspace_id},headers={'Authorization':'Bearer invalid'})).status_code==401


async def test_large_update_quarantined_then_next_update_does_not_stick(enabled_bots):
    f=enabled_bots;pin=f['pins'][0];large=update(6,'x'*70000)
    result=await polling.poll_once(pin,f['redis'],transport=fixture_http(pin,[large,update()],[]))
    assert result.next_offset==8 and await snapshot(pin)==(8,2,1)
    async with Session() as db:
        receipt=await db.scalar(select(TelegramRuntimeReceipt).where(TelegramRuntimeReceipt.update_id==6))
        assert receipt.reason=='malformed' and not receipt.inbound_id


async def test_clock_skew_cannot_force_early_cursor_reset(enabled_bots,monkeypatch):
    f=enabled_bots;pin=f['pins'][0]
    await polling.poll_once(pin,f['redis'],transport=fixture_http(pin,[{'update_id':900,'callback_query':{}}],[]))
    future=now()+timedelta(days=8)
    # DB clock and application clock both enforce the quiet horizon. Seed the
    # fixture timestamp through the old-version test setup is not permitted;
    # transaction-local PostgreSQL clock is immutable, so test the denied path
    # here and use a clone with an eight-day fixture clock for positive recovery.
    monkeypatch.setattr(polling,'now',lambda:future)
    with pytest.raises(rt.TelegramRuntimeError):await polling.poll_once(pin,f['redis'],transport=fixture_http(pin,[update()],[]))
    async with Session() as db:
        profile=await db.scalar(select(TelegramRuntimeProfile).where(TelegramRuntimeProfile.connection_id==pin.connection_id))
        assert profile.cursor_epoch==0 and profile.next_offset==901


async def test_old_durable_cursor_resets_to_new_epoch_and_accepts_lower_id(enabled_bots):
    from pao.modules.channels import telegram_identity as identities
    from test_telegram_scoped import http
    f=enabled_bots;old=now()-timedelta(days=8)
    async with Session.begin() as db:
        c=TelegramConnection(workspace_id=f['pins'][0].workspace_id,owner_id=f['owner'],bot_user_id='333');db.add(c);await db.flush()
        pin=rt.RuntimePin(c.workspace_id,c.id,c.owner_id,c.version,c.bot_user_id)
    async with rt.own_bot(pin) as lease:
        await identities.verify_identity(lease,token(pin),request_key=str(uuid4()),consent=True,transport=http(pin))
        async with store._transaction(lease) as db:
            p=TelegramRuntimeProfile(workspace_id=pin.workspace_id,connection_id=pin.connection_id,connection_version=1,
                generation=1,status='disabled',token_ciphertext=store._seal(pin,1,token(pin)),cursor_touched_at=old)
            db.add(p);await db.flush()
            db.add(TelegramRuntimeAudit(workspace_id=pin.workspace_id,connection_id=pin.connection_id,actor_id=pin.owner_id,
                request_key=str(uuid4()),generation=1,action='stored',content_hash='a'*64))
            db.add(TelegramRuntimeReceipt(workspace_id=pin.workspace_id,connection_id=pin.connection_id,generation=1,
                cursor_epoch=0,update_id=7,content_hash='b'*64,reason='unsupported',created_at=old))
            await db.flush();p.next_offset=8
        await scoped.control_profile(lease,generation=1,request_key=str(uuid4()),action='enable',consent=True,transport=http(pin))
    seen=[];result=await polling.poll_once(pin,f['redis'],transport=fixture_http(pin,[update()],seen))
    assert result.next_offset==8 and seen[1][1]['offset']==0
    async with Session() as db:
        p=await db.scalar(select(TelegramRuntimeProfile).where(TelegramRuntimeProfile.connection_id==pin.connection_id))
        assert p.cursor_epoch==1 and p.next_offset==8
        assert set(await db.scalars(select(TelegramRuntimeReceipt.cursor_epoch).where(TelegramRuntimeReceipt.connection_id==pin.connection_id)))=={0,1}


async def hook_mode(f,monkeypatch):
    pin=f['pins'][0];monkeypatch.setattr(settings(),'telegram_public_base_url','https://pao.fixture.invalid')
    secrets=[]
    async def provider(request):
        body=json.loads(request.content);assert request.url.path.endswith('/setWebhook')
        assert body['drop_pending_updates'] is False and body['max_connections']==1
        assert pin.connection_id in body['url'] and token(pin).get_secret_value() not in body['url']
        secrets.append(body['secret_token']);return httpx.Response(200,json={'ok':True,'result':True})
    async with rt.own_bot(pin) as lease:
        disabled=await scoped.control_profile(lease,generation=2,request_key=str(uuid4()),action='disable',consent=True)
        changed=await transport.configure(lease,generation=disabled.generation,request_key=str(uuid4()),mode='webhook',consent=True,transport=httpx.MockTransport(provider))
        from test_telegram_scoped import http
        enabled=await scoped.control_profile(lease,generation=changed.generation,request_key=str(uuid4()),action='enable',consent=True,transport=http(pin))
    return pin,secrets[0],enabled.generation


async def test_webhook_header_mode_bound_and_out_of_order_dedup(client,enabled_bots,monkeypatch):
    f=enabled_bots;pin,secret,generation=await hook_mode(f,monkeypatch);path='/v1/telegram/scoped/'+pin.connection_id+'/webhook'
    headers={'X-Telegram-Bot-Api-Secret-Token':secret}
    assert (await client.post(path,json=update())).status_code==503
    assert (await client.post('/v1/telegram/scoped/'+f['pins'][1].connection_id+'/webhook',headers=headers,json=update())).status_code==503
    for value in (update(9),update(7),update(9)):
        response=await client.post(path,headers=headers,json=value);assert response.status_code==200,response.text
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(TelegramRuntimeReceipt))==2
    with pytest.raises(rt.TelegramRuntimeError,match='mode_conflict'):await polling.poll_once(pin,f['redis'],transport=fixture_http(pin,[],[]))
    response=await client.post(path,headers={**headers,'content-type':'application/json'},content=b' '*(2097152+1));assert response.status_code==413
    assert secret not in response.text


async def test_uncertain_mode_change_remains_disabled_and_no_automatic_retry(enabled_bots,monkeypatch):
    f=enabled_bots;pin=f['pins'][0];calls=[]
    def failure(request):calls.append(request);raise httpx.ReadTimeout('private provider error',request=request)
    async with rt.own_bot(pin) as lease:
        await scoped.control_profile(lease,generation=2,request_key=str(uuid4()),action='disable',consent=True)
        with pytest.raises(rt.TelegramRuntimeError,match='change_uncertain'):
            await transport.configure(lease,generation=3,request_key=str(uuid4()),mode='polling',consent=True,transport=httpx.MockTransport(failure))
    async with Session() as db:
        profile=await db.scalar(select(TelegramRuntimeProfile).where(TelegramRuntimeProfile.connection_id==pin.connection_id));assert profile.status=='disabled' and profile.generation==4
    assert len(calls)==1


async def test_create_requires_provider_identity_proof_before_reserving_id(client,enabled_bots,monkeypatch):
    f=enabled_bots;seen=[]
    def provider(request):
        seen.append(request.url.path)
        return httpx.Response(200,json={'ok':True,'result':{'id':333,'is_bot':True}})
    monkeypatch.setattr(httpx,'AsyncHTTPTransport',lambda **kwargs:httpx.MockTransport(provider))
    value={'workspace_id':f['pins'][0].workspace_id,'bot_user_id':'333','token':'333:'+'SYNTHETIC_SETUP_'*3,'consent':True}
    result=await client.post('/v1/telegram/scoped',headers=auth(f['owner']),json=value)
    assert result.status_code==201,result.text
    assert result.json()['identity_verified'] is True and result.json()['status']=='empty'
    async with Session() as db:assert not await db.scalar(select(TelegramRuntimeProfile.id).where(TelegramRuntimeProfile.connection_id==result.json()['id']))
    denied=await client.post('/v1/telegram/scoped',headers=auth(f['owner']),json={**value,'bot_user_id':'444','token':'444:'+'SYNTHETIC_SETUP_'*3})
    assert denied.status_code==409 and 'SYNTHETIC' not in denied.text
    async with Session() as db:assert not await db.scalar(select(TelegramConnection.id).where(TelegramConnection.bot_user_id=='444'))
    assert len(seen)==2


async def test_connection_admin_cannot_read_private_actor_inbound(client,enabled_bots):
    f=enabled_bots;await receive(f)
    response=await client.get('/v1/channels/bindings/'+f['bindings'][0]+'/inbox',headers=auth(f['owner']))
    assert response.status_code==200 and response.json()[0]['text'] is None and response.json()[0]['response'] is None


async def test_webhook_owner_conflict_and_rotated_generation_fail_closed(client,enabled_bots,monkeypatch):
    f=enabled_bots;pin,secret,generation=await hook_mode(f,monkeypatch)
    path='/v1/telegram/scoped/'+pin.connection_id+'/webhook';headers={'X-Telegram-Bot-Api-Secret-Token':secret}
    async with rt.own_bot(pin):assert (await client.post(path,headers=headers,json=update())).status_code==503
    async with rt.own_bot(pin) as lease:
        await store.save_profile(lease,token(pin),expected_generation=generation,request_key=str(uuid4()),consent=True)
    assert (await client.post(path,headers=headers,json=update())).status_code==503
    async with Session() as db:assert await db.scalar(select(func.count()).select_from(TelegramRuntimeReceipt))==0


async def test_rotation_and_reenable_never_resurrect_old_grant(client,enabled_bots):
    from test_telegram_scoped import http
    f=enabled_bots;pin=f['pins'][0];peer=await confirmed(f)
    async with rt.own_bot(pin) as lease:
        async with store._transaction(lease) as db:
            profile=await store._profile(db,pin)
            b=await setup.grant(db,pin,profile,f['owner'],peer,allow_chat=True,allow_reports=True,
                confirm_destination=True,version=0,request_key=str(uuid4()));bid=b.id;version=b.version
        await store.save_profile(lease,token(pin),expected_generation=2,request_key=str(uuid4()),consent=True)
        await scoped.control_profile(lease,generation=3,request_key=str(uuid4()),action='enable',consent=True,transport=http(pin))
    async with Session() as db:
        b=await db.get(ChannelBinding,bid);assert not b.enabled and not b.outbound_confirmed and not b.reports_enabled and b.version>version
    result=await client.post('/v1/telegram/scoped/'+pin.connection_id+'/team/grant',headers=auth(f['owner']),json={
        'peer_id':peer,'request_key':str(uuid4()),'version':b.version,'allow_chat':True,'confirm_destination':True})
    assert result.status_code==409 and result.json()['detail']=='telegram_pairing_confirmation_required'


async def test_repairing_cannot_repin_existing_private_brain(client,enabled_bots):
    f=enabled_bots;pin=f['pins'][0]
    async with Session() as db:existing=await db.get(ChannelBinding,f['bindings'][0]);peer_id=existing.peer_id;version=existing.version
    ident,code=await prepare(f,user=f['actor'],tgid='777',brain=None)
    await observe(f,code,tgid=777)
    async with rt.own_bot(pin) as lease:
        async with store._transaction(lease) as db:
            profile=await store._profile(db,pin);await setup.confirm(db,pin,profile,f['actor'],ident)
    result=await client.post('/v1/telegram/scoped/'+pin.connection_id+'/team/grant',headers=auth(f['owner']),json={
        'peer_id':peer_id,'request_key':str(uuid4()),'version':version,'allow_chat':True,'confirm_destination':True})
    assert result.status_code==409 and result.json()['detail']=='telegram_binding_brain_immutable'
