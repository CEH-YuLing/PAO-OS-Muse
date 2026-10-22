"""EA2.1 own-profile authority. Synthetic profiles/transport, no provider calls."""
from uuid import uuid4
import pytest
from sqlalchemy import select,func,text
from sqlalchemy.exc import DBAPIError
from pao.config import settings
from pao.db import Session
from pao.models import (CliModelConnection,PersonalCliPolicy,PersonalCliRevision,Member,User,
    Workspace,ChatSession,Run,TenantConnectionGrant,LlmAttempt,CliModelDispatch,now)
from pao.modules.cli_connections import personal,service,gateway
from pao.modules.engines.contract import EngineFailure,ManagedEngine,capabilities
from pao.modules.engines.service import choose_config,default_config,pin_run
from pao.modules.connections.model_fence import check_run
from pao.modules.chat.ledger import AccountingEngine,reserve
from pao_cli_runtime.contracts import Outcome

@pytest.fixture
async def own(client,identity,monkeypatch):
    monkeypatch.setattr(settings(),'cli_connections_enabled',True)
    monkeypatch.setattr(settings(),'cli_device_id',str(uuid4()))
    monkeypatch.setattr(settings(),'engine_contract_enabled',True)
    monkeypatch.setattr(settings(),'chat_features_enabled',True)
    async with Session.begin() as db:
        row=CliModelConnection(workspace_id=identity['workspace'],owner_id=identity['user_id'],provider='codex_cli',
            model='synthetic-model',device_id=settings().cli_device_id,profile_id=str(uuid4()),request_key=str(uuid4()),
            status='connected',version=1,binary_sha256='3e2584f3f3829a43a0495011a1cecb2facbe64a2403e2b682351fd9c2983f970',
            binary_version='0.157.1',runtime_image_id='sha256:'+'a'*64,auth_checked_at=now())
        db.add(row);await db.flush();return row.id

def path(identity):return f"/v1/workspaces/{identity['workspace']}/personal-cli"
def body(own,revision=0,**extra):return {'request_key':str(uuid4()),'expected_revision':revision,'enabled':True,
    'connection_id':own,'make_default':True,'allow_personal_inference_ack':True,**extra}
async def enable(client,identity,own,**extra):
    result=await client.put(path(identity),headers=identity['owner'],json=body(own,**extra));assert result.status_code==200,result.text
    return result.json()


async def cache_models(identity,own,choices=None):
    from pao.modules.cli_connections import model_catalog
    async with Session.begin() as db:
        await db.scalar(select(Workspace.id).where(Workspace.id==identity['workspace']).with_for_update())
        row=await db.get(CliModelConnection,own)
        saved=await model_catalog.capture(db,identity['workspace'],identity['user_id'],service.pin(row),choices or [
            {'model':'synthetic-model','display_name':'Model ban đầu'},
            {'model':'second-model','display_name':'Model thứ hai'},
            {'model':'third-model','display_name':'Model thứ ba'}])
        return saved.id


async def test_full_model_catalog_does_not_activate_or_change_profile(client,identity,own):
    await cache_models(identity,own)
    read=(await client.get(path(identity),headers=identity['owner'])).json()
    assert not read['enabled'] and not read['ready'] and read['revision']==0
    saved=await enable(client,identity,own)
    assert saved['revision']==2 and saved['ready']
    from pao.modules.engines.api import personal_engines
    async with Session() as db:
        rows=await personal_engines(db,identity['workspace'],identity['user_id'])
        assert rows[0]['models']==['synthetic-model','second-model','third-model']
        assert rows[0]['model_details'][1]['display_name']=='Model thứ hai'
        assert rows[0]['personal_cli_source_id']==own
        assert (await db.get(CliModelConnection,own)).model=='synthetic-model'
        assert (await personal.policy(db,identity['workspace'],identity['user_id'])).content['source_pin']['model']=='synthetic-model'


