"""Synthetic catalog/change/fencing tests; no provider or credential I/O."""
from uuid import uuid4
import pytest
from sqlalchemy import select
from pao.db import Session
from pao.config import settings
from pao.models import CliModelConnection,Member,User,PersonalCliPolicy,now
from pao.modules.cli_connections import model_api,runtime,personal
from pao.modules.cli_connections.catalog import models,CatalogTransport
from pao_cli_runtime.contracts import CliFailure

class FakeCatalog:
    failure=False;cleanup=True;hook=None;calls=0
    def __init__(self,pin,operation,authorize):self.cleanup_verified=False;self.authorize=authorize
    async def read(self):
        FakeCatalog.calls+=1;await self.authorize()
        if FakeCatalog.hook:await FakeCatalog.hook()
        if FakeCatalog.failure:raise RuntimeError('SECRET_SENTINEL')
        return [{'model':'supported-model','is_default':True}]
    async def close(self):self.cleanup_verified=FakeCatalog.cleanup

@pytest.fixture
async def own(identity,monkeypatch):
    config={'device_id':str(uuid4()),'image_id':'sha256:'+'a'*64,'binary_sha256':'3e2584f3f3829a43a0495011a1cecb2facbe64a2403e2b682351fd9c2983f970','binary_version':'0.157.1','host_runtime_sha256':'b'*64}
    monkeypatch.setattr(settings(),'cli_connections_enabled',True)
    monkeypatch.setattr(runtime,'device_config',lambda:config);monkeypatch.setattr(runtime,'resolve',lambda pin:None)
    monkeypatch.setattr(model_api,'CatalogTransport',FakeCatalog)
    FakeCatalog.failure=False;FakeCatalog.cleanup=True;FakeCatalog.hook=None;FakeCatalog.calls=0
    async with Session.begin() as db:
        row=CliModelConnection(workspace_id=identity['workspace'],owner_id=identity['user_id'],device_id=config['device_id'],profile_id=str(uuid4()),request_key=str(uuid4()),model='unsupported-old',status='connected',version=1,binary_sha256=config['binary_sha256'],binary_version=config['binary_version'],runtime_image_id=config['image_id'],auth_checked_at=now())
        db.add(row);await db.flush();return row.id

def path(identity,own,action='models'):return f"/v1/workspaces/{identity['workspace']}/cli-connections/{own}/{action}"
def change(**extra):return {'version':1,'model':'supported-model','confirm_model_change':True,**extra}

async def test_catalog_whitelist_and_no_inference_or_model_change(client,identity,own):
    result=await client.post(path(identity,own),headers=identity['owner'],json={'version':1})
    assert result.status_code==200,result.text
    value=result.json();assert value['models']==[{'model':'supported-model','is_default':True}] and value['current_model']=='unsupported-old' and not value['inference_called']
    assert result.headers['cache-control']=='no-store'
    async with Session() as db:
        row=await db.get(CliModelConnection,own);assert row.version==1 and row.setup_operation_id is None

async def test_change_is_versioned_no_implicit_personal_repin(client,identity,own):
    from pao.modules.cli_connections.personal_api import router
    base=f"/v1/workspaces/{identity['workspace']}/personal-cli"
    saved=await client.put(base,headers=identity['owner'],json={'request_key':str(uuid4()),'expected_revision':0,'connection_id':own,'enabled':True,'make_default':True,'allow_personal_inference_ack':True})
    assert saved.status_code==200 and saved.json()['ready']
    result=await client.post(path(identity,own,'model'),headers=identity['owner'],json=change())
    assert result.status_code==200,result.text
    assert result.json()['version']==2 and result.json()['consent_required']
    view=(await client.get(base,headers=identity['owner'])).json();assert not view['ready'] and view['revision']==1
    async with Session() as db:
        row=await db.get(CliModelConnection,own);assert row.model=='supported-model' and row.setup_operation_id is None
        policy=await personal.policy(db,identity['workspace'],identity['user_id']);assert policy.content['source_pin']['model']=='unsupported-old'
    assert (await client.post(path(identity,own,'model'),headers=identity['owner'],json=change())).status_code==409

