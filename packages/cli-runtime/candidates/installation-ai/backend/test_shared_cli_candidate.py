"""Candidate execution tests: synthetic identity, native ACL/lease/ledger/SQL.

No production API, provider, credential volume, login cache or quota is used.
"""
import asyncio
import importlib.util
from pathlib import Path
from uuid import uuid4
from types import SimpleNamespace
import pytest
from sqlalchemy import select, text, func
from sqlalchemy.exc import DBAPIError
from pao.config import settings
from pao.db import Session
from pao.models import (Workspace, Member, User, ChatSession, Run, CliModelConnection,
    CliModelDispatch, LlmAttempt, TenantModelLease, ToolCall, now)
from pao.modules.installation_ai import service as common
from pao.modules.installation_ai.models import InstallationAIResource
from pao.modules.cli_connections import shared, service, gateway
from pao.modules.engines.service import choose_config, pin_run, gateway_for_run, checked_snapshot
from pao.modules.engines.contract import EngineFailure
from pao.modules.chat.ledger import AccountingEngine, reserve
from pao_cli_runtime.contracts import Outcome


@pytest.fixture
async def common_cli(identity, monkeypatch):
    for name in ('installation_ai_enabled','cli_connections_enabled','engine_contract_enabled','chat_features_enabled'):
        monkeypatch.setattr(settings(), name, True)
    monkeypatch.setattr(settings(), 'installation_ai_manager_ids', [identity['user_id']])
    monkeypatch.setattr(settings(), 'cli_device_id', str(uuid4()))
    async with Session.begin() as db:
        row = CliModelConnection(workspace_id=identity['workspace'],owner_id=identity['user_id'],
            device_id=settings().cli_device_id,profile_id=str(uuid4()),request_key=str(uuid4()),
            model='orchestrator-A',status='connected',version=1,
            binary_sha256='3e2584f3f3829a43a0495011a1cecb2facbe64a2403e2b682351fd9c2983f970',
            binary_version='0.157.1',runtime_image_id='sha256:'+'a'*64,auth_checked_at=now())
        db.add(row);await db.flush()
        await common.capture(db,identity['user_id'],identity['workspace'],row.id,'cli',[
            {'model':'orchestrator-A','reasoning_efforts':['low','high']},
            {'model':'specialist-B','reasoning_efforts':['low','high']}])
        resource = await db.scalar(select(InstallationAIResource))
        return resource.id,row.id


@pytest.fixture
async def synthetic_identity(monkeypatch,client,identity,common_cli):
    async def admitted(db, resource):
        assert resource.provider == 'codex_cli' and resource.source_kind == 'cli'
    monkeypatch.setattr(shared, 'admit', admitted)
    response=await client.put('/v1/installation-ai/'+common_cli[0],headers=identity['owner'],json={
        'request_key':str(uuid4()),'expected_revision':1,'enabled':True,'is_default':False,'default_model':'orchestrator-A'})
    assert response.status_code==200,response.text


async def run_for(identity, common_cli, *, role='operator', model='specialist-B', effort='high', same_sme=False):
    async with Session.begin() as db:
        uid = await db.scalar(select(User.id).where(User.email=='other@example.test'))
        if same_sme:
            wid=identity['workspace'];(await db.get(Member,(wid,uid))).role=role
        else:
            workspace=Workspace(name='Synthetic independent caller');db.add(workspace);await db.flush()
            wid=workspace.id;db.add(Member(workspace_id=wid,user_id=uid,role=role));await db.flush()
        chat=ChatSession(workspace_id=wid,user_id=uid,memory_enabled=False,
            chat_profile={'policy':{'privacy':'cloud_allowed'},**({'enterprise_ai_read_only':True} if role=='viewer' else {})})
        db.add(chat);await db.flush()
        chat.engine_config=await choose_config(db,wid,'codex_cli',model,actor_id=uid,
            installation_resource_id=common_cli[0],reasoning_effort=effort)
        run=Run(workspace_id=wid,session_id=chat.id,status='running',prompt='Synthetic request',request_key=uuid4().hex)
        db.add(run);await db.flush();await pin_run(db,run,chat)
        return run,uid