async def test_two_chats_choose_different_models_without_repinning_profile(client,identity,own):
    await enable(client,identity,own)
    record=await cache_models(identity,own)
    async with Session.begin() as db:
        configs=[await choose_config(db,identity['workspace'],'codex_cli',model,actor_id=identity['user_id'],personal_cli_source_id=own)
                 for model in ('second-model','third-model')]
        assert [c['cli_pin']['model'] for c in configs]==['second-model','third-model']
        assert configs[0]['cli_model_catalog']['record_id']==record
        for config in configs:
            chat=ChatSession(workspace_id=identity['workspace'],user_id=identity['user_id'],memory_enabled=False,
                chat_profile={'policy':{'privacy':'cloud_allowed'}},engine_config=config)
            db.add(chat);await db.flush()
            run=Run(workspace_id=chat.workspace_id,session_id=chat.id,request_key=uuid4().hex,prompt='Synthetic text',status='running')
            db.add(run);await db.flush();await pin_run(db,run,chat);await check_run(db,run)
            assert run.engine_snapshot['model']==config['model']
        policy=await personal.policy(db,identity['workspace'],identity['user_id'])
        assert policy.revision==1 and policy.content['source_pin']['model']=='synthetic-model'


async def test_selected_model_reaches_native_accounted_transport(client,identity,own,monkeypatch):
    await enable(client,identity,own)
    await cache_models(identity,own)
    async with Session.begin() as db:
        config=await choose_config(db,identity['workspace'],'codex_cli','second-model',actor_id=identity['user_id'],personal_cli_source_id=own)
        chat=ChatSession(workspace_id=identity['workspace'],user_id=identity['user_id'],memory_enabled=False,
            chat_profile={'policy':{'privacy':'cloud_allowed'}},engine_config=config)
        db.add(chat);await db.flush()
        run=Run(workspace_id=chat.workspace_id,session_id=chat.id,request_key=uuid4().hex,prompt='Synthetic text',status='running')
        db.add(run);await db.flush();await pin_run(db,run,chat)
    seen=[]
    class Synthetic:
        cleanup_verified=True
        async def invoke(self,pin,aid,prompt,authorize):
            assert await authorize(pin);seen.append(pin['model'])
            return Outcome('SECOND_MODEL_OK',input_tokens=10,output_tokens=3)
    monkeypatch.setattr(gateway,'transport_for',lambda pin:Synthetic())
    wrapper=AccountingEngine(ManagedEngine(gateway.CliGateway(run.id,run.engine_snapshot),capabilities('codex_cli')),run)
    chunks=[v.text async for v in wrapper.stream([{'role':'system','content':'PAO'},{'role':'user','content':'Synthetic text'}])]
    assert chunks==['SECOND_MODEL_OK'] and seen==['second-model']
    async with Session() as db:
        attempt=await db.scalar(select(LlmAttempt).where(LlmAttempt.run_id==run.id))
        dispatch=await db.scalar(select(CliModelDispatch).where(CliModelDispatch.attempt_id==attempt.id))
        assert attempt.model=='second-model' and attempt.status==dispatch.status=='completed'


@pytest.mark.parametrize('change',['unknown_model','different_model','catalog_hash','profile_changed'])
async def test_database_multimodel_dispatch_rejects_unbound_native_attempt(client,identity,own,change):
    from pao.modules.engines.service import digest
    await enable(client,identity,own);await cache_models(identity,own)
    async with Session.begin() as db:
        config=await choose_config(db,identity['workspace'],'codex_cli','second-model',actor_id=identity['user_id'],personal_cli_source_id=own)
        chat=ChatSession(workspace_id=identity['workspace'],user_id=identity['user_id'],memory_enabled=False,
            chat_profile={'policy':{'privacy':'cloud_allowed'}},engine_config=config)
        db.add(chat);await db.flush()
        run=Run(workspace_id=chat.workspace_id,session_id=chat.id,request_key=uuid4().hex,prompt='Synthetic text',status='running')
        db.add(run);await db.flush();await pin_run(db,run,chat)
        if change=='catalog_hash':
            snapshot={k:v for k,v in run.engine_snapshot.items() if k!='sha256'}
            snapshot['cli_model_catalog']={**snapshot['cli_model_catalog'],'sha256':'0'*64}
            snapshot['sha256']=digest(snapshot);run.engine_snapshot=snapshot
    model={'unknown_model':'not-in-catalog','different_model':'third-model'}.get(change,'second-model')
    aid=await reserve(run.id,'synthetic:'+str(uuid4()),'chat_final','codex_cli',model,{'estimated_tokens':10},64)
    if change=='profile_changed':
        async with Session.begin() as db:(await db.get(CliModelConnection,own)).version+=1
    with pytest.raises(DBAPIError,match='cli_dispatch_native_attempt_required'):
        async with Session.begin() as db:
            db.add(CliModelDispatch(workspace_id=identity['workspace'],connection_id=own,attempt_id=aid,status='dispatched'))
            await db.flush()


