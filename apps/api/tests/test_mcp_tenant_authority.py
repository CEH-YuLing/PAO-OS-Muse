"""Real DB/API/ARQ, fixture MCP only. Consent never replaces native tool review."""
import asyncio
import signal
from datetime import timedelta
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from pao.config import settings
from pao.db import Session
from pao.models import (Brain, BrainMember, ChatSession, ConnectionReadActivation, ConnectorConnection,
    ConnectorSecret, Member, Run, TenantConnectionGrant, ToolCall, User, now)
from pao.modules.connectors import service, gateway
from pao.modules.connectors.transport import Client
from pao.modules.connections.read_authority import DENIED
from pao.tool_gateway import execute_tool, dispatch_tools
from test_connectors import connectors, connected, granted, pinned_run
from test_connection_inventory import corpus, path
from test_model_grant_activation import stage, revoke


async def setup(client,c,*,actor='other',brand=None,brain=False):
    row=await granted(client,c,await connected(client,c));bid=None
    if brain:
        async with Session.begin() as db:
            private=Brain(workspace_id=c['workspace'],owner_id=c['user_id'],brand_id=brand,name='MCP private')
            db.add(private);await db.flush();bid=private.id
            db.add(BrainMember(brain_id=bid,workspace_id=c['workspace'],user_id=c['operator_id'],role='editor'))
            native=await db.get(ConnectorConnection,row['id']);native.brain_id=bid
    # Native owner supplies the reviewed, bounded tool permission; not the grant.
    await pinned_run(client,c,row)
    chat=await client.post('/v1/sessions',headers=c[actor],json={
        'workspace_id':c['workspace'],'brand_id':brand,'memory_enabled':False})
    assert chat.status_code==201,chat.text
    sid=chat.json()['id']
    if bid:
        selected=await client.put(f'/v1/sessions/{sid}/brain',headers=c[actor],json={'brain_id':bid,'version':1})
        assert selected.status_code==200,selected.text
    admitted=await client.post('/v1/runs',headers=c[actor],json={
        'session_id':sid,'message':'/p5-probe {"text":"Synthetic"}','request_key':uuid4().hex})
    assert admitted.status_code==202,admitted.text
    context={**c,'connections':{'a':{**c['connections']['a'],'mcp':row['id']}}}
    saved,_=await stage(client,context,'mcp',{'expected_version':row['version'],'brand_id':brand,
        'grantee_id':c['operator_id'] if actor=='other' else c['user_id']})
    assert saved.status_code==201,saved.text
    return {'row':row,'saved':saved.json(),'run':admitted.json()['id'],'session':sid,'actor':actor,'brain':bid}


async def activate(client,c,f,*,body=None,headers=None):
    saved=f['saved'];route=path(c['workspace'])+f"/references/{saved['reference']['id']}/grants/{saved['grant']['id']}/activate-mcp"
    value=body or {'reference_revision':1,'grant_revision':1,'request_key':str(uuid4()),
                  'capability':'mcp_read','allow_mcp_read_ack':True}
    return await client.post(route,headers=headers or c['owner'],json=value),route,value


async def propose(client,c,f,*,grant=True,change=None,headers=None,key=None):
    body={'run_id':f['run'],'tool_id':f['row']['tools'][0]['id'],'request_key':key or uuid4().hex}
    if grant:body['grant_id']=f['saved']['grant']['id']
    return await client.post(f"/v1/connectors/connections/{f['row']['id']}/calls",headers=headers or c[f['actor']],
                             json={**body,**(change or {})})


async def record(cid):
    async with Session() as db:return await db.get(ToolCall,cid)


@pytest.fixture(autouse=True)
def brains_on(monkeypatch):monkeypatch.setattr(settings(),'brain_manager_enabled',True)