async def new_attempt(run):
    return await reserve(run.id,uuid4().hex,'chat_final','codex_cli',run.engine_snapshot['model'],{'estimated_tokens':10},32)


async def test_provider_identity_gate_is_not_bypassed(client, identity, common_cli):
    response=await client.put('/v1/installation-ai/'+common_cli[0],headers=identity['owner'],json={
        'request_key':str(uuid4()),'expected_revision':1,'enabled':True,'is_default':False,'default_model':'orchestrator-A'})
    assert response.status_code==409 and response.json()['detail']=='installation_ai_cli_adapter_pending'
    async with Session.begin() as db:
        resource=await db.get(InstallationAIResource,common_cli[0])
        assert not resource.enabled and resource.revision==1
        resource.enabled=True;await db.flush()  # A bad persisted flag is not identity admission either.
        with pytest.raises(EngineFailure,match='installation_ai_cli_adapter_pending'):
            await common.config(db,identity['workspace'],identity['user_id'],None,common_cli[0],'specialist-B','high')


@pytest.mark.parametrize('role', ['operator','viewer'])
@pytest.mark.parametrize('effort', ['low','high'])
async def test_actual_gateway_carries_model_effort_and_accounts_caller(client,identity,common_cli,synthetic_identity,monkeypatch,role,effort):
    run,uid=await run_for(identity,common_cli,role=role,effort=effort)
    seen=[]
    class Transport:
        cleanup_verified=True
        async def invoke(self,pin,attempt,prompt,authorize,**selection):
            assert await authorize(pin)
            assert pin['workspace_id']==identity['workspace'] and pin['actor_id']==identity['user_id']
            assert pin['model']=='orchestrator-A'  # Source identity never repinned.
            assert selection=={'model':'specialist-B','reasoning_effort':effort}
            seen.append((attempt,selection))
            return Outcome('SYNTHETIC_OK',input_tokens=10,output_tokens=3)
    monkeypatch.setattr(gateway,'transport_for',lambda pin:Transport())
    async with Session() as db:engine=await gateway_for_run(db,await db.get(Run,run.id))
    wrapped=AccountingEngine(engine,run)
    chunks=[v async for v in wrapped.stream([{'role':'system','content':'PAO synthetic test'}, {'role':'user','content':run.prompt}])]
    assert ''.join(v.text for v in chunks)=='SYNTHETIC_OK' and len(seen)==1
    async with Session() as db:
        attempt=await db.scalar(select(LlmAttempt).where(LlmAttempt.run_id==run.id))
        dispatch=await db.scalar(select(CliModelDispatch).where(CliModelDispatch.attempt_id==attempt.id))
        assert attempt.user_id==uid and attempt.workspace_id==dispatch.workspace_id==run.workspace_id!=identity['workspace']
        assert attempt.model=='specialist-B' and attempt.status==dispatch.status=='completed'
        assert attempt.usage_state=='reported' and attempt.input_tokens==10
        assert not await db.scalar(select(TenantModelLease.id).where(TenantModelLease.attempt_id==attempt.id,TenantModelLease.status=='active'))
        assert await db.scalar(select(func.count()).select_from(ToolCall))==0
        assert (await db.get(CliModelConnection,common_cli[1])).model=='orchestrator-A'
        assert checked_snapshot((await db.get(Run,run.id)).engine_snapshot)['reasoning_effort']==effort