async def test_catalog_refresh_preserves_old_selection_and_policy_history(client,identity,own):
    from pao.modules.cli_connections import model_catalog
    await enable(client,identity,own)
    first=await cache_models(identity,own)
    async with Session() as db:
        config=await choose_config(db,identity['workspace'],'codex_cli','second-model',actor_id=identity['user_id'],personal_cli_source_id=own)
    assert await cache_models(identity,own)==first
    second=await cache_models(identity,own,[{'model':'synthetic-model'},{'model':'new-model'}])
    assert second!=first
    async with Session() as db:
        row=await db.get(CliModelConnection,own)
        await service.check_source(db,identity['workspace'],config)
        assert (await personal.policy(db,identity['workspace'],identity['user_id'])).revision==1
        assert (await model_catalog.latest(db,identity['workspace'],identity['user_id'],service.pin(row))).id==second
        with pytest.raises(EngineFailure):
            await choose_config(db,identity['workspace'],'codex_cli','second-model',actor_id=identity['user_id'],personal_cli_source_id=own)
    result=await client.put(path(identity),headers=identity['owner'],json=body(own,revision=1))
    assert result.status_code==200 and result.json()['revision']==4


@pytest.mark.parametrize('change',['model','pin_model','catalog_hash','catalog_record','disconnect','version','other_actor'])
async def test_multimodel_tampering_and_scope_change_denied(client,identity,own,change):
    await enable(client,identity,own);await cache_models(identity,own)
    async with Session.begin() as db:
        config=await choose_config(db,identity['workspace'],'codex_cli','second-model',actor_id=identity['user_id'],personal_cli_source_id=own)
        if change=='model':config['model']='not-in-catalog'
        elif change=='pin_model':config['cli_pin']={**config['cli_pin'],'model':'third-model'}
        elif change=='catalog_hash':config['cli_model_catalog']={**config['cli_model_catalog'],'sha256':'0'*64}
        elif change=='catalog_record':config['cli_model_catalog']={**config['cli_model_catalog'],'record_id':str(uuid4())}
        elif change=='disconnect':(await db.get(CliModelConnection,own)).status='disconnected'
        elif change=='version':(await db.get(CliModelConnection,own)).version+=1
        else:config['connection_authority']={**config['connection_authority'],'actor_id':str(uuid4())}
        with pytest.raises(EngineFailure):await service.check_source(db,identity['workspace'],config)


async def test_forged_legacy_model_is_not_a_multimodel_selection(client,identity,own):
    await enable(client,identity,own)
    async with Session() as db:
        config=await personal.config(db,identity['workspace'],identity['user_id'])
        config['model']='not-in-catalog';config['cli_pin']={**config['cli_pin'],'model':'not-in-catalog'}
        with pytest.raises(EngineFailure):await service.check_source(db,identity['workspace'],config)


