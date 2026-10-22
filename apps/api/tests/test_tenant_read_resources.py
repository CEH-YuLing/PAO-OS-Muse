"""SME native read queues, real database concurrency, fixture providers only."""
import asyncio
from uuid import uuid4
from datetime import timedelta
from unittest.mock import AsyncMock
import pytest
from sqlalchemy import select,text
from sqlalchemy.exc import DBAPIError
from pao.db import Session,engine
from pao.config import settings
from pao.models import Workspace,Member,Run,ChatSession,ToolCall,MetaSyncJob,GoogleAdsSyncJob,now
from pao.modules.connections import read_resources
from test_meta import meta,connected as meta_connected
from test_google_ads import google_ads,connected as google_connected
from test_connectors import connectors,connected as mcp_connected,granted,pinned_run,propose
from pao.tool_gateway import execute_tool


def route(wid):return f'/v1/workspaces/{wid}/resources/reads'


async def configure(client,i,version=0,daily=100,queued=20,active=2):
    return await client.put(route(i['workspace']),headers=i['owner'],json={
        'expected_version':version,'daily_read_jobs':daily,'queued_read_jobs':queued,'concurrent_reads':active})


async def second(i):
    async with Session.begin() as db:
        row=Workspace(name='Isolated read SME');db.add(row);await db.flush()
        db.add(Member(workspace_id=row.id,user_id=i['user_id'],role='owner'))
        return {**i,'workspace':row.id}


async def setup(i):
    return {'meta':await meta_connected(i),'google':await google_connected(i)}


async def insert(i,sources,kind='meta',status='queued',updated=None):
    async with Session.begin() as db:
        await read_resources.lock(db,i['workspace'])
        if kind=='mcp':
            chat=ChatSession(workspace_id=i['workspace'],user_id=i['user_id']);db.add(chat);await db.flush()
            run=Run(workspace_id=i['workspace'],session_id=chat.id,request_key=uuid4().hex,prompt='Fixture',status='running')
            db.add(run);await db.flush()
            row=ToolCall(workspace_id=i['workspace'],user_id=i['user_id'],run_id=run.id,request_key=uuid4().hex,
                fingerprint='fixture',name='mcp.fixture',agent_key='chief_of_staff',arguments={},result={},status=status)
        else:
            model=MetaSyncJob if kind=='meta' else GoogleAdsSyncJob
            row=model(connection_id=sources[kind],connection_version=1,
                api_version=settings().meta_graph_api_version if kind=='meta' else settings().google_ads_api_version,
                request_key=uuid4().hex,kind='accounts',status=status,updated_at=updated or now())
        db.add(row);await db.flush();return row.id


async def usage(i):
    async with Session() as db:return await read_resources.usage(db,i['workspace'])


async def test_defaults_scope_and_no_secret_reflection(client,identity):
    result=await client.get(route(identity['workspace']),headers=identity['owner'])
    assert result.status_code==200 and result.headers['cache-control']=='no-store'
    data=result.json();assert data['read_policy']=={'version':0,**read_resources.DEFAULTS}
    assert data['provider_remaining_quota'] is None and data['grants_authorized'] is False
    for who,code in (('other',403),('outsider',404)):
        assert (await client.get(route(identity['workspace']),headers=identity[who])).status_code==code
    assert (await client.get(route(str(uuid4())),headers=identity['owner'])).status_code==404
    marker='fixture-not-a-real-secret'
    bad=await client.put(route(identity['workspace']),headers=identity['owner'],json={'secret':marker})
    assert bad.status_code==422 and marker not in bad.text


@pytest.mark.parametrize('field,value',[('daily_read_jobs',True),('daily_read_jobs',0),('daily_read_jobs',10001),
    ('queued_read_jobs',101),('concurrent_reads',9)])
async def test_host_bounds(client,identity,field,value):
    body={'expected_version':0,'daily_read_jobs':100,'queued_read_jobs':20,'concurrent_reads':2,field:value}
    assert (await client.put(route(identity['workspace']),headers=identity['owner'],json=body)).status_code==422


async def test_cas_concurrent_independent_from_model_policy(client,identity):
    results=await asyncio.gather(configure(client,identity,active=1),configure(client,identity,active=2))
    assert sorted(row.status_code for row in results)==[200,409]
    model=await client.get(f"/v1/workspaces/{identity['workspace']}/resources/models",headers=identity['owner'])
    assert model.status_code==200 and model.json()['model_policy']['version']==0


