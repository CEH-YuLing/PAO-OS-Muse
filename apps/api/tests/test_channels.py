"""HTTP/DB/Run integration, identity isolation and uncertain delivery; no network."""
import asyncio
from uuid import uuid4
from datetime import timedelta
from unittest.mock import AsyncMock
import pytest
from sqlalchemy import select,func,text
from sqlalchemy.exc import DBAPIError
from pao.config import settings
from pao.db import Session
from pao.models import ChannelBinding,ChannelInbound,ChannelOutbox,Run,Member,BrainMember,TelegramPeer,BrainFile,now
from pao.modules.channels import service
from pao.runtime import execute_run
from test_memory import Gateway
from test_brain_manager import brains_on
from test_knowledge_sources import sources_on
from test_knowledge_workspace import p2_on,source
from test_telegram import peer

@pytest.fixture
def channels_on(monkeypatch):
    monkeypatch.setattr(settings(),'channels_enabled',True)
    monkeypatch.setattr(settings(),'engine_contract_enabled',True)
    monkeypatch.setattr(settings(),'chat_features_enabled',True)

async def binding(client,identity,**changes):
    body={'workspace_id':identity['workspace'],'actor_id':identity['user_id'],'external_identity':'fixture-peer','channel':'local',**changes}
    response=await client.post('/v1/channels/bindings',headers=identity['owner'],json=body)
    assert response.status_code==201,response.text
    return response.json(),body

async def control(client,identity,row,action,**changes):
    r=await client.post('/v1/channels/bindings/'+row['id']+'/control',headers=identity['owner'],json={'request_key':str(uuid4()),'version':row['version'],'action':action,**changes})
    assert r.status_code==200,r.text
    return r.json()

async def inbound(client,identity,row,text='Xin chào',key=None):
    return await client.post('/v1/channels/bindings/'+row['id']+'/inbound',headers=identity['owner'],json={'message_key':key or str(uuid4()),'text':text})

async def test_personal_shared_run_dedup_busy_stop_and_web_same_session(client,identity,channels_on):
    row,body=await binding(client,identity)
    assert not row['outbound_confirmed'] and row['mode']=='quiet'
    row=await control(client,identity,row,'auto')
    values=await asyncio.gather(*(inbound(client,identity,row,key='same') for _ in range(3)))
    assert all(v.status_code==202 for v in values),[v.text for v in values]
    assert len({v.json()['run_id'] for v in values})==1
    first=values[0].json();sid=first['session_id'];rid=first['run_id']
    assert (await inbound(client,identity,row,'Changed',key='same')).status_code==409
    assert (await inbound(client,identity,row)).json()['status']=='busy'
    web=await client.post('/v1/runs',headers=identity['owner'],json={'session_id':sid,'message':'Web concurrent','request_key':str(uuid4())})
    assert web.status_code==409
    assert (await inbound(client,identity,row,'/cancel')).json()['status']=='command'
    async with Session() as db:
        assert (await db.get(Run,rid)).status=='cancelled'
        assert await db.scalar(select(func.count(Run.id)))==1
    second=await inbound(client,identity,row,key='second');assert second.status_code==202
    await execute_run({'gateway':Gateway()},second.json()['run_id'])
    await service.collect();await service.collect()
    async with Session() as db:
        assert (await db.get(Run,second.json()['run_id'])).status=='completed'
        assert await db.scalar(select(func.count(ChannelOutbox.id)).where(ChannelOutbox.request_key=='result:'+second.json()['run_id']))==1
    assert (await client.get('/v1/sessions/'+sid,headers=identity['owner'])).status_code==200

async def test_takeover_cancels_and_manual_reply_is_durable_not_external(client,identity,channels_on):
    row,_=await binding(client,identity);row=await control(client,identity,row,'auto')
    admitted=(await inbound(client,identity,row)).json()
    row=await control(client,identity,row,'human')
    async with Session() as db:assert (await db.get(Run,admitted['run_id'])).status=='cancelled'
    assert (await inbound(client,identity,row,'Khách nhắn thêm')).json()['status']=='quiet'
    base='/v1/channels/bindings/'+row['id'];body={'request_key':str(uuid4()),'text':'Nhân viên đã tiếp quản.'}
    values=await asyncio.gather(*(client.post(base+'/reply',headers=identity['owner'],json=body) for _ in range(3)))
    assert all(v.status_code==201 and not v.json()['external_send_performed'] for v in values)
    assert len({v.json()['id'] for v in values})==1
    send=AsyncMock(return_value={'message_id':'receipt-1'})
    await asyncio.gather(*(service.send_one(send,'local') for _ in range(3)))
    assert send.await_count==1
    assert (await client.get(base+'/outbox',headers=identity['owner'])).json()[0]['status']=='sent'
    assert (await client.get(base+'/inbox',headers=identity['other'])).status_code==403
    assert (await client.get(base+'/inbox',headers=identity['outsider'])).status_code==404

