"""Native tenant onboarding/catalogue gates; no model or provider calls."""
import asyncio
from uuid import uuid4
import pytest
from sqlalchemy import select,func
from pao.config import settings
from pao.db import Session
from pao.models import Workspace,Member,Brand,LifecycleAudit,StudioVersion
from test_studio import make,publish,SCHEMA

def base(identity):return f"/v1/workspaces/{identity['workspace']}/organization"
def body(name='Doanh nghiệp riêng',**extra):return {'name':name,'request_key':str(uuid4()),**extra}

async def test_owner_creates_independent_enterprise_and_receipt(client,identity):
    payload=body();url=base(identity)+'/enterprises'
    first=await client.post(url,headers=identity['owner'],json=payload)
    assert first.status_code==201,first.text
    new=first.json();assert new['id']!=identity['workspace'] and new['revision']==1
    retry=await client.post(url,headers=identity['owner'],json=payload)
    assert retry.json()==new
    assert (await client.post(url,headers=identity['owner'],json={**payload,'name':'Khác'})).status_code==409
    async with Session() as db:
        members=list(await db.scalars(select(Member).where(Member.workspace_id==new['id'])))
        assert len(members)==1 and members[0].user_id==identity['user_id'] and members[0].role=='owner'
        assert await db.scalar(select(func.count()).select_from(Brand).where(Brand.workspace_id==new['id']))==0
        audit=await db.scalar(select(LifecycleAudit).where(LifecycleAudit.workspace_id==new['id']))
        assert set(audit.details)=={'fingerprint','revision'} and payload['name'] not in str(audit.details)
    assert (await client.get(f"/v1/workspaces/{new['id']}/organization",headers=identity['other'])).status_code==404
    data=(await client.get(f"/v1/workspaces/{new['id']}/organization",headers=identity['owner'])).json()
    assert data['brands']==[] and not data['public_signup'] and not data['copies_connections_or_permissions']

@pytest.mark.parametrize('actor,status',[('other',403),('outsider',404)])
async def test_create_owner_only(client,identity,actor,status):
    assert (await client.post(base(identity)+'/enterprises',headers=identity[actor],json=body())).status_code==status

@pytest.mark.parametrize('name',['','   ','bad\x00name','bad\x7fname','a'*121])
async def test_invalid_names(client,identity,name):
    assert (await client.post(base(identity)+'/brands',headers=identity['owner'],json=body(name))).status_code==422

async def test_name_revision_idempotency_and_no_public_signup(client,identity):
    url=base(identity);read=await client.get(url,headers=identity['owner']);assert read.headers['cache-control']=='no-store'
    revision=read.json()['enterprise']['revision'];payload=body('Tên mới',expected_revision=revision)
    result=await client.post(url+'/name',headers=identity['owner'],json=payload);assert result.status_code==200,result.text
    assert result.json()['revision']==revision+1
    assert (await client.post(url+'/name',headers=identity['owner'],json=payload)).json()==result.json()
    assert (await client.post(url+'/name',headers=identity['owner'],json=body(expected_revision=revision))).status_code==409
    assert (await client.post(url+'/name',headers=identity['other'],json=body(expected_revision=revision+1))).status_code==403
    assert (await client.post('/v1/auth/signup',json={})).status_code in (404,405)

async def test_brand_names_scope_and_concurrent_cas(client,identity):
    url=base(identity);a=await client.post(url+'/brands',headers=identity['owner'],json=body(' Nhãn A '));assert a.status_code==201,a.text
    brand=a.json();assert brand['name']=='Nhãn A' and brand['revision']==1
    assert (await client.post(url+'/brands',headers=identity['owner'],json=body('nhãn a'))).status_code==409
    path=url+f"/brands/{brand['id']}/name"
    results=await asyncio.gather(*[client.post(path,headers=identity['owner'],json=body(name,expected_revision=1)) for name in ('B','C')])
    assert sorted(x.status_code for x in results)==[200,409]
    assert (await client.post(url+f'/brands/{uuid4()}/name',headers=identity['owner'],json=body(expected_revision=0))).status_code==404
    assert (await client.post(url+'/brands',headers=identity['other'],json=body())).status_code==403
    async with Session.begin() as db:
        member=await db.scalar(select(Member).where(Member.workspace_id==identity['workspace'],Member.user_id!=identity['user_id']))
        member.role='admin'
    assert (await client.post(url+'/brands',headers=identity['other'],json=body('Quản trị tạo'))).status_code==201
    assert (await client.post(url+'/enterprises',headers=identity['other'],json=body())).status_code==403