@pytest.mark.parametrize('change',[None,'off','disconnect','source_version','setup_pending','other_actor'])
async def test_installation_catalog_keeps_valid_personal_cli_without_discovery(client,identity,own,monkeypatch,change):
    from pao.modules.engines import api as engine_api
    from pao.modules.installation_ai import service as installation
    await enable(client,identity,own)
    monkeypatch.setattr(settings(),'installation_ai_enabled',True)
    async def installed(db,workspace,actor):
        return [{'provider':'openai','models':['synthetic-api'],'local':False,'error':None,
                 'installation_resource_id':'synthetic-installation'}]
    async def forbidden(*args,**kwargs):
        raise AssertionError('Catalogue must not discover models or call providers')
    monkeypatch.setattr(installation,'catalog',installed)
    monkeypatch.setattr(engine_api,'local_models',forbidden)
    async with Session.begin() as db:
        if change=='off':
            policy=await personal.policy(db,identity['workspace'],identity['user_id'])
            policy.content={**policy.content,'enabled':False}
        elif change=='disconnect':(await db.get(CliModelConnection,own)).status='disconnected'
        elif change=='source_version':(await db.get(CliModelConnection,own)).version+=1
        elif change=='setup_pending':(await db.get(CliModelConnection,own)).setup_operation_id=str(uuid4())
        before=await db.scalar(select(func.count()).select_from(PersonalCliRevision))
    headers=identity['other'] if change=='other_actor' else identity['owner']
    result=await client.get('/v1/engines',params={'workspace_id':identity['workspace']},headers=headers)
    assert result.status_code==200,result.text
    value=result.json()
    assert value['scope']=='installation' and value['provider_calls'] is False
    assert result.headers['cache-control']=='no-store'
    assert value['engines'][0]['installation_resource_id']=='synthetic-installation'
    own_sources=[row for row in value['engines'] if row['provider']=='codex_cli']
    assert len(own_sources)==(1 if change is None else 0)
    if own_sources:
        assert own_sources[0]['personal_cli_source_id']==own
        assert own_sources[0]['models']==['synthetic-model'] and own_sources[0]['error'] is None
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(PersonalCliRevision))==before
        assert await db.scalar(select(func.count()).select_from(TenantConnectionGrant))==0


async def test_metadata_read_is_self_only_and_not_activation(client,identity,own):
    result=await client.get(path(identity),headers=identity['owner']);assert result.status_code==200
    value=result.json();assert not value['enabled'] and value['revision']==0 and value['expires_at'] is None
    assert value['connections'][0]['id']==own and value['scope']=='local_personal_self_only'
    assert result.headers['cache-control']=='no-store' and not value['provider_calls']
    async with Session() as db:assert await db.scalar(select(func.count()).select_from(PersonalCliPolicy))==0


async def test_explicit_reconnect_repins_new_login_without_rewriting_old_policy(client,identity,own):
    await enable(client,identity,own,make_default=False)
    async with Session.begin() as db:
        row=await db.get(CliModelConnection,own);row.version+=1;row.auth_checked_at=now()
        original=(await personal.policy(db,identity['workspace'],identity['user_id'])).content
    state=(await client.get(path(identity),headers=identity['owner'])).json()
    assert not state['ready'] and state['enabled']
    result=await client.put(path(identity),headers=identity['owner'],json=body(own,revision=1,make_default=False))
    assert result.status_code==200,result.text
    assert result.json()['ready'] and not result.json()['make_default']
    async with Session() as db:
        old=await db.scalar(select(PersonalCliRevision).where(PersonalCliRevision.revision==1))
        assert old.content==original
        assert (await personal.config(db,identity['workspace'],identity['user_id']))['cli_pin']['source_version']==2

@pytest.mark.parametrize('role',['operator','analyst','viewer'])
async def test_non_managers_cannot_use_owner_profile(client,identity,own,role):
    async with Session.begin() as db:
        uid=await db.scalar(select(User.id).where(User.email=='other@example.test'));(await db.get(Member,(identity['workspace'],uid))).role=role
    assert (await client.put(path(identity),headers=identity['other'],json=body(own))).status_code==403

async def test_another_admin_cannot_use_or_read_owners_profile(client,identity,own):
    async with Session.begin() as db:
        uid=await db.scalar(select(User.id).where(User.email=='other@example.test'));(await db.get(Member,(identity['workspace'],uid))).role='admin'
    assert (await client.get(path(identity),headers=identity['other'])).json()['connections']==[]
    assert (await client.put(path(identity),headers=identity['other'],json=body(own))).status_code==409

@pytest.mark.parametrize('patch',[{'allow_personal_inference_ack':False},{'connection_id':None},{'expected_revision':5},
    {'enabled':'true'},{'token':'SYNTHETIC-SECRET'},{'ttl_minutes':60},{'actor_id':str(uuid4())},{'grantee_id':str(uuid4())}])
