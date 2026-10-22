"""Model authority: fixture providers only, real HTTP admission and worker."""
import asyncio
import signal
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from pao.db import Session
from pao.config import settings
from pao.models import Brain, BrainMember, ModelGrantActivation, ModelProviderConnection, Member, User, TenantConnectionGrant, now
from pao.modules.connections.model_authority import DENIED
from pao.modules.engines.contract import EngineFailure
from pao.modules.engines.service import digest, gateway_for_run
from pao.runtime import execute_run
from test_model_connection_fence import fenced, saved_run
from test_connection_inventory import corpus, path, proposal
from test_engine_contract import engines


async def stage(client, c, kind='model', change=None):
    base = {**proposal(c,kind), **(change or {})}
    preview = await client.post(path(c['workspace'])+'/mapping-preview',headers=c['owner'],json=base)
    assert preview.status_code==200,preview.text
    body={**base,'preview_hash':preview.json()['preview_hash'],'request_key':str(uuid4()),
          'ttl_minutes':60,'manager_id':c['user_id'] if kind=='model' else None,'apply_data_only_ack':True}
    return await client.post(path(c['workspace'])+'/references',headers=c['owner'],json=body),body


async def consent(client, c, *, change=None, headers=None, kind='model', stage_change=None):
    result, _ = await stage(client,c,kind,stage_change or {'brand_id':None})
    assert result.status_code == 201, result.text
    saved = result.json()
    route = path(c['workspace'])+f"/references/{saved['reference']['id']}/grants/{saved['grant']['id']}/activate-model"
    body = {'reference_revision':1,'grant_revision':1,'request_key':str(uuid4()),
            'capability':'model_inference','allow_model_inference_ack':True, **(change or {})}
    return await client.post(route,headers=headers or c['owner'],json=body), saved, route, body


async def selected(client,c,saved, *, headers=None, wid=None, brand=None):
    headers = headers or c['other']
    result = await client.post('/v1/sessions',headers=headers,json={
        'workspace_id':wid or c['workspace'],'brand_id':brand,'memory_enabled':False})
    assert result.status_code == 201,result.text
    sid = result.json()['id']
    profile=await client.put(f'/v1/sessions/{sid}/chat',headers=headers,json={'version':1,'policy':{'privacy':'cloud_allowed'}})
    assert profile.status_code==200,profile.text
    choice = await client.put(f'/v1/sessions/{sid}/engine',headers=headers,json={
        'provider':'openai','model':'local-fixture','version':1,'grant_id':saved['grant']['id']})
    return sid, choice


async def admit(client,c,sid):
    result = await client.post('/v1/runs',headers=c['other'],json={
        'session_id':sid,'message':'explicit model grant fixture','request_key':uuid4().hex})
    assert result.status_code == 202,result.text
    return result.json()['id']


async def revoke(client,c,saved):
    response = await client.post(path(c['workspace'])+f"/references/{saved['reference']['id']}/grants/{saved['grant']['id']}/revoke",
        headers=c['owner'],json={'reference_revision':1,'grant_revision':1})
    assert response.status_code == 200,response.text


async def test_explicit_consent_selection_and_worker_no_secret_egress(client,fenced):
    c,calls,_ = fenced
    response,saved,route,body = await consent(client,c)
    assert response.status_code == 201,response.text
    assert response.headers['cache-control']=='no-store' and response.json()['tools_enabled'] is False
    assert 'source_stamp' not in response.text and 'fingerprint' not in response.text
    replay = await client.post(route,headers=c['owner'],json=body)
    assert replay.json()['id']==response.json()['id'] and replay.json()['replayed'] is True
    sid,choice = await selected(client,c,saved)
    assert choice.status_code == 200,choice.text
    assert 'connection_authority' not in choice.text
    rid = await admit(client,c,sid)
    before,_ = await saved_run(rid)
    pin = before.engine_snapshot['connection_authority']
    assert pin['mode']=='model_grant' and pin['actor_id']==c['operator_id'] and pin['grant_id']==saved['grant']['id']
    await execute_run({},rid)
    row,events = await saved_run(rid)
    assert row.status=='completed' and row.engine_snapshot==before.engine_snapshot
    assert calls['stream']==1 and any(e.type=='response.completed' for e in events)


