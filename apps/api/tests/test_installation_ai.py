"""Shared resource / distinct tenant authority. Synthetic credentials only."""
from types import SimpleNamespace
from uuid import uuid4
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from pao.config import settings
from pao.db import Session
from pao.models import ModelProviderConnection, User, Workspace, Member, ChatSession, Run
from pao.model_router import encrypt_key
from pao.modules.installation_ai import service
from pao.modules.installation_ai.models import InstallationAIResource
from pao.modules.engines.service import choose_config, pin_run
from pao.modules.engines.contract import EngineFailure
from pao.modules.connections.model_fence import check_run


@pytest.fixture
async def resource(identity,monkeypatch):
    monkeypatch.setattr(settings(),'installation_ai_enabled',True)
    monkeypatch.setattr(settings(),'installation_ai_manager_ids',[identity['user_id']])
    monkeypatch.setattr(settings(),'engine_contract_enabled',True)
    async with Session.begin() as db:
        source=ModelProviderConnection(workspace_id=identity['workspace'],provider='openrouter',model='fixture-A',
            api_key_ciphertext=encrypt_key('SYNTHETIC-RESOURCE-KEY'),status='connected',is_default=False)
        db.add(source);await db.flush()
        await service.capture(db,identity['user_id'],identity['workspace'],source.id,'api',[
            {'model':'fixture-A','reasoning_efforts':['low','high'],'default_effort':'low'},'fixture-B'])
        row=await db.scalar(select(InstallationAIResource))
        return row.id,source.id


async def enable(client,identity,resource,**extra):
    body={'request_key':str(uuid4()),'expected_revision':1,'enabled':True,'is_default':True,'default_model':'fixture-A',**extra}
    return await client.put('/v1/installation-ai/'+resource[0],headers=identity['owner'],json=body)


async def test_read_does_not_enable_or_expose_credentials(client,identity,resource):
    response=await client.get('/v1/installation-ai',params={'workspace_id':identity['workspace']},headers=identity['other'])
    assert response.status_code==200 and response.headers['cache-control']=='no-store'
    value=response.json();assert not value['can_manage'] and not value['provider_calls']
    row=value['resources'][0];assert not row['enabled'] and row['error']=='installation_ai_resource_disabled'
    assert 'SYNTHETIC' not in response.text and '"source_id"' not in response.text and resource[1] not in response.text
    assert (await client.get('/v1/installation-ai',params={'workspace_id':identity['workspace']},headers=identity['outsider'])).status_code==404


async def test_only_installation_manager_can_save_not_any_sme_owner(client,identity,resource):
    body={'request_key':str(uuid4()),'expected_revision':1,'enabled':True,'default_model':'fixture-A'}
    assert (await client.put('/v1/installation-ai/'+resource[0],headers=identity['other'],json=body)).status_code==403
    async with Session.begin() as db:
        user=await db.scalar(select(User).where(User.email=='other@example.test'))
        (await db.get(Member,(identity['workspace'],user.id))).role='owner'
    assert (await client.put('/v1/installation-ai/'+resource[0],headers=identity['other'],json=body)).status_code==403
    assert (await enable(client,identity,resource)).status_code==200


async def test_member_selects_many_models_and_effort_without_grants(client,identity,resource):
    assert (await enable(client,identity,resource)).status_code==200
    async with Session.begin() as db:
        uid=await db.scalar(select(User.id).where(User.email=='other@example.test'))
        value=await choose_config(db,identity['workspace'],'openrouter','fixture-B',actor_id=uid,installation_resource_id=resource[0])
        assert value['model']=='fixture-B' and value['connection_authority']['actor_id']==uid
        assert (await db.get(ModelProviderConnection,resource[1])).model=='fixture-A'
        value=await choose_config(db,identity['workspace'],'openrouter','fixture-A',actor_id=uid,installation_resource_id=resource[0],reasoning_effort='high')
        assert value['reasoning_effort']=='high'
        with pytest.raises(EngineFailure,match='ai_effort_not_supported'):
            await choose_config(db,identity['workspace'],'openrouter','fixture-B',actor_id=uid,installation_resource_id=resource[0],reasoning_effort='high')
    response=await client.get('/v1/engines',params={'workspace_id':identity['workspace']},headers=identity['other'])
    assert response.status_code==200 and response.json()['scope']=='installation'
    assert response.json()['engines'][0]['models']==['fixture-A','fixture-B']


