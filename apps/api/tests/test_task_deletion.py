import asyncio
import pytest
from sqlalchemy import select
from pao.db import Session
from pao.models import Member, Task, TaskActivity, TaskComment
from test_tasks import make_project, make_task


async def erase(client, identity, task, **kwargs):
    return await client.delete(f"/v1/tasks/{task['id']}", headers=kwargs.get('headers', identity['owner']),
                               params={'version': kwargs.get('version', task['version'])})


@pytest.mark.parametrize('status', ['draft', 'ready', 'waiting_approval', 'failed', 'cancelled', 'blocked'])
async def test_delete_retains_history_and_hides_all_views(client, identity, status):
    task = await make_task(client, identity, None, status=status)
    await client.post(f"/v1/tasks/{task['id']}/comments", headers=identity['owner'], json={'body':'Lịch sử cần giữ'})
    response = await erase(client, identity, task)
    assert response.status_code == 200, response.text
    assert response.json()['status'] == 'cancelled'
    assert response.json()['version'] == task['version'] + 1
    listed = await client.get('/v1/tasks', headers=identity['owner'], params={'workspace_id':identity['workspace']})
    assert listed.json() == []
    for suffix in ('', '/comments', '/activity', '/attempts'):
        assert (await client.get(f"/v1/tasks/{task['id']}"+suffix, headers=identity['owner'])).status_code == 404
    assert (await client.patch(f"/v1/tasks/{task['id']}", headers=identity['owner'], json={
        'version':response.json()['version'], 'status':'ready'})).status_code == 404
    assert (await client.post(f"/v1/tasks/{task['id']}/attempts", headers=identity['owner'], json={
        'request_key':'deleted-no-start', 'input':{}})).status_code == 404
    assert (await client.post(f"/v1/tasks/{task['id']}/comments", headers=identity['owner'], json={'body':'Không ghi thêm'})).status_code == 404
    # An exact, explicit retry after a lost ACK does not duplicate the tombstone.
    assert (await erase(client, identity, task)).status_code == 200
    assert (await erase(client, identity, task, version=response.json()['version'])).status_code == 404
    async with Session() as db:
        assert await db.get(Task, task['id']) is not None
        assert len(list(await db.scalars(select(TaskComment).where(TaskComment.task_id==task['id'])))) == 1
        events=list(await db.scalars(select(TaskActivity).where(TaskActivity.task_id==task['id'])))
        assert [e.event for e in events].count('task.deleted') == 1
        assert {'task.created','comment.created','task.deleted'} <= {e.event for e in events}
    # Deleting never removes the project or prevents creating a replacement.
    await make_task(client, identity, None, title=task['title'])


async def test_delete_permissions_version_and_sme(client, identity):
    project = await make_project(client, identity)
    task = await make_task(client, identity, project['id'])
    assert (await erase(client, identity, task, headers=identity['outsider'])).status_code == 404
    assert (await erase(client, identity, task, headers=identity['other'])).status_code == 403
    assert (await erase(client, identity, task, version=0)).status_code == 422
    assert (await erase(client, identity, task, version=2)).status_code == 409
    assert (await client.delete(f"/v1/tasks/{task['id']}", headers=identity['owner'])).status_code == 422
    async with Session.begin() as db:
        member=await db.get(Member,(identity['workspace'],identity['user_id']));member.role='viewer'
    assert (await erase(client, identity, task)).status_code == 403
    async with Session.begin() as db:
        member=await db.get(Member,(identity['workspace'],identity['user_id']));member.role='operator'
    assert (await erase(client, identity, task)).status_code == 200
    assert (await client.get('/v1/projects',headers=identity['owner'],params={'workspace_id':identity['workspace']})).json()[0]['id']==project['id']


@pytest.mark.parametrize('fields', [
    {'status':'running'},
    {'status':'completed','success_criteria':['Đã duyệt'],'evidence':[{'reference':'result'}]},
    {'kind':'ai'}, {'source':'pao'}, {'source':'automation'},
    {'evidence':[{'reference':'result'}]}, {'result_reference':{'reference':'result'}},
])
async def test_delete_rejects_executing_or_result_work(client, identity, fields):
    task=await make_task(client, identity, None, **fields)
    response=await erase(client, identity, task)
    assert response.status_code == 409, response.text
    assert (await client.get(f"/v1/tasks/{task['id']}",headers=identity['owner'])).status_code==200


