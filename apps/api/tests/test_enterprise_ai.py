"""Native enterprise inheritance; synthetic keys, no provider/login calls."""
from uuid import uuid4
import pytest
from sqlalchemy import select, func
from fastapi import HTTPException
from pao.config import settings
from pao.db import Session
from pao.models import (ModelProviderConnection, EnterpriseAIPolicy, EnterpriseAIRevision,
    TenantConnectionGrant, CliModelConnection, Member, User, Workspace, ChatSession,
    Run, LlmAttempt, ToolCall, MemoryJob)
from pao.auth import issue_token
from pao.model_router import encrypt_key
from pao.modules.engines.service import choose_config, pin_run, digest
from pao.modules.engines.contract import EngineFailure
from pao.modules.connections import enterprise_ai
from pao.modules.connections.model_fence import check_run
from pao.gateway import Chunk


def endpoint(identity):
    return f"/v1/workspaces/{identity['workspace']}/enterprise-ai"


@pytest.fixture
async def source(client, identity, monkeypatch):
    monkeypatch.setattr(settings(), 'engine_contract_enabled', True)
    monkeypatch.setattr(settings(), 'chat_features_enabled', True)
    async with Session.begin() as db:
        row=ModelProviderConnection(workspace_id=identity['workspace'],provider='openai',model='synthetic-model',
            api_key_ciphertext=encrypt_key('SYNTHETIC-ENTERPRISE-KEY'),status='connected',is_default=False)
        db.add(row);await db.flush();return row.id


async def enable(client, identity, source, revision=0, **overrides):
    body={'request_key':str(uuid4()),'expected_revision':revision,'enabled':True,
          'connection_ids':[source],'default_connection_id':source,'allow_enterprise_inference_ack':True,**overrides}
    return await client.put(endpoint(identity),headers=identity['owner'],json=body)


async def viewer(identity):
    async with Session.begin() as db:
        user=await db.scalar(select(User).where(User.email=='other@example.test'))
        member=await db.get(Member,(identity['workspace'],user.id));member.role='viewer'
        return user.id


async def test_read_is_scoped_secret_free_and_disabled_without_owner_consent(client,identity,source):
    value=await client.get(endpoint(identity),headers=identity['other'])
    assert value.status_code==200 and value.headers['cache-control']=='no-store'
    assert not value.json()['enabled'] and not value.json()['can_manage']
    assert 'ciphertext' not in value.text and 'SYNTHETIC' not in value.text
    assert (await client.get(endpoint(identity),headers=identity['outsider'])).status_code==404
    async with Session() as db:assert await db.scalar(select(func.count()).select_from(EnterpriseAIPolicy))==0


@pytest.mark.parametrize('role',['operator','analyst','viewer'])
async def test_non_managers_cannot_enable(client,identity,source,role):
    async with Session.begin() as db:
        user=await db.scalar(select(User).where(User.email=='other@example.test'))
        (await db.get(Member,(identity['workspace'],user.id))).role=role
    result=await client.put(endpoint(identity),headers=identity['other'],json={
        'request_key':str(uuid4()),'expected_revision':0,'enabled':True,'connection_ids':[source],
        'default_connection_id':source,'allow_enterprise_inference_ack':True})
    assert result.status_code==403


@pytest.mark.parametrize('overrides',[
    {'allow_enterprise_inference_ack':False},{'default_connection_id':None},
    {'connection_ids':[]},{'connection_ids':lambda value:[value,value]},
    {'default_connection_id':str(uuid4())}, {'expected_revision':8}])
async def test_invalid_policy_denied(client,identity,source,overrides):
    overrides={k:(v(source) if callable(v) else v) for k,v in overrides.items()}
    assert (await enable(client,identity,source,**overrides)).status_code in (409,422)


async def test_no_per_user_grants_and_new_members_inherit(client,identity,source):
    result=await enable(client,identity,source);assert result.status_code==200,result.text
    async with Session.begin() as db:
        user=await db.scalar(select(User).where(User.email=='other@example.test'))
        value=await choose_config(db,identity['workspace'],'openai','synthetic-model',actor_id=user.id)
        assert value['connection_authority']['mode']=='enterprise_policy'
        assert value['connection_authority']['actor_id']==user.id
        assert await db.scalar(select(func.count()).select_from(TenantConnectionGrant))==0


async def test_idempotent_lost_ack_and_revision_conflict(client,identity,source):
    key=str(uuid4());first=await enable(client,identity,source,request_key=key)
    replay=await enable(client,identity,source,request_key=key)
    assert first.status_code==replay.status_code==200 and replay.json()['replayed']
    assert (await enable(client,identity,source)).status_code==409
    assert (await enable(client,identity,source,request_key=key,enabled=False)).status_code==409
    async with Session() as db:assert await db.scalar(select(func.count()).select_from(EnterpriseAIRevision))==1