async def test_actual_engine_put_and_pin_keep_effort_and_never_change_source(client,identity,resource):
    assert (await enable(client,identity,resource)).status_code==200
    async with Session.begin() as db:
        chat=ChatSession(workspace_id=identity['workspace'],user_id=identity['user_id'],memory_enabled=False)
        db.add(chat);await db.flush();sid=chat.id
    selected=await client.put(f'/v1/sessions/{sid}/engine',headers=identity['owner'],json={
        'provider':'openrouter','model':'fixture-A','version':1,'installation_resource_id':resource[0],'reasoning_effort':'high'})
    assert selected.status_code==200,selected.text
    assert selected.json()['selection']['reasoning_effort']=='high'
    async with Session.begin() as db:
        chat=await db.get(ChatSession,sid)
        run=Run(workspace_id=identity['workspace'],session_id=sid,prompt='fixture',request_key=str(uuid4()))
        db.add(run);await db.flush();await pin_run(db,run,chat)
        assert run.engine_snapshot['reasoning_effort']=='high'
        await check_run(db,run)
        (await db.get(ModelProviderConnection,resource[1])).model='fixture-B'
        await db.flush();await check_run(db,run)
        run_id=run.id
    result=await client.get(f'/v1/runs/{run_id}/engine',headers=identity['owner'])
    assert result.status_code==200 and result.json()['snapshot']['reasoning_effort']=='high'
    assert 'credential' not in result.text and resource[1] not in result.text


async def test_cross_sme_inference_resource_does_not_copy_members_or_context(client,identity,resource):
    assert (await enable(client,identity,resource)).status_code==200
    async with Session.begin() as db:
        uid=await db.scalar(select(User.id).where(User.email=='other@example.test'))
        workspace=Workspace(name='Independent SME');db.add(workspace);await db.flush()
        db.add(Member(workspace_id=workspace.id,user_id=uid,role='operator'));await db.flush()
        value=await service.config(db,workspace.id,uid,None,resource[0],'fixture-B')
        assert value['connection_authority']['workspace_id']==workspace.id
        with pytest.raises(EngineFailure):await service.config(db,workspace.id,identity['user_id'],None,resource[0])
        assert not await db.scalar(select(ModelProviderConnection.id).where(ModelProviderConnection.workspace_id==workspace.id))


@pytest.mark.parametrize('change',['credential','disable','membership','source_membership','auth','manager'])
async def test_queued_pin_rechecks_all_authority(client,identity,resource,monkeypatch,change):
    assert (await enable(client,identity,resource)).status_code==200
    async with Session.begin() as db:
        uid=await db.scalar(select(User.id).where(User.email=='other@example.test'))
        value=await service.config(db,identity['workspace'],uid,None,resource[0],'fixture-A','high')
        chat=SimpleNamespace(user_id=uid,brand_id=None)
        run=SimpleNamespace(workspace_id=identity['workspace'],brain_id=None,brain_context=None)
        await service.check(db,run,chat,value)
        if change=='credential':(await db.get(ModelProviderConnection,resource[1])).api_key_ciphertext=encrypt_key('SYNTHETIC-ROTATED-KEY')
        elif change=='disable':(await db.get(InstallationAIResource,resource[0])).enabled=False
        elif change=='membership':await db.delete(await db.get(Member,(identity['workspace'],uid)))
        elif change=='source_membership':await db.delete(await db.get(Member,(identity['workspace'],identity['user_id'])))
        elif change=='auth':(await db.get(User,uid)).auth_version+=1
        else:monkeypatch.setattr(settings(),'installation_ai_manager_ids',[])
        await db.flush()
        with pytest.raises(EngineFailure):await service.check(db,run,chat,value)


async def test_save_idempotency_revision_and_immutable_history(client,identity,resource):
    key=str(uuid4())
    result=await enable(client,identity,resource,request_key=key)
    assert result.status_code==200
    assert (await enable(client,identity,resource,request_key=key)).json()['replayed']
    assert (await enable(client,identity,resource,request_key=key,default_model='fixture-B')).status_code==409
    assert (await enable(client,identity,resource)).status_code==409
    async with Session.begin() as db:
        with pytest.raises(DBAPIError):
            async with db.begin_nested():await db.execute(text("UPDATE installation_ai_revisions SET revision=revision+10"))


def test_reasoning_transport_is_real_not_only_ui():
    from pao.gateway import cloud_gateway,CloudProviderError
    gateway=cloud_gateway('openrouter','SYNTHETIC','fixture',reasoning_effort='high')
    assert gateway._reasoning({'temperature':0.4,'model':'fixture'})=={'model':'fixture','reasoning':{'effort':'high'}}
    with pytest.raises(CloudProviderError):cloud_gateway('gemini','SYNTHETIC','fixture',reasoning_effort='high')


