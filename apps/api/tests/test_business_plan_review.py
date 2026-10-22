import asyncio
from copy import deepcopy
from datetime import timedelta
from uuid import uuid4
import pytest
from sqlalchemy import select,text
from sqlalchemy.exc import DBAPIError
from pao.config import settings
from pao.db import Session
from pao.models import Member,Task,TaskDependency,BusinessPlanReview,BusinessPlanAdmission
from test_business_planning import profile,plan,base,saved


@pytest.fixture
async def ready(identity,monkeypatch):
    monkeypatch.setattr(settings(),'business_planning_enabled',True)
    return identity


async def draft(client,identity):
    profile_row,_=await saved(client,identity)
    body={'expected_revision':0,'request_key':str(uuid4()),'profile_id':profile_row['id'],'profile_revision':1,'content':plan()}
    path=base(identity)+'/plans/'+str(uuid4())
    response=await client.put(path,headers=identity['owner'],json=body);assert response.status_code==200,response.text
    return path,response.json(),body


def decision(row,**changes):
    return {'request_key':str(uuid4()),'revision':row['revision'],'content_hash':row['content_hash'],
        'decision':'approve','self_review':True,'acknowledge_missing':True,'expiry_hours':168,**changes}


def material(row,review):
    return {'request_key':str(uuid4()),'revision':row['revision'],'review_id':review['id'],
        'content_hash':row['content_hash'],'confirm_drafts_only':True}


async def approved(client,identity):
    path,row,body=await draft(client,identity)
    response=await client.post(path+'/review',headers=identity['owner'],json=decision(row));assert response.status_code==200,response.text
    return path,row,response.json(),body


@pytest.mark.parametrize('field,value',[('self_review',False),('acknowledge_missing',False),('self_review',1),('expiry_hours',0),('expiry_hours',721)])
async def test_confirmation_and_bounds(client,ready,field,value):
    path,row,_=await draft(client,ready)
    response=await client.post(path+'/review',headers=ready['owner'],json=decision(row,**{field:value}))
    assert response.status_code==422


async def test_admin_is_not_default_approver(client,ready):
    path,row,_=await draft(client,ready)
    async with Session.begin() as db:
        member=await db.get(Member,(ready['workspace'],ready['user_id']));member.role='admin'
    response=await client.post(path+'/review',headers=ready['owner'],json=decision(row))
    assert response.status_code==403


async def test_review_once_and_idempotent(client,ready):
    path,row,_=await draft(client,ready);body=decision(row)
    first=await client.post(path+'/review',headers=ready['owner'],json=body)
    again=await client.post(path+'/review',headers=ready['owner'],json=body)
    assert first.status_code==again.status_code==200 and first.json()['id']==again.json()['id']
    assert first.json()['effective'] is True and first.json()['external_actions_allowed'] is False
    assert (await client.post(path+'/review',headers=ready['owner'],json=decision(row))).status_code==409
    body['decision']='reject';assert (await client.post(path+'/review',headers=ready['owner'],json=body)).status_code==409


async def test_reject_needs_new_plan_version(client,ready):
    path,row,body=await draft(client,ready)
    response=await client.post(path+'/review',headers=ready['owner'],json=decision(row,decision='reject'))
    assert response.json()['effective'] is False
    assert (await client.post(path+'/materialize',headers=ready['owner'],json=material(row,response.json()))).status_code==403
    body.update(expected_revision=1,request_key=str(uuid4()));body['content']['title']='Kế hoạch sửa'
    new=(await client.put(path,headers=ready['owner'],json=body)).json()
    assert new['approval_status']=='not_requested'
    assert (await client.post(path+'/review',headers=ready['owner'],json=decision(new))).status_code==200


async def test_revision_and_profile_change_invalidates_effective_review(client,ready):
    path,row,review,body=await approved(client,ready)
    body.update(expected_revision=1,request_key=str(uuid4()));body['content']['title']='Mới'
    assert (await client.put(path,headers=ready['owner'],json=body)).status_code==200
    old=(await client.get(path+'/versions/1',headers=ready['owner'])).json()
    assert old['plan_review']['effective'] is False and old['plan_review']['id']==review['id']
    assert (await client.post(path+'/materialize',headers=ready['owner'],json=material(row,review))).status_code==409


