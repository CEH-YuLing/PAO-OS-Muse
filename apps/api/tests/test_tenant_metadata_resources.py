"""Real PostgreSQL metadata admissions; fixture providers, no live credentials."""
import asyncio
from uuid import uuid4
import httpx
import pytest
from sqlalchemy import select,text,func,update,delete
from sqlalchemy.exc import DBAPIError
from pao.db import Session
from pao.models import (Workspace,Member,User,Brain,BrainMember,ConnectorConnection,ConnectorSecret,
    ConnectorEvent,ModelProviderConnection,TenantMetadataLease,TenantModelLease,LlmAttempt,now)
from pao.config import settings
from pao.modules.connections import metadata_resources as resources
from pao.modules.connectors import service
from test_model_metadata import configured,KEY
from test_connectors import connectors,connected


def route(wid):return f'/v1/workspaces/{wid}/resources/metadata'


async def configure(client,identity,daily=20,slots=2,version=0,wid=None):
    return await client.put(route(wid or identity['workspace']),headers=identity['owner'],json={
        'expected_version':version,'daily_metadata_requests':daily,'concurrent_metadata':slots})


async def book(identity,*,wid=None,key=None,kind='model_catalogue'):
    scope=wid or identity['workspace']
    async with Session.begin() as db:
        await resources.lock(db,scope)
        row=await resources.admit(db,scope,identity['user_id'],kind,key,'fixture-target')
        return row.id


async def usage(identity):
    async with Session() as db:return await resources.usage(db,identity['workspace'])


async def test_metadata_defaults_acl_no_credentials_billing_or_policy(client,identity):
    result=await client.get(route(identity['workspace']),headers=identity['owner'])
    assert result.status_code==200 and result.headers['cache-control']=='no-store'
    data=result.json();assert data['metadata_policy']=={'version':0,**resources.DEFAULTS}
    assert data['usage']=={'daily_requests':0,'active_requests':0,'expired_unknown_requests':0,'provider_remaining_quota':None,'billing_amount':None}
    assert data['grants_authorized'] is False
    async with Session() as db:
        assert await db.scalar(text('SELECT count(*) FROM tenant_metadata_policies'))==0
    assert (await client.get(route(identity['workspace']),headers=identity['other'])).status_code==403
    assert (await client.get(route(str(uuid4())),headers=identity['owner'])).status_code==404


async def test_metadata_policy_cas_bounds_redaction_and_no_cross_sme_change(client,identity):
    first=await configure(client,identity,daily=3,slots=1)
    assert first.status_code==200 and first.json()['metadata_policy']['version']==1
    assert (await configure(client,identity)).status_code==409
    assert (await configure(client,identity,version=1,daily=1001)).status_code==422
    bad=await client.put(route(identity['workspace']),headers=identity['owner'],json={'secret':KEY})
    assert bad.status_code==422 and KEY not in bad.text
    async with Session.begin() as db:
        b=Workspace(name='SME B');db.add(b);await db.flush();wid=b.id
        db.add(Member(workspace_id=wid,user_id=identity['user_id'],role='owner'))
    other=await client.get(route(wid),headers=identity['owner'])
    assert other.json()['metadata_policy']['version']==0 and other.json()['usage']['daily_requests']==0


async def test_atomic_sme_daily_admission_across_kinds(client,identity):
    assert (await configure(client,identity,daily=3,slots=8)).status_code==200
    async def attempt(kind):
        try:return await book(identity,kind=kind)
        except Exception as exc:
            assert getattr(exc,'status_code',None)==429 and exc.detail=='tenant_metadata_daily_exhausted'
    results=await asyncio.gather(*(attempt(kind) for kind in ['model_connect','model_catalogue','model_select','mcp_discovery']*2))
    assert sum(x is not None for x in results)==3
    assert (await usage(identity))['daily_requests']==3