async def test_uncertain_no_resend_owner_reconcile_and_retryable_backoff(client,identity,channels_on):
    row,_=await binding(client,identity);row=await control(client,identity,row,'human')
    r=await client.post('/v1/channels/bindings/'+row['id']+'/reply',headers=identity['owner'],json={'request_key':str(uuid4()),'text':'Reply'})
    ident=r.json()['id'];send=AsyncMock(side_effect=TimeoutError())
    await service.send_one(send,'local');await service.send_one(send,'local');assert send.await_count==1
    body={'request_key':str(uuid4()),'remote_id':'seen-remote-1','observed_delivered':True}
    r=await client.post('/v1/channels/outbox/'+ident+'/reconcile',headers=identity['owner'],json=body);assert r.status_code==200 and r.json()['source']=='owner_observation_not_provider_query'
    assert (await client.post('/v1/channels/outbox/'+ident+'/reconcile',headers=identity['owner'],json=body)).status_code==200
    assert (await client.post('/v1/channels/outbox/'+ident+'/reconcile',headers=identity['owner'],json={**body,'remote_id':'changed'})).status_code==409
    await client.post('/v1/channels/bindings/'+row['id']+'/reply',headers=identity['owner'],json={'request_key':str(uuid4()),'text':'Rate limited'})
    async with Session() as db:
        second=await db.scalar(select(ChannelOutbox).where(ChannelOutbox.status=='queued'))
    assert (await client.post('/v1/channels/outbox/'+second.id+'/reconcile',headers=identity['owner'],json=body)).status_code==409
    retry=AsyncMock(side_effect=service.RetryableDelivery())
    await service.send_one(retry,'local');await service.send_one(retry,'local');assert retry.await_count==1
    async with Session.begin() as db:
        saved=await db.scalar(select(ChannelOutbox).where(ChannelOutbox.status=='queued'));saved.available_at=now()-timedelta(seconds=1)
    await service.send_one(AsyncMock(return_value={'message_id':'ok'}),'local')
    async with Session() as db:assert (await db.get(ChannelOutbox,saved.id)).attempts==2

async def test_customer_grounded_brain_only_and_tool_boundary(client,identity,channels_on,p2_on,brains_on,monkeypatch):
    bid,_,_,_,_=await source(client,identity)
    async with Session.begin() as db:
        member=await db.scalar(select(Member).where(Member.workspace_id==identity['workspace'],Member.user_id!=identity['user_id']))
        actor=member.user_id;db.add(BrainMember(brain_id=bid,workspace_id=identity['workspace'],user_id=actor,role='editor'))
    row,_=await binding(client,identity,actor_id=actor,kind='customer',brain_id=bid)
    row=await control(client,identity,row,'auto')
    assert (await inbound(client,identity,row)).json()['status']=='blocked'
    monkeypatch.setattr(settings(),'channel_autoreply_enabled',True)
    r=await inbound(client,identity,row,'Doi tra trong bao nhieu ngay?');assert r.status_code==202,r.text
    rid=r.json()['run_id'];await execute_run({'gateway':AsyncMock(side_effect=AssertionError('No customer LLM'))},rid)
    async with Session() as db:
        run=await db.get(Run,rid);assert run.status=='completed' and run.brain_id==bid and run.brain_context['knowledge']
        assert '7 ngay' in run.response
    from pao.tool_gateway import guard
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error:
        async with Session() as db:await guard(db,await db.get(Run,rid),actor,'web.search')
    assert error.value.detail=='customer_tools_denied'
    assert (await inbound(client,identity,row,'/goal tự duyệt')).json()['status']=='command'
    async with Session() as db:assert await db.scalar(select(func.count(Run.id)))==1
    with pytest.raises(DBAPIError):
        async with Session.begin() as db:await db.execute(text('DELETE FROM channel_audits'))

