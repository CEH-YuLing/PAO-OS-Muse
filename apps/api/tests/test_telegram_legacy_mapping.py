"""S3.1B real HTTP/DB: explicit owner consent, journal and no legacy resend."""
import asyncio,json
from uuid import uuid4
from unittest.mock import AsyncMock
import pytest
from sqlalchemy import select,func,text
from sqlalchemy.exc import DBAPIError
from pao.config import settings
from pao.db import Session,engine
from pao.main import app
from pao.models import (Workspace,Member,User,Brain,ChatSession,Run,TelegramConnection,TelegramPeer,TelegramUpdate,TelegramDelivery,
    ChannelBinding,ChannelInbound,ChannelOutbox,ChannelAudit,TelegramLegacyMapping,TelegramLegacyPeerMap,TelegramLegacyMappingAudit)
from pao.modules.channels import service,telegram_helpers
from pao.telegram import ingest,deliver,bot_api

def base(c):return '/v1/telegram/legacy/'+c['workspace']

@pytest.fixture
async def legacy(identity,monkeypatch):
    monkeypatch.setattr(settings(),'telegram_enabled',False)
    async with Session.begin() as db:
        other=await db.scalar(select(User).where(User.email=='other@example.test'))
        brain=Brain(workspace_id=identity['workspace'],owner_id=other.id,name='PRIVATE BRAIN');db.add(brain);await db.flush()
        session=ChatSession(workspace_id=identity['workspace'],user_id=identity['user_id'],title='Legacy private',memory_enabled=True,brain_id=brain.id)
        db.add(session);await db.flush()
        peer=TelegramPeer(workspace_id=identity['workspace'],user_id=identity['user_id'],telegram_user_id='12345',chat_id='12345',session_id=session.id)
        db.add(peer);await db.flush()
        binding=ChannelBinding(workspace_id=identity['workspace'],actor_id=identity['user_id'],channel='telegram',
            identity_hash=service.identity('telegram','12345:12345'),peer_id=peer.id,brain_id=brain.id,session_id=session.id,
            kind='personal',mode='auto',enabled=True,outbound_confirmed=True)
        db.add(binding);await db.flush()
        run=Run(workspace_id=identity['workspace'],session_id=session.id,request_key=uuid4().hex,prompt='PRIVATE PROMPT',response='PRIVATE RESPONSE',status='completed')
        db.add(run);await db.flush()
        db.add(TelegramUpdate(peer_id=peer.id,update_id=123,run_id=run.id))
        for status in ('unknown','queued'):
            db.add(TelegramDelivery(peer_id=peer.id,dedup_key='private-'+status,payload={'chat_id':'12345','text':'PRIVATE TRANSCRIPT'},status=status))
            db.add(ChannelOutbox(workspace_id=identity['workspace'],binding_id=binding.id,request_key='old-'+status,
                content_hash='a'*64,body='PRIVATE TRANSCRIPT',kind='auto',status=status))
        db.add(ChannelInbound(workspace_id=identity['workspace'],binding_id=binding.id,external_key='a'*64,content_hash='b'*64,body='PRIVATE TRANSCRIPT',status='accepted',run_id=run.id))
    return {**identity,'peer':peer.id,'binding':binding.id,'session':session.id,'run':run.id,'brain':brain.id}

async def proposal(client,c):
    response=await client.get(base(c)+'/preview',headers=c['owner']);assert response.status_code==200,response.text
    data=response.json();assert data['eligible'],data
    return {'request_key':str(uuid4()),'expected_version':0,'preview_hash':data['preview_hash'],'data_only_ack':True,'no_history_replay_ack':True}

async def mapped(client,c):
    body=await proposal(client,c);r=await client.post(base(c)+'/apply',headers=c['owner'],json=body)
    assert r.status_code==201,r.text
    return r.json(),body

async def test_preview_read_only_scoped_no_private_content_and_disabled_generation(client,legacy):
    c=legacy;r=await client.get(base(c)+'/preview',headers=c['owner']);assert r.status_code==200 and r.headers['cache-control']=='no-store'
    data=r.json();assert data['peer_count']==data['binding_count']==1 and data['held_delivery_count']==4
    assert 'PRIVATE' not in r.text and c['brain'] not in r.text and c['session'] not in r.text
    async with Session() as db:assert await db.scalar(select(func.count()).select_from(TelegramConnection))==0
    result,body=await mapped(client,c)
    repeated=await client.post(base(c)+'/apply',headers=c['owner'],json=body);assert repeated.status_code==201 and repeated.json()==result
    assert not result['provider_calls'] and not result['transport_active'] and not result['history_rewritten']
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(TelegramLegacyMapping))==1
        assert await db.scalar(select(func.count()).select_from(TelegramLegacyMappingAudit))==1
        link=await db.scalar(select(TelegramLegacyPeerMap));assert link.source_peer_id==c['peer'] and link.source_binding_id==c['binding']
        target=await db.get(TelegramPeer,link.peer_id);binding=await db.get(ChannelBinding,link.binding_id)
        assert not target.enabled and target.session_id is None and target.connection_id==result['connection_id']
        assert not binding.enabled and not binding.outbound_confirmed and binding.mode=='quiet' and binding.brain_id is binding.session_id is None
        assert await db.scalar(select(func.count()).select_from(Run))==1
        assert await db.scalar(select(func.count()).select_from(TelegramUpdate))==1
        assert await db.scalar(select(func.count()).select_from(TelegramDelivery))==2
        assert (await db.get(TelegramPeer,c['peer'])).session_id==c['session']
        assert (await db.get(ChannelBinding,c['binding'])).brain_id==c['brain']
        assert all(row.payload['text']=='PRIVATE TRANSCRIPT' for row in await db.scalars(select(TelegramDelivery)))