async def test_pool_capacity_releases_but_daily_and_replay_identity_remain(client,identity):
    assert (await configure(client,identity,daily=3,slots=1)).status_code==200
    key=uuid4();lid=await book(identity,key=key)
    from fastapi import HTTPException
    with pytest.raises(HTTPException,match='tenant_metadata_concurrency_exhausted'):await book(identity)
    await resources.finish(identity['workspace'],lid);await resources.finish(identity['workspace'],lid)
    with pytest.raises(HTTPException,match='tenant_metadata_replay_denied'):await book(identity,key=key,kind='mcp_discovery')
    await book(identity)
    assert (await usage(identity))['daily_requests']==2
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(TenantModelLease))==0
        assert await db.scalar(select(func.count()).select_from(LlmAttempt))==0


@pytest.mark.parametrize('sql',[
    "DELETE FROM tenant_metadata_leases WHERE id=:id",
    "UPDATE tenant_metadata_leases SET request_key=gen_random_uuid() WHERE id=:id",
    "UPDATE tenant_metadata_leases SET created_at=created_at-interval '1 day',expires_at=expires_at-interval '1 day' WHERE id=:id",
    "UPDATE tenant_metadata_leases SET expires_at=expires_at+interval '1 second' WHERE id=:id",
    "UPDATE tenant_metadata_leases SET status='expired',released_at=now() WHERE id=:id",
    "UPDATE tenant_metadata_leases SET target_hash=repeat('0',64) WHERE id=:id",
])
async def test_sql_history_immutable_and_no_early_expiry(client,identity,sql):
    lid=await book(identity)
    with pytest.raises(DBAPIError):
        async with Session.begin() as db:await db.execute(text(sql),{'id':lid})
    assert (await usage(identity))['daily_requests']==1


async def test_sql_direct_insert_cannot_bypass_cap_or_server_stamp(client,identity):
    assert (await configure(client,identity,daily=1,slots=1)).status_code==200
    lid=await book(identity)
    with pytest.raises(DBAPIError):
        async with Session.begin() as db:
            await db.execute(text("""INSERT INTO tenant_metadata_leases
              (id,created_at,workspace_id,actor_id,kind,request_key,target_hash,policy_version,status,expires_at)
              VALUES (gen_random_uuid(),now()-interval '1 day',:wid,:actor,'model_connect',gen_random_uuid(),repeat('0',64),0,'active',now())"""),
                {'wid':identity['workspace'],'actor':identity['user_id']})
    await resources.finish(identity['workspace'],lid)
    with pytest.raises(DBAPIError):
        async with Session.begin() as db:await db.execute(text("UPDATE tenant_metadata_leases SET status='active',released_at=NULL WHERE id=:id"),{'id':lid})
    # Durable history deliberately prevents deleting the enterprise parent.
    with pytest.raises(DBAPIError):
        async with Session.begin() as db:
            await db.execute(delete(Member).where(Member.workspace_id==identity['workspace']))
            await db.execute(delete(Workspace).where(Workspace.id==identity['workspace']))


async def test_server_owned_utc_stamp_expiry_and_policy_version(client,identity):
    before=now()
    async with Session.begin() as db:
        row=(await db.execute(text("""INSERT INTO tenant_metadata_leases
          (id,created_at,workspace_id,actor_id,kind,request_key,target_hash,policy_version,status,expires_at)
          VALUES (gen_random_uuid(),now()-interval '1 day',:wid,:actor,'model_catalogue',gen_random_uuid(),repeat('0',64),999,'active',now())
          RETURNING created_at,expires_at,policy_version"""),{'wid':identity['workspace'],'actor':identity['user_id']})).one()
    assert row.created_at>=before and (row.expires_at-row.created_at).total_seconds()==90 and row.policy_version==0
    assert (await usage(identity))['daily_requests']==1