async def test_explicit_grantee_consent_native_review_and_discovery(client,corpus,connectors):
    c=corpus;f=await setup(client,c)
    assert (await propose(client,c,f)).status_code==403 and connectors.calls==0
    consent,route,body=await activate(client,c,f)
    assert consent.status_code==201,consent.text
    assert consent.json()['native_tool_permission_required'] is True
    assert consent.json()['provider_health_verified'] is False and consent.headers['cache-control']=='no-store'
    assert 'fingerprint' not in consent.text and 'source_stamp' not in consent.text
    replay=await client.post(route,headers=c['owner'],json=body)
    assert replay.json()['id']==consent.json()['id'] and replay.json()['replayed'] is True
    queued=await propose(client,c,f,key='same-call');assert queued.status_code==202,queued.text
    duplicate=await propose(client,c,f,key='same-call');assert duplicate.json()['id']==queued.json()['id']
    before=await record(queued.json()['id']);authority=before.connector_snapshot['connection_authority']
    assert authority['actor_id']==c['operator_id'] and authority['capability']=='mcp_read'
    await execute_tool({},before.id);await execute_tool({},before.id)
    after=await record(before.id)
    assert after.status=='completed' and after.result=={'text':'Synthetic read result'} and connectors.calls==1
    assert before.connector_snapshot==after.connector_snapshot
    catalog=await client.get('/v1/connectors/grants',headers=c['other'],params={'workspace_id':c['workspace']})
    assert catalog.status_code==200 and catalog.headers['cache-control']=='no-store'
    assert len(catalog.json()['items'])==1 and catalog.json()['items'][0]['grant_id']==f['saved']['grant']['id']
    assert 'synthetic-secret' not in catalog.text and 'endpoint' not in catalog.text and 'ciphertext' not in catalog.text
    assert (await client.get('/v1/connectors/grants',params={'workspace_id':c['workspace']})).status_code==401
    assert (await client.get('/v1/connectors/grants',headers=c['outsider'],params={'workspace_id':c['workspace']})).status_code==403


async def test_registered_native_owner_and_old_pin_fail_closed(client,corpus,connectors,monkeypatch):
    c=corpus;row=await granted(client,c,await connected(client,c));rid=await pinned_run(client,c,row)
    legacy={'row':row,'run':rid,'actor':'owner'}
    queued=await propose(client,c,legacy,grant=False);assert queued.status_code==202
    context={**c,'connections':{'a':{**c['connections']['a'],'mcp':row['id']}}}
    saved,_=await stage(client,context,'mcp',{'expected_version':row['version'],'brand_id':None,'grantee_id':c['user_id']})
    assert saved.status_code==201,saved.text
    assert (await propose(client,c,legacy,grant=False)).status_code==403
    calls=[]
    async def forbidden(*args):calls.append(1);raise AssertionError('Token must not resolve on deny')
    monkeypatch.setattr(service,'token',forbidden)
    await execute_tool({},queued.json()['id'])
    assert (await record(queued.json()['id'])).status=='cancelled' and not calls and connectors.calls==0


@pytest.mark.parametrize('change',['revoke','reference','manager_role','manager_inactive','grantee_role',
    'grantee_inactive','grantee_removed','expiry','rotate','permission','manifest','source_status'])
async def test_queued_no_token_no_network_on_changed_authority(client,corpus,connectors,monkeypatch,change):
    c=corpus;f=await setup(client,c);consent,_,_=await activate(client,c,f);assert consent.status_code==201
    queued=await propose(client,c,f);assert queued.status_code==202,queued.text
    before=await record(queued.json()['id'])
    if change=='revoke':await revoke(client,c,f['saved'])
    elif change=='reference':
        r=await client.post(path(c['workspace'])+f"/references/{f['saved']['reference']['id']}/revoke",
                            headers=c['owner'],json={'reference_revision':1});assert r.status_code==200
    elif change=='expiry':
        from pao.modules.connections import grants
        future=now()+timedelta(days=2)
        monkeypatch.setattr(grants,'now',lambda:future)
    else:
        async with Session.begin() as db:
            row=await db.get(ConnectorConnection,f['row']['id'])
            if change in ('manager_role','grantee_role'):
                uid=c['user_id'] if change=='manager_role' else c['operator_id']
                (await db.get(Member,(c['workspace'],uid))).role='viewer'
            elif change in ('manager_inactive','grantee_inactive'):
                uid=c['user_id'] if change=='manager_inactive' else c['operator_id']
                (await db.get(User,uid)).active=False
            elif change=='grantee_removed':await db.delete(await db.get(Member,(c['workspace'],c['operator_id'])))
            elif change=='rotate':(await db.scalar(select(ConnectorSecret).where(ConnectorSecret.connection_id==row.id))).ciphertext=service.seal('new-synthetic-token')
            elif change=='permission':row.permissions={}
            elif change=='manifest':row.manifest_hash='f'*64
            elif change=='source_status':row.status='draft'
    calls=[]
    async def forbidden(*args):calls.append(1);raise AssertionError('Token resolved on deny')
    monkeypatch.setattr(service,'token',forbidden)
    await execute_tool({},before.id);after=await record(before.id)
    assert after.status=='cancelled' and after.result=={} and not calls and connectors.calls==0
    assert after.connector_snapshot==before.connector_snapshot