@pytest.mark.parametrize('extra',[{'confirm_model_change':False},{'model':'not-in-catalog'},{'version':2},{'version':True},{'command':'SECRET_SENTINEL'},{'model':'SECRET SENTINEL'},{'token':'SECRET_SENTINEL'}])
async def test_invalid_change_denied_redacted(client,identity,own,extra):
    result=await client.post(path(identity,own,'model'),headers=identity['owner'],json=change(**extra))
    assert result.status_code in (409,422) and 'SECRET' not in result.text
    async with Session() as db:assert (await db.get(CliModelConnection,own)).model=='unsupported-old'

@pytest.mark.parametrize('role',['viewer','operator','admin'])
async def test_other_actor_cannot_use_owners_profile(client,identity,own,role):
    async with Session.begin() as db:
        uid=await db.scalar(select(User.id).where(User.email=='other@example.test'));(await db.get(Member,(identity['workspace'],uid))).role=role
    response=await client.post(path(identity,own),headers=identity['other'],json={'version':1})
    assert response.status_code in (403,404) and FakeCatalog.calls==0

async def test_busy_setup_denied_before_external(client,identity,own):
    async with Session.begin() as db:(await db.get(CliModelConnection,own)).setup_operation_id=str(uuid4())
    assert (await client.post(path(identity,own),headers=identity['owner'],json={'version':1})).status_code==409
    assert FakeCatalog.calls==0

async def test_catalog_error_never_exposes_raw_provider_body(client,identity,own):
    FakeCatalog.failure=True
    result=await client.post(path(identity,own),headers=identity['owner'],json={'version':1})
    assert result.status_code==503 and 'SECRET' not in result.text
    async with Session() as db:assert (await db.get(CliModelConnection,own)).setup_operation_id is None

async def test_uncertain_cleanup_preserves_durable_fence(client,identity,own):
    FakeCatalog.cleanup=False
    result=await client.post(path(identity,own,'model'),headers=identity['owner'],json=change());assert result.status_code==503
    async with Session() as db:
        row=await db.get(CliModelConnection,own);assert row.setup_operation_id and row.model=='unsupported-old'

async def test_role_revoked_during_catalog_denies_publication(client,identity,own):
    async def demote():
        async with Session.begin() as db:(await db.get(Member,(identity['workspace'],identity['user_id']))).role='viewer'
    FakeCatalog.hook=demote
    result=await client.post(path(identity,own,'model'),headers=identity['owner'],json=change());assert result.status_code==403
    async with Session() as db:
        row=await db.get(CliModelConnection,own);assert row.model=='unsupported-old' and row.setup_operation_id is None

@pytest.mark.parametrize('value',[{}, {'data':[]},{'data':[{'model':'bad model','isDefault':True}]},{'data':[{'model':'ok','isDefault':'true'}]}, {'data':[{'model':'ok','isDefault':True}],'nextCursor':'more'}, {'data':[{'model':'a','isDefault':True},{'model':'b','isDefault':True}]}])
def test_catalog_invalid_shapes_fail_closed(value):
    with pytest.raises(CliFailure):models(value)

def test_catalog_discards_account_metadata():
    value=models({'data':[{'model':'ok','isDefault':True,'email':'SECRET','token':'SECRET'}]})
    assert value==[{'model':'ok','is_default':True}]

async def test_catalog_transport_only_account_and_model_methods(monkeypatch):
    client=CatalogTransport.__new__(CatalogTransport);seen=[]
    async def opened():seen.append('open')
    async def rpc(n,m,p):seen.append(m);return {'account':{'type':'chatgpt'}}
    async def auth():seen.append('authorize')
    async def send(value):seen.append(value['method'])
    async def receive():return {'id':3,'result':{'data':[{'model':'ok','isDefault':True}]}}
    client.open=opened;client.rpc=rpc;client.authorize=auth;client.send=send;client.receive=receive
    assert await client.read()==[{'model':'ok','is_default':True}]
    assert seen==['open','account/read','authorize','model/list']