@pytest.mark.parametrize('operation',['connect','models','model'])
async def test_model_quota_denies_before_encrypt_decrypt_or_provider(client,identity,monkeypatch,operation):
    await configured(identity,monkeypatch);assert (await configure(client,identity,daily=1)).status_code==200
    lid=await book(identity);await resources.finish(identity['workspace'],lid)
    def forbidden(*args,**kwargs):raise AssertionError('quota must precede credentials/provider')
    for name in ('decrypt_key','encrypt_key','fetch_models'):monkeypatch.setattr('pao.model_api.'+name,forbidden)
    path='/v1/model-providers/openai/'+operation
    if operation=='connect':result=await client.post(path,headers=identity['owner'],json={'workspace_id':identity['workspace'],'api_key':KEY})
    elif operation=='model':result=await client.put(path,headers=identity['owner'],json={'workspace_id':identity['workspace'],'model':'fixture-old'})
    else:result=await client.get(path,headers=identity['owner'],params={'workspace_id':identity['workspace']})
    assert result.status_code==429 and result.json()['detail']=='tenant_metadata_daily_exhausted'


async def test_native_header_replay_error_consumes_daily_without_resend(client,identity,monkeypatch):
    await configured(identity,monkeypatch);calls=[]
    async def fail(provider,key):calls.append(provider);raise TimeoutError()
    monkeypatch.setattr('pao.model_api.fetch_models',fail)
    headers={**identity['owner'],'Idempotency-Key':str(uuid4())}
    first=await client.get('/v1/model-providers/openai/models',headers=headers,params={'workspace_id':identity['workspace']})
    assert first.status_code==503
    second=await client.get('/v1/model-providers/openai/models',headers=headers,params={'workspace_id':identity['workspace']})
    assert second.status_code==409 and second.json()['detail']=='tenant_metadata_replay_denied' and calls==['openai']
    used=await usage(identity);assert used['daily_requests']==1 and used['active_requests']==0


async def test_mcp_model_shared_pool_and_quota_before_token(client,identity,connectors,monkeypatch):
    row=await connected(client,identity);await configured(identity,monkeypatch)
    assert (await configure(client,identity,daily=1,slots=1)).status_code==200
    def forbidden(*args,**kwargs):raise AssertionError('no credentials/provider after cap')
    monkeypatch.setattr(service,'token',forbidden)
    probe=await client.post(f"/v1/connectors/connections/{row['id']}/test",headers=identity['owner'],json={'version':row['version']})
    assert probe.status_code==429
    monkeypatch.setattr('pao.model_api.decrypt_key',forbidden)
    models=await client.get('/v1/model-providers/openai/models',headers=identity['owner'],params={'workspace_id':identity['workspace']})
    assert models.status_code==429 and len(connectors.requests)==3