@pytest.mark.parametrize('change',['remove','reader','archive','brand'])
async def test_private_brain_scope_recheck(client,corpus,connectors,monkeypatch,change):
    c=corpus;f=await setup(client,c,brain=True)
    consent,_,_=await activate(client,c,f);assert consent.status_code==201,consent.text
    queued=await propose(client,c,f);assert queued.status_code==202,queued.text
    async with Session.begin() as db:
        brain=await db.get(Brain,f['brain']);member=await db.get(BrainMember,(brain.id,c['operator_id']))
        if change=='remove':await db.delete(member)
        elif change=='reader':member.role='reader'
        elif change=='archive':brain.archived_at=now()
        else:brain.brand_id=c['brands']['a']
    calls=[]
    async def forbidden(*args):calls.append(1);raise AssertionError('Token resolved after Brain loss')
    monkeypatch.setattr(service,'token',forbidden)
    await execute_tool({},queued.json()['id'])
    assert (await record(queued.json()['id'])).status=='cancelled' and not calls and connectors.calls==0


async def test_exact_brand_actor_cross_sme_and_pin_integrity(client,corpus,connectors):
    c=corpus;f=await setup(client,c,brand=c['brands']['a'])
    assert (await activate(client,c,f))[0].status_code==201
    assert (await propose(client,c,f,headers=c['owner'])).status_code==403
    catalog=await client.get('/v1/connectors/grants',headers=c['other'],params={'workspace_id':c['workspace']})
    assert catalog.json()['items']==[]  # Null is not a wildcard.
    catalog=await client.get('/v1/connectors/grants',headers=c['other'],params={'workspace_id':c['workspace'],'brand_id':c['brands']['a']})
    assert len(catalog.json()['items'])==1
    foreign=await propose(client,c,f,change={'tool_id':'mcp.'+c['connections']['b']['mcp'].replace('-','')+'.read_report'})
    assert foreign.status_code in (403,409) and connectors.calls==0
    queued=await propose(client,c,f);assert queued.status_code==202
    call=await record(queued.json()['id'])
    for key in ('actor_id','workspace_id','brand_id','source_id','activation_id','grant_id','capability','expires_at'):
        pin={**call.connector_snapshot,'connection_authority':{**call.connector_snapshot['connection_authority'],key:str(uuid4())}}
        from pao.modules.studio.contracts import digest
        pin['sha256']=digest({k:v for k,v in pin.items() if k!='sha256'})
        async with Session() as db:
            with pytest.raises(HTTPException):await gateway.guard(db,await db.get(Run,f['run']),c['operator_id'],call.name,pin)
    assert connectors.calls==0


async def test_catalog_derives_owned_run_scope_and_never_foreign_run(client,corpus,connectors):
    c=corpus;f=await setup(client,c,brand=c['brands']['a'],brain=True)
    assert (await activate(client,c,f))[0].status_code==201
    params={'workspace_id':c['workspace'],'run_id':f['run']}
    catalog=await client.get('/v1/connectors/grants',headers=c['other'],params=params)
    assert catalog.status_code==200 and len(catalog.json()['items'])==1,catalog.text
    assert catalog.json()['items'][0]['brain_id']==f['brain']
    assert (await client.get('/v1/connectors/grants',headers=c['owner'],params=params)).status_code==404
    assert (await client.get('/v1/connectors/grants',headers=c['other'],params={**params,'brand_id':c['brands']['b']})).status_code==403
    async with Session.begin() as db:db.add(Member(workspace_id=c['second'],user_id=c['operator_id'],role='operator'))
    assert (await client.get('/v1/connectors/grants',headers=c['other'],params={**params,'workspace_id':c['second']})).status_code==404
    assert connectors.calls==0


async def test_consent_cross_workspace_insert_is_rejected(client,corpus,connectors):
    c=corpus;f=await setup(client,c);assert (await activate(client,c,f))[0].status_code==201
    async with Session() as db:
        consent=await db.scalar(select(ConnectionReadActivation))
        values={'workspace_id':c['second'],'grant_id':consent.grant_id,'actor_id':consent.actor_id,'kind':'mcp',
            'capability':'mcp_read','reference_revision':1,'grant_revision':1,'source_stamp':consent.source_stamp,
            'request_key':str(uuid4()),'fingerprint':consent.fingerprint}
    with pytest.raises(DBAPIError):
        async with Session.begin() as db:db.add(ConnectionReadActivation(**values));await db.flush()
    assert connectors.calls==0


