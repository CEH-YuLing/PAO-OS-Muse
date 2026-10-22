import asyncio
from copy import deepcopy
from uuid import uuid4
import pytest
from sqlalchemy import text, delete
from sqlalchemy.exc import DBAPIError
from pao.config import settings
from pao.db import Session
from pao.models import Brand, Member, Workspace
from pao.modules.business_planning.contracts import ProfileContent, PlanContent, digest, missing


def profile():
    return {'description':'Doanh nghiệp thử, không phải dữ liệu khách hàng','products':['Sản phẩm A'],
        'audience':'Nhóm thử nghiệm','brand_voice':'Rõ ràng, không bịa thông tin','objectives':['Chuẩn bị nội dung tháng'],
        'kpis':[{'name':'Số bản nháp được duyệt','target':None,'unit':'bản'}],
        'resources':'Một biên tập viên','monthly_budget':None,'currency':'VND','timezone':'Asia/Ho_Chi_Minh'}


def plan():
    return {'title':'Kế hoạch tháng 10','month':'2026-10-01','campaign_brief':'Chỉ soạn nội dung để duyệt, không đăng thật',
        'deliverables':[{'key':'research','title':'Tổng hợp sản phẩm','specialist':'analyst','due_date':'2026-10-05',
            'brief':'Đọc hồ sơ đã cung cấp','acceptance':['Nêu dữ liệu còn thiếu'],'depends_on':[]},
            {'key':'content','title':'Viết bản nháp','specialist':'content','due_date':'2026-10-06',
            'brief':'Dựa trên kết quả nghiên cứu','acceptance':['Không phát minh ưu đãi'],'depends_on':['research']}]}


@pytest.fixture
async def ready(identity,monkeypatch):
    monkeypatch.setattr(settings(),'business_planning_enabled',True)
    return identity


def base(identity):return '/v1/workspaces/'+identity['workspace']+'/business-planning'


async def saved(client,identity,content=None,query=''):
    body={'expected_revision':0,'request_key':str(uuid4()),'content':content or profile()}
    response=await client.put(base(identity)+'/profile'+query,headers=identity['owner'],json=body)
    assert response.status_code==200,response.text
    return response.json(),body


@pytest.mark.parametrize('field,value',[('monthly_budget',12.1),('monthly_budget',True),('monthly_budget','NaN'),('monthly_budget','-1'),('monthly_budget','1.001'),('timezone','Not/AZone'),('currency','vnd'),('products',['']),('resources','x'*2001),('description','\x00'),('description','\ud800')])
def test_profile_validation(field,value):
    content=profile();content[field]=value
    with pytest.raises(ValueError):ProfileContent.model_validate(content)


def test_unknown_not_zero_and_digest():
    content=ProfileContent.model_validate(profile()).model_dump(mode='json')
    assert content['monthly_budget'] is None and content['kpis'][0]['target'] is None
    assert 'monthly_budget' in missing(content) and 'kpis.0.target' in missing(content)
    assert digest(content)==digest(dict(reversed(list(content.items()))))
    content['monthly_budget']='0';assert 'monthly_budget' not in missing(content)


@pytest.mark.parametrize('kind',['duplicate','cycle','missing','late','outside_month','not_first','empty_acceptance'])
def test_deliverable_dag(kind):
    content=plan();rows=content['deliverables']
    if kind=='duplicate':rows[1]['key']='research'
    if kind=='cycle':rows[0]['depends_on']=['content']
    if kind=='missing':rows[1]['depends_on']=['missing']
    if kind=='late':rows[0]['due_date']='2026-10-07'
    if kind=='outside_month':rows[1]['due_date']='2026-11-01'
    if kind=='not_first':content['month']='2026-10-02'
    if kind=='empty_acceptance':rows[0]['acceptance']=[' ']
    with pytest.raises(ValueError):PlanContent.model_validate(content)


async def test_flag_role_and_anonymous(client,identity):
    status=await client.get(base(identity)+'/status',headers=identity['owner']);assert status.status_code==200
    assert status.json()['available'] is False and status.json()['execution_enabled'] is False
    assert (await client.get(base(identity)+'/profile',headers=identity['owner'])).status_code==503
    assert (await client.get(base(identity)+'/status',headers=identity['outsider'])).status_code==404
    assert (await client.get(base(identity)+'/status')).status_code==401


async def test_profiles_version_cas_idempotency(client,ready):
    row,body=await saved(client,ready);assert row['revision']==1
    assert 'monthly_budget' in row['missing_fields']
    same=await client.put(base(ready)+'/profile',headers=ready['owner'],json=body)
    assert same.json()['version_id']==row['version_id']
    changed=deepcopy(body);changed['content']['audience']='Khác'
    assert (await client.put(base(ready)+'/profile',headers=ready['owner'],json=changed)).status_code==409
    changed['request_key']=str(uuid4());assert (await client.put(base(ready)+'/profile',headers=ready['owner'],json=changed)).status_code==409
    changed['expected_revision']=1;new=await client.put(base(ready)+'/profile',headers=ready['owner'],json=changed)
    assert new.status_code==200 and new.json()['revision']==2
    old=await client.get(base(ready)+'/profiles/'+row['id']+'/versions/1',headers=ready['owner'])
    assert old.json()['content']==row['content'] and old.json()['current_revision']==2
    assert (await client.put(base(ready)+'/profile',headers=ready['owner'],json=body)).status_code==409