@pytest.mark.parametrize('change',['rotate','disconnect','demote','deactivate','archive_brain','remove_brain_grant'])
@pytest.mark.parametrize('failed',[False,True])
async def test_mcp_late_mutation_denies_publish_and_preserves_native_state(client,identity,connectors,monkeypatch,change,failed):
    row=await connected(client,identity);cid=row['id']
    if change in ('archive_brain','remove_brain_grant'):
        monkeypatch.setattr(settings(),'brain_manager_enabled',True)
        async with Session.begin() as db:
            owner=identity['user_id'] if change=='archive_brain' else await db.scalar(select(Member.user_id).where(
                Member.workspace_id==identity['workspace'],Member.user_id!=identity['user_id']))
            brain=Brain(workspace_id=identity['workspace'],owner_id=owner,name='Private');db.add(brain);await db.flush();bid=brain.id
            if change=='remove_brain_grant':db.add(BrainMember(brain_id=bid,workspace_id=identity['workspace'],user_id=identity['user_id'],role='reader'))
            await db.execute(update(ConnectorConnection).where(ConnectorConnection.id==cid).values(brain_id=bid))
    async def exchange():
        async with asyncio.timeout(3),Session.begin() as db:
            if change=='rotate':
                await db.execute(update(ConnectorSecret).where(ConnectorSecret.connection_id==cid).values(ciphertext=service.seal('fixture-rotated-secret')))
                await db.execute(update(ConnectorConnection).where(ConnectorConnection.id==cid).values(version=row['version']+1,status='draft'))
            elif change=='disconnect':await db.execute(update(ConnectorConnection).where(ConnectorConnection.id==cid).values(version=row['version']+1,status='revoked'))
            elif change=='demote':await db.execute(update(Member).where(Member.workspace_id==identity['workspace'],Member.user_id==identity['user_id']).values(role='operator'))
            elif change=='deactivate':await db.execute(update(User).where(User.id==identity['user_id']).values(active=False))
            elif change=='archive_brain':await db.execute(update(Brain).where(Brain.id==bid).values(archived_at=now()))
            else:await db.execute(delete(BrainMember).where(BrainMember.brain_id==bid,BrainMember.user_id==identity['user_id']))
        if failed:raise service.ConnectorFailure('connector_timeout')
        return {'protocol':'2025-11-25','tools':{},'capability_hash':'fixture'}
    class Fake:pass
    Fake.exchange=staticmethod(exchange)
    monkeypatch.setattr(service,'Client',lambda *args:Fake())
    result=await client.post(f'/v1/connectors/connections/{cid}/test',headers=identity['owner'],json={'version':row['version']})
    assert result.status_code in (403,404,409),result.text
    async with Session() as db:
        source=await db.get(ConnectorConnection,cid)
        assert source.failures==0 and source.manifest_hash==row['manifest_hash']
        assert await db.scalar(select(func.count()).select_from(ConnectorEvent).where(ConnectorEvent.action=='discovery_failed'))==0
    assert (await usage(identity))['active_requests']==0 and (await usage(identity))['daily_requests']==2


async def test_mcp_private_brain_not_bypassed_by_enterprise_owner(client,identity,connectors,monkeypatch):
    monkeypatch.setattr(settings(),'brain_manager_enabled',True)
    row=await connected(client,identity);count=len(connectors.requests)
    async with Session.begin() as db:
        other=await db.scalar(select(Member.user_id).where(Member.workspace_id==identity['workspace'],Member.user_id!=identity['user_id']))
        brain=Brain(workspace_id=identity['workspace'],owner_id=other,name='Other private');db.add(brain);await db.flush()
        await db.execute(update(ConnectorConnection).where(ConnectorConnection.id==row['id']).values(brain_id=brain.id))
    probe=await client.post(f"/v1/connectors/connections/{row['id']}/test",headers=identity['owner'],json={'version':row['version']})
    assert probe.status_code==404 and len(connectors.requests)==count


async def test_metadata_lease_expiry_is_unknown_not_replay_or_refund(client,identity,monkeypatch):
    # PostgreSQL is the admission/recovery clock. Advance it only inside a test
    # database function via a temporary fixture clock, retaining all guards.
    lid=await book(identity);key=None
    async with Session() as db:
        row=await db.get(TenantMetadataLease,lid);key=row.request_key
        function=await db.scalar(text("SELECT pg_get_functiondef(oid) FROM pg_proc WHERE proname='pao_metadata_resource_guard'"))
    shifted=function.replace('clock_timestamp()',"(clock_timestamp()+interval '100 seconds')")
    try:
        async with Session.begin() as db:await db.execute(text(shifted))
        await book(identity)
        async with Session() as db:assert (await db.get(TenantMetadataLease,lid)).status=='expired'
        from fastapi import HTTPException
        with pytest.raises(HTTPException,match='tenant_metadata_replay_denied'):await book(identity,key=key)
        with pytest.raises(HTTPException,match='tenant_metadata_lease_expired'):await resources.require_current(identity['workspace'],lid)
        assert (await usage(identity))['daily_requests']==2
    finally:
        async with Session.begin() as db:await db.execute(text(function))


