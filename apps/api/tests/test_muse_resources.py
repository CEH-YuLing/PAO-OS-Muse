"""Muse installation registry/ledger boundary. All native calls are synthetic."""
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock
import pytest
from sqlalchemy import select
from pao.config import settings
from pao.db import Session
from pao.models import ChatSession,Run,User,Workspace,Member,LlmAttempt
from pao.modules.cli_connections import muse_client as native,muse_resource as muse,muse_execution
from pao.modules.installation_ai.models import InstallationAIResource
from pao.modules.installation_ai import service
from pao.modules.engines.service import choose_config,pin_run,gateway_for_run
from pao.modules.engines.contract import EngineFailure


@pytest.fixture
async def muse_source(identity,monkeypatch,tmp_path):
    for field in ('installation_ai_enabled','engine_contract_enabled','chat_features_enabled'):
        monkeypatch.setattr(settings(),field,True)
    monkeypatch.setattr(settings(),'installation_ai_manager_ids',[identity['user_id']])
    monkeypatch.setattr(native,'STATE',tmp_path/'muse.json')
    data={'account_state':'accountLogin','models':[{'model':'muse-fixture','display_name':'Muse fixture',
        'reasoning_efforts':['low','high'],'default_effort':'low','provider_output_modalities':['text']}],
        'observed_at':'2026-10-21T00:00:00+00:00','binary_version':native.VERSION,
        'binary_sha256':native.SHA,'schema_fingerprint':native.SCHEMA,'profile':'pao_isolated'}
    probe=AsyncMock(return_value=data);monkeypatch.setattr(native,'discover',probe)
    return data,probe


async def connect(client,identity):
    result=await client.post('/v1/muse-client',params={'workspace_id':identity['workspace']},headers=identity['owner'],
        json={'request_key':str(uuid4()),'expected_revision':0})
    assert result.status_code==200,result.text
    assert result.json()['inference_enabled'] and result.json()['connection_mode']=='text_adapter'
    async with Session() as db:return (await db.scalar(select(InstallationAIResource).where(InstallationAIResource.provider=='muse'))).id


async def test_connect_publishes_existing_registry_once_and_get_never_probes(client,identity,muse_source):
    data,probe=muse_source
    body={'request_key':str(uuid4()),'expected_revision':0};url='/v1/muse-client?workspace_id='+identity['workspace']
    first=await client.post(url,headers=identity['owner'],json=body)
    again=await client.post(url,headers=identity['owner'],json=body)
    assert first.status_code==again.status_code==200 and first.json()==again.json()
    result=await client.get('/v1/engines',params={'workspace_id':identity['workspace']},headers=identity['other'])
    assert result.status_code==200
    row=next(v for v in result.json()['engines'] if v['provider']=='muse')
    assert row['models']==['muse-fixture'] and row['error'] is None
    assert row['model_details'][0]['reasoning_efforts']==['low','high']
    cached=await client.get(url,headers=identity['other'])
    assert cached.status_code==200 and cached.headers['cache-control']=='no-store'
    assert 'binary_sha256' not in cached.text and 'source_stamp' not in cached.text
    assert probe.await_count==1


async def test_no_grants_needed_two_smes_but_actor_scope_separate(client,identity,muse_source):
    rid=await connect(client,identity)
    async with Session.begin() as db:
        other=await db.scalar(select(User).where(User.email=='other@example.test'))
        workspace=Workspace(name='Synthetic second SME');db.add(workspace);await db.flush()
        db.add(Member(workspace_id=workspace.id,user_id=other.id,role='admin'))
        first=await choose_config(db,identity['workspace'],'muse','muse-fixture',actor_id=identity['user_id'],installation_resource_id=rid)
        second=await choose_config(db,workspace.id,'muse','muse-fixture',actor_id=other.id,installation_resource_id=rid,reasoning_effort='high')
        assert first['reasoning_effort']=='low' and second['reasoning_effort']=='high'
        assert first['connection_authority']['workspace_id']!=second['connection_authority']['workspace_id']
        assert second['connection_authority']['actor_id']==other.id
        with pytest.raises(Exception):await choose_config(db,workspace.id,'muse','muse-fixture',actor_id=identity['user_id'],installation_resource_id=rid)