async def test_two_sme_brand_and_roles(client,ready):
    async with Session.begin() as db:
        second=Workspace(name='Doanh nghiệp B');db.add(second);await db.flush()
        db.add(Member(workspace_id=second.id,user_id=ready['user_id'],role='owner'))
        a=Brand(workspace_id=ready['workspace'],name='Cùng tên');b=Brand(workspace_id=second.id,name='Cùng tên');db.add_all([a,b]);await db.flush()
    first,_=await saved(client,ready,query='?brand_id='+a.id)
    assert (await client.get(base(ready)+'/profile?brand_id='+b.id,headers=ready['owner'])).status_code==404
    second_base='/v1/workspaces/'+second.id+'/business-planning'
    assert (await client.get(second_base+'/profiles/'+first['id']+'/versions/1',headers=ready['owner'])).status_code==404
    assert (await client.get(base(ready)+'/profile',headers=ready['other'])).status_code==403
    enterprise,_=await saved(client,ready);assert enterprise['id']!=first['id']
    assert (await client.get(second_base+'/profile',headers=ready['owner'])).json()['item'] is None


async def test_plan_pins_versions_no_execution_and_stale(client,ready):
    source,profile_body=await saved(client,ready);pid=str(uuid4());path=base(ready)+'/plans/'+pid
    body={'expected_revision':0,'request_key':str(uuid4()),'profile_id':source['id'],'profile_revision':1,'content':plan()}
    response=await client.put(path,headers=ready['owner'],json=body);assert response.status_code==200,response.text
    first=response.json();assert first['execution_enabled'] is False and first['approval_status']=='not_requested'
    assert first['profile_hash']==source['content_hash'] and first['status']=='draft'
    assert (await client.put(path,headers=ready['owner'],json=body)).json()['version_id']==first['version_id']
    body['expected_revision']=1;body['request_key']=str(uuid4());body['content']['title']='Sửa kế hoạch'
    second=await client.put(path,headers=ready['owner'],json=body);assert second.status_code==200
    old=await client.get(path+'/versions/1',headers=ready['owner']);assert old.json()['content']==first['content']
    profile_body.update(expected_revision=1,request_key=str(uuid4()));profile_body['content']['brand_voice']='Giọng mới'
    assert (await client.put(base(ready)+'/profile',headers=ready['owner'],json=profile_body)).status_code==200
    reread=(await client.get(path,headers=ready['owner'])).json();assert reread['profile_stale'] is True and reread['profile_hash']==source['content_hash']
    body.update(expected_revision=2,request_key=str(uuid4()))
    assert (await client.put(path,headers=ready['owner'],json=body)).status_code==409
    listing=await client.get(base(ready)+'/plans?profile_id='+source['id'],headers=ready['owner']);assert len(listing.json()['items'])==1
    async with Session() as db:
        for table in ('tasks','task_attempts','goal_executions','studio_executions'):
            assert await db.scalar(text('SELECT count(*) FROM '+table))==0


async def test_concurrent_cas_has_one_winner(client,ready):
    row,_=await saved(client,ready)
    async def change(voice):return await client.put(base(ready)+'/profile',headers=ready['owner'],json={
        'expected_revision':1,'request_key':str(uuid4()),'content':{**profile(),'brand_voice':voice}})
    responses=await asyncio.gather(change('A'),change('B'))
    assert sorted(response.status_code for response in responses)==[200,409]


@pytest.mark.parametrize('operation',['update_version','delete_version','skip_head','cross_brand'])
async def test_database_guards(client,ready,operation):
    row,_=await saved(client,ready)
    async with Session.begin() as db:
        other=Workspace(name='Khác');db.add(other);await db.flush()
        brand=Brand(workspace_id=other.id,name='Khác');db.add(brand);await db.flush()
    with pytest.raises(DBAPIError):
        async with Session.begin() as db:
            if operation=='update_version':await db.execute(text("UPDATE business_profile_versions SET content='{}' WHERE profile_id=:id"),{'id':row['id']})
            if operation=='delete_version':await db.execute(text('DELETE FROM business_profile_versions WHERE profile_id=:id'),{'id':row['id']})
            if operation=='skip_head':await db.execute(text('UPDATE business_profiles SET revision=revision+1 WHERE id=:id'),{'id':row['id']})
            if operation=='cross_brand':await db.execute(text('UPDATE business_profiles SET brand_id=:brand WHERE id=:id'),{'brand':brand.id,'id':row['id']})


async def test_invalid_body_is_redacted_and_bounded(client,ready):
    body={'expected_revision':0,'request_key':str(uuid4()),'content':{**profile(),'secret':'PRIVATE_TEST_MARKER'}}
    response=await client.put(base(ready)+'/profile',headers=ready['owner'],json=body)
    assert response.status_code==422 and 'PRIVATE_TEST_MARKER' not in response.text
    assert response.headers['cache-control']=='no-store'
    response=await client.put(base(ready)+'/profile',headers=ready['owner'],content=b'x'*65537)
    assert response.status_code==413


async def test_membership_revoked_and_plan_idor(client,ready):
    source,_=await saved(client,ready)
    assert (await client.get(base(ready)+'/plans/'+str(uuid4()),headers=ready['owner'])).status_code==404
    async with Session.begin() as db:await db.execute(delete(Member).where(Member.user_id==ready['user_id'],Member.workspace_id==ready['workspace']))
    assert (await client.get(base(ready)+'/profiles/'+source['id']+'/versions/1',headers=ready['owner'])).status_code==404
