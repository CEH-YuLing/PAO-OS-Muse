"""Append-only reapply; no token resolve, provider call or old consent revival."""
import asyncio
from datetime import timedelta
from uuid import uuid4
import pytest
from sqlalchemy import select,text,func
from sqlalchemy.exc import DBAPIError
from pao.gateway import Chunk
from pao.db import Session
from pao.models import (MetaConnection,ModelProviderConnection,ConnectorConnection,
    GoogleAdsConnection,MetaSyncJob,MetaSnapshot,GoogleAdsSyncJob,AdEntity,
    TenantConnectionReference,TenantConnectionGrant,TenantConnectionAudit,now)
from test_connection_inventory import corpus,path,proposal
from test_connection_grants import stage,eligibility

MODELS={'model':ModelProviderConnection,'mcp':ConnectorConnection,'meta_ads':MetaConnection,'google_ads':GoogleAdsConnection}


async def setup(client,c,kind):
    async with Session.begin() as db:
        row=await db.get(MODELS[kind],c['connections']['a'][kind])
        row.status='connected'
        if kind=='meta_ads':row.expires_at=now()+timedelta(hours=1)
    res,_=await stage(client,c,kind);assert res.status_code==201,res.text
    return res.json()


async def rotate(c,kind):
    async with Session.begin() as db:
        row=await db.get(MODELS[kind],c['connections']['a'][kind])
        if kind=='model':row.api_key_ciphertext='different-fixture-not-a-token'
        else:row.version+=1
        if kind in ('meta_ads','google_ads'):
            jobtype=MetaSyncJob if kind=='meta_ads' else GoogleAdsSyncJob
            job=jobtype(connection_id=row.id,connection_version=row.version,api_version='fixture',
                request_key='rediscovery:'+uuid4().hex,kind='accounts',status='completed')
            db.add(job);await db.flush()
            if kind=='meta_ads':db.add(MetaSnapshot(job_id=job.id,kind='accounts',remote_key='act_123',payload={}))
            else:db.add(AdEntity(google_connection_id=row.id,connection_version=row.version,
                platform='google',kind='account',account_id='1234567890',remote_id='1234567890',
                currency='USD',timezone='UTC',google_source_job_id=job.id))


async def reapply_body(client,c,kind,saved):
    body=proposal(c,kind)
    async with Session() as db:
        row=await db.get(MODELS[kind],c['connections']['a'][kind])
        body['expected_version']=None if kind=='model' else row.version
    preview=await client.post(path(c['workspace'])+'/mapping-preview',headers=c['owner'],json=body)
    assert preview.status_code==200,preview.text
    return {**body,'preview_hash':preview.json()['preview_hash'],'request_key':str(uuid4()),
        'ttl_minutes':60,'manager_id':c['user_id'] if kind=='model' else None,'apply_data_only_ack':True,
        'reference_revision':saved['reference']['revision'],'revoke_old_generation_ack':True}


async def apply(client,c,saved,body,headers=None):
    return await client.post(path(c['workspace'])+f"/references/{saved['reference']['id']}/reapply",
        headers=headers or c['owner'],json=body)


@pytest.mark.parametrize('kind',list(MODELS))
async def test_rotation_new_generation_preserves_old_identity_ttl_and_audit(client,corpus,kind,monkeypatch):
    c=corpus;saved=await setup(client,c,kind)
    await rotate(c,kind)
    assert (await eligibility(client,c,saved)).status_code==403
    body=await reapply_body(client,c,kind,saved)
    # Reapply is metadata-only, even for native stores containing fixture secrets.
    def forbidden(*args,**kwargs):raise AssertionError('Reapply must not resolve credential or probe provider')
    monkeypatch.setattr('pao.model_router.decrypt_key',forbidden)
    monkeypatch.setattr('pao.integrations.meta.client.decrypt',forbidden)
    monkeypatch.setattr('pao.integrations.google_ads.client.decrypt',forbidden)
    result=await apply(client,c,saved,body);assert result.status_code==201,result.text
    fresh=result.json();assert fresh['reference']['generation']==2
    assert fresh['reference']['supersedes_id']==saved['reference']['id']
    assert fresh['reference']['source_id']==saved['reference']['source_id']
    assert fresh['grant']['id']!=saved['grant']['id'] and fresh['grant']['execution_enabled'] is False
    assert result.headers['cache-control']=='no-store' and 'source_stamp' not in result.text
    assert (await eligibility(client,c,fresh)).status_code==200
    assert (await eligibility(client,c,saved)).status_code==403
    replay=await apply(client,c,saved,body)
    assert replay.status_code==201 and replay.json()['replayed'] is True
    assert replay.json()['grant']['id']==fresh['grant']['id']
    async with Session() as db:
        old=await db.get(TenantConnectionGrant,saved['grant']['id'])
        assert old.status=='revoked' and old.revision==2 and old.expires_at.isoformat()==saved['grant']['expires_at']
        oldref=await db.get(TenantConnectionReference,saved['reference']['id'])
        assert oldref.generation==1 and oldref.supersedes_id is None and oldref.status=='revoked'
        events=list(await db.scalars(select(TenantConnectionAudit.action).order_by(TenantConnectionAudit.created_at)))
        assert events.count('reference_staged')==2 and events.count('grant_staged')==2
        assert events.count('grant_revoked')==events.count('reference_revoked')==1


