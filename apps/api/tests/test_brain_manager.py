from unittest.mock import AsyncMock
from uuid import uuid4
import pytest
pytestmark=pytest.mark.usefixtures('accounted_runs')
from sqlalchemy import select
from pao.config import settings
from pao.db import Session
from pao.models import Brain, BrainMember, Member, Run, MemoryJob
from pao.modules.brains.context import memory_scope
from pao.runtime import execute_run
from test_memory import Gateway


@pytest.fixture
def brains_on(monkeypatch):
    monkeypatch.setattr(settings(),'brain_manager_enabled',True)


async def create(client,identity,name='Private Brain',headers=None):
    result=await client.post('/v1/brains',headers=headers or identity['owner'],json={
        'workspace_id':identity['workspace'],'name':name})
    assert result.status_code==201,result.text
    return result.json()


async def test_brain_crud_isolation_revision_archive_restore(client,identity,brains_on):
    brain=await create(client,identity)
    bid=brain['id']; h=identity['owner']
    assert (await client.get('/v1/brains',headers=identity['other'],params={'workspace_id':identity['workspace']})).json()==[]
    assert (await client.patch(f'/v1/brains/{bid}',headers=identity['other'],json={'revision':1,'name':'Stolen'})).status_code==404
    renamed=await client.patch(f'/v1/brains/{bid}',headers=h,json={'revision':1,'name':'Renamed'})
    assert renamed.status_code==200 and renamed.json()['revision']==2
    assert (await client.patch(f'/v1/brains/{bid}',headers=h,json={'revision':1,'name':'Stale'})).status_code==409
    archived=await client.patch(f'/v1/brains/{bid}',headers=h,json={'revision':2,'archived':True})
    assert archived.status_code==200 and archived.json()['archived_at']
    assert (await client.get('/v1/brains',headers=h,params={'workspace_id':identity['workspace']})).json()==[]
    assert len((await client.get('/v1/brains',headers=h,params={'workspace_id':identity['workspace'],'archived':True})).json())==1
    assert (await client.patch(f'/v1/brains/{bid}',headers=h,json={'revision':3,'archived':False})).json()['archived_at'] is None
    assert (await client.post('/v1/brains',headers=h,json={'workspace_id':identity['workspace'],'name':'   '})).status_code==422


async def test_grants_do_not_leak_private_legacy_memory(client,identity,brains_on):
    h=identity['owner']; wid=identity['workspace']
    private=(await client.post('/v1/brains/default',headers=h,json={'workspace_id':wid})).json()
    async with Session() as db:
        other=await db.scalar(select(Member.user_id).where(Member.workspace_id==wid,Member.user_id!=identity['user_id']))
    grant=await client.put(f"/v1/brains/{private['id']}/members/{other}",headers=h,json={'revision':1,'role':'reader'})
    assert grant.status_code==200 and grant.json()['legacy_memory_shared'] is False
    assert (await client.get(f"/v1/brains/{private['id']}/memory",headers=identity['other'])).json()==[]
    assert (await client.patch(f"/v1/brains/{private['id']}",headers=identity['other'],json={'revision':2,'name':'No'})).status_code==403
    assert (await client.delete(f"/v1/brains/{private['id']}/members/{other}?revision=2",headers=h)).status_code==200
    assert (await client.get('/v1/brains',headers=identity['other'],params={'workspace_id':wid})).json()==[]