async def test_atomic_queue_admission_two_sme_shared_native_kinds(client,identity,meta,google_ads):
    sources=await setup(identity);other=await second(identity);others=await setup(other)
    assert (await configure(client,identity,queued=1)).status_code==200
    results=await asyncio.gather(*(insert(identity,sources,kind) for kind in ('meta','google','mcp')*2),return_exceptions=True)
    assert len([row for row in results if isinstance(row,str)])==1
    assert all(isinstance(row,str) or isinstance(row,DBAPIError) for row in results)
    assert await usage(identity)=={'daily_jobs':1,'queued_jobs':1,'running_jobs':0}
    assert isinstance(await insert(other,others,'google'),str)
    assert (await usage(other))['queued_jobs']==1


async def test_daily_admission_count_retained_on_cancel_and_policy_change(client,identity,meta,google_ads):
    sources=await setup(identity);assert (await configure(client,identity,daily=1)).status_code==200
    jid=await insert(identity,sources)
    async with Session.begin() as db:(await db.get(MetaSyncJob,jid)).status='cancelled'
    assert (await configure(client,identity,version=1,daily=1)).status_code==200
    with pytest.raises(DBAPIError):await insert(identity,sources,'google')
    assert (await usage(identity))['daily_jobs']==1


async def test_atomic_running_cap_across_meta_google_and_mcp(client,identity,meta,google_ads):
    sources=await setup(identity);assert (await configure(client,identity,active=1)).status_code==200
    rows=[(await insert(identity,sources,kind),model) for kind,model in
        (('meta',MetaSyncJob),('google',GoogleAdsSyncJob),('mcp',ToolCall))]
    async def start(jid,model):
        async with Session.begin() as db:
            await read_resources.lock(db,identity['workspace'])
            row=await db.get(model,jid,with_for_update=True);row.status='running'
    results=await asyncio.gather(*(start(*row) for row in rows),return_exceptions=True)
    assert sum(row is None for row in results)==1 and sum(isinstance(row,DBAPIError) for row in results)==2
    assert (await usage(identity))['running_jobs']==1


@pytest.mark.parametrize('sql',["UPDATE meta_sync_jobs SET resource_admitted_at=NULL WHERE id=:id",
    "UPDATE meta_sync_jobs SET created_at=created_at-interval '1 day' WHERE id=:id",
    "DELETE FROM meta_sync_jobs WHERE id=:id"])
async def test_sql_budget_history_immutable(client,identity,meta,google_ads,sql):
    jid=await insert(identity,await setup(identity))
    with pytest.raises(DBAPIError):
        async with engine.begin() as db:await db.execute(text(sql),{'id':jid})


@pytest.mark.parametrize('kind',['meta','google','mcp'])
async def test_sql_terminal_job_cannot_requeue_and_charge_again(client,identity,meta,google_ads,kind):
    jid=await insert(identity,await setup(identity),kind,status='completed')
    model={'meta':MetaSyncJob,'google':GoogleAdsSyncJob,'mcp':ToolCall}[kind]
    with pytest.raises(DBAPIError):
        async with Session.begin() as db:(await db.get(model,jid)).status='queued'


@pytest.mark.parametrize('kind',['meta','google','mcp'])
async def test_fair_batch_and_saturated_tenant_skip(client,identity,meta,google_ads,kind):
    from pao.models import MetaConnection,GoogleAdsConnection
    sources=await setup(identity);other=await second(identity);others=await setup(other)
    assert (await configure(client,identity,queued=100,active=1)).status_code==200
    backlog=[await insert(identity,sources,kind) for _ in range(25)]
    bid=await insert(other,others,kind)
    model={'meta':MetaSyncJob,'google':GoogleAdsSyncJob,'mcp':ToolCall}[kind]
    source={'meta':MetaConnection,'google':GoogleAdsConnection,'mcp':None}[kind]
    async with Session() as db:batch=await read_resources.fair_queued(db,model,source,20)
    assert bid in batch and len(batch)==2
    async with Session.begin() as db:
        await read_resources.lock(db,identity['workspace']);(await db.get(model,backlog[0])).status='running'
    async with Session() as db:batch=await read_resources.fair_queued(db,model,source,20)
    assert batch==[bid]


