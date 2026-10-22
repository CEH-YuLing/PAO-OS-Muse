"""P3.1 pins/capabilities/revocation without real provider calls or local data."""
import asyncio
import json
from uuid import uuid4

from cryptography.fernet import Fernet
import httpx
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from pao.config import settings
from pao.db import Session
from pao.gateway import Chunk, OllamaGateway
from pao.model_router import encrypt_key
from pao.models import ChatSession, Message, ModelProviderConnection, Run, RunEvent, AgentRun, Member
from pao.modules.engines.contract import capabilities, EngineFailure, ManagedEngine, require_capability
from pao.modules.engines.service import gateway_for_run, pin_run, checked_snapshot, local_url
from pao.runtime import execute_run


@pytest.fixture
def engines(monkeypatch):
    monkeypatch.setattr(settings(), 'engine_contract_enabled', True)
    monkeypatch.setattr(settings(), 'chat_features_enabled', True)
    monkeypatch.setattr(settings(), 'integration_encryption_key', Fernet.generate_key().decode())
    async def tags():
        return ['local-a', 'local-b']
    monkeypatch.setattr('pao.modules.engines.service.local_models', tags)
    monkeypatch.setattr('pao.modules.engines.api.local_models', tags)
    monkeypatch.setattr(settings(), 'ollama_model', 'local-a')


async def session(client, identity):
    value = await client.post('/v1/sessions', json={'workspace_id': identity['workspace']}, headers=identity['owner'])
    assert value.status_code == 201
    policy=await client.put(f"/v1/sessions/{value.json()['id']}/chat",headers=identity['owner'],json={'version':1,'policy':{'privacy':'cloud_allowed'}})
    assert policy.status_code==200,policy.text
    return value.json()['id']


async def run(client, identity, sid):
    value = await client.post('/v1/runs', json={'session_id': sid, 'message': 'synthetic P3 question', 'request_key': uuid4().hex}, headers=identity['owner'])
    assert value.status_code == 202, value.text
    return value.json()['id']


async def cloud(identity, model='cloud-a'):
    async with Session.begin() as db:
        row = ModelProviderConnection(workspace_id=identity['workspace'], provider='openai', model=model,
            api_key_ciphertext=encrypt_key('synthetic-test-only'), is_default=True)
        db.add(row)
        await db.flush()
        return row.id


async def test_local_pin_survives_global_change_and_preserves_history(client, identity, engines, monkeypatch):
    sid = await session(client, identity)
    selected = await client.put(f'/v1/sessions/{sid}/engine', headers=identity['owner'], json={'provider':'ollama','model':'local-b','version':1})
    assert selected.status_code == 200 and selected.json()['version'] == 2
    rid = await run(client, identity, sid)
    monkeypatch.setattr(settings(), 'ollama_model', 'changed-default')
    async with Session() as db:
        item = await db.get(Run, rid)
        gateway = await gateway_for_run(db, item)
        assert gateway.model_name == 'local-b'
        assert (await db.scalar(select(Message).where(Message.run_id == rid))).content == item.prompt
        assert (await db.get(ChatSession, sid)).engine_config['model'] == 'local-b'
    out = await client.get(f'/v1/runs/{rid}/engine', headers=identity['owner'])
    assert out.json()['snapshot']['model'] == 'local-b'
    assert 'local_url' not in out.text and 'credential' not in out.text and 'sha256' not in out.text


async def test_cloud_pin_survives_default_model_change_without_credential_egress(client, identity, engines):
    connection = await cloud(identity)
    sid = await session(client, identity)
    rid = await run(client, identity, sid)
    async with Session.begin() as db:
        row = await db.get(ModelProviderConnection, connection)
        row.model, row.is_default = 'cloud-b', False
    async with Session() as db:
        item = await db.get(Run, rid)
        gateway = await gateway_for_run(db, item)
        assert gateway.model_name == 'cloud-a'
    result = await client.get(f'/v1/sessions/{sid}/engine', headers=identity['owner'])
    assert result.json()['selection']['model'] == 'cloud-a'
    assert 'synthetic-test-only' not in result.text and 'connection_id' not in result.text


@pytest.mark.parametrize('change', ['rotate', 'disconnect', 'status'])
async def test_changed_cloud_connection_fails_worker_closed(client, identity, engines, change):
    connection = await cloud(identity)
    rid = await run(client, identity, await session(client, identity))
    async with Session.begin() as db:
        row = await db.get(ModelProviderConnection, connection)
        if change == 'rotate': row.api_key_ciphertext = encrypt_key('rotated-synthetic')
        elif change == 'disconnect': await db.delete(row)
        else: row.status = 'error'
    await execute_run({}, rid)
    async with Session() as db:
        value = await db.get(Run, rid)
        assert value.status == 'failed' and value.error_code == ('engine_connection_changed' if change == 'rotate' else 'engine_connection_unavailable')
        assert not await db.scalar(select(AgentRun.id).where(AgentRun.run_id == rid))