@pytest.mark.parametrize('role',['operator','viewer'])
async def test_native_accounted_execution_uses_caller_sme_and_selected_effort(client,identity,resource,monkeypatch,role):
    from pao.models import LlmAttempt,ToolCall,MemoryJob
    from sqlalchemy import func
    from pao.gateway import Chunk
    from pao.runtime import execute_run
    monkeypatch.setattr(settings(),'chat_features_enabled',True)
    assert (await enable(client,identity,resource)).status_code==200
    async with Session.begin() as db:
        uid=await db.scalar(select(User.id).where(User.email=='other@example.test'))
        workspace=Workspace(name='Caller SME');db.add(workspace);await db.flush()
        db.add(Member(workspace_id=workspace.id,user_id=uid,role=role));wid=workspace.id
    seen=[]
    class Provider:
        provider_name='openrouter';model_name='fixture-A'
        async def stream(self,*args,**kwargs):yield Chunk(text='SYNTHETIC_OK',usage={'input_tokens':20,'output_tokens':10})
    def factory(provider,key,model,**kwargs):
        assert key=='SYNTHETIC-RESOURCE-KEY'
        seen.append((provider,model,kwargs));return Provider()
    monkeypatch.setattr('pao.modules.engines.service.cloud_gateway',factory)
    response=await client.post('/v1/sessions',headers=identity['other'],json={'workspace_id':wid})
    assert response.status_code==201,response.text
    sid=response.json()['id']
    choice=await client.put(f'/v1/sessions/{sid}/engine',headers=identity['other'],json={
        'provider':'openrouter','model':'fixture-A','version':1,'installation_resource_id':resource[0],'reasoning_effort':'high'})
    assert choice.status_code==200,choice.text
    result=await client.post('/v1/runs',headers=identity['other'],json={'session_id':sid,'request_key':uuid4().hex,'message':'Synthetic request'})
    assert result.status_code==202,result.text
    rid=result.json()['id'];await execute_run({},rid)
    async with Session() as db:
        run=await db.get(Run,rid)
        assert run.status=='completed' and run.response=='SYNTHETIC_OK',run.error_code
        attempt=await db.scalar(select(LlmAttempt).where(LlmAttempt.run_id==rid))
        assert attempt.workspace_id==wid and attempt.user_id==uid and attempt.usage_state=='reported'
        assert run.engine_snapshot['reasoning_effort']=='high'
        assert (run.engine_snapshot.get('interaction_mode')=='read_only_ai')==(role=='viewer')
        assert await db.scalar(select(func.count()).select_from(ToolCall).where(ToolCall.run_id==rid))==0
        assert await db.scalar(select(func.count()).select_from(MemoryJob).where(MemoryJob.run_id==rid))==0
    assert seen==[('openrouter','fixture-A',{'reasoning_effort':'high'})]
    assert (await client.get(f'/v1/runs/{rid}',headers=identity['owner'])).status_code==404


async def test_specialist_model_does_not_overwrite_chat_orchestrator(client,identity,resource,monkeypatch):
    monkeypatch.setattr(settings(),'chat_features_enabled',True)
    assert (await enable(client,identity,resource)).status_code==200
    async with Session.begin() as db:
        original=await service.config(db,identity['workspace'],identity['user_id'],None,resource[0],'fixture-A','high')
        chat=ChatSession(workspace_id=identity['workspace'],user_id=identity['user_id'],memory_enabled=False,engine_config=original)
        db.add(chat);await db.flush()
        run=SimpleNamespace(engine_snapshot=None,workspace_id=identity['workspace'],brain_id=None,brain_context=None,
            studio_snapshot={'agent':{'payload':{'model_preference':{'provider':'openrouter','model':'fixture-B','installation_resource_id':resource[0]}}},
                             'skill':{'payload':{'token_budget':2048,'output_tokens':128}}})
        with pytest.raises(EngineFailure,match='cloud_egress_denied'):await pin_run(db,run,chat)
        chat.chat_profile={'policy':{'privacy':'cloud_allowed'}}
        await pin_run(db,run,chat)
        assert run.engine_snapshot['model']=='fixture-B' and run.engine_snapshot['reasoning_effort'] is None
        assert chat.engine_config['model']=='fixture-A' and chat.engine_config['reasoning_effort']=='high'
        assert run.engine_snapshot['chat_policy']['max_calls']==1