@pytest.mark.parametrize('reason',['grantee','other_tenant','cas','ack','extra','capability','mcp'])
async def test_consent_denied_without_side_effects(client,fenced,reason):
    c,calls,_ = fenced
    kwargs = {'headers':c['other']} if reason=='grantee' else {}
    changes = {'cas':{'grant_revision':2},'ack':{'allow_model_inference_ack':False},
               'extra':{'secret':'never-echo-fixture'},'capability':{'capability':'tool_write'}}
    if reason in changes:kwargs['change']=changes[reason]
    if reason=='mcp':kwargs['kind']='mcp'
    response,saved,route,body = await consent(client,c,**kwargs)
    if reason=='other_tenant':
        assert response.status_code==201
        other = route.replace(c['workspace'],c['second'])
        response = await client.post(other,headers=c['owner'],json=body)
    assert response.status_code in (403,404,409,422),response.text
    assert 'never-echo-fixture' not in response.text
    async with Session() as db:
        rows=list(await db.scalars(select(ModelGrantActivation)))
        assert len(rows)==(1 if reason=='other_tenant' else 0)
    assert calls['factory']==0


async def test_concurrent_consent_replay_collision_and_revoked_never_revived(client,fenced):
    c,calls,_=fenced
    # First exercise a previously unused activation request concurrently.
    response,_=await stage(client,c,change={'brand_id':None})
    saved=response.json()
    route=path(c['workspace'])+f"/references/{saved['reference']['id']}/grants/{saved['grant']['id']}/activate-model"
    body={'reference_revision':1,'grant_revision':1,'request_key':str(uuid4()),'capability':'model_inference','allow_model_inference_ack':True}
    results=await asyncio.gather(*[client.post(route,headers=c['owner'],json=body) for _ in range(3)])
    assert all(r.status_code==201 for r in results)
    assert len({r.json()['id'] for r in results})==1
    collision=await client.post(route,headers=c['owner'],json={**body,'grant_revision':2})
    assert collision.status_code==409
    await revoke(client,c,saved)
    replay=await client.post(route,headers=c['owner'],json=body)
    assert replay.status_code==201 and replay.json()['replayed'] is True
    _,selection=await selected(client,c,saved)
    assert selection.status_code==409 and selection.json()['detail']==DENIED
    assert calls['factory']==0


@pytest.mark.parametrize('change',['revoke','manager_role','manager_inactive','grantee_role','grantee_removed','rotate','model','delete','status'])
async def test_queued_run_rechecks_before_credential_resolve(client,fenced,monkeypatch,change):
    c,calls,_=fenced
    response,saved,_,_=await consent(client,c)
    assert response.status_code==201
    sid,selection=await selected(client,c,saved)
    assert selection.status_code==200,selection.text
    rid=await admit(client,c,sid)
    before,_=await saved_run(rid)
    if change=='revoke':await revoke(client,c,saved)
    else:
        async with Session.begin() as db:
            source=await db.get(ModelProviderConnection,c['connections']['a']['model'])
            if change=='rotate':source.api_key_ciphertext='rotated-cipher-fixture'
            if change=='model':source.model='changed-model'
            if change=='delete':await db.delete(source)
            if change=='status':source.status='error'
            if change=='manager_role':(await db.get(Member,(c['workspace'],c['user_id']))).role='operator'
            if change=='manager_inactive':(await db.get(User,c['user_id'])).active=False
            if change=='grantee_role':(await db.get(Member,(c['workspace'],c['operator_id']))).role='viewer'
            if change=='grantee_removed':await db.delete(await db.get(Member,(c['workspace'],c['operator_id'])))
    def forbidden(*args):raise AssertionError('No decrypt for denied grant')
    monkeypatch.setattr('pao.modules.engines.service.decrypt_key',forbidden)
    await execute_run({},rid)
    row,events=await saved_run(rid)
    assert row.status=='failed' and row.response=='' and row.engine_snapshot==before.engine_snapshot
    assert not any(e.type=='response.completed' for e in events) and calls['factory']==0


async def test_late_result_after_revoke_discarded(client,fenced,monkeypatch):
    c,calls,fake=fenced
    _,saved,_,_=await consent(client,c)
    sid,choice=await selected(client,c,saved); assert choice.status_code==200
    rid=await admit(client,c,sid)
    original=fake.stream
    async def late(*args,**kwargs):
        await revoke(client,c,saved)
        async for chunk in original(*args,**kwargs):yield chunk
    monkeypatch.setattr(fake,'stream',late)
    await execute_run({},rid)
    row,events=await saved_run(rid)
    assert row.status=='failed' and row.response=='' and calls['closed']==1
    assert not any(e.type in ('response.delta','response.completed') for e in events)