@pytest.mark.parametrize('endpoint,method',[('preview','GET'),('mapping','GET'),('apply','POST'),('revoke','POST')])
@pytest.mark.parametrize('actor',['other','outsider'])
async def test_all_endpoints_require_selected_sme_owner(client,legacy,endpoint,method,actor):
    c=legacy;data=await proposal(client,c) if endpoint=='apply' else {'request_key':str(uuid4()),'mapping_id':str(uuid4()),'version':1,'no_legacy_fallback_ack':True}
    r=await client.request(method,base(c)+'/'+endpoint,headers=c[actor],**({'json':data} if method=='POST' else {}))
    assert r.status_code==(404 if actor=='outsider' else 403) and r.headers['cache-control']=='no-store'
    assert 'PRIVATE' not in r.text

@pytest.mark.parametrize('change',['peer','role','binding','delivery','new_receipt'])
async def test_preview_stale_revalidated_no_partial_mapping(client,legacy,change):
    c=legacy;body=await proposal(client,c)
    async with Session.begin() as db:
        if change=='peer':(await db.get(TelegramPeer,c['peer'])).enabled=False
        elif change=='role':(await db.get(Member,(c['workspace'],c['user_id']))).role='admin'
        elif change=='binding':(await db.get(ChannelBinding,c['binding'])).version+=1
        elif change=='delivery':(await db.scalar(select(TelegramDelivery).where(TelegramDelivery.status=='queued'))).status='cancelled'
        else:db.add(TelegramUpdate(peer_id=c['peer'],update_id=999))
    r=await client.post(base(c)+'/apply',headers=c['owner'],json=body)
    assert r.status_code==(403 if change=='role' else 409)
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(TelegramConnection))==0
        assert await db.scalar(select(func.count()).select_from(TelegramLegacyMapping))==0

@pytest.mark.parametrize('block',['foreign_sme','active_run','inflight','enabled','revoked_actor','foreign_session'])
async def test_ambiguous_or_active_source_blocks_preview_without_foreign_details(client,legacy,monkeypatch,block):
    c=legacy;foreign=str(uuid4())
    if block=='enabled':monkeypatch.setattr(settings(),'telegram_enabled',True)
    async with Session.begin() as db:
        if block=='foreign_sme':
            space=Workspace(id=foreign,name='Do not expose');db.add(space);await db.flush()
            db.add(Member(workspace_id=foreign,user_id=c['user_id'],role='owner'))
            db.add(TelegramPeer(workspace_id=foreign,user_id=c['user_id'],telegram_user_id='777',chat_id='777'))
        elif block=='active_run':(await db.get(Run,c['run'])).status='running'
        elif block=='inflight':(await db.scalar(select(TelegramDelivery).limit(1))).status='sending'
        elif block=='revoked_actor':(await db.get(User,c['user_id'])).active=False
        elif block=='foreign_session':
            other=await db.scalar(select(User).where(User.email=='other@example.test'))
            chat=ChatSession(workspace_id=c['workspace'],user_id=other.id,title='Private');db.add(chat);await db.flush()
            (await db.get(TelegramPeer,c['peer'])).session_id=chat.id
    r=await client.get(base(c)+'/preview',headers=c['owner'])
    if block=='revoked_actor':assert r.status_code==401;return
    assert r.status_code==200 and not r.json()['eligible'] and r.json()['peers']==[] and foreign not in r.text

async def test_no_peer_case_is_not_fake_mapping(client,identity):
    r=await client.get(base(identity)+'/preview',headers=identity['owner'])
    assert r.status_code==200 and r.json()['reason']=='no_legacy_peers' and not r.json()['eligible']