async def test_session_default_pins_once_and_next_runs_keep_model(client, identity, engines, monkeypatch):
    sid = await session(client, identity)
    rid = await run(client, identity, sid)
    async with Session.begin() as db:
        item = await db.get(Run, rid)
        item.status = 'cancelled'
    monkeypatch.setattr(settings(), 'ollama_model', 'local-b')
    second = await run(client, identity, sid)
    async with Session() as db:
        assert (await db.get(Run, second)).engine_snapshot['model'] == 'local-a'


async def test_error_default_connection_does_not_silently_become_local(client, identity, engines):
    connection = await cloud(identity)
    async with Session.begin() as db:
        (await db.get(ModelProviderConnection, connection)).status = 'error'
    sid = await session(client, identity)
    response = await client.post('/v1/runs', headers=identity['owner'], json={'session_id':sid,'message':'synthetic','request_key':uuid4().hex})
    assert response.status_code == 503 and response.json()['detail'] == 'engine_connection_unavailable'
    async with Session() as db:
        assert (await db.get(ChatSession, sid)).engine_config is None
        assert not await db.scalar(select(Run.id).where(Run.session_id == sid))
    selected = await client.get(f'/v1/sessions/{sid}/engine',headers=identity['owner'])
    assert selected.status_code == 200 and selected.json()['selection'] is None
    assert selected.json()['error'] == 'engine_connection_unavailable'
    recovered = await client.put(f'/v1/sessions/{sid}/engine',headers=identity['owner'],
        json={'provider':'ollama','model':'local-a','version':1})
    assert recovered.status_code == 200 and recovered.json()['selection']['provider'] == 'ollama'


async def test_knowledge_engine_pin_does_not_resolve_cloud_or_repin_chat(client, identity, engines):
    from pao.models import Run
    await cloud(identity)
    sid = await session(client, identity)
    async with Session.begin() as db:
        chat = await db.get(ChatSession, sid)
        item = Run(workspace_id=chat.workspace_id,session_id=sid,request_key=uuid4().hex,
                   prompt='fixture knowledge',brain_context={'knowledge':True})
        await pin_run(db,item,chat)
        assert item.engine_snapshot['provider'] == 'knowledge'
        assert item.engine_snapshot['model'] == 'pao-grounded-excerpts-v1'
        assert 'credential_binding' not in item.engine_snapshot and chat.engine_config is None


async def test_validation_never_echoes_untrusted_model_input(client, identity, engines):
    sid = await session(client, identity)
    response = await client.put(f'/v1/sessions/{sid}/engine',headers=identity['owner'],
        json={'provider':'custom-cli','model':'synthetic-sensitive-string','version':1,'api_key':'do-not-echo'})
    assert response.status_code == 422 and 'do-not-echo' not in response.text and 'synthetic-sensitive-string' not in response.text


async def test_revision_active_access_and_invalid_model_guards(client, identity, engines):
    sid = await session(client, identity)
    path = f'/v1/sessions/{sid}/engine'
    body = {'provider':'ollama','model':'local-a','version':1}
    for who in ('other', 'outsider'):
        assert (await client.get(path, headers=identity[who])).status_code == 404
        assert (await client.put(path, headers=identity[who], json=body)).status_code == 404
    assert (await client.put(path, headers=identity['owner'], json={**body,'model':'not-installed'})).status_code == 409
    assert (await client.put(path, headers=identity['owner'], json={**body,'version':99})).status_code == 409
    rid = await run(client, identity, sid)
    assert (await client.put(path, headers=identity['owner'], json={**body,'version':2})).status_code == 409
    assert (await client.get(f'/v1/runs/{rid}/engine', headers=identity['other'])).status_code == 404
    async with Session.begin() as db:
        member = await db.get(Member, (identity['workspace'], identity['user_id']))
        member.role = 'viewer'
    assert (await client.put(path, headers=identity['owner'], json=body)).status_code == 403


async def test_catalog_only_existing_workspace_connections_and_no_remote_discovery(client, identity, engines, monkeypatch):
    await cloud(identity)
    async def forbidden(*args, **kwargs): raise AssertionError('No remote discovery')
    monkeypatch.setattr('pao.model_router.fetch_models', forbidden)
    response = await client.get('/v1/engines', headers=identity['owner'], params={'workspace_id':identity['workspace']})
    assert response.status_code == 200
    assert [row['provider'] for row in response.json()['engines']] == ['ollama','openai']
    assert response.json()['engines'][1]['models'] == ['cloud-a']
    assert 'synthetic-test-only' not in response.text and 'ciphertext' not in response.text
    assert (await client.get('/v1/engines', headers=identity['outsider'], params={'workspace_id':identity['workspace']})).status_code == 404


async def test_engine_flag_off_fails_existing_selection_no_default_fallback(client, identity, engines, monkeypatch):
    sid = await session(client, identity)
    rid = await run(client, identity, sid)
    monkeypatch.setattr(settings(), 'engine_contract_enabled', False)
    await execute_run({}, rid)
    async with Session() as db:
        assert (await db.get(Run, rid)).error_code == 'engine_contract_disabled'
        (await db.get(Run, rid)).status = 'cancelled'
        await db.commit()
    response = await client.post('/v1/runs', headers=identity['owner'], json={'session_id':sid,'message':'second','request_key':uuid4().hex})
    assert response.status_code == 503 and response.json()['detail'] == 'engine_contract_disabled'