async def test_native_telegram_uses_shared_receipts_and_no_fallback_when_gate_off(client,identity,channels_on,peer):
    row,_=await binding(client,identity,channel='telegram',peer_id=peer.id,external_identity='12345:12345')
    row=await control(client,identity,row,'auto')
    from pao.telegram import ingest
    from arq import create_pool
    from arq.connections import RedisSettings
    redis=await create_pool(RedisSettings.from_dsn(settings().redis_url))
    value={'update_id':123,'message':{'from':{'id':12345},'chat':{'id':12345,'type':'private'},'text':'Native channel'}}
    try:
        await ingest(value,redis);await ingest(value,redis)
        settings().channels_enabled=False
        await ingest({**value,'update_id':124},redis)
        async with Session() as db:
            assert await db.scalar(select(func.count(ChannelInbound.id)))==1
            assert await db.scalar(select(func.count(Run.id)))==1
    finally:await redis.aclose()

async def test_permission_revocation_and_stale_claim_never_auto_retry(client,identity,channels_on):
    row,_=await binding(client,identity);row=await control(client,identity,row,'human')
    result=await client.post('/v1/channels/bindings/'+row['id']+'/reply',headers=identity['owner'],json={'request_key':str(uuid4()),'text':'Pending'})
    async with Session.begin() as db:
        (await db.get(Member,(identity['workspace'],identity['user_id']))).role='viewer'
    send=AsyncMock();await service.send_one(send,'local');send.assert_not_awaited()
    async with Session.begin() as db:
        delivery=await db.get(ChannelOutbox,result.json()['id']);assert delivery.status=='cancelled'
        delivery.status='sending';delivery.updated_at=now()-timedelta(minutes=3)
    await service.reconcile_stale()
    async with Session() as db:assert (await db.get(ChannelOutbox,delivery.id)).status=='unknown'