async def test_cli_planner_supplies_schema_and_preserves_user_input(monkeypatch):
    from pao.modules.cli_connections.gateway import CliGateway
    from pao_cli_runtime.contracts import Outcome
    from pao.agents import ExecutionPlan
    received=[]
    async def invoke(self,messages):
        received.extend(messages)
        return Outcome('{"goal":"small synthetic test","steps":[],"tools":[]}',mode='fixture')
    monkeypatch.setattr(CliGateway,'invoke',invoke)
    result=await CliGateway(str(uuid4()),{'model':'synthetic'}).plan([{'role':'system','content':'Old chat system'},{'role':'user','content':'untrusted example'}])
    assert result.steps==[] and received[1]=={'role':'user','content':'untrusted example'}
    assert 'PAO execution planner' in received[0]['content'] and 'Schema:' in received[0]['content'] and '"required"' in received[0]['content']

async def test_cli_planner_invalid_json_stays_failed(monkeypatch):
    from pao.modules.cli_connections.gateway import CliGateway
    from pao_cli_runtime.contracts import Outcome
    from pao.modules.engines.contract import EngineFailure
    async def invoke(self,messages):return Outcome('PAO_CODEX_OK',mode='fixture')
    monkeypatch.setattr(CliGateway,'invoke',invoke)
    with pytest.raises(EngineFailure,match='cli_plan_invalid'):
        await CliGateway(str(uuid4()),{'model':'synthetic'}).plan([{'role':'system','content':'test'},{'role':'user','content':'test'}])

@pytest.mark.parametrize('wrap',[lambda value:value,lambda value:'```json\n'+value+'\n```',lambda value:'```\n'+value+'\n```'])
async def test_cli_planner_accepts_only_lossless_json_envelopes(monkeypatch,wrap):
    from pao.modules.cli_connections.gateway import CliGateway
    from pao_cli_runtime.contracts import Outcome
    async def invoke(self,messages):return Outcome(wrap('{"goal":"synthetic","steps":[],"tools":[]}'))
    monkeypatch.setattr(CliGateway,'invoke',invoke)
    plan=await CliGateway(str(uuid4()),{'model':'synthetic'}).plan([{'role':'system','content':'test'},{'role':'user','content':'Only final text'}])
    assert plan.goal=='synthetic' and plan.steps==[] and plan.tools==[]

@pytest.mark.parametrize('raw',['Explanation: {"goal":"synthetic","steps":[],"tools":[]}',
    '```json\n{"goal":"synthetic","steps":[],"tools":[]}\n``` trailing',
    '{"goal":"first","goal":"second","steps":[],"tools":[]}',
    '```python\n{"goal":"synthetic","steps":[],"tools":[]}\n```'])
async def test_cli_planner_does_not_extract_or_repair_arbitrary_output(monkeypatch,raw):
    from pao.modules.cli_connections.gateway import CliGateway
    from pao.modules.engines.contract import EngineFailure
    from pao_cli_runtime.contracts import Outcome
    async def invoke(self,messages):return Outcome(raw)
    monkeypatch.setattr(CliGateway,'invoke',invoke)
    with pytest.raises(EngineFailure,match='cli_plan_invalid'):
        await CliGateway(str(uuid4()),{'model':'synthetic'}).plan([{'role':'system','content':'test'},{'role':'user','content':'test'}])

@pytest.mark.parametrize('explicit',[False,True])
async def test_new_personal_chat_has_no_implicit_local_memory(client,identity,own,explicit):
    base=f"/v1/workspaces/{identity['workspace']}/personal-cli"
    result=await client.put(base,headers=identity['owner'],json={'request_key':str(uuid4()),'expected_revision':0,'connection_id':own,'enabled':True,'make_default':True,'allow_personal_inference_ack':True});assert result.status_code==200
    response=await client.post('/v1/sessions',headers=identity['owner'],json={'workspace_id':identity['workspace'],**({'memory_enabled':True} if explicit else {})})
    assert response.status_code==201 and response.json()['memory_enabled'] is explicit