async def configured_run(client,identity,source,actor_id=None):
    assert (await enable(client,identity,source)).status_code==200
    async with Session.begin() as db:
        chat=ChatSession(workspace_id=identity['workspace'],user_id=actor_id or identity['user_id'],memory_enabled=False,
            chat_profile={'policy':{'privacy':'cloud_allowed'}})
        db.add(chat);await db.flush()
        run=Run(workspace_id=chat.workspace_id,session_id=chat.id,prompt='Synthetic test',request_key=uuid4().hex,status='running')
        db.add(run);await db.flush();await pin_run(db,run,chat)
    return chat,run


@pytest.mark.parametrize('change',['disable','rotate','disconnect','membership','inactive','role','revision'])
async def test_execution_rechecks_exact_authority(client,identity,source,change):
    chat,run=await configured_run(client,identity,source)
    async with Session.begin() as db:
        if change in ('disable','revision'):
            row=await db.scalar(select(EnterpriseAIPolicy));row.revision+=1
            if change=='disable':row.content={**row.content,'enabled':False}
        elif change in ('rotate','disconnect'):
            row=await db.get(ModelProviderConnection,source)
            if change=='rotate':row.api_key_ciphertext=encrypt_key('NEW-SYNTHETIC')
            else:await db.delete(row)
        elif change=='membership':await db.delete(await db.get(Member,(chat.workspace_id,chat.user_id)))
        elif change=='inactive':(await db.get(User,chat.user_id)).active=False
        else:(await db.get(Member,(chat.workspace_id,chat.user_id))).role='viewer'
    async with Session() as db:
        with pytest.raises(EngineFailure):await check_run(db,run)


async def test_disable_still_works_after_key_removed(client,identity,source):
    assert (await enable(client,identity,source)).status_code==200
    async with Session.begin() as db:await db.delete(await db.get(ModelProviderConnection,source))
    result=await enable(client,identity,source,revision=1,enabled=False)
    assert result.status_code==200 and not result.json()['enabled']


async def test_membership_remove_and_reinvite_cannot_revive_old_run(client,identity,source):
    chat,run=await configured_run(client,identity,source)
    async with Session.begin() as db:
        workspace=await db.get(Workspace,chat.workspace_id)
        workspace.lifecycle_version+=2  # Native remove + accept-invite generations.
    async with Session() as db:
        with pytest.raises(EngineFailure,match='enterprise_ai_policy_changed'):await check_run(db,run)


async def test_cross_workspace_source_and_brand_denied(client,identity,source):
    async with Session.begin() as db:
        other=Workspace(name='Other SME');db.add(other);await db.flush()
        item=ModelProviderConnection(workspace_id=other.id,provider='openai',model='synthetic-model',
            api_key_ciphertext=encrypt_key('OTHER-SYNTHETIC'),status='connected',is_default=False)
        db.add(item);await db.flush();sid=item.id
    assert (await enable(client,identity,sid)).status_code==409
    assert (await enable(client,identity,source)).status_code==200
    async with Session() as db:
        with pytest.raises(EngineFailure):await enterprise_ai.pin(db,identity['workspace'],identity['user_id'],str(uuid4()),source)


async def test_personal_cli_is_never_shared_by_policy_ack(client,identity,source):
    async with Session.begin() as db:
        row=CliModelConnection(workspace_id=identity['workspace'],owner_id=identity['user_id'],provider='codex_cli',
            model='synthetic-model',device_id=str(uuid4()),profile_id=str(uuid4()),request_key=str(uuid4()),status='pending')
        db.add(row);await db.flush();cid=row.id
    result=await enable(client,identity,cid)
    assert result.status_code==409 and result.json()['detail']=='enterprise_cli_provisioning_required'
    async with Session() as db:
        assert (await db.get(CliModelConnection,cid)).status=='pending'
        assert await db.scalar(select(func.count()).select_from(TenantConnectionGrant))==0


async def test_viewer_own_text_chat_native_execution_no_planner_tools_or_memory(client,identity,source,monkeypatch):
    uid=await viewer(identity)
    assert (await enable(client,identity,source)).status_code==200
    monkeypatch.setattr(settings(),'agent_runtime_enabled',True)
    monkeypatch.setattr(settings(),'tools_enabled',True)
    monkeypatch.setattr(settings(),'memory_enabled',True)
    class Engine:
        provider_name='openai';model_name='synthetic-model'
        async def plan(self,*args):raise AssertionError('Viewer must never plan')
        async def stream(self,*args,**kwargs):yield Chunk(text='SYNTHETIC_OK',usage={'input_tokens':20,'output_tokens':10})
    import pao.runtime as runtime
    async def gateway(db,run):return Engine()
    monkeypatch.setattr(runtime,'gateway_for_run',gateway)
    session=await client.post('/v1/sessions',headers=identity['other'],json={'workspace_id':identity['workspace']})
    assert session.status_code==201,session.text
    sid=session.json()['id']
    response=await client.post('/v1/runs',headers=identity['other'],json={'session_id':sid,'request_key':uuid4().hex,'message':'Synthetic hello'})
    assert response.status_code==202,response.text
    rid=response.json()['id'];await runtime.execute_run({},rid)
    async with Session() as db:
        run=await db.get(Run,rid)
        assert run.status=='completed',run.error_code
        assert run.response=='SYNTHETIC_OK' and enterprise_ai.read_only(run)
        assert await db.scalar(select(func.count()).select_from(ToolCall).where(ToolCall.run_id==rid))==0
        assert await db.scalar(select(func.count()).select_from(MemoryJob).where(MemoryJob.run_id==rid))==0
        attempt=await db.scalar(select(LlmAttempt).where(LlmAttempt.run_id==rid))
        assert attempt.user_id==uid and attempt.status=='completed' and attempt.usage_state=='reported'
    assert (await client.get(f'/v1/runs/{rid}',headers=identity['owner'])).status_code==404