async def test_identity_cannot_change_and_long_telegram_parts_preserve_unicode(client,identity,channels_on,peer):
    row,_=await binding(client,identity,channel='telegram',peer_id=peer.id,external_identity='12345:12345')
    with pytest.raises(DBAPIError):
        async with Session.begin() as db:
            saved=await db.get(ChannelBinding,row['id']);saved.kind='customer'
    body='Chào 😀 '+('Xin chào Việt Nam 😀! '*600)
    async with Session.begin() as db:
        saved=await db.get(ChannelBinding,row['id'])
        await service.queue(db,saved,'unicode-result',body);await service.queue(db,saved,'unicode-result',body)
    async with Session() as db:
        parts=list(await db.scalars(select(ChannelOutbox).order_by(ChannelOutbox.request_key)))
        assert len(parts)>1
        assert ''.join(item.body for item in parts)==body
        assert all(len(item.body.encode('utf-16-le'))//2<=3500 for item in parts)

async def test_retention_purges_bodies_preserves_dedup_and_running_turn(client,identity,channels_on,p2_on,brains_on,monkeypatch):
    # Explicit opt-in only: SaaS defaults now preserve data, including when off.
    monkeypatch.setattr(settings(),'channel_retention_enabled',True)
    bid,_,_,_,_=await source(client,identity)
    async with Session.begin() as db:
        member=await db.scalar(select(Member).where(Member.workspace_id==identity['workspace'],Member.user_id!=identity['user_id']))
        actor=member.user_id;db.add(BrainMember(brain_id=bid,workspace_id=identity['workspace'],user_id=actor,role='editor'))
    row,_=await binding(client,identity,actor_id=actor,kind='customer',brain_id=bid,retention_days=1)
    row=await control(client,identity,row,'auto');monkeypatch.setattr(settings(),'channel_autoreply_enabled',True)
    received=(await inbound(client,identity,row,'Doi tra trong bao nhieu ngay?',key='retained')).json()
    await execute_run({'gateway':AsyncMock()},received['run_id']);await service.collect()
    pending=(await inbound(client,identity,row,'Chưa xong',key='active')).json()
    async with Session.begin() as db:
        for item in await db.scalars(select(ChannelInbound)):item.created_at=now()-timedelta(days=2)
        for item in await db.scalars(select(ChannelOutbox)):item.created_at=now()-timedelta(days=2)
    assert (await service.purge_expired())['purged']==1
    async with Session() as db:
        assert (await db.get(ChannelInbound,received['id'])).body is None
        assert (await db.get(Run,received['run_id'])).response=='[retention purged]'
        assert (await db.get(ChannelInbound,pending['id'])).body=='Chưa xong'
        assert all(item.body is None for item in await db.scalars(select(ChannelOutbox)))
    repeated=(await inbound(client,identity,row,'Doi tra trong bao nhieu ngay?',key='retained')).json()
    assert repeated['run_id']==received['run_id']

async def test_rotated_identity_key_never_falls_back_to_legacy(client,identity,channels_on,peer,monkeypatch):
    await binding(client,identity,channel='telegram',peer_id=peer.id,external_identity='12345:12345')
    monkeypatch.setattr(settings(),'channel_identity_key','k'*40)
    from pao.telegram import ingest
    from pao.main import app
    await ingest({'update_id':456,'message':{'from':{'id':12345},'chat':{'id':12345,'type':'private'},'text':'No legacy fallback'}},app.state.redis)
    async with Session() as db:assert await db.scalar(select(func.count(Run.id)))==0

async def test_provider_rate_limit_classified_without_leaking_token(client,identity,peer,monkeypatch):
    import httpx
    import pao.telegram as telegram
    original=httpx.AsyncClient
    def transport(status,body):
        def factory(**kwargs):return original(transport=httpx.MockTransport(lambda req:httpx.Response(status,json=body)))
        monkeypatch.setattr(telegram.httpx,'AsyncClient',factory)
    transport(429,{'ok':False,'error_code':429})
    with pytest.raises(telegram.TelegramRateLimited,match='telegram_rate_limited'):await telegram.bot_api('sendMessage',{'chat_id':'12345','text':'Fixture'})
    transport(500,{'ok':False,'error_code':500})
    with pytest.raises(RuntimeError,match='^telegram_transport_unavailable$'):await telegram.bot_api('sendMessage',{'chat_id':'12345','text':'Fixture'})

async def test_revoked_native_peer_blocks_inbound_and_queued_run(client,identity,channels_on,peer):
    row,_=await binding(client,identity,channel='telegram',peer_id=peer.id,external_identity='12345:12345')
    row=await control(client,identity,row,'auto')
    from pao.telegram import ingest
    from pao.main import app
    update={'update_id':801,'message':{'from':{'id':12345},'chat':{'id':12345,'type':'private'},'text':'Queued before revocation'}}
    await ingest(update,app.state.redis)
    async with Session.begin() as db:
        run=await db.scalar(select(Run));rid=run.id
        (await db.get(TelegramPeer,peer.id)).enabled=False
    await ingest({**update,'update_id':802},app.state.redis)
    gateway=AsyncMock(side_effect=AssertionError('Revoked peer must not call model'))
    await execute_run({'gateway':gateway},rid)
    async with Session() as db:
        assert await db.scalar(select(func.count(ChannelInbound.id)))==1
        assert await db.scalar(select(func.count(Run.id)))==1
        assert (await db.get(Run,rid)).status=='failed'
    await service.collect()
    async with Session() as db:assert await db.scalar(select(func.count(ChannelOutbox.id)))==0

async def test_cached_customer_result_revoked_source_is_masked_and_not_sent(client,identity,channels_on,p2_on,brains_on,monkeypatch):
    bid,file,_,_,_=await source(client,identity)
    async with Session.begin() as db:
        member=await db.scalar(select(Member).where(Member.workspace_id==identity['workspace'],Member.user_id!=identity['user_id']))
        actor=member.user_id;db.add(BrainMember(brain_id=bid,workspace_id=identity['workspace'],user_id=actor,role='editor'))
    row,_=await binding(client,identity,actor_id=actor,kind='customer',brain_id=bid)
    row=await control(client,identity,row,'auto');monkeypatch.setattr(settings(),'channel_autoreply_enabled',True)
    received=(await inbound(client,identity,row,'Doi tra trong bao nhieu ngay?')).json()
    await execute_run({'gateway':AsyncMock()},received['run_id']);await service.collect()
    base='/v1/channels/bindings/'+row['id']+'/outbox'
    assert '7 ngay' in (await client.get(base,headers=identity['owner'])).json()[0]['text']
    async with Session.begin() as db:(await db.get(BrainFile,file['id'])).trashed_at=now()
    assert (await client.get(base,headers=identity['owner'])).json()[0]['text']=='[Nguồn không còn được phép truy cập]'
    transport=AsyncMock(side_effect=AssertionError('Revoked quote must not be delivered'))
    await service.send_one(transport,'local');transport.assert_not_awaited()
    async with Session() as db:assert (await db.scalar(select(ChannelOutbox))).status=='cancelled'