async def test_enterprise_quota_and_concurrent_duplicate(client,identity):
    payload=body();responses=await asyncio.gather(*[client.post(base(identity)+'/enterprises',headers=identity['owner'],json=payload) for _ in range(2)])
    assert all(r.status_code==201 for r in responses)
    assert responses[0].json()==responses[1].json()
    async with Session.begin() as db:
        for _ in range(18):
            row=Workspace(name='Giới hạn');db.add(row);await db.flush();db.add(Member(workspace_id=row.id,user_id=identity['user_id'],role='owner'))
    assert (await client.post(base(identity)+'/enterprises',headers=identity['owner'],json=body())).status_code==409

@pytest.fixture
def studio_catalog(monkeypatch):monkeypatch.setattr(settings(),'studio_enabled',True)

async def skill(client,identity,agent,category='design'):
    result=await client.post('/v1/studio/definitions',headers=identity['owner'],json={
        'workspace_id':identity['workspace'],'kind':'skills','slug':'design-helper','name':'Skill thiết kế','category':category,
        'payload':{'instruction':'Write a factual text brief.','agent_version_id':agent['version']['id'],'input_schema':SCHEMA,'output_schema':SCHEMA}})
    assert result.status_code==201,result.text
    return result.json()

async def test_category_atomic_and_no_execution_change(client,identity,studio_catalog):
    agent=await publish(client,identity,await make(client,identity))
    item=await skill(client,identity,agent);url=f"/v1/studio/definitions/{item['definition']['id']}"
    data=(await client.get('/v1/studio/skill-catalog',headers=identity['owner'],params={'workspace_id':identity['workspace']})).json()
    entry=next(x for x in data['items'] if x['kind']=='skills')
    assert entry['category']=='design' and entry['agent_version_id']==agent['version']['id'] and entry['published_agent_version_id'] is None
    assert not data['assignment_is_execution_permission']
    response=await client.post(url+'/category',headers=identity['owner'],json={'revision':item['definition']['revision'],'category':'ads'})
    assert response.status_code==200,response.text
    assert not response.json()['execution_changed']
    detail=(await client.get(url,headers=identity['owner'])).json()
    assert detail['versions']==[item['version']]
    assert (await client.post(url+'/category',headers=identity['owner'],json={'revision':item['definition']['revision'],'category':'editor'})).status_code==409
    assert (await client.post(url+'/category',headers=identity['other'],json={'revision':response.json()['revision'],'category':'editor'})).status_code==403
    assert (await client.get('/v1/studio/skill-catalog',headers=identity['outsider'],params={'workspace_id':identity['workspace']})).status_code==404
    assert (await client.post(url+'/category',headers=identity['owner'],json={'revision':response.json()['revision'],'category':'shell'})).status_code==422

async def test_reassign_creates_draft_preserves_published_binding(client,identity,studio_catalog):
    first=await publish(client,identity,await make(client,identity))
    second=await publish(client,identity,await make(client,identity,slug='another-agent'))
    item=await publish(client,identity,await skill(client,identity,first));definition=item['definition']
    result=await client.post(f"/v1/studio/definitions/{definition['id']}/versions",headers=identity['owner'],json={
        'revision':definition['revision'],'payload':{**item['version']['payload'],'agent_version_id':second['version']['id']}})
    assert result.status_code==201,result.text
    data=(await client.get('/v1/studio/skill-catalog',headers=identity['owner'],params={'workspace_id':identity['workspace']})).json()
    row=next(x for x in data['items'] if x['kind']=='skills')
    assert row['agent_version_id']==second['version']['id'] and row['published_agent_version_id']==first['version']['id']
    async with Session() as db:
        saved=await db.get(StudioVersion,item['version']['id']);assert saved.content_hash==item['version']['hash'] and saved.status=='published'

async def test_agent_rejects_skill_category_and_foreign_agent(client,identity,studio_catalog):
    result=await client.post('/v1/studio/definitions',headers=identity['owner'],json={'workspace_id':identity['workspace'],'kind':'agents','slug':'bad-category','name':'Bad','payload':{'instruction':'Write concise facts.'},'category':'ads'})
    assert result.status_code==422
    foreign=await client.post('/v1/studio/definitions',headers=identity['owner'],json={'workspace_id':identity['workspace'],'kind':'skills','slug':'foreign-agent','name':'Bad','category':'ads','payload':{'instruction':'Write a concise brief.','agent_version_id':str(uuid4()),'input_schema':SCHEMA,'output_schema':SCHEMA}})
    assert foreign.status_code==404