@pytest.mark.parametrize('cause',['profile','expired','role'])
async def test_effective_review_rechecked(client,ready,monkeypatch,cause):
    path,row,review,_=await approved(client,ready)
    if cause=='profile':
        changed={'expected_revision':1,'request_key':str(uuid4()),'content':{**profile(),'brand_voice':'Giọng mới'}}
        assert (await client.put(base(ready)+'/profile',headers=ready['owner'],json=changed)).status_code==200
    if cause=='expired':
        from pao.modules.business_planning import review as service
        current=service.now();monkeypatch.setattr(service,'now',lambda:current+timedelta(days=10))
    if cause=='role':
        async with Session.begin() as db:
            member=await db.get(Member,(ready['workspace'],ready['user_id']));member.role='admin'
    assert (await client.get(path+'/review',headers=ready['owner'])).json()['effective'] is False
    assert (await client.post(path+'/materialize',headers=ready['owner'],json=material(row,review))).status_code==403


async def test_atomic_materialization_and_native_guard(client,ready,monkeypatch):
    path,row,review,_=await approved(client,ready);body=material(row,review)
    first=await client.post(path+'/materialize',headers=ready['owner'],json=body);assert first.status_code==200,first.text
    value=first.json();assert len(value['tasks'])==2 and value['execution_enabled'] is False
    again=await client.post(path+'/materialize',headers=ready['owner'],json=body);assert again.json()==value
    assert (await client.post(path+'/materialize',headers=ready['owner'],json=material(row,review))).status_code==409
    async with Session() as db:
        tasks=list(await db.scalars(select(Task).where(Task.goal_id==value['goal_id'])))
        assert all(task.status=='draft' and task.assignee_type=='unassigned' and task.run_id is None for task in tasks)
        assert len(list(await db.scalars(select(TaskDependency).where(TaskDependency.task_id.in_([task.id for task in tasks])))))==1
        assert await db.scalar(text('SELECT count(*) FROM task_attempts'))==0
    # Disabling S5 cannot make pinned tasks editable through the old Task API.
    monkeypatch.setattr(settings(),'business_planning_enabled',False)
    for task in tasks:
        response=await client.patch('/v1/tasks/'+task.id,headers=ready['owner'],json={'version':task.version,'status':'ready'})
        assert response.status_code==409,response.text
    response=await client.patch('/v1/goals/'+value['goal_id'],headers=ready['owner'],json={'version':1,'status':'active'})
    assert response.status_code==409


async def test_concurrent_materialization_exactly_one_native_set(client,ready):
    path,row,review,_=await approved(client,ready);body=material(row,review)
    async def submit():return await client.post(path+'/materialize',headers=ready['owner'],json=body)
    responses=await asyncio.gather(submit(),submit());assert [r.status_code for r in responses]==[200,200]
    assert responses[0].json()==responses[1].json()
    async with Session() as db:assert len(list(await db.scalars(select(Task))))==2


async def test_no_materialization_before_approval(client,ready):
    path,row,_=await draft(client,ready)
    body={'request_key':str(uuid4()),'revision':1,'review_id':str(uuid4()),'content_hash':row['content_hash'],'confirm_drafts_only':True}
    assert (await client.post(path+'/materialize',headers=ready['owner'],json=body)).status_code==403
    async with Session() as db:assert await db.scalar(text('SELECT count(*) FROM tasks'))==0


@pytest.mark.parametrize('table',['business_plan_reviews','business_plan_admissions','business_plan_tasks'])
async def test_review_admission_pins_immutable(client,ready,table):
    path,row,review,_=await approved(client,ready)
    assert (await client.post(path+'/materialize',headers=ready['owner'],json=material(row,review))).status_code==200
    with pytest.raises(DBAPIError):
        async with Session.begin() as db:await db.execute(text('DELETE FROM '+table))
