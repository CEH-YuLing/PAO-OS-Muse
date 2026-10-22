"""M4.5 cross-domain transaction/scoping and operator diagnostics gates."""
from datetime import timedelta
from unittest.mock import AsyncMock
import pytest
from sqlalchemy import select, func
from sqlalchemy.exc import DBAPIError
from pao.config import settings
from pao.db import Session
from pao.models import BusinessEvent, BusinessOutbox, BusinessReceipt, Workspace, ToolCall, AdAction, Member, User, Task, now, uid
from pao.modules.events.producer import requested
from pao.modules.events.delivery import claim, consume
from test_business_events import task
from test_tools import tools_on, submit, decision
from test_memory import run_chat
from test_ads_actions import write_setup, proposal
from test_meta import meta


@pytest.fixture
def m4_on(monkeypatch):
    for flag in ('business_events_enabled','business_event_delivery_enabled','unified_approvals_enabled'):
        monkeypatch.setattr(settings(),flag,True)


async def test_scoped_diagnostics_and_safe_ledger(client,identity,m4_on):
    await task(client,identity)
    response=await client.get('/v1/business-events/diagnostics',params={'workspace_id':identity['workspace']},headers=identity['owner'])
    assert response.status_code==200 and response.json()['states']=={'pending':1}
    assert response.json()['event_types']=={'task.completed':1}
    assert await consume(*(await claim())[0])
    response=await client.get('/v1/business-events/diagnostics',params={'workspace_id':identity['workspace']},headers=identity['owner'])
    assert response.json()['receipts']==1 and response.json()['states']=={'delivered':1}
    ledger=await client.get('/v1/business-events/ledger',params={'workspace_id':identity['workspace'],'limit':1},headers=identity['owner'])
    assert len(ledger.json())==1 and 'synthetic-private-marker' not in ledger.text
    assert (await client.get('/v1/business-events/ledger',params={'workspace_id':identity['workspace']},headers=identity['outsider'])).status_code==404
    assert (await client.get('/v1/business-events/diagnostics',params={'workspace_id':identity['workspace']},headers=identity['outsider'])).status_code==404
    assert (await client.get('/v1/business-events/ledger',params={'workspace_id':identity['workspace'],'limit':101},headers=identity['owner'])).status_code==422


@pytest.mark.parametrize('invalid',['cross_tenant','null_profile','two_targets'])
async def test_profile_and_tenant_constraints(client,identity,m4_on,tools_on,invalid):
    task_row=await task(client,identity)
    _,rid=await run_chat(client,identity,'Synthetic tool request');call=(await submit(client,identity,rid)).json()
    async with Session.begin() as db:
        other=Workspace(name='Synthetic other workspace');db.add(other);await db.flush();wid=other.id
    with pytest.raises(DBAPIError) as denied:
        async with Session.begin() as db:
            event=await db.scalar(select(BusinessEvent).where(BusinessEvent.event_type=='task.completed'))
            values={key:getattr(event,key) for key in ('workspace_id','event_type','schema_version','aggregate_type','aggregate_id',
                'actor_id','occurred_at','correlation_id','causation_id','payload_reference','content_hash')}
            values.update(id=uid(),aggregate_version=99,task_id=task_row['id'])
            if invalid=='cross_tenant': values['workspace_id']=wid
            elif invalid=='null_profile':values.update(task_id=None,tool_call_id=call['id'])
            else:values['tool_call_id']=call['id']
            db.add(BusinessEvent(**values));await db.flush()
    assert denied.value.orig.sqlstate==('23503' if invalid=='cross_tenant' else '23514')


@pytest.mark.parametrize('domain',['task','tool'])
async def test_approval_event_failure_rolls_back_source(client,identity,m4_on,tools_on,monkeypatch,domain):
    async def fail(db,row,who,kind):
        await requested(db,row,who,kind)
        raise RuntimeError('synthetic_after_approval_event')
    if domain=='task':
        monkeypatch.setattr('pao.task_api.record_approval_requested',fail)
        with pytest.raises(RuntimeError,match='synthetic_after_approval_event'):await task(client,identity,'waiting_approval')
        model=Task
    else:
        _,rid=await run_chat(client,identity,'Synthetic tool request')
        monkeypatch.setattr('pao.tool_gateway.record_approval_requested',fail)
        with pytest.raises(RuntimeError,match='synthetic_after_approval_event'):await submit(client,identity,rid)
        model=ToolCall
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(model))==0
        assert await db.scalar(select(func.count()).select_from(BusinessEvent))==0
        assert await db.scalar(select(func.count()).select_from(BusinessOutbox))==0