async def test_delete_rejects_dependencies_children_attempts_and_goals(client, identity):
    parent=await make_task(client,identity,None)
    child=await make_task(client,identity,None,parent_task_id=parent['id'])
    dependent=await make_task(client,identity,None,dependencies=[parent['id']])
    for task in (parent,child,dependent):
        assert (await erase(client,identity,task)).status_code==409
    started=await make_task(client,identity,None,status='ready',success_criteria=['Có kết quả'])
    attempt=await client.post(f"/v1/tasks/{started['id']}/attempts",headers=identity['owner'],json={'request_key':'delete-test-run','input':{}})
    assert attempt.status_code==201
    cancelled=await client.patch(f"/v1/tasks/{started['id']}",headers=identity['owner'],json={'version':2,'status':'cancelled'})
    assert cancelled.status_code==200
    assert (await erase(client,identity,cancelled.json())).status_code==409
    goal=await client.post('/v1/goals',headers=identity['owner'],json={'workspace_id':identity['workspace'],'title':'Goal','success_criteria':['Đạt']})
    task=await make_task(client,identity,None,goal_id=goal.json()['id'])
    assert (await erase(client,identity,task)).status_code==409


async def test_deleted_task_cannot_be_used_as_new_dependency_or_parent(client,identity):
    task=await make_task(client,identity,None)
    assert (await erase(client,identity,task)).status_code==200
    for fields in ({'dependencies':[task['id']]},{'parent_task_id':task['id']}):
        response=await client.post('/v1/tasks',headers=identity['owner'],json={
            'workspace_id':identity['workspace'],'title':'Không gắn lại',**fields})
        assert response.status_code==404


async def test_delete_respects_native_planning_guard(client,identity,monkeypatch):
    from fastapi import HTTPException
    from pao.modules.studio import planning
    async def guarded(db,task):
        raise HTTPException(409,'workflow_plan_tasks_frozen_no_runner')
    task=await make_task(client,identity,None)
    monkeypatch.setattr(planning,'guard_planned_task',guarded)
    assert (await erase(client,identity,task)).status_code==409


@pytest.mark.parametrize('link', ['dependencies','parent_task_id'])
async def test_delete_and_new_link_are_serialized(client,identity,link):
    task=await make_task(client,identity,None)
    fields={link:[task['id']] if link=='dependencies' else task['id']}
    created,deleted=await asyncio.gather(
        client.post('/v1/tasks',headers=identity['owner'],json={
            'workspace_id':identity['workspace'],'title':'Tạo liên kết đồng thời',**fields}),
        erase(client,identity,task))
    assert (created.status_code,deleted.status_code) in ((201,409),(404,200))


async def test_duplicate_delete_is_one_atomic_tombstone(client,identity):
    task=await make_task(client,identity,None)
    first,second=await asyncio.gather(erase(client,identity,task),erase(client,identity,task))
    assert first.status_code==second.status_code==200
    async with Session() as db:
        events=list(await db.scalars(select(TaskActivity).where(
            TaskActivity.task_id==task['id'],TaskActivity.event=='task.deleted')))
        assert len(events)==1


async def test_deleting_waiting_task_invalidates_old_approval_ticket(client,identity,monkeypatch):
    from pao.config import settings
    monkeypatch.setattr(settings(),'unified_approvals_enabled',True)
    task=await make_task(client,identity,None,status='waiting_approval')
    path='/v1/business-events/approvals'
    inbox=await client.get(path,headers=identity['owner'],params={'workspace_id':identity['workspace']})
    assert inbox.status_code==200
    [item]=inbox.json()
    assert (await erase(client,identity,task)).status_code==200
    assert (await client.get(path,headers=identity['owner'],params={'workspace_id':identity['workspace']})).json()==[]
    response=await client.post(path+'/decision',headers=identity['owner'],json={'ticket':item['ticket'],'decision':'approve'})
    assert response.status_code==409