@pytest.mark.parametrize('kind',list(MODELS))
async def test_no_implicit_reapply_and_no_change_denied(client,corpus,kind):
    c=corpus;saved=await setup(client,c,kind)
    body=await reapply_body(client,c,kind,saved)
    unchanged=await apply(client,c,saved,body)
    assert unchanged.status_code==409 and unchanged.json()['detail']=='connection_generation_no_change'
    await rotate(c,kind)
    current=await reapply_body(client,c,kind,saved)
    normal={k:v for k,v in current.items() if k not in ('reference_revision','revoke_old_generation_ack')}
    ordinary=await client.post(path(c['workspace'])+'/references',headers=c['owner'],json=normal)
    assert ordinary.status_code==409
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(TenantConnectionReference))==1


@pytest.mark.parametrize('change',['actor','revision','identity','ack','preview','foreign_brand','source_not_ready'])
async def test_denied_reapply_is_atomic(client,corpus,change):
    c=corpus;saved=await setup(client,c,'model');await rotate(c,'model')
    body=await reapply_body(client,c,'model',saved);headers=None
    if change=='actor':headers=c['other']
    if change=='revision':body['reference_revision']=2
    if change=='identity':body['connection_id']=c['connections']['b']['model']
    if change=='ack':body['revoke_old_generation_ack']=False
    if change=='preview':body['preview_hash']='f'*64
    if change=='foreign_brand':body['brand_id']=c['brands']['b']
    if change=='source_not_ready':
        async with Session.begin() as db:(await db.get(ModelProviderConnection,c['connections']['a']['model'])).status='error'
    result=await apply(client,c,saved,body,headers)
    assert result.status_code in (403,404,409,422),result.text
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(TenantConnectionReference))==1
        assert (await db.get(TenantConnectionGrant,saved['grant']['id'])).status=='staged'
        assert (await db.get(TenantConnectionReference,saved['reference']['id'])).revision==1


async def test_concurrent_reapply_and_stale_parent_do_not_revoke_new_generation(client,corpus):
    c=corpus;saved=await setup(client,c,'model');await rotate(c,'model')
    body=await reapply_body(client,c,'model',saved)
    results=await asyncio.gather(*[apply(client,c,saved,body) for _ in range(4)])
    assert all(r.status_code==201 for r in results)
    fresh=results[0].json();assert len({r.json()['grant']['id'] for r in results})==1
    stale=await apply(client,c,saved,{**body,'request_key':str(uuid4())})
    assert stale.status_code==409
    async with Session() as db:
        assert (await db.get(TenantConnectionGrant,fresh['grant']['id'])).status=='staged'
    mismatch=await apply(client,c,saved,{**body,'ttl_minutes':61})
    assert mismatch.status_code==409


async def test_database_generation_identity_and_parent_are_immutable(client,corpus):
    c=corpus;saved=await setup(client,c,'model');await rotate(c,'model')
    fresh=(await apply(client,c,saved,await reapply_body(client,c,'model',saved))).json()
    for sql in ('generation=generation+1','supersedes_id=NULL','source_stamp=repeat(\'0\',64)'):
        with pytest.raises(DBAPIError):
            async with Session.begin() as db:
                await db.execute(text('UPDATE tenant_connection_references SET '+sql+' WHERE id=:id'),{'id':fresh['reference']['id']})


async def test_reapply_a_does_not_touch_b_or_copy_credential(client,corpus):
    c=corpus
    b={**c,'workspace':c['second'],'operator_id':c['outside_id'],'other':c['outsider'],
       'connections':{'a':c['connections']['b']},'brands':{'a':c['brands']['b']}}
    a_saved=await setup(client,c,'model');b_saved=await setup(client,b,'model')
    async with Session() as db:
        before=(await db.get(ModelProviderConnection,c['connections']['b']['model'])).api_key_ciphertext
    await rotate(c,'model')
    changed=await apply(client,c,a_saved,await reapply_body(client,c,'model',a_saved))
    assert changed.status_code==201
    assert (await eligibility(client,b,b_saved,headers=c['outsider'])).status_code==200
    async with Session() as db:
        assert (await db.get(ModelProviderConnection,c['connections']['b']['model'])).api_key_ciphertext==before
        assert (await db.get(TenantConnectionReference,b_saved['reference']['id'])).generation==1
        assert await db.scalar(select(func.count()).select_from(ModelProviderConnection))==2