async def test_selection_budget_change_is_explicit_and_privacy_preserved(client,identity,muse_source):
    rid=await connect(client,identity)
    async with Session.begin() as db:
        chat=ChatSession(workspace_id=identity['workspace'],user_id=identity['user_id'],memory_enabled=False,
            chat_profile={'policy':{'privacy':'cloud_allowed','context_tokens':4096,'max_run_tokens':32768}})
        db.add(chat);await db.flush();sid=chat.id
    payload={'provider':'muse','model':'muse-fixture','installation_resource_id':rid,'version':1}
    result=await client.put(f'/v1/sessions/{sid}/engine',headers=identity['owner'],json=payload)
    assert result.status_code==200,result.text
    async with Session.begin() as db:
        chat=await db.get(ChatSession,sid)
        assert chat.chat_profile['policy']['context_tokens']==4096
        run=Run(workspace_id=identity['workspace'],session_id=sid,prompt='fixture',request_key=str(uuid4()))
        db.add(run);await db.flush()
        with pytest.raises(EngineFailure,match='muse_context_budget_too_small'):await pin_run(db,run,chat)
        # This deliberately refused synthetic admission must not remain queued:
        # changing the model while an active run exists is correctly forbidden.
        run.status='failed';run.error_code='muse_context_budget_too_small'
    result=await client.put(f'/v1/sessions/{sid}/engine',headers=identity['owner'],json={**payload,'version':2,'prepare_muse_context':True})
    assert result.status_code==200,result.text
    async with Session.begin() as db:
        chat=await db.get(ChatSession,sid);policy=chat.chat_profile['policy']
        assert policy['context_tokens']==32768 and policy['max_run_tokens']==65536 and policy['privacy']=='cloud_allowed'
        run=Run(workspace_id=identity['workspace'],session_id=sid,prompt='fixture',request_key=str(uuid4()))
        db.add(run);await db.flush();await pin_run(db,run,chat)
        assert run.engine_snapshot['provider']=='muse' and 'credential_binding' not in run.engine_snapshot
        gateway=await gateway_for_run(db,run)
        assert gateway.provider_name=='muse'


async def test_disconnect_and_refresh_invalidate_old_selection(client,identity,muse_source):
    rid=await connect(client,identity)
    async with Session.begin() as db:
        old=await service.config(db,identity['workspace'],identity['user_id'],None,rid,'muse-fixture','high')
        stamp=old['connection_authority']['source_stamp']
    result=await client.request('DELETE','/v1/muse-client',params={'workspace_id':identity['workspace']},headers=identity['owner'],
        json={'request_key':str(uuid4()),'expected_revision':1})
    assert result.status_code==200 and not result.json()['inference_enabled']
    async with Session() as db:
        row=await db.get(InstallationAIResource,rid)
        assert not row.enabled and row.source_stamp==stamp
        with pytest.raises(EngineFailure):await service.ready(db,row)


async def test_failed_publication_is_not_admitted_and_metadata_retry_reconciles(client,identity,muse_source,monkeypatch):
    original=muse.publish
    body={'request_key':str(uuid4()),'expected_revision':0};url='/v1/muse-client?workspace_id='+identity['workspace']
    monkeypatch.setattr(muse,'publish',AsyncMock(side_effect=EngineFailure('synthetic_publication_failure')))
    result=await client.post(url,headers=identity['owner'],json=body)
    assert result.status_code==409
    status=await client.get(url,headers=identity['owner'])
    assert status.status_code==200 and not status.json()['inference_enabled']
    monkeypatch.setattr(muse,'publish',original)
    again=await client.post(url,headers=identity['owner'],json=body)
    assert again.status_code==200 and again.json()['inference_enabled']
    assert muse_source[1].await_count==1


async def test_unknown_model_or_effort_never_dispatches(client,identity,muse_source):
    rid=await connect(client,identity)
    async with Session.begin() as db:
        for model,effort in [('not-a-model','low'),('muse-fixture','ultra')]:
            with pytest.raises(EngineFailure):await service.config(db,identity['workspace'],identity['user_id'],None,rid,model,effort)


async def test_manager_revocation_blocks_shared_resource(client,identity,muse_source,monkeypatch):
    rid=await connect(client,identity)
    monkeypatch.setattr(settings(),'installation_ai_manager_ids',[])
    async with Session() as db:
        with pytest.raises(EngineFailure,match='installation_ai_manager_revoked'):await service.ready(db,await db.get(InstallationAIResource,rid))


async def test_durable_attempt_cannot_dispatch_twice(client,identity,muse_source,monkeypatch):
    rid=await connect(client,identity)
    async with Session.begin() as db:
        config=await service.config(db,identity['workspace'],identity['user_id'],None,rid,'muse-fixture','low')
        chat=ChatSession(workspace_id=identity['workspace'],user_id=identity['user_id'],memory_enabled=False,
            engine_config=config,chat_profile={'policy':{'privacy':'cloud_allowed','context_tokens':32768,'max_run_tokens':65536}})
        db.add(chat);await db.flush()
        run=Run(workspace_id=identity['workspace'],session_id=chat.id,prompt='fixture',status='running',request_key=str(uuid4()))
        db.add(run);await db.flush();await pin_run(db,run,chat)
        row=LlmAttempt(workspace_id=run.workspace_id,user_id=chat.user_id,session_id=chat.id,run_id=run.id,
            provider='muse',model='muse-fixture',request_key='fixture',source='chat_final',estimated_input_tokens=16020,reserved_output_tokens=512,trace={})
        db.add(row);await db.flush();attempt=row.id;gateway=muse_execution.MuseGateway(run.id,run.engine_snapshot)
    await gateway.authorize(attempt,claim=True)
    with pytest.raises(EngineFailure,match='engine_attempt_replay_denied'):await gateway.authorize(attempt,claim=True)
    await gateway.authorize(attempt)
    async with Session.begin() as db:(await db.get(Run,gateway.run_id)).cancel_requested=True
    with pytest.raises(EngineFailure,match='engine_run_not_active'):await gateway.authorize(attempt)