async def test_consent_cas_auth_validation_immutable_and_replay(client,corpus,connectors):
    c=corpus;f=await setup(client,c)
    _,route,body=await activate(client,c,f,headers=c['other'])
    assert (await client.post(route,headers=c['other'],json=body)).status_code==403
    assert (await client.post(route,headers=c['owner'],json={**body,'grant_revision':2})).status_code==409
    bad=await client.post(route,headers=c['owner'],json={**body,'secret':'never-echo-mcp-fixture'})
    assert bad.status_code==422 and 'never-echo-mcp-fixture' not in bad.text
    values=await asyncio.gather(*[client.post(route,headers=c['owner'],json=body) for _ in range(3)])
    assert all(v.status_code==201 for v in values) and len({v.json()['id'] for v in values})==1
    assert (await client.post(route,headers=c['owner'],json={**body,'grant_revision':2})).status_code==409
    for sql in ("UPDATE connection_read_activations SET capability='mcp_read'",'DELETE FROM connection_read_activations'):
        with pytest.raises(DBAPIError):
            async with Session.begin() as db:await db.execute(text(sql))
    await revoke(client,c,f['saved'])
    replay=await client.post(route,headers=c['owner'],json=body)
    assert replay.status_code==201 and replay.json()['replayed'] is True
    assert (await propose(client,c,f)).status_code==403 and connectors.calls==0


async def test_late_revocation_discards_valid_provider_response(client,corpus,connectors,monkeypatch):
    c=corpus;f=await setup(client,c);assert (await activate(client,c,f))[0].status_code==201
    queued=await propose(client,c,f);assert queued.status_code==202
    started=asyncio.Event();release=asyncio.Event();original=connectors.respond
    async def slow(request):
        import json
        if json.loads(request.content)['method']=='tools/call':started.set();await release.wait()
        return await original(request)
    monkeypatch.setattr(service,'Client',lambda url,token=None:Client(url,token,httpx.MockTransport(slow)))
    task=asyncio.create_task(execute_tool({},queued.json()['id']))
    try:
        await asyncio.wait_for(started.wait(),5);await revoke(client,c,f['saved'])
        release.set();await asyncio.wait_for(task,5)
        row=await record(queued.json()['id'])
        assert row.status=='failed' and row.result=={} and row.error_code=='connector_permission_changed'
    finally:
        release.set()
        if not task.done():task.cancel()
        await asyncio.gather(task,return_exceptions=True)


async def test_native_rotation_serializes_token_resolution_not_network(client,corpus,connectors,monkeypatch):
    c=corpus;f=await setup(client,c);assert (await activate(client,c,f))[0].status_code==201
    queued=await propose(client,c,f);assert queued.status_code==202
    resolving=asyncio.Event();release_token=asyncio.Event();network=asyncio.Event();release_network=asyncio.Event()
    original_token=service.token;seen=[]
    async def slow_token(db,row):
        token=await original_token(db,row);resolving.set();await release_token.wait();return token
    class Provider:
        def __init__(self,endpoint,token):seen.append(token=='synthetic-secret-marker-1234')
        async def exchange(self,pin):network.set();await release_network.wait();return {'text':'Late fixture result'}
    monkeypatch.setattr(service,'token',slow_token);monkeypatch.setattr(service,'Client',Provider)
    worker=asyncio.create_task(execute_tool({},queued.json()['id']));rotation=None
    try:
        await asyncio.wait_for(resolving.wait(),5)
        rotation=asyncio.create_task(client.put(f"/v1/connectors/connections/{f['row']['id']}/credential",headers=c['owner'],
            json={'version':f['row']['version'],'token':'new-synthetic-credential'}))
        # Bounded race gate: rotation must remain blocked while token check is held.
        with pytest.raises(TimeoutError):await asyncio.wait_for(asyncio.shield(rotation),.1)
        release_token.set();await asyncio.wait_for(network.wait(),5)
        changed=await asyncio.wait_for(rotation,5);assert changed.status_code==200,changed.text
        assert seen==[True]  # Old authorized token, never the concurrently rotated one.
        release_network.set();await asyncio.wait_for(worker,5)
        result=await record(queued.json()['id']);assert result.status=='cancelled' and result.result=={}
    finally:
        release_token.set();release_network.set()
        for task in (worker,rotation):
            if task and not task.done():task.cancel()
        await asyncio.gather(*(task for task in (worker,rotation) if task),return_exceptions=True)