@pytest.mark.parametrize('change',['resource','catalog','profile','setup','source_membership','caller_membership','auth','epoch','cancel','privacy','manager'])
async def test_queued_work_rechecks_before_dispatch(client,identity,common_cli,synthetic_identity,monkeypatch,change):
    run,uid=await run_for(identity,common_cli);aid=await new_attempt(run)
    async with Session.begin() as db:
        if change=='resource':(await db.get(InstallationAIResource,common_cli[0])).enabled=False
        elif change=='catalog':(await db.get(InstallationAIResource,common_cli[0])).catalog=[{'model':'orchestrator-A','reasoning_efforts':[]}]
        elif change=='profile':(await db.get(CliModelConnection,common_cli[1])).version+=1
        elif change=='setup':(await db.get(CliModelConnection,common_cli[1])).setup_operation_id=str(uuid4())
        elif change=='source_membership':await db.delete(await db.get(Member,(identity['workspace'],identity['user_id'])))
        elif change=='caller_membership':await db.delete(await db.get(Member,(run.workspace_id,uid)))
        elif change=='auth':(await db.get(User,uid)).auth_version+=1
        elif change=='epoch':(await db.get(Workspace,run.workspace_id)).lifecycle_version+=1
        elif change=='cancel':(await db.get(Run,run.id)).cancel_requested=True
        elif change=='privacy':(await db.get(ChatSession,run.session_id)).chat_profile={'policy':{'privacy':'local_only'}}
        else:monkeypatch.setattr(settings(),'installation_ai_manager_ids',[])
    with pytest.raises(EngineFailure):await service.claim(run.id,aid)
    async with Session() as db:assert not await db.scalar(select(CliModelDispatch.id))


async def test_durable_fence_spans_caller_smes_and_unknown_is_not_retried(client,identity,common_cli,synthetic_identity):
    run,_=await run_for(identity,common_cli)
    other,_=await run_for(identity,common_cli,model='orchestrator-A',effort='low')
    first=await new_attempt(run);second=await new_attempt(other)
    dispatch,_=await service.claim(run.id,first)
    with pytest.raises(EngineFailure,match='cli_profile_busy'):await service.claim(other.id,second)
    await service.finish(dispatch,'failed',cleanup_verified=False)
    with pytest.raises(EngineFailure,match='cli_profile_busy'):await service.claim(other.id,second)
    with pytest.raises(EngineFailure,match='already_dispatched'):await service.claim(run.id,first)


@pytest.mark.parametrize('change',['resource','model','caller','workspace','profile','effort','custodian','lease'])
async def test_sql_guard_rejects_unpinned_dispatch_even_if_python_is_skipped(client,identity,common_cli,synthetic_identity,change):
    run,uid=await run_for(identity,common_cli);aid=await new_attempt(run)
    async with Session.begin() as db:
        if change=='resource':(await db.get(InstallationAIResource,common_cli[0])).enabled=False
        elif change=='model':(await db.get(InstallationAIResource,common_cli[0])).catalog=[{'model':'orchestrator-A','reasoning_efforts':['high']}]
        elif change=='effort':(await db.get(InstallationAIResource,common_cli[0])).catalog=[{'model':'specialist-B','reasoning_efforts':['low']}]
        elif change=='caller':await db.delete(await db.get(Member,(run.workspace_id,uid)))
        elif change=='custodian':await db.delete(await db.get(Member,(identity['workspace'],identity['user_id'])))
        elif change=='lease':
            lease=await db.scalar(select(TenantModelLease).where(TenantModelLease.attempt_id==aid))
            lease.status='released';lease.released_at=now()
        elif change=='profile':(await db.get(CliModelConnection,common_cli[1])).version+=1
        else:(await db.get(Workspace,run.workspace_id)).lifecycle_version+=1
    with pytest.raises(DBAPIError,match='cli_dispatch_native_attempt_required'):
        async with Session.begin() as db:
            db.add(CliModelDispatch(workspace_id=run.workspace_id,connection_id=common_cli[1],attempt_id=aid,status='dispatched'))
            await db.flush()


@pytest.mark.parametrize('outcome',['cancel','revoked','failed'])
async def test_result_recheck_and_cleanup_never_publish_or_retry(client,identity,common_cli,synthetic_identity,monkeypatch,outcome):
    run,uid=await run_for(identity,common_cli);aid=await new_attempt(run)
    class Transport:
        cleanup_verified=True
        async def invoke(self,pin,attempt,prompt,authorize,**selection):
            assert await authorize(pin)
            if outcome=='cancel':raise asyncio.CancelledError()
            if outcome=='failed':raise RuntimeError('SYNTHETIC_SECRET')
            async with Session.begin() as db:(await db.get(InstallationAIResource,common_cli[0])).enabled=False
            return Outcome('MUST_NOT_PUBLISH',input_tokens=1,output_tokens=1)
    monkeypatch.setattr(gateway,'transport_for',lambda pin:Transport())
    from pao.modules.chat.ledger import CURRENT_ATTEMPT
    token=CURRENT_ATTEMPT.set(aid)
    try:
        with pytest.raises((EngineFailure,asyncio.CancelledError)) as failure:
            await gateway.CliGateway(run.id,run.engine_snapshot).invoke([{'role':'user','content':'Synthetic'}])
        assert 'SYNTHETIC_SECRET' not in str(failure.value)
    finally:CURRENT_ATTEMPT.reset(token)
    async with Session() as db:
        row=await db.scalar(select(CliModelDispatch).where(CliModelDispatch.attempt_id==aid))
        assert row.status==('cancelled' if outcome=='cancel' else 'failed')
    with pytest.raises(EngineFailure):await service.claim(run.id,aid)