async def test_snapshot_db_immutable_and_legacy_not_retroactively_invented(client, identity, engines, monkeypatch):
    sid = await session(client, identity)
    rid = await run(client, identity, sid)
    async with Session() as db:
        with pytest.raises(DBAPIError):
            await db.execute(text("UPDATE runs SET engine_snapshot=NULL WHERE id=:id"), {'id':rid})
        await db.rollback()
        value = (await db.get(Run, rid)).engine_snapshot
        with pytest.raises(EngineFailure): checked_snapshot({**value,'model':'tampered'})
    legacy_sid=await session(client,identity)
    monkeypatch.setattr(settings(), 'engine_contract_enabled', False)
    monkeypatch.setattr(settings(), 'chat_features_enabled', False)
    legacy = await run(client, identity, legacy_sid)
    response = await client.get(f'/v1/runs/{legacy}/engine', headers=identity['owner'])
    assert response.json() == {'snapshot':None,'status':'legacy_unknown'}


async def test_worker_emits_existing_sse_schema_with_safe_engine_data(client, identity, engines):
    from pao.schemas import EventOut
    rid = await run(client, identity, await session(client, identity))
    class Fake:
        provider_name,model_name='ollama','local-a'
        async def stream(self, messages, max_tokens=None): yield Chunk(text='P3 fixture response')
    await execute_run({'gateway':Fake()}, rid)
    async with Session() as db:
        item = await db.get(Run, rid)
        assert item.status == 'completed'
        events = list(await db.scalars(select(RunEvent).where(RunEvent.run_id == rid)))
        for event in events: EventOut.model_validate(event)
        assert next(e for e in events if e.type == 'run.started').data['engine']['model'] == 'local-a'
        agent = await db.scalar(select(AgentRun).where(AgentRun.run_id == rid))
        assert agent.model == 'local-a' and agent.usage == {}  # unknown, not zero


@pytest.mark.parametrize('url', ['https://example.test:443','http://169.254.169.254:80','http://user:pass@127.0.0.1:11434','http://127.0.0.1:11434/escape','http://localhost:11434/?x=1'])
def test_engine_local_endpoint_rejects_remote_credentials_paths(url):
    with pytest.raises(EngineFailure): local_url(url)


def test_adapter_capabilities_do_not_grant_vision_native_tools_or_shell():
    for provider in ('ollama','openai','anthropic','gemini','openrouter'):
        value = capabilities(provider)
        assert value['text'] and value['stream'] and not value['vision'] and not value['native_tools']
        assert value['cancel'] == 'client_stream' and value['usage'] == 'reported_optional'
    with pytest.raises(EngineFailure): require_capability(capabilities('knowledge'), 'tools')
    with pytest.raises(EngineFailure): capabilities('custom-cli')


async def test_managed_stream_cancel_closes_resource_and_unknown_usage():
    started, closed = asyncio.Event(), asyncio.Event()
    class Fake:
        provider_name, model_name = 'ollama','synthetic'
        async def stream(self, messages, max_tokens=None):
            try:
                yield Chunk(text='fixture')
                started.set()
                await asyncio.Event().wait()
            finally: closed.set()
    engine = ManagedEngine(Fake(), capabilities('ollama'))
    async def consume():
        async for chunk in engine.stream([]): assert chunk.usage == {}
    task = asyncio.create_task(consume())
    await asyncio.wait_for(started.wait(), 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError): await task
    assert closed.is_set()


@pytest.mark.parametrize('exception,code', [(httpx.ReadTimeout('private-secret'),'engine_timeout'), (RuntimeError('private-secret'),'engine_unavailable')])
async def test_managed_errors_redacted(exception, code):
    class Fake:
        provider_name, model_name = 'ollama','synthetic'
        async def stream(self, messages, max_tokens=None):
            raise exception
            yield
    with pytest.raises(EngineFailure) as error:
        async for _ in ManagedEngine(Fake(), capabilities('ollama')).stream([]): pass
    assert str(error.value) == code and 'private-secret' not in str(error.value)


async def test_capability_denial_happens_before_adapter_call():
    class Fake:
        provider_name, model_name = 'ollama','synthetic'
        async def plan(self, messages): raise AssertionError('Must not call')
    with pytest.raises(EngineFailure, match='engine_capability_denied'):
        await ManagedEngine(Fake(), capabilities('knowledge')).plan([])


async def test_ollama_pinned_object_does_not_follow_settings(monkeypatch):
    value = OllamaGateway(model='fixed', url='http://127.0.0.1:11434')
    monkeypatch.setattr(settings(), 'ollama_model', 'new-default')
    monkeypatch.setattr(settings(), 'ollama_url', 'http://127.0.0.1:11435')
    assert value.model_name == 'fixed' and value.base_url == 'http://127.0.0.1:11434'