async def test_viewer_no_global_write_permission_and_no_legacy_chat_upgrade(client,identity,source):
    uid=await viewer(identity)
    denied=await client.post('/v1/sessions',headers=identity['other'],json={'workspace_id':identity['workspace']})
    assert denied.status_code==403
    assert (await enable(client,identity,source)).status_code==200
    async with Session.begin() as db:
        old=ChatSession(workspace_id=identity['workspace'],user_id=uid)
        db.add(old);await db.flush();sid=old.id
    result=await client.post('/v1/runs',headers=identity['other'],json={'session_id':sid,'request_key':uuid4().hex,'message':'test'})
    assert result.status_code==403
    from pao.access import membership
    from pao.auth import Principal
    async with Session() as db:
        with pytest.raises(HTTPException):await membership(db,identity['workspace'],Principal(uid,0),True)


async def test_queued_run_policy_revoked_before_credential_factory(client,identity,source,monkeypatch):
    assert (await enable(client,identity,source)).status_code==200
    session=await client.post('/v1/sessions',headers=identity['other'],json={'workspace_id':identity['workspace']})
    result=await client.post('/v1/runs',headers=identity['other'],json={'session_id':session.json()['id'],
        'request_key':uuid4().hex,'message':'Synthetic request'})
    assert result.status_code==202,result.text
    rid=result.json()['id']
    assert (await enable(client,identity,source,revision=1,enabled=False)).status_code==200
    import pao.modules.engines.service as engines
    def factory(*args):raise AssertionError('Revoked work must not decrypt/use a provider credential')
    monkeypatch.setattr(engines,'cloud_gateway',factory)
    from pao.runtime import execute_run
    await execute_run({},rid)
    async with Session() as db:
        row=await db.get(Run,rid)
        assert row.status=='failed' and row.error_code=='enterprise_ai_access_denied'
        assert await db.scalar(select(func.count()).select_from(LlmAttempt).where(LlmAttempt.run_id==rid))==0


async def test_new_owner_chat_default_inherits_without_rewriting_local_history(client,identity,source):
    old=await client.post('/v1/sessions',headers=identity['owner'],json={'workspace_id':identity['workspace']})
    assert (await enable(client,identity,source)).status_code==200
    new=await client.post('/v1/sessions',headers=identity['other'],json={'workspace_id':identity['workspace']})
    choice=await client.get('/v1/sessions/'+new.json()['id']+'/engine',headers=identity['other'])
    assert choice.status_code==200 and choice.json()['selection']['enterprise_source_id']==source
    async with Session() as db:
        prior=await db.get(ChatSession,old.json()['id'])
        assert prior.chat_profile is None and prior.engine_config is None


@pytest.mark.parametrize('role',['operator','viewer'])
async def test_http_selection_enterprise_source_without_individual_grant(client,identity,source,role):
    if role=='viewer':await viewer(identity)
    assert (await enable(client,identity,source)).status_code==200
    session=await client.post('/v1/sessions',headers=identity['other'],json={'workspace_id':identity['workspace']})
    sid=session.json()['id']
    response=await client.put(f'/v1/sessions/{sid}/engine',headers=identity['other'],json={
        'provider':'openai','model':'synthetic-model','version':1,'enterprise_source_id':source})
    assert response.status_code==200,response.text
    assert response.json()['selection']['enterprise_source_id']==source
    assert 'grant_id' not in response.json()['selection']


@pytest.mark.parametrize('body',[{'token':'DO_NOT_REFLECT'},'x'*9000])
async def test_bounded_secret_free_policy_validation(client,identity,source,body):
    result=await client.put(endpoint(identity),headers={**identity['owner'],'Content-Type':'application/json'},
        **({'json':body} if isinstance(body,dict) else {'content':body}))
    assert result.status_code in (413,422) and 'DO_NOT_REFLECT' not in result.text
    assert result.headers['cache-control']=='no-store'


async def test_history_only_managers_and_storage_is_append_only(client,identity,source):
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError
    assert (await enable(client,identity,source)).status_code==200
    assert (await client.get(endpoint(identity)+'/history',headers=identity['other'])).status_code==403
    result=await client.get(endpoint(identity)+'/history',headers=identity['owner'])
    assert result.json()['items'][0]['revision']==1 and 'stamp' not in result.text
    async with Session() as db:
        with pytest.raises(DBAPIError):await db.execute(text('UPDATE enterprise_ai_revisions SET revision=99'))
        await db.rollback()