async def test_dispatch_history_cannot_be_rewritten_or_downgraded(client,identity,common_cli,synthetic_identity):
    run,_=await run_for(identity,common_cli);aid=await new_attempt(run)
    dispatch,_=await service.claim(run.id,aid);await service.finish(dispatch,'completed',cleanup_verified=True)
    async with Session.begin() as db:
        for statement in ('DELETE FROM cli_model_dispatches','UPDATE cli_model_dispatches SET workspace_id=:wid'):
            with pytest.raises(DBAPIError):
                async with db.begin_nested():await db.execute(text(statement),{'wid':identity['workspace']})
        from alembic.migration import MigrationContext
        from alembic.operations import Operations
        from pao.config import ROOT
        spec=importlib.util.spec_from_file_location('candidate_revision',ROOT/'apps/api/migrations/versions/0076_candidate_cli_selection.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        def denied(connection):
            with Operations.context(MigrationContext.configure(connection)):
                with pytest.raises(RuntimeError,match='Populated shared CLI history cannot be downgraded'):
                    module.downgrade()
        await (await db.connection()).run_sync(denied)
        assert await db.scalar(text('SELECT version_num FROM alembic_version'))=='0076'


def test_legacy_selection_cannot_smuggle_effort_or_another_model():
    base={'model':'same','cli_pin':{'model':'same'},'connection_authority':{'mode':'personal_cli'}}
    assert shared.invocation(base)=={}
    for value in ({**base,'reasoning_effort':'high'},{**base,'model':'other'}):
        with pytest.raises(EngineFailure):shared.invocation(value)


async def test_agent_model_and_effort_override_only_the_specialist_run(client,identity,common_cli,synthetic_identity):
    run,uid=await run_for(identity,common_cli,model='orchestrator-A',effort='low',same_sme=True)
    async with Session() as db:
        chat=await db.get(ChatSession,run.session_id)
        value=SimpleNamespace(engine_snapshot=None,workspace_id=run.workspace_id,brain_id=None,brain_context=None,
            studio_snapshot={'agent':{'payload':{'model_preference':{'provider':'codex_cli','model':'specialist-B',
                'installation_resource_id':common_cli[0],'reasoning_effort':'high'}}},
                'skill':{'payload':{'token_budget':2048,'output_tokens':128}}})
        await pin_run(db,value,chat)
        assert checked_snapshot(value.engine_snapshot)['model']=='specialist-B'
        assert value.engine_snapshot['reasoning_effort']=='high'
        assert shared.invocation(value.engine_snapshot)=={'model':'specialist-B','reasoning_effort':'high'}
        assert chat.engine_config['model']=='orchestrator-A' and chat.engine_config['reasoning_effort']=='low'
        assert value.engine_snapshot['cli_pin']==run.engine_snapshot['cli_pin']


@pytest.mark.parametrize('model,effort',[('not-in-catalog','high'),('specialist-B','max'),('specialist-B','--unsafe')])
async def test_invalid_selection_fails_before_any_dispatch(client,identity,common_cli,synthetic_identity,model,effort):
    async with Session() as db:
        with pytest.raises(EngineFailure):
            await choose_config(db,identity['workspace'],'codex_cli',model,actor_id=identity['user_id'],
                installation_resource_id=common_cli[0],reasoning_effort=effort)
        assert not await db.scalar(select(CliModelDispatch.id))