async def test_scope_pins_tamper_and_two_tenant_brand_denied(client,fenced):
    c,calls,_=fenced
    _,saved,_,_=await consent(client,c,stage_change={'brand_id':c['brands']['a']})
    _,choice=await selected(client,c,saved); assert choice.status_code==409
    _,choice=await selected(client,c,saved,headers=c['owner']); assert choice.status_code==409
    _,choice=await selected(client,c,saved,headers=c['owner'],wid=c['second']); assert choice.status_code==409
    sid,choice=await selected(client,c,saved,brand=c['brands']['a']); assert choice.status_code==200,choice.text
    rid=await admit(client,c,sid)
    row,_=await saved_run(rid)
    pin=row.engine_snapshot['connection_authority']
    for field in ('activation_id','reference_id','reference_revision','grant_revision','capability','expires_at','actor_id','source_id','workspace_id','brand_id'):
        payload={**row.engine_snapshot,'connection_authority':{**pin,field:str(uuid4())}}
        payload['sha256']=digest({k:v for k,v in payload.items() if k!='sha256'})
        bad=SimpleNamespace(id=row.id,engine_snapshot=payload,session_id=row.session_id,workspace_id=row.workspace_id,brain_id=None)
        async with Session() as db:
            with pytest.raises(EngineFailure):await gateway_for_run(db,bad)
    assert calls['factory']==0


async def test_activation_dml_immutable_and_cross_tenant_fk(client,fenced):
    c,_,_=fenced
    response,saved,_,_=await consent(client,c)
    aid=response.json()['id']
    for sql in ('UPDATE model_grant_activations SET capability=\'tool_write\' WHERE id=:id',
                'DELETE FROM model_grant_activations WHERE id=:id'):
        async with Session() as db:
            with pytest.raises(DBAPIError):await db.execute(text(sql),{'id':aid})
            await db.rollback()
    async with Session() as db:
        with pytest.raises(DBAPIError):
            await db.execute(text('''INSERT INTO model_grant_activations
                (id,created_at,workspace_id,grant_id,actor_id,reference_revision,grant_revision,source_stamp,capability,request_key,fingerprint)
                SELECT :id,created_at,:workspace,grant_id,actor_id,reference_revision,grant_revision,source_stamp,capability,:request,fingerprint
                FROM model_grant_activations WHERE id=:old'''),
                {'id':str(uuid4()),'workspace':c['second'],'request':str(uuid4()),'old':aid})
        await db.rollback()
    async with Session() as db:
        grant=await db.get(TenantConnectionGrant,saved['grant']['id'])
        assert grant.revision==1 and grant.status=='staged'


async def test_expiry_no_ttl_extension_default_no_implicit_grant(client,fenced,monkeypatch):
    c,calls,_=fenced
    _,saved,_,_=await consent(client,c)
    sid,choice=await selected(client,c,saved);assert choice.status_code==200
    rid=await admit(client,c,sid)
    # Even activated, a registered source may not silently become the default.
    result=await client.post('/v1/sessions',headers=c['other'],json={'workspace_id':c['workspace']})
    rejected=await client.post('/v1/runs',headers=c['other'],json={
        'session_id':result.json()['id'],'message':'no explicit grant','request_key':uuid4().hex})
    assert rejected.status_code==503 and calls['factory']==0
    monkeypatch.setattr('pao.modules.connections.grants.now',lambda:now()+timedelta(hours=2))
    await execute_run({},rid)
    row,_=await saved_run(rid)
    assert row.status=='failed' and row.error_code==DENIED and calls['factory']==0
    listed=await client.get(f"/v1/workspaces/{c['workspace']}/model-grants",headers=c['other'])
    assert listed.status_code==200 and listed.json()['items']==[]


@pytest.mark.parametrize('change',['remove','reader','archive','brand'])
async def test_resolved_gateway_rechecks_private_brain_before_network(client,fenced,monkeypatch,change):
    c,calls,_=fenced
    monkeypatch.setattr(settings(),'brain_manager_enabled',True)
    _,saved,_,_=await consent(client,c)
    sid,choice=await selected(client,c,saved);assert choice.status_code==200
    rid=await admit(client,c,sid)
    row,_=await saved_run(rid)
    async with Session.begin() as db:
        brain=Brain(workspace_id=c['workspace'],owner_id=c['user_id'],name='Private fixture')
        db.add(brain);await db.flush()
        db.add(BrainMember(brain_id=brain.id,workspace_id=c['workspace'],user_id=c['operator_id'],role='editor'))
        bid=brain.id
    candidate=SimpleNamespace(id=row.id,engine_snapshot=row.engine_snapshot,workspace_id=row.workspace_id,
                              session_id=row.session_id,brain_id=bid,brain_context={'brand_id':None})
    async with Session() as db:
        gateway=await gateway_for_run(db,candidate)
    async with Session.begin() as db:
        member=await db.get(BrainMember,(bid,c['operator_id']))
        if change=='remove':await db.delete(member)
        if change=='reader':member.role='reader'
        if change=='archive':(await db.get(Brain,bid)).archived_at=now()
        if change=='brand':(await db.get(Brain,bid)).brand_id=c['brands']['a']
    with pytest.raises(EngineFailure,match=DENIED):
        async for _ in gateway.stream([{'role':'user','content':'private fixture'}]):pass
    assert calls['factory']==1 and calls['stream']==0