@pytest.mark.parametrize('loss',['viewer','inactive','expired'])
async def test_tool_executor_rechecks_after_approval(client,identity,tools_on,loss):
    _,rid=await run_chat(client,identity,'Synthetic tool request');call=(await submit(client,identity,rid)).json()
    assert (await decision(client,identity,call)).status_code==200
    async with Session.begin() as db:
        if loss=='viewer':(await db.get(Member,(identity['workspace'],identity['user_id']))).role='viewer'
        elif loss=='inactive':(await db.get(User,identity['user_id'])).active=False
        else:(await db.get(ToolCall,call['id'])).created_at=now()-timedelta(hours=25)
    from pao.tool_gateway import execute_tool
    provider=AsyncMock();await execute_tool({'tool_invoke':provider},call['id']);provider.assert_not_awaited()
    async with Session() as db:assert (await db.get(ToolCall,call['id'])).status=='cancelled'


async def test_ads_approval_event_rollback(client,identity,m4_on,write_setup,monkeypatch):
    from pao.models import AdAction
    async def fail(db,row,who,kind):
        await requested(db,row,who,kind)
        raise RuntimeError('synthetic_after_ads_event')
    monkeypatch.setattr('pao.ads_actions.record_approval_requested',fail)
    with pytest.raises(RuntimeError,match='synthetic_after_ads_event'):
        await client.post('/v1/ads/actions',json=proposal(identity),headers=identity['owner'])
    async with Session() as db:
        for model in (AdAction,BusinessEvent,BusinessOutbox):
            assert await db.scalar(select(func.count()).select_from(model))==0


async def test_analysis_event_rollback(client,identity,m4_on,meta,monkeypatch):
    from datetime import date
    from test_intelligence import seed,target,analysis
    from pao.models import AdIntelligenceRun,AdRecommendation,AdAnomaly
    from pao.modules.events.producer import analyzed
    day=date(2026,2,3);await seed(identity,[(day,'30','0','0')])
    assert (await client.put('/v1/ads/targets',json=target(identity),headers=identity['owner'])).status_code==200
    async def fail(db,row,who):
        await analyzed(db,row,who)
        raise RuntimeError('synthetic_after_analysis_event')
    monkeypatch.setattr('pao.intelligence.record_analysis_completed',fail)
    with pytest.raises(RuntimeError,match='synthetic_after_analysis_event'):
        await client.post('/v1/ads/intelligence/analyze',json=analysis(identity,day),headers=identity['owner'])
    async with Session() as db:
        for model in (AdIntelligenceRun,AdRecommendation,AdAnomaly,BusinessEvent,BusinessOutbox):
            assert await db.scalar(select(func.count()).select_from(model))==0


async def test_downgrade_refuses_new_profiles_without_data_loss(client,identity,m4_on):
    import asyncio,subprocess,sys
    from sqlalchemy import text
    await task(client,identity,'waiting_approval')
    async with Session() as db:
        before_revision=await db.scalar(text('SELECT version_num FROM alembic_version'))
        before_tables=list(await db.scalars(text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")))
    result=await asyncio.to_thread(subprocess.run,[sys.executable,'-m','alembic','downgrade','0036'],
        capture_output=True,text=True,timeout=30)
    assert result.returncode!=0 and 'new_event_profiles_require_backup' in result.stderr
    async with Session() as db:
        assert await db.scalar(text('SELECT version_num FROM alembic_version'))==before_revision
        assert list(await db.scalars(text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")))==before_tables
        assert await db.scalar(select(func.count()).select_from(BusinessEvent))==1


@pytest.mark.parametrize('domain',['tool','ads'])
async def test_non_task_approval_delivery_internal_only(client,identity,m4_on,tools_on,write_setup,domain):
    if domain=='tool':
        _,rid=await run_chat(client,identity,'Synthetic tool request')
        response=await submit(client,identity,rid);assert response.status_code==201
        ident=response.json()['id']
    else:
        response=await client.post('/v1/ads/actions',json=proposal(identity),headers=identity['owner']);assert response.status_code==201
        ident=response.json()['action']['id']
    assert await consume(*(await claim())[0])
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(BusinessReceipt))==1
        source=await db.get(ToolCall if domain=='tool' else AdAction,ident)
        assert (source.status if domain=='tool' else source.approval_status)=='pending'
    assert write_setup[0].writes==[]