async def test_consent_schema_and_revision_fail_closed(client,identity,own,patch):
    result=await client.put(path(identity),headers=identity['owner'],json=body(own,**patch))
    assert result.status_code in (409,422) and 'SYNTHETIC-SECRET' not in result.text

async def test_no_grants_no_expiry_and_exact_request_replay(client,identity,own):
    data=body(own);first=await client.put(path(identity),headers=identity['owner'],json=data)
    repeat=await client.put(path(identity),headers=identity['owner'],json=data)
    assert first.json()['ready'] and repeat.json()['replayed'] and repeat.json()['revision']==1
    conflict=await client.put(path(identity),headers=identity['owner'],json={**data,'make_default':False});assert conflict.status_code==409
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(TenantConnectionGrant))==0
        assert await db.scalar(select(func.count()).select_from(PersonalCliRevision))==1

async def native_run(client,identity,own):
    await enable(client,identity,own)
    async with Session.begin() as db:
        chat=ChatSession(workspace_id=identity['workspace'],user_id=identity['user_id'],memory_enabled=False,
            chat_profile={'policy':{'privacy':'cloud_allowed'}});db.add(chat);await db.flush()
        chat.engine_config=await default_config(db,chat.workspace_id,actor_id=chat.user_id)
        run=Run(workspace_id=chat.workspace_id,session_id=chat.id,request_key=uuid4().hex,prompt='Synthetic text',status='running')
        db.add(run);await db.flush();await pin_run(db,run,chat)
    return run

async def test_new_chat_inherits_own_default_and_not_other_member(client,identity,own):
    await enable(client,identity,own)
    created=await client.post('/v1/sessions',headers=identity['owner'],json={'workspace_id':identity['workspace'],'title':'Synthetic'})
    assert created.status_code==201,created.text
    selection=await client.get(f"/v1/sessions/{created.json()['id']}/engine",headers=identity['owner'])
    assert selection.json()['selection']['personal_cli_source_id']==own
    async with Session() as db:
        uid=await db.scalar(select(User.id).where(User.email=='other@example.test'))
        assert await personal.default_config(db,identity['workspace'],uid) is None
        assert (await db.get(ChatSession,created.json()['id'])).chat_profile['policy']['cloud_references'] is False

async def test_explicit_selection_and_wrong_model_or_grant_denied(client,identity,own):
    await enable(client,identity,own)
    async with Session() as db:
        choice=await choose_config(db,identity['workspace'],'codex_cli','synthetic-model',actor_id=identity['user_id'],personal_cli_source_id=own)
        assert choice['connection_authority']['mode']=='personal_cli'
        for extra in [{'grant_id':str(uuid4())},{'enterprise_source_id':str(uuid4())}]:
            with pytest.raises(EngineFailure):await choose_config(db,identity['workspace'],'codex_cli','synthetic-model',actor_id=identity['user_id'],personal_cli_source_id=own,**extra)
        with pytest.raises(EngineFailure):await choose_config(db,identity['workspace'],'codex_cli','other-model',actor_id=identity['user_id'],personal_cli_source_id=own)

@pytest.mark.parametrize('change',['off','disconnect','source_version','role','auth','epoch','cancel','setup_pending'])
async def test_queued_or_running_job_rechecks_self_authority(client,identity,own,change):
    run=await native_run(client,identity,own)
    aid=await reserve(run.id,'synthetic:'+str(uuid4()),'chat_final','codex_cli','synthetic-model',{'estimated_tokens':10},64)
    async with Session.begin() as db:
        if change=='off':
            row=await personal.policy(db,identity['workspace'],identity['user_id']);row.content={**row.content,'enabled':False};row.revision+=1
        elif change=='disconnect':(await db.get(CliModelConnection,own)).status='disconnected'
        elif change=='source_version':(await db.get(CliModelConnection,own)).version+=1
        elif change=='role':(await db.get(Member,(identity['workspace'],identity['user_id']))).role='viewer'
        elif change=='auth':(await db.get(User,identity['user_id'])).auth_version+=1
        elif change=='epoch':(await db.get(Workspace,identity['workspace'])).lifecycle_version+=1
        elif change=='cancel':(await db.get(Run,run.id)).cancel_requested=True
        else:(await db.get(CliModelConnection,own)).setup_operation_id=str(uuid4())
    with pytest.raises(EngineFailure):await service.claim(run.id,aid)