async def test_real_mcp_busy_a_does_not_block_b_model_and_cancel_releases_slot(client,identity,connectors,monkeypatch):
    from pao.model_router import encrypt_key
    row=await connected(client,identity)
    assert (await configure(client,identity,daily=10,slots=1)).status_code==200
    async with Session.begin() as db:
        other=Workspace(name='SME B independent');db.add(other);await db.flush();wid=other.id
        db.add(Member(workspace_id=wid,user_id=identity['user_id'],role='owner'))
        db.add(ModelProviderConnection(workspace_id=wid,provider='openai',model='fixture-b',api_key_ciphertext=encrypt_key('fixture-b-secret')))
    entered=asyncio.Event();release=asyncio.Event();tokens=[]
    class Slow:
        async def exchange(self):entered.set();await release.wait();return {'tools':{},'protocol':'2025-11-25'}
    monkeypatch.setattr(service,'Client',lambda url,token=None:tokens.append(token) or Slow())
    async def catalogue(provider,key):assert key=='fixture-b-secret';return ['fixture-b']
    monkeypatch.setattr('pao.model_api.fetch_models',catalogue)
    task=asyncio.create_task(client.post(f"/v1/connectors/connections/{row['id']}/test",headers=identity['owner'],json={'version':row['version']}))
    try:
        async with asyncio.timeout(5):
            await entered.wait()
            denied=await client.post(f"/v1/connectors/connections/{row['id']}/test",headers=identity['owner'],json={'version':row['version']})
            assert denied.status_code==429 and denied.json()['detail']=='tenant_metadata_concurrency_exhausted'
            result=await client.get('/v1/model-providers/openai/models',headers=identity['owner'],params={'workspace_id':wid})
            assert result.status_code==200 and result.json()['models']==['fixture-b'] and not task.done()
        assert len(tokens)==1
    finally:
        task.cancel();await asyncio.gather(task,return_exceptions=True)
    assert (await usage(identity))['active_requests']==0 and (await usage(identity))['daily_requests']==2


async def test_mcp_adapter_deadline_bounded_and_failure_preserves_daily(client,identity,connectors,monkeypatch):
    row=await connected(client,identity)
    class Slow:
        async def exchange(self):await asyncio.sleep(2)
    monkeypatch.setattr(service,'Client',lambda *args:Slow())
    monkeypatch.setattr(service,'PROBE_TIMEOUT',.05)
    result=await client.post(f"/v1/connectors/connections/{row['id']}/test",headers=identity['owner'],json={'version':row['version']})
    assert result.status_code==502 and result.json()['detail']=='connector_timeout'
    used=await usage(identity);assert used['daily_requests']==2 and used['active_requests']==0


async def test_source_scope_drift_cannot_bill_a_or_decrypt_b(client,identity,connectors,monkeypatch):
    from types import SimpleNamespace
    row=await connected(client,identity);native=service.probe_source;calls=len(connectors.requests)
    async def drift(db,cid,who):
        actual,pin=await native(db,cid,who)
        return SimpleNamespace(workspace_id=str(uuid4())),pin
    def forbidden(*args):raise AssertionError('no foreign credential resolution')
    monkeypatch.setattr(service,'probe_source',drift);monkeypatch.setattr(service,'token',forbidden)
    result=await client.post(f"/v1/connectors/connections/{row['id']}/test",headers=identity['owner'],json={'version':row['version']})
    assert result.status_code==403 and result.json()['detail']=='connector_probe_scope_changed'
    assert len(connectors.requests)==calls and (await usage(identity))['daily_requests']==1


async def test_delayed_lease_does_not_start_catalogue_and_releases_admission(client,identity,monkeypatch):
    from fastapi import HTTPException
    await configured(identity,monkeypatch)
    async def expired(*args):raise HTTPException(409,'tenant_metadata_lease_expired')
    def forbidden(*args):raise AssertionError('no I/O after expired admission')
    monkeypatch.setattr(resources,'require_current',expired)
    monkeypatch.setattr('pao.model_api.fetch_models',forbidden)
    result=await client.get('/v1/model-providers/openai/models',headers=identity['owner'],params={'workspace_id':identity['workspace']})
    assert result.status_code==409 and result.json()['detail']=='tenant_metadata_lease_expired'
    used=await usage(identity);assert used['daily_requests']==1 and used['active_requests']==0