async def test_scoped_discovery_manager_options_and_public_selection(client,fenced):
    c,calls,_=fenced
    response,saved,_,_=await consent(client,c)
    route=f"/v1/workspaces/{c['workspace']}/model-grants"
    listed=await client.get(route,headers=c['other'])
    assert listed.status_code==200 and listed.headers['cache-control']=='no-store'
    assert [r['grant_id'] for r in listed.json()['items']]==[saved['grant']['id']]
    assert 'source_stamp' not in listed.text and 'ciphertext' not in listed.text
    assert (await client.get(route,headers=c['owner'])).json()['items']==[]
    assert (await client.get(route.replace(c['workspace'],c['second']),headers=c['owner'])).json()['items']==[]
    assert (await client.get(route)).status_code==401
    sid,choice=await selected(client,c,saved);assert choice.status_code==200
    assert choice.json()['selection']['grant_id']==saved['grant']['id']
    assert 'activation_id' not in choice.text
    options=path(c['workspace'])+'/options'
    assert (await client.get(options,headers=c['other'])).status_code==403
    value=await client.get(options,headers=c['owner']);assert value.status_code==200
    assert {r['id'] for r in value.json()['brands']}=={c['brands']['a']}
    grants_route=path(c['workspace'])+f"/references/{saved['reference']['id']}/grants"
    value=await client.get(grants_route,headers=c['owner']);assert value.status_code==200
    assert value.json()['items'][0]['model_consent_recorded'] is True
    assert (await client.get(grants_route,headers=c['other'])).status_code==403
    assert (await client.get(grants_route.replace(c['workspace'],c['second']),headers=c['owner'])).status_code==404
    await revoke(client,c,saved)
    assert (await client.get(route,headers=c['other'])).json()['items']==[] and calls['factory']==0


@pytest.mark.parametrize('revoked',[False,True])
async def test_actual_arq_registered_grant_a_b_isolated(client,fenced,revoked):
    from arq import create_pool
    from arq.worker import create_worker
    from arq.connections import RedisSettings
    from arq.constants import job_key_prefix,in_progress_key_prefix,retry_key_prefix,result_key_prefix,default_queue_name
    c,calls,_=fenced
    _,saved,_,_=await consent(client,c)
    sid,choice=await selected(client,c,saved);assert choice.status_code==200
    a=await admit(client,c,sid)
    bctx={**c,'workspace':c['second'],'operator_id':c['outside_id'],
          'connections':{'a':c['connections']['b']},'brands':{'a':c['brands']['b']},'other':c['outsider']}
    result,bsaved,_,_=await consent(client,bctx);assert result.status_code==201,result.text
    bsid,bchoice=await selected(client,bctx,bsaved);assert bchoice.status_code==200,bchoice.text
    b=await admit(client,bctx,bsid)
    if revoked:await revoke(client,c,saved)
    config=RedisSettings.from_dsn(settings().redis_url);assert config.database==15
    queue='pao-test:s21b2b:'+uuid4().hex
    redis=await create_pool(config,default_queue_name=queue)
    ids=['run:'+a,'run:'+b];runner=None
    class Workers:
        functions=[execute_run]
        redis_settings=config
        queue_name=queue
        handle_signals=False
        burst=True
        max_jobs=max_burst_jobs=2
        keep_result=0
        poll_delay=.05
        job_timeout=20
    try:
        for jid in ids:
            assert await redis.exists(job_key_prefix+jid)
            score=await redis.zscore(default_queue_name,jid);assert score is not None
            await redis.zrem(default_queue_name,jid);await redis.zadd(queue,{jid:score})
        runner=create_worker(Workers);await asyncio.wait_for(runner.async_run(),25)
        assert runner.jobs_complete==2 and runner.jobs_failed==0
        assert (await saved_run(a))[0].status==('failed' if revoked else 'completed')
        assert (await saved_run(b))[0].status=='completed'
        assert calls['factory']==calls['stream']==(1 if revoked else 2)
    finally:
        if runner:
            if not hasattr(signal,'SIGUSR1'):
                runner.handle_sig(signal.SIGTERM);runner._handle_signals=True
            await runner.close()
        await redis.delete(queue,*(prefix+jid for jid in ids for prefix in (job_key_prefix,in_progress_key_prefix,retry_key_prefix,result_key_prefix)))
        await redis.aclose()