async def test_native_accounting_dispatch_and_no_profile_sharing(client,identity,own,monkeypatch):
    run=await native_run(client,identity,own)
    class Synthetic:
        cleanup_verified=True
        async def invoke(self,pin,aid,prompt,authorize):
            assert pin['actor_id']==identity['user_id'] and await authorize(pin)
            return Outcome('Synthetic text',input_tokens=10,output_tokens=3)
    monkeypatch.setattr(gateway,'transport_for',lambda pin:Synthetic())
    engine=AccountingEngine(ManagedEngine(gateway.CliGateway(run.id,run.engine_snapshot),capabilities('codex_cli')),run)
    chunks=[v async for v in engine.stream([{'role':'system','content':'PAO'},{'role':'user','content':run.prompt}])]
    assert ''.join(v.text for v in chunks)=='Synthetic text'
    async with Session() as db:
        attempt=await db.scalar(select(LlmAttempt).where(LlmAttempt.run_id==run.id))
        dispatch=await db.scalar(select(CliModelDispatch).where(CliModelDispatch.attempt_id==attempt.id))
        assert attempt.status==dispatch.status=='completed' and attempt.input_tokens==10

async def test_invalid_default_never_falls_back_and_disable_still_works(client,identity,own):
    await enable(client,identity,own)
    async with Session.begin() as db:(await db.get(CliModelConnection,own)).status='disconnected'
    async with Session() as db:
        with pytest.raises(EngineFailure):await default_config(db,identity['workspace'],actor_id=identity['user_id'])
    denied=await client.post('/v1/sessions',headers=identity['owner'],json={'workspace_id':identity['workspace']})
    assert denied.status_code==409 and denied.json()['detail']=='cli_connection_unavailable'
    disabled=await client.put(path(identity),headers=identity['owner'],json=body(None,revision=1,enabled=False,allow_personal_inference_ack=False))
    assert disabled.status_code==200 and not disabled.json()['enabled']

async def test_workspace_scope_and_history_immutability(client,identity,own):
    await enable(client,identity,own)
    assert (await client.get(path({'workspace':str(uuid4())}),headers=identity['owner'])).status_code==404
    with pytest.raises(DBAPIError):
        async with Session.begin() as db:await db.execute(text('UPDATE personal_cli_revisions SET revision=9'))

async def test_old_request_replay_never_reenables_after_disable(client,identity,own):
    data=body(own)
    assert (await client.put(path(identity),headers=identity['owner'],json=data)).status_code==200
    assert (await client.put(path(identity),headers=identity['owner'],json=body(None,revision=1,enabled=False))).status_code==200
    replay=await client.put(path(identity),headers=identity['owner'],json=data)
    assert replay.status_code==200 and replay.json()['replayed'] and not replay.json()['enabled'] and replay.json()['revision']==2

async def test_revoke_during_inference_denies_publication(client,identity,own,monkeypatch):
    run=await native_run(client,identity,own)
    class Revoke:
        cleanup_verified=True
        invoked=False
        async def invoke(self,pin,aid,prompt,authorize):
            type(self).invoked=True
            assert await authorize(pin)
            async with Session.begin() as db:
                row=await personal.policy(db,identity['workspace'],identity['user_id']);row.content={**row.content,'enabled':False};row.revision+=1
            return Outcome('MUST NOT PUBLISH',input_tokens=10,output_tokens=3)
    monkeypatch.setattr(gateway,'transport_for',lambda pin:Revoke())
    wrapper=AccountingEngine(ManagedEngine(gateway.CliGateway(run.id,run.engine_snapshot),capabilities('codex_cli')),run)
    exposed=[]
    with pytest.raises(EngineFailure,match='personal_cli_not_enabled'):
        async for chunk in wrapper.stream([{'role':'system','content':'PAO'},{'role':'user','content':run.prompt}]):exposed.append(chunk.text)
    assert Revoke.invoked and exposed==[]