async def test_model_old_consent_does_not_activate_new_generation(client,corpus):
    c=corpus;saved=await setup(client,c,'model')
    url=path(c['workspace'])+f"/references/{saved['reference']['id']}/grants/{saved['grant']['id']}/activate-model"
    consent={'reference_revision':1,'grant_revision':1,'request_key':str(uuid4()),
        'capability':'model_inference','allow_model_inference_ack':True}
    assert (await client.post(url,headers=c['owner'],json=consent)).status_code==201
    await rotate(c,'model')
    fresh=(await apply(client,c,saved,await reapply_body(client,c,'model',saved))).json()
    from pao.modules.connections.model_authority import pin
    from pao.modules.engines.contract import EngineFailure
    async with Session() as db:
        for grant in (saved['grant']['id'],fresh['grant']['id']):
            with pytest.raises(EngineFailure):await pin(db,c['workspace'],c['operator_id'],c['brands']['a'],grant)
    replay=await client.post(url,headers=c['owner'],json=consent)
    assert replay.status_code==201 and replay.json()['replayed'] is True
    async with Session() as db:
        with pytest.raises(EngineFailure):await pin(db,c['workspace'],c['operator_id'],c['brands']['a'],saved['grant']['id'])
    activated=await client.post(path(c['workspace'])+f"/references/{fresh['reference']['id']}/grants/{fresh['grant']['id']}/activate-model",
        headers=c['owner'],json={**consent,'request_key':str(uuid4())})
    assert activated.status_code==201
    async with Session() as db:
        current=await pin(db,c['workspace'],c['operator_id'],c['brands']['a'],fresh['grant']['id'])
        assert current['reference_id']==fresh['reference']['id']


@pytest.mark.parametrize('route',['models','test'])
@pytest.mark.parametrize('role',['operator','viewer'])
async def test_nonmanager_probe_denied_before_key_or_provider(client,corpus,monkeypatch,route,role):
    from pao.models import Member
    c=corpus
    async with Session.begin() as db:(await db.get(Member,(c['workspace'],c['operator_id']))).role=role
    def forbidden(*args):raise AssertionError('Denied probe accessed credential/provider')
    monkeypatch.setattr('pao.model_api.decrypt_key',forbidden)
    monkeypatch.setattr('pao.model_api.fetch_models',forbidden)
    monkeypatch.setattr('pao.model_api.cloud_gateway',forbidden)
    method=client.get if route=='models' else client.post
    result=await method('/v1/model-providers/openai/'+route,headers=c['other'],params={'workspace_id':c['workspace']})
    assert result.status_code==403


async def test_registered_native_model_test_cannot_bypass_consent(client,corpus,monkeypatch):
    c=corpus;await setup(client,c,'model')
    def forbidden(*args):raise AssertionError('Registered native test accessed credential/provider')
    monkeypatch.setattr('pao.model_api.decrypt_key',forbidden)
    monkeypatch.setattr('pao.model_api.cloud_gateway',forbidden)
    result=await client.post('/v1/model-providers/openai/test',headers=c['owner'],params={'workspace_id':c['workspace']})
    assert result.status_code==403


async def test_legacy_management_probe_owner_and_role_revoke_late(client,corpus,monkeypatch):
    from pao.models import Member
    c=corpus;started,release=asyncio.Event(),asyncio.Event()
    class Fake:
        provider_name='openai';model_name='local-fixture'
        async def stream(self,*args,**kwargs):
            started.set();await release.wait();yield Chunk(text='PAO OK')
    monkeypatch.setattr('pao.model_api.decrypt_key',lambda value:'fixture-token')
    monkeypatch.setattr('pao.model_api.cloud_gateway',lambda *args:Fake())
    task=asyncio.create_task(client.post('/v1/model-providers/openai/test',headers=c['owner'],params={'workspace_id':c['workspace']}))
    try:
        await asyncio.wait_for(started.wait(),5)
        async with Session.begin() as db:(await db.get(Member,(c['workspace'],c['user_id']))).role='viewer'
        release.set();result=await asyncio.wait_for(task,5)
        assert result.status_code==403
        async with Session() as db:
            row=await db.get(ModelProviderConnection,c['connections']['a']['model'])
            assert row.status=='connected' and row.last_checked_at is None
    finally:
        release.set();await asyncio.gather(task,return_exceptions=True)
