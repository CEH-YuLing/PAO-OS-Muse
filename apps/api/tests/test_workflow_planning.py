import asyncio
from uuid import uuid4
import pytest
from sqlalchemy import select,func
from pao.config import settings
from pao.db import Session
from pao.models import Task,TaskDependency,TaskAttempt,Run,StudioEvent,StudioVersion
from test_studio import make,publish,SCHEMA

@pytest.fixture
def planner(monkeypatch):
    monkeypatch.setattr(settings(),'studio_enabled',True)
    monkeypatch.setattr(settings(),'workflow_planning_enabled',True)

async def definitions(client,identity):
    agent=await publish(client,identity,await make(client,identity))
    skill=await publish(client,identity,await make(client,identity,'skills','planning-skill',{
        'instruction':'Return a concise JSON object.','agent_version_id':agent['version']['id'],
        'input_schema':SCHEMA,'output_schema':SCHEMA,'exit_criteria':['non_empty:text']}))
    workflow=await publish(client,identity,await make(client,identity,'workflows','planning-workflow',{
        'input_schema':SCHEMA,'output_schema':SCHEMA,'steps':[
            {'id':'second','skill_version_id':skill['version']['id'],'depends_on':['first'],
             'inputs':{'text':{'source':'step','step':'first','field':'text'}}},
            {'id':'first','skill_version_id':skill['version']['id'],'inputs':{'text':{'source':'workflow','field':'text'}}}],
        'outputs':{'text':{'source':'step','step':'second','field':'text'}}}))
    return workflow,skill,agent

async def preview(client,identity,workflow,actor='owner',**updates):
    data={'version_id':workflow['version']['id'],'request_key':str(uuid4()),'input':{'text':'Fixture planning'}}
    data.update(updates)
    base='/v1/studio/definitions/'+workflow['definition']['id']
    response=await client.post(base+'/plan-preview',headers=identity[actor],json=data)
    return base,data,response

async def test_plan_atomic_dependencies_pins_readback_no_attempts(client,identity,planner):
    workflow,skill,agent=await definitions(client,identity)
    base,data,response=await preview(client,identity,workflow)
    assert response.status_code==200,response.text
    snap=response.json();assert [v['step_id'] for v in snap['steps']]==['first','second']
    assert snap['steps'][0]['skill']['hash']==skill['version']['hash']
    assert snap['steps'][0]['agent']['hash']==agent['version']['hash']
    assert not snap['execution_enabled'] and not snap['evidence_verified']
    async with Session() as db:assert await db.scalar(select(func.count(Task.id)))==0
    data['confirmation_hash']=snap['sha256']
    saved=await client.post(base+'/plans',headers=identity['owner'],json=data)
    assert saved.status_code==201,saved.text
    plan=saved.json();assert len(plan['task_ids'])==2
    replay=await client.post(base+'/plans',headers=identity['owner'],json=data)
    assert replay.status_code==201 and replay.json()==plan
    read=await client.get('/v1/studio/plans/'+plan['plan_id'],headers=identity['owner'])
    assert read.json()==plan
    async with Session() as db:
        tasks=list(await db.scalars(select(Task)))
        assert len(tasks)==2 and all(task.status=='draft' and task.run_id is None for task in tasks)
        assert await db.scalar(select(func.count(TaskDependency.id)))==1
        assert await db.scalar(select(func.count(TaskAttempt.id)))==0
        assert await db.scalar(select(func.count(Run.id)))==0
    target=plan['task_ids'][0]
    for changes in ({'version':1,'status':'ready'},{'version':1,'result_reference':{}}):
        assert (await client.patch('/v1/tasks/'+target,headers=identity['owner'],json=changes)).status_code==409
    settings().workflow_planning_enabled=False
    assert (await client.post('/v1/tasks/'+target+'/attempts',headers=identity['owner'],json={'request_key':str(uuid4()),'input':{}})).status_code==409

async def test_concurrent_same_request_one_plan(client,identity,planner):
    workflow,_,_=await definitions(client,identity);base,data,response=await preview(client,identity,workflow)
    data['confirmation_hash']=response.json()['sha256']
    results=await asyncio.gather(*(client.post(base+'/plans',headers=identity['owner'],json=data) for _ in range(2)))
    assert all(result.status_code==201 for result in results)
    assert results[0].json()==results[1].json()
    async with Session() as db:assert await db.scalar(select(func.count(Task.id)))==2

@pytest.mark.parametrize('actor,expected',[('other',403),('outsider',404)])
async def test_scope_no_writes(client,identity,planner,actor,expected):
    workflow,_,_=await definitions(client,identity)
    _,_,response=await preview(client,identity,workflow,actor)
    assert response.status_code==expected

async def test_bad_input_and_confirmation_no_tasks(client,identity,planner):
    workflow,_,_=await definitions(client,identity)
    for value in ({'text':123},{'token':'hidden'},{'text':'Bearer synthetic-secret-123456'}):
        _,_,response=await preview(client,identity,workflow,input=value)
        assert response.status_code==422
    base,data,response=await preview(client,identity,workflow)
    data['confirmation_hash']='0'*64
    result=await client.post(base+'/plans',headers=identity['owner'],json=data)
    assert result.status_code==409
    async with Session() as db:assert await db.scalar(select(func.count(Task.id)))==0

async def test_input_conflict_and_pin_survives_publish(client,identity,planner):
    workflow,_,agent=await definitions(client,identity);base,data,response=await preview(client,identity,workflow)
    data['confirmation_hash']=response.json()['sha256']
    first=(await client.post(base+'/plans',headers=identity['owner'],json=data)).json()
    definition=agent['definition'];edited=await client.post('/v1/studio/definitions/'+definition['id']+'/versions',
        headers=identity['owner'],json={'revision':definition['revision'],'payload':{'instruction':'A new reviewed instruction.'}})
    await publish(client,identity,edited.json())
    assert (await client.post(base+'/plans',headers=identity['owner'],json=data)).json()==first
    data['input']={'text':'changed'}
    assert (await client.post(base+'/plans',headers=identity['owner'],json=data)).status_code==409
    assert (await client.get('/v1/studio/plans/'+first['plan_id'],headers=identity['outsider'])).status_code==404

async def test_flag_off_and_invalid_ids(client,identity,planner):
    workflow,_,_=await definitions(client,identity)
    _,_,response=await preview(client,identity,workflow,request_key='bad')
    assert response.status_code==422
    settings().workflow_planning_enabled=False
    _,_,response=await preview(client,identity,workflow)
    assert response.status_code==503