async def test_mcp_api_replay_then_quota_deny_no_provider(client,identity,connectors):
    row=await granted(client,identity,await mcp_connected(client,identity));rid=await pinned_run(client,identity,row)
    assert (await configure(client,identity,daily=1)).status_code==200
    first=await propose(client,identity,row,rid,'quota-1');assert first.status_code==202,first.text
    again=await propose(client,identity,row,rid,'quota-1');assert again.status_code==202 and again.json()['id']==first.json()['id']
    denied=await propose(client,identity,row,rid,'quota-2')
    assert denied.status_code==429 and denied.json()['detail']=='tenant_read_daily_jobs_exhausted'
    assert connectors.calls==0 and (await usage(identity))['daily_jobs']==1


async def test_mcp_wait_before_token_then_release_and_execute(client,identity,connectors,meta,monkeypatch):
    row=await granted(client,identity,await mcp_connected(client,identity));rid=await pinned_run(client,identity,row)
    assert (await configure(client,identity,active=1)).status_code==200
    cid=await meta_connected(identity);holder=await insert(identity,{'meta':cid},'meta',status='running')
    call=await propose(client,identity,row,rid);assert call.status_code==202,call.text
    from pao.modules.connectors import service
    original=service.token
    async def forbidden(*args):raise AssertionError('Quota wait resolved credential')
    monkeypatch.setattr(service,'token',forbidden)
    await execute_tool({},call.json()['id']);assert connectors.calls==0
    async with Session() as db:
        current=await db.get(ToolCall,call.json()['id']);assert current.status=='queued' and current.error_code=='tenant_read_concurrency_wait'
    async with Session.begin() as db:(await db.get(MetaSyncJob,holder)).status='completed'
    monkeypatch.setattr(service,'token',original)
    await execute_tool({},call.json()['id']);assert connectors.calls==1
    assert (await usage(identity))['running_jobs']==0


async def test_empty_fixture_has_no_admissions(client):
    for table in ('tool_calls','meta_sync_jobs','google_ads_sync_jobs'):
        async with Session() as db:
            assert await db.scalar(text(f'SELECT count(*) FROM {table} WHERE resource_admitted_at IS NOT NULL'))==0


async def test_internal_tools_json_null_not_counted_as_mcp(client,identity):
    async with Session.begin() as db:
        chat=ChatSession(workspace_id=identity['workspace'],user_id=identity['user_id']);db.add(chat);await db.flush()
        run=Run(workspace_id=identity['workspace'],session_id=chat.id,request_key=uuid4().hex,prompt='Fixture');db.add(run);await db.flush()
        call=ToolCall(workspace_id=identity['workspace'],user_id=identity['user_id'],run_id=run.id,request_key=uuid4().hex,
            fingerprint='fixture',name='business.kpi.read',agent_key='chief_of_staff',arguments={},result={},status='queued',
            connector_snapshot=None)
        db.add(call);await db.flush();ident=call.id
    assert await usage(identity)=={'daily_jobs':0,'queued_jobs':0,'running_jobs':0}
    async with Session() as db:
        row=await db.get(ToolCall,ident);assert row.resource_admitted_at is None
        assert await read_resources.fair_queued(db,ToolCall,limit=50)==[ident]


async def test_daily_window_uses_statement_not_stale_transaction_time(client):
    async with Session() as db:
        body=await db.scalar(text("SELECT pg_get_functiondef('pao_read_resource_usage(uuid)'::regprocedure)"))
    assert 'statement_timestamp()' in body and 'CURRENT_TIMESTAMP' not in body


@pytest.mark.parametrize('kind',['meta','google'])
async def test_lost_ads_worker_no_resend_after_restart(client,identity,meta,google_ads,kind):
    from pao.integrations.meta.sync import dispatch_meta
    from pao.integrations.google_ads.sync import dispatch_google_ads
    sources=await setup(identity);jid=await insert(identity,sources,kind,'running',now()-timedelta(minutes=10))
    await engine.dispose()
    redis=AsyncMock();dispatch=dispatch_meta if kind=='meta' else dispatch_google_ads
    await dispatch({'redis':redis});await dispatch({'redis':redis});redis.enqueue_job.assert_not_awaited()
    model=MetaSyncJob if kind=='meta' else GoogleAdsSyncJob
    async with Session() as db:
        row=await db.get(model,jid);assert row.status=='failed' and row.error_code.endswith('worker_lost_unknown')
    assert (await usage(identity))['daily_jobs']==1 and (await usage(identity))['running_jobs']==0