@pytest.mark.parametrize('missing',['native_permission','review','skill_tool','model_grant'])
async def test_grant_never_replaces_native_authority(client,corpus,connectors,missing):
    c=corpus;f=await setup(client,c);assert (await activate(client,c,f))[0].status_code==201
    if missing=='model_grant':
        staged,_=await stage(client,c,'model',{'brand_id':None})
        assert staged.status_code==201
        saved=staged.json()
        consent=await client.post(path(c['workspace'])+f"/references/{saved['reference']['id']}/grants/{saved['grant']['id']}/activate-model",
            headers=c['owner'],json={'reference_revision':1,'grant_revision':1,'request_key':str(uuid4()),
                                    'capability':'model_inference','allow_model_inference_ack':True})
        assert consent.status_code==201,consent.text
        denied=await propose(client,c,f,change={'grant_id':staged.json()['grant']['id']})
    elif missing=='review':
        chat=await client.post('/v1/sessions',headers=c['other'],json={'workspace_id':c['workspace'],'memory_enabled':False})
        run=await client.post('/v1/runs',headers=c['other'],json={'session_id':chat.json()['id'],'message':'No published skill',
                                                               'request_key':uuid4().hex})
        assert run.status_code==202,run.text
        f['run']=run.json()['id'];denied=await propose(client,c,f)
    else:
        async with Session.begin() as db:
            row=await db.get(ConnectorConnection,f['row']['id'])
            if missing=='native_permission':row.permissions={}
            else:
                # Supply a tool absent from the published skill, not forged JSON.
                f['row']['tools'][0]['id']='mcp.'+row.id.replace('-','')+'.unreviewed'
        denied=await propose(client,c,f)
    assert denied.status_code in (403,409) and connectors.calls==0


@pytest.mark.parametrize('revoked',[False,True])
async def test_two_sme_real_arq_tools(client,corpus,connectors,revoked):
    from arq import create_pool
    from arq.worker import create_worker
    from arq.connections import RedisSettings
    from arq.constants import job_key_prefix,in_progress_key_prefix,retry_key_prefix,result_key_prefix,default_queue_name
    c=corpus
    async with Session.begin() as db:db.add(Member(workspace_id=c['second'],user_id=c['operator_id'],role='operator'))
    b={**c,'workspace':c['second'],'brands':{'a':c['brands']['b']},'connections':{'a':c['connections']['b']}}
    fixtures=[await setup(client,context) for context in (c,b)]
    ids=[]
    for context,f in zip((c,b),fixtures):
        assert (await activate(client,context,f))[0].status_code==201
        queued=await propose(client,context,f);assert queued.status_code==202,queued.text
        ids.append(queued.json()['id'])
    if revoked:await revoke(client,c,fixtures[0]['saved'])
    config=RedisSettings.from_dsn(settings().redis_url);assert config.database==15
    queue='pao-test:s21b2c:'+uuid4().hex;redis=await create_pool(config,default_queue_name=queue)
    jobs=['tool:'+cid for cid in ids];runner=None
    class Workers:
        functions=[execute_tool];redis_settings=config;queue_name=queue;handle_signals=False;burst=True
        max_jobs=max_burst_jobs=2;keep_result=0;poll_delay=.05;job_timeout=20
    try:
        # Real dispatcher/admission job payloads, moved only for these owned IDs.
        class DefaultQueue:
            async def enqueue_job(self,*args,**kw):return await redis.enqueue_job(*args,_queue_name=default_queue_name,**kw)
        await dispatch_tools({'redis':DefaultQueue()})
        for jid in jobs:
            assert await redis.exists(job_key_prefix+jid)
            score=await redis.zscore(default_queue_name,jid);assert score is not None
            await redis.zrem(default_queue_name,jid);await redis.zadd(queue,{jid:score})
        runner=create_worker(Workers);await asyncio.wait_for(runner.async_run(),25)
        assert runner.jobs_complete==2 and runner.jobs_failed==0
        assert (await record(ids[0])).status==('cancelled' if revoked else 'completed')
        assert (await record(ids[1])).status=='completed' and connectors.calls==(1 if revoked else 2)
    finally:
        if runner:
            if not hasattr(signal,'SIGUSR1'):runner.handle_sig(signal.SIGTERM);runner._handle_signals=True
            await runner.close()
        await redis.delete(queue,*(prefix+jid for jid in jobs for prefix in (job_key_prefix,in_progress_key_prefix,retry_key_prefix,result_key_prefix)))
        await redis.aclose()