async def test_apply_revoke_replay_never_restores_legacy_transport(client,legacy,monkeypatch):
    c=legacy;result,_=await mapped(client,c)
    body={'request_key':str(uuid4()),'mapping_id':result['mapping_id'],'version':1,'no_legacy_fallback_ack':True}
    r=await client.post(base(c)+'/revoke',headers=c['owner'],json=body);assert r.status_code==200 and r.json()['version']==2 and r.json()['status']=='revoked'
    assert (await client.post(base(c)+'/revoke',headers=c['owner'],json=body)).json()==r.json()
    stale=await client.post(base(c)+'/revoke',headers=c['owner'],json={**body,'request_key':str(uuid4())});assert stale.status_code==409
    monkeypatch.setattr(settings(),'telegram_enabled',True);monkeypatch.setattr(settings(),'telegram_bot_token','fixture-NO-PROVIDER')
    monkeypatch.setattr(settings(),'channels_enabled',True)
    send=AsyncMock(side_effect=AssertionError('No legacy resend'));await ingest({'update_id':999,'message':{'from':{'id':12345},'chat':{'id':12345,'type':'private'},'text':'No old authority'}},app.state.redis)
    from pao.telegram import collect
    await collect();assert (await service.collect())['processed']==0
    await deliver(send);await service.send_one(send);send.assert_not_awaited()
    with pytest.raises(RuntimeError,match='telegram_legacy_mapped'):await bot_api('getMe',{})
    async with Session() as db:
        assert await telegram_helpers.legacy_blocked(db)
        assert not await telegram_helpers.permitted(db,await db.get(TelegramPeer,c['peer']))
        assert await db.scalar(select(func.count()).select_from(TelegramUpdate))==1
        assert (await db.scalar(select(ChannelInbound))).status=='accepted'
        assert all(row.status in ('unknown','queued') for row in await db.scalars(select(TelegramDelivery)))
        assert all(row.status in ('unknown','queued') and row.attempts==0 for row in await db.scalars(select(ChannelOutbox)))

@pytest.mark.parametrize('table',['telegram_legacy_mappings','telegram_legacy_peer_maps','telegram_legacy_mapping_audits'])
async def test_journal_append_only_and_populated_downgrade_refused(client,legacy,table):
    await mapped(client,legacy)
    with pytest.raises(DBAPIError):
        async with Session.begin() as db:await db.execute(text('DELETE FROM '+table))
    from importlib import import_module
    from alembic.operations import Operations
    from alembic.migration import MigrationContext
    async with engine.connect() as db:
        revision_before=await db.scalar(text('SELECT version_num FROM alembic_version'))
        try:
            def run(connection):
                with Operations.context(MigrationContext.configure(connection)):import_module('migrations.versions.0060_telegram_legacy_mapping').downgrade()
            with pytest.raises(RuntimeError,match='legacy mapping history'):await db.run_sync(run)
        finally:await db.rollback()
        # Refusing the historical0060 downgrade must preserve the CURRENT head,
        # including later additive migrations; do not pin the test DB to0060.
        assert await db.scalar(text('SELECT version_num FROM alembic_version'))==revision_before

async def test_new_legacy_writes_database_barrier_local_channels_still_work(client,legacy):
    c=legacy;await mapped(client,c)
    with pytest.raises(DBAPIError):
        async with Session.begin() as db:db.add(TelegramUpdate(peer_id=c['peer'],update_id=777));await db.flush()
    async with Session.begin() as db:
        binding=ChannelBinding(workspace_id=c['workspace'],actor_id=c['user_id'],channel='local',identity_hash='d'*64,kind='personal')
        db.add(binding);await db.flush();await service.queue(db,binding,'local-safe','Local still works')

async def test_malformed_secret_and_oversized_body_never_reflected(client,legacy):
    body=await proposal(client,legacy);body['token']='PRIVATE SECRET'
    r=await client.post(base(legacy)+'/apply',headers=legacy['owner'],json=body)
    assert r.status_code==422 and 'PRIVATE SECRET' not in r.text and r.headers['cache-control']=='no-store'
    r=await client.post(base(legacy)+'/apply',headers={**legacy['owner'],'Content-Type':'application/json'},content=json.dumps({'token':'X'*9000}))
    assert r.status_code==413 and r.headers['cache-control']=='no-store'

async def test_advisory_lease_and_parallel_consent_do_not_duplicate_mapping(client,legacy):
    c=legacy;body=await proposal(client,c)
    async with engine.connect() as db:
        await db.execute(text('SELECT pg_advisory_lock(600005)'))
        try:
            r=await client.post(base(c)+'/apply',headers=c['owner'],json=body);assert r.status_code==409 and r.json()['detail']=='telegram_bridge_busy'
        finally:await db.execute(text('SELECT pg_advisory_unlock(600005)'))
    results=await asyncio.gather(*(client.post(base(c)+'/apply',headers=c['owner'],json=body) for _ in range(2)))
    assert any(r.status_code==201 for r in results) and all(r.status_code in (201,409) for r in results)
    r=await client.post(base(c)+'/apply',headers=c['owner'],json=body);assert r.status_code==201
    changed=await client.post(base(c)+'/apply',headers=c['owner'],json={**body,'preview_hash':'f'*64});assert changed.status_code==409
    async with Session() as db:assert await db.scalar(select(func.count()).select_from(TelegramLegacyMapping))==1