@pytest.mark.parametrize('kind',['meta','google'])
async def test_native_ads_api_replay_and_quota_after_cancel(client,identity,meta,google_ads,kind):
    await setup(identity);assert (await configure(client,identity,daily=1)).status_code==200
    base='/v1/integrations/meta' if kind=='meta' else '/v1/integrations/google-ads'
    body={'workspace_id':identity['workspace'],'request_key':str(uuid4()),'kind':'accounts'}
    first=await client.post(base+'/sync',headers=identity['owner'],json=body);assert first.status_code==202,first.text
    replay=await client.post(base+'/sync',headers=identity['owner'],json=body)
    assert replay.status_code==202 and replay.json()['id']==first.json()['id']
    model=MetaSyncJob if kind=='meta' else GoogleAdsSyncJob
    async with Session.begin() as db:(await db.get(model,first.json()['id'])).status='cancelled'
    denied=await client.post(base+'/sync',headers=identity['owner'],json={**body,'request_key':str(uuid4())})
    assert denied.status_code==429 and denied.json()['detail']=='tenant_read_daily_jobs_exhausted'
    assert (await usage(identity))['daily_jobs']==1


@pytest.mark.parametrize('kind',['meta','google'])
async def test_real_arq_saturated_a_does_not_block_b(client,identity,meta,google_ads,monkeypatch,kind):
    import signal
    from arq import create_pool
    from arq.worker import create_worker
    from arq.connections import RedisSettings
    from arq.constants import job_key_prefix,in_progress_key_prefix,retry_key_prefix,result_key_prefix
    from pao.integrations.meta.sync import dispatch_meta,sync_meta
    from pao.integrations.google_ads.sync import dispatch_google_ads,sync_google_ads
    sources=await setup(identity);other=await second(identity);others=await setup(other)
    assert (await configure(client,identity,queued=100,active=1)).status_code==200
    holder=await insert(identity,sources,kind,'running')
    for _ in range(25):await insert(identity,sources,kind)
    bid=await insert(other,others,kind);calls=[]
    if kind=='meta':
        async def rows(*args):calls.append('b');return;yield
        monkeypatch.setattr('pao.integrations.meta.sync.MetaClient.rows',rows)
    else:
        async def fetch(*args):calls.append('b');return []
        monkeypatch.setattr('pao.integrations.google_ads.sync.fetch_accounts',fetch)
    config=RedisSettings.from_dsn(settings().redis_url);assert config.database==15
    queue='pao-test:s22b2a:'+uuid4().hex;redis=await create_pool(config,default_queue_name=queue)
    fn=sync_meta if kind=='meta' else sync_google_ads;dispatch=dispatch_meta if kind=='meta' else dispatch_google_ads
    jid=('meta:' if kind=='meta' else 'google-ads:')+bid;runner=None
    class Workers:
        functions=[fn];redis_settings=config;queue_name=queue;handle_signals=False;burst=True
        max_jobs=max_burst_jobs=1;keep_result=0;poll_delay=.05;job_timeout=20
    try:
        await dispatch({'redis':redis});assert await redis.zcard(queue)==1
        runner=create_worker(Workers);await asyncio.wait_for(runner.async_run(),25)
        assert runner.jobs_complete==1 and runner.jobs_failed==0 and calls==['b']
        model=MetaSyncJob if kind=='meta' else GoogleAdsSyncJob
        async with Session() as db:
            assert (await db.get(model,bid)).status=='completed'
            assert (await db.get(model,holder)).status=='running'
        assert (await usage(other))['running_jobs']==0
    finally:
        if runner:
            if not hasattr(signal,'SIGUSR1'):runner.handle_sig(signal.SIGTERM);runner._handle_signals=True
            await runner.close()
        await redis.delete(*(prefix+jid for prefix in (job_key_prefix,in_progress_key_prefix,retry_key_prefix,result_key_prefix)))
        await redis.delete(queue);await redis.aclose()
