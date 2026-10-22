"""M4.1 transaction/tenant/immutability tests, no delivery or providers."""
import asyncio,json
import pytest
from sqlalchemy import select,func,text
from sqlalchemy.exc import DBAPIError
from pao.config import settings
from pao.db import Session
from pao.models import BusinessEvent,BusinessOutbox,Task,TaskActivity,Workspace
from pao.auth import Principal
from pao.modules.events.producer import completed

@pytest.fixture
def events(monkeypatch):monkeypatch.setattr(settings(),'business_events_enabled',True)

async def task(client,identity,status='completed'):
    response=await client.post('/v1/tasks',headers=identity['owner'],json={
        'workspace_id':identity['workspace'],'title':'Synthetic M4 task','status':status,
        'success_criteria':['Synthetic criteria'],'evidence':[{'text':'synthetic-private-marker'}]})
    assert response.status_code==201,response.text
    return response.json()

async def counts():
    async with Session() as db:
        return tuple([await db.scalar(select(func.count()).select_from(model)) for model in (BusinessEvent,BusinessOutbox)])

async def test_disabled_no_events(client,identity):
    await task(client,identity)
    assert await counts()==(0,0)

async def test_create_envelope_reference_not_raw_payload(client,identity,events):
    row=await task(client,identity)
    assert await counts()==(1,1)
    async with Session() as db:
        event=await db.scalar(select(BusinessEvent));outbox=await db.scalar(select(BusinessOutbox))
        assert event.aggregate_id==row['id'] and event.aggregate_version==row['version']
        assert event.workspace_id==identity['workspace'] and event.actor_id==identity['user_id']
        assert event.schema_version==1 and event.event_type=='task.completed'
        assert event.correlation_id==row['id'] and event.causation_id is None
        assert len(event.content_hash)==64 and len(event.payload_reference['evidence_sha256'])==64
        assert 'synthetic-private-marker' not in json.dumps(event.payload_reference)
        assert outbox.event_id==event.id and outbox.status=='pending' and outbox.attempts==0

async def test_transition_and_concurrent_completion(client,identity,events):
    row=await task(client,identity,'ready');assert await counts()==(0,0)
    async def finish():return await client.patch('/v1/tasks/'+row['id'],headers=identity['owner'],json={'version':row['version'],'status':'completed'})
    results=await asyncio.gather(finish(),finish())
    assert sorted(result.status_code for result in results)==[200,409]
    assert await counts()==(1,1)

async def test_same_status_edit_does_not_reemit(client,identity,events):
    row=await task(client,identity)
    response=await client.patch('/v1/tasks/'+row['id'],headers=identity['owner'],json={'version':row['version'],'status':'completed','title':'Edited'})
    assert response.status_code==200 and await counts()==(1,1)

@pytest.mark.parametrize('operation',['create','transition'])
async def test_event_failure_rolls_back_business_state(client,identity,events,monkeypatch,operation):
    existing=await task(client,identity,'ready') if operation=='transition' else None
    async def fail(db,row,who):
        await completed(db,row,who)
        raise RuntimeError('synthetic_after_outbox_flush')
    monkeypatch.setattr('pao.task_api.record_task_completed',fail)
    with pytest.raises(RuntimeError,match='synthetic_after_outbox_flush'):
        if existing:
            await client.patch('/v1/tasks/'+existing['id'],headers=identity['owner'],json={'version':existing['version'],'status':'completed'})
        else:await task(client,identity)
    assert await counts()==(0,0)
    async with Session() as db:
        rows=list(await db.scalars(select(Task)))
        assert len(rows)==(1 if existing else 0)
        if existing:assert rows[0].status=='ready' and rows[0].version==existing['version']
        assert await db.scalar(select(func.count()).select_from(TaskActivity))==(1 if existing else 0)

async def test_idempotent_internal_republication_and_conflict(client,identity,events):
    row=await task(client,identity)
    async def republish():
        async with Session.begin() as db:
            record=await db.get(Task,row['id'])
            return (await completed(db,record,Principal(identity['user_id'],0))).id
    ids=await asyncio.gather(republish(),republish())
    assert ids[0]==ids[1] and await counts()==(1,1)
    with pytest.raises(ValueError,match='business_event_content_conflict'):
        async with Session.begin() as db:
            record=await db.get(Task,row['id']);record.evidence=[{'text':'forged'}]
            await completed(db,record,Principal(identity['user_id'],0))
    assert await counts()==(1,1)

@pytest.mark.parametrize('sql',["UPDATE business_events SET schema_version=2","DELETE FROM business_events",
    "UPDATE business_outbox SET event_id='00000000-0000-0000-0000-000000000000'"])
async def test_immutable_envelope_and_outbox_scope(client,identity,events,sql):
    await task(client,identity)
    with pytest.raises(DBAPIError):
        async with Session.begin() as db:await db.execute(text(sql))
    assert await counts()==(1,1)

async def test_cross_tenant_fk_and_permission(client,identity,events):
    row=await task(client,identity)
    async with Session.begin() as db:
        other=Workspace(name='Different tenant');db.add(other);await db.flush();wid=other.id
    with pytest.raises(DBAPIError) as denied:
        async with Session.begin() as db:
            source=await db.scalar(select(BusinessEvent))
            # Remove only the test outbox inside the transaction to ensure this
            # exercises the composite tenant FK, not the event_id unique key.
            await db.execute(text('DELETE FROM business_outbox'))
            db.add(BusinessOutbox(workspace_id=wid,event_id=source.id,status='pending',attempts=0))
            await db.flush()
    assert denied.value.orig.sqlstate=='23503'
    response=await client.patch('/v1/tasks/'+row['id'],headers=identity['outsider'],json={'version':row['version'],'status':'completed'})
    assert response.status_code in (403,404) and await counts()==(1,1)

async def test_insufficient_evidence_denied_without_event(client,identity,events):
    response=await client.post('/v1/tasks',headers=identity['owner'],json={
        'workspace_id':identity['workspace'],'title':'Invalid completion','status':'completed'})
    assert response.status_code==409 and await counts()==(0,0)