async def test_session_switch_pins_runs_and_conflicts_without_mutating_history(client,identity,brains_on):
    h=identity['owner']; wid=identity['workspace']
    custom=await create(client,identity)
    session=(await client.post('/v1/sessions',headers=h,json={'workspace_id':wid})).json()
    sid=session['id']
    association=(await client.get(f'/v1/sessions/{sid}/brain',headers=h)).json()
    original=association['brain_id']
    response=await client.post('/v1/runs',headers=h,json={'session_id':sid,'message':'Hello','request_key':'brain-first'})
    assert response.status_code==202
    rid=response.json()['id']
    assert (await client.put(f'/v1/sessions/{sid}/brain',headers=h,json={'version':1,'brain_id':custom['id']})).status_code==409
    assert (await client.patch(f'/v1/brains/{original}',headers=h,json={'revision':1,'archived':True})).status_code==409
    assert (await client.post(f'/v1/runs/{rid}/cancel',headers=h)).status_code==200
    assert (await client.put(f'/v1/sessions/{sid}/brain',headers=h,json={'version':1,'brain_id':custom['id']})).json()['version']==2
    assert (await client.put(f'/v1/sessions/{sid}/brain',headers=h,json={'version':1,'brain_id':original})).status_code==409
    pinned=(await client.get(f'/v1/runs/{rid}/brain',headers=h)).json()
    assert pinned['brain_id']==original and pinned['revision']==1 and pinned['context']['legacy']
    archived=(await client.patch(f"/v1/brains/{custom['id']}",headers=h,json={'revision':1,'archived':True})).json()
    assert archived['archived_at']
    assert (await client.post('/v1/runs',headers=h,json={'session_id':sid,'message':'No','request_key':'brain-blocked'})).status_code==409


async def test_custom_brain_never_retrieves_or_schedules_legacy_memory(client,identity,brains_on,monkeypatch):
    monkeypatch.setattr(settings(),'memory_enabled',True)
    retrieve=AsyncMock(side_effect=AssertionError('Legacy memory must not be queried'))
    monkeypatch.setattr('pao.runtime.retrieve',retrieve)
    h=identity['owner']
    custom=await create(client,identity)
    sid=(await client.post('/v1/sessions',headers=h,json={'workspace_id':identity['workspace']})).json()['id']
    assert (await client.put(f'/v1/sessions/{sid}/brain',headers=h,json={'version':1,'brain_id':custom['id']})).status_code==200
    rid=(await client.post('/v1/runs',headers=h,json={'session_id':sid,'message':'Hello','request_key':'brain-custom'})).json()['id']
    await execute_run({'gateway':Gateway()},rid)
    retrieve.assert_not_awaited()
    async with Session() as db:
        run=await db.get(Run,rid)
        assert run.status=='completed'
        assert run.brain_id==custom['id'] and not run.brain_context['legacy']
        assert not await db.get(MemoryJob,rid)


async def test_disabled_brain_routes_and_custom_session_fail_closed(client,identity,brains_on,monkeypatch):
    h=identity['owner']; custom=await create(client,identity)
    sid=(await client.post('/v1/sessions',headers=h,json={'workspace_id':identity['workspace']})).json()['id']
    await client.put(f'/v1/sessions/{sid}/brain',headers=h,json={'version':1,'brain_id':custom['id']})
    monkeypatch.setattr(settings(),'brain_manager_enabled',False)
    assert (await client.get('/v1/brains',headers=h,params={'workspace_id':identity['workspace']})).status_code==503
    assert (await client.post('/v1/runs',headers=h,json={'session_id':sid,'message':'No','request_key':'brain-off'})).status_code==503


async def test_run_rechecks_revoked_brain_before_provider(client,identity,brains_on):
    h=identity['owner']; custom=await create(client,identity,headers=identity['other'])
    async with Session.begin() as db:
        db.add(BrainMember(brain_id=custom['id'],workspace_id=identity['workspace'],user_id=identity['user_id'],role='editor'))
    sid=(await client.post('/v1/sessions',headers=h,json={'workspace_id':identity['workspace']})).json()['id']
    await client.put(f'/v1/sessions/{sid}/brain',headers=h,json={'version':1,'brain_id':custom['id']})
    rid=(await client.post('/v1/runs',headers=h,json={'session_id':sid,'message':'No provider','request_key':'brain-revoked'})).json()['id']
    async with Session.begin() as db:
        await db.delete(await db.get(BrainMember,(custom['id'],identity['user_id'])))
    gateway=AsyncMock(side_effect=AssertionError('Provider not permitted'))
    await execute_run({'gateway':gateway},rid)
    async with Session() as db:
        run=await db.get(Run,rid)
        assert run.status=='failed' and run.error_code=='brain_access_unavailable'
