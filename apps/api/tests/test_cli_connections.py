"""Native CLI scope/consent/ledger tests. All identities and transports synthetic."""
import asyncio
from dataclasses import replace
from uuid import uuid4
import pytest
from sqlalchemy import select, func, text
from sqlalchemy.exc import DBAPIError
from pao.config import settings
from pao.db import Session
from pao.models import (CliModelConnection, CliModelDispatch, Workspace, Member, ChatSession, Run,
                        LlmAttempt, TenantModelLease, TenantConnectionReference, TenantConnectionGrant, now)
from pao.modules.engines.contract import EngineFailure, ManagedEngine, capabilities
from pao.modules.engines.service import choose_config, pin_run, checked_snapshot, digest, CLI_VERSION
from pao.modules.cli_connections import service, gateway
from pao.modules.chat.ledger import AccountingEngine, CURRENT_ATTEMPT, reserve
from pao_cli_runtime.contracts import Outcome


@pytest.fixture
def cli(monkeypatch):
    monkeypatch.setattr(settings(), 'cli_connections_enabled', True)
    monkeypatch.setattr(settings(), 'cli_device_id', str(uuid4()))
    monkeypatch.setattr(settings(), 'engine_contract_enabled', True)
    monkeypatch.setattr(settings(), 'chat_features_enabled', True)


def path(identity):
    return f"/v1/workspaces/{identity['workspace']}/cli-connections"


async def created(client, identity):
    response = await client.post(path(identity), headers=identity['owner'],
        json={'request_key': str(uuid4()), 'model': 'synthetic-model'})
    assert response.status_code == 201, response.text
    return response.json()


async def authenticated_fixture(client, identity):
    data = await created(client, identity)
    async with Session.begin() as db:
        row = await db.get(CliModelConnection, data['id'])
        row.status = 'connected'
        row.binary_sha256 = '3e2584f3f3829a43a0495011a1cecb2facbe64a2403e2b682351fd9c2983f970'
        row.binary_version = '0.157.1'
        row.runtime_image_id = 'sha256:' + 'a' * 64
        row.auth_checked_at = now()
    return data


async def grant(client, identity, data, *, grantee=None):
    base = f"/v1/workspaces/{identity['workspace']}/connection-inventory"
    body = {'kind': 'cli_model', 'connection_id': data['id'], 'expected_version': 1,
            'grantee_id': grantee or identity['user_id'], 'permission': 'read_only'}
    preview = await client.post(base + '/mapping-preview', headers=identity['owner'], json=body)
    if preview.status_code != 200:
        return preview
    staged = await client.post(base + '/references', headers=identity['owner'], json={**body,
        'preview_hash': preview.json()['preview_hash'], 'request_key': str(uuid4()), 'ttl_minutes': 60,
        'apply_data_only_ack': True})
    assert staged.status_code == 201, staged.text
    saved = staged.json()
    active = await client.post(base + f"/references/{saved['reference']['id']}/grants/{saved['grant']['id']}/activate-model",
        headers=identity['owner'], json={'reference_revision': 1, 'grant_revision': 1, 'request_key': str(uuid4()),
            'capability': 'model_inference', 'allow_model_inference_ack': True})
    return active, saved


async def pinned(client, identity):
    data = await authenticated_fixture(client, identity)
    activated, saved = await grant(client, identity, data)
    assert activated.status_code == 201, activated.text
    async with Session.begin() as db:
        chat = ChatSession(workspace_id=identity['workspace'], user_id=identity['user_id'],
                           chat_profile={'policy': {'privacy': 'cloud_allowed'}})
        db.add(chat)
        await db.flush()
        chat.engine_config = await choose_config(db, chat.workspace_id, 'codex_cli', 'synthetic-model',
            grant_id=saved['grant']['id'], actor_id=chat.user_id)
        run = Run(workspace_id=chat.workspace_id, session_id=chat.id, request_key=uuid4().hex,
                  prompt='Synthetic PAO request', status='running')
        db.add(run)
        await db.flush()
        await pin_run(db, run, chat)
    return data, saved, run


async def attempt(run):
    return await reserve(run.id, 'synthetic:' + str(uuid4()), 'chat_final', 'codex_cli',
                         'synthetic-model', {'estimated_tokens': 10}, 64)


async def test_registration_disabled_by_default(client, identity):
    response = await client.get(path(identity), headers=identity['owner'])
    assert response.status_code == 503


async def test_registration_is_not_auth_and_has_no_secret_columns(client, identity, cli):
    data = await created(client, identity)
    assert data['status'] == 'pending' and not data['authentication_ready']
    assert data['credentials_stored_in_PAO'] is False
    assert not any('token' in c.name or 'ciphertext' in c.name or 'secret' in c.name for c in CliModelConnection.__table__.columns)
    listed = await client.get(path(identity), headers=identity['owner'])
    assert listed.status_code == 200 and len(listed.json()['items']) == 1
    assert listed.headers['cache-control'] == 'no-store'


async def test_registration_idempotency_and_conflict(client, identity, cli):
    body = {'request_key': str(uuid4()), 'model': 'synthetic-model'}
    first = await client.post(path(identity), headers=identity['owner'], json=body)
    repeat = await client.post(path(identity), headers=identity['owner'], json=body)
    assert first.json()['id'] == repeat.json()['id'] and repeat.json()['replayed']
    changed = await client.post(path(identity), headers=identity['owner'], json={**body, 'model': 'other'})
    assert changed.status_code == 409


@pytest.mark.parametrize('extra', [{'token':'SECRET'}, {'secret':'SECRET'}, {'profile_id':str(uuid4())}, {'command':'cmd.exe'}])
async def test_registration_rejects_credentials_and_caller_profiles(client, identity, cli, extra):
    result = await client.post(path(identity), headers=identity['owner'],
        json={'request_key': str(uuid4()), 'model': 'synthetic-model', **extra})
    assert result.status_code == 422 and 'SECRET' not in result.text


@pytest.mark.parametrize('role', ['other', 'outsider'])
async def test_only_native_managers_can_configure(client, identity, cli, role):
    response = await client.get(path(identity), headers=identity[role])
    assert response.status_code == 403


async def test_unprovisioned_device_denied(client, identity, cli, monkeypatch):
    monkeypatch.setattr(settings(), 'cli_device_id', '')
    response = await client.post(path(identity), headers=identity['owner'],
        json={'request_key': str(uuid4()), 'model': 'synthetic-model'})
    assert response.status_code == 503


async def test_two_enterprises_get_independent_profiles(client, identity, cli):
    first = await created(client, identity)
    async with Session.begin() as db:
        second = Workspace(name='Other SME')
        db.add(second)
        await db.flush()
        db.add(Member(workspace_id=second.id, user_id=identity['user_id'], role='owner'))
    other = {**identity, 'workspace': second.id}
    next_profile = await created(client, other)
    assert first['profile_id'] != next_profile['profile_id']
    assert next_profile['status'] == 'pending'
    result = await client.post(path(other) + '/' + first['id'] + '/disconnect', headers=identity['owner'], json={'version': 1})
    assert result.status_code == 404


async def test_disconnect_version_and_no_logout(client, identity, cli):
    data = await authenticated_fixture(client, identity)
    result = await client.post(path(identity) + '/' + data['id'] + '/disconnect', headers=identity['owner'], json={'version': 1})
    assert result.status_code == 200 and result.json()['version'] == 2
    assert result.json()['provider_logout_performed'] is False
    stale = await client.post(path(identity) + '/' + data['id'] + '/disconnect', headers=identity['owner'], json={'version': 1})
    assert stale.status_code == 409


async def test_pending_auth_does_not_activate_grant(client, identity, cli):
    data = await created(client, identity)
    active, _ = await grant(client, identity, data)
    assert active.status_code == 403


async def test_personal_subscription_cannot_be_granted_to_another_user(client, identity, cli):
    data = await authenticated_fixture(client, identity)
    async with Session() as db:
        other = await db.scalar(select(Member.user_id).where(Member.workspace_id == identity['workspace'], Member.role == 'operator'))
    denied = await grant(client, identity, data, grantee=other)
    assert denied.status_code == 422


async def test_cli_snapshot_is_new_version_and_no_token_binding(client, identity, cli):
    data, saved, run = await pinned(client, identity)
    snapshot = checked_snapshot(run.engine_snapshot)
    assert snapshot['version'] == CLI_VERSION
    assert snapshot['connection_authority']['grant_id'] == saved['grant']['id']
    assert snapshot['cli_pin']['profile_id'] == data['profile_id']
    assert 'credential_binding' not in snapshot
    changed = {**snapshot, 'version': 'p3.1-v1'}
    changed['sha256'] = digest({k:v for k,v in changed.items() if k != 'sha256'})
    with pytest.raises(EngineFailure):
        checked_snapshot(changed)


async def test_no_implicit_cli_connection_or_grant(client, identity, cli):
    await authenticated_fixture(client, identity)
    async with Session() as db:
        with pytest.raises(EngineFailure, match='grant_denied'):
            await choose_config(db, identity['workspace'], 'codex_cli', 'synthetic-model', actor_id=identity['user_id'])


async def test_dispatch_requires_native_accounting(client, identity, cli):
    _, _, run = await pinned(client, identity)
    with pytest.raises(EngineFailure, match='accounting_required'):
        await service.claim(run.id, str(uuid4()))


async def test_durable_dispatch_rejects_duplicate_even_after_finish(client, identity, cli):
    _, _, run = await pinned(client, identity)
    aid = await attempt(run)
    did, _ = await service.claim(run.id, aid)
    await service.finish(did, 'completed', cleanup_verified=True)
    with pytest.raises(EngineFailure, match='already_dispatched'):
        await service.claim(run.id, aid)


async def test_unresolved_profile_serializes_distinct_attempts(client, identity, cli):
    _, _, run = await pinned(client, identity)
    first, second = await attempt(run), await attempt(run)
    did, _ = await service.claim(run.id, first)
    with pytest.raises(EngineFailure, match='profile_busy'):
        await service.claim(run.id, second)
    await service.finish(did, 'failed', cleanup_verified=False)
    with pytest.raises(EngineFailure, match='profile_busy'):
        await service.claim(run.id, second)


@pytest.mark.parametrize('mutation', ['disconnect', 'membership', 'cancel', 'privacy', 'image', 'grant'])
async def test_queued_authority_is_rechecked(client, identity, cli, mutation):
    data, saved, run = await pinned(client, identity)
    aid = await attempt(run)
    async with Session.begin() as db:
        if mutation == 'disconnect':
            row = await db.get(CliModelConnection, data['id']); row.status = 'disconnected'; row.version += 1
        elif mutation == 'membership':
            await db.delete(await db.get(Member, (identity['workspace'], identity['user_id'])))
        elif mutation == 'cancel':
            row = await db.get(Run, run.id); row.cancel_requested = True
        elif mutation == 'privacy':
            row = await db.get(ChatSession, run.session_id); row.chat_profile = {'policy': {'privacy': 'local_only'}}
        elif mutation == 'image':
            row = await db.get(CliModelConnection, data['id']); row.runtime_image_id = 'sha256:' + 'b'*64
        else:
            row = await db.get(TenantConnectionGrant, saved['grant']['id']); row.status = 'revoked'; row.revision += 1
    with pytest.raises(EngineFailure):
        await service.claim(run.id, aid)


async def test_connected_state_needs_complete_pins(client, identity, cli):
    data = await created(client, identity)
    with pytest.raises(DBAPIError):
        async with Session.begin() as db:
            row = await db.get(CliModelConnection, data['id']); row.status = 'connected'


class SyntheticTransport:
    cleanup_verified = True
    async def invoke(self, pin, aid, prompt, authorize):
        assert await authorize(pin)
        return Outcome('Synthetic text', input_tokens=10, output_tokens=3)


async def test_accounting_gateway_uses_native_ledger_not_second_runner(client, identity, cli, monkeypatch):
    _, _, run = await pinned(client, identity)
    monkeypatch.setattr(gateway, 'transport_for', lambda pin: SyntheticTransport())
    wrapper = AccountingEngine(ManagedEngine(gateway.CliGateway(run.id, run.engine_snapshot), capabilities('codex_cli')), run)
    chunks = [c async for c in wrapper.stream([{'role':'system','content':'PAO'}, {'role':'user','content':run.prompt}])]
    assert ''.join(c.text for c in chunks) == 'Synthetic text'
    assert CURRENT_ATTEMPT.get() is None
    async with Session() as db:
        row = await db.scalar(select(LlmAttempt).where(LlmAttempt.run_id == run.id))
        dispatch = await db.scalar(select(CliModelDispatch).where(CliModelDispatch.attempt_id == row.id))
        assert row.status == dispatch.status == 'completed'
        assert row.input_tokens == 10 and row.cost_estimate is None
        assert not await db.scalar(select(TenantModelLease.id).where(TenantModelLease.attempt_id == row.id, TenantModelLease.status == 'active'))


async def test_gateway_without_accounting_context_never_spawns(client, identity, cli, monkeypatch):
    _, _, run = await pinned(client, identity)
    monkeypatch.setattr(gateway, 'transport_for', lambda pin: pytest.fail('unaccounted spawn'))
    with pytest.raises(EngineFailure, match='accounting_required'):
        await gateway.CliGateway(run.id, run.engine_snapshot).invoke([{'role':'user','content':'x'}])


@pytest.fixture
def profiles(cli, monkeypatch):
    from pao.modules.cli_connections import runtime
    from pao_cli_runtime.codex_worker import BINARY_SHA256, VERSION
    config = {'version':2,'device_id':settings().cli_device_id,'image_id':'sha256:'+'a'*64,
              'binary_sha256':BINARY_SHA256,'binary_version':VERSION, 'host_runtime_sha256':runtime.host_digest()}
    monkeypatch.setattr(runtime, 'device_config', lambda: dict(config))
    class Admin:
        cleanup_verified = True
        action = None
        verified = True
        auth = 'chatgpt'
        def __init__(self, image):
            self.cleanup_verified = self.verified
        async def operation(self, pin, mode):
            if type(self).action:
                await type(self).action(pin, mode)
            return {'initialized':True} if mode == 'initialize' else {'auth_mode':type(self).auth}
        def login_command(self, pin):
            return ['synthetic-test-only', 'login', '--device-auth']
    monkeypatch.setattr('pao_cli_runtime.profile_transport.ProfileAdmin', Admin)
    return Admin


async def test_host_transport_change_invalidates_pin_and_grant_stamp(client, identity, cli, monkeypatch):
    from pao.modules.cli_connections import runtime
    from pao.modules.connections.grants import source_stamp
    data, _, run = await pinned(client, identity)
    async with Session() as db:
        _, before = await source_stamp(db, identity['workspace'], 'cli_model', data['id'], identity['user_id'])
        assert run.engine_snapshot['cli_pin']['host_runtime_sha256'] == runtime.host_digest()
        monkeypatch.setattr(runtime, 'host_digest', lambda: '0' * 64)
        _, after = await source_stamp(db, identity['workspace'], 'cli_model', data['id'], identity['user_id'])
        assert before != after
        with pytest.raises(EngineFailure, match='^cli_connection_changed$'):
            await service.check_source(db, identity['workspace'], run.engine_snapshot)


def test_device_registry_requires_current_host_transport(cli, monkeypatch, tmp_path):
    import json
    from pao.modules.cli_connections import runtime
    from pao_cli_runtime.codex_worker import BINARY_SHA256, VERSION
    monkeypatch.setattr(runtime, 'ROOT', tmp_path)
    (tmp_path / '.runtime').mkdir()
    path = tmp_path / '.runtime/cli-device.json'
    config = {'version':2, 'device_id':settings().cli_device_id, 'image_id':'sha256:'+'a'*64,
              'binary_sha256':BINARY_SHA256, 'binary_version':VERSION, 'host_runtime_sha256':runtime.host_digest()}
    path.write_text(json.dumps(config), encoding='utf-8')
    assert runtime.device_config() == config
    path.write_text(json.dumps({**config, 'host_runtime_sha256':'0'*64}), encoding='utf-8')
    with pytest.raises(EngineFailure, match='^cli_runtime_pin_invalid$'):
        runtime.device_config()
    path.write_text(json.dumps({k:v for k,v in config.items() if k != 'host_runtime_sha256'}), encoding='utf-8')
    with pytest.raises(EngineFailure, match='^cli_runtime_pin_invalid$'):
        runtime.device_config()


def test_resolve_rejects_changed_host_pin_without_spawning(cli, monkeypatch):
    from pao.modules.cli_connections import runtime
    from pao_cli_runtime.codex_worker import BINARY_SHA256, VERSION
    config = {'version':2, 'device_id':settings().cli_device_id, 'image_id':'sha256:'+'a'*64,
              'binary_sha256':BINARY_SHA256, 'binary_version':VERSION, 'host_runtime_sha256':runtime.host_digest()}
    monkeypatch.setattr(runtime, 'device_config', lambda: dict(config))
    selected = {**config, 'runtime_image_id':config['image_id']}
    assert runtime.resolve(selected).image.image_id == config['image_id']
    with pytest.raises(EngineFailure, match='^cli_runtime_pin_invalid$'):
        runtime.resolve({**selected, 'host_runtime_sha256':'0'*64})


async def test_prepare_and_status_are_not_inference_or_consent(client, identity, profiles):
    data = await created(client, identity)
    prepared = await client.post(path(identity)+'/'+data['id']+'/prepare', headers=identity['owner'], json={'version':1})
    assert prepared.status_code == 200, prepared.text
    assert prepared.json()['status'] == 'pending' and prepared.json()['version'] == 2
    assert not prepared.json()['authentication_ready'] and not prepared.json()['grant_activated']
    checked = await client.post(path(identity)+'/'+data['id']+'/check-auth', headers=identity['owner'], json={'version':2})
    assert checked.status_code == 200, checked.text
    assert checked.json()['authentication_ready'] and checked.json()['version'] == 3
    assert checked.json()['provider_inference_verified'] is False
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(LlmAttempt)) == 0
        assert await db.scalar(select(func.count()).select_from(TenantConnectionGrant)) == 0


async def test_auth_change_requires_disconnect_not_silent_repin(client, identity, profiles):
    data = await authenticated_fixture(client, identity)
    result = await client.post(path(identity)+'/'+data['id']+'/check-auth', headers=identity['owner'], json={'version':1})
    assert result.status_code == 409 and 'disconnect_before' in result.text


async def test_auth_probe_rechecks_membership_before_publication(client, identity, profiles):
    data = await created(client, identity)
    async def revoke(pin, mode):
        async with Session.begin() as db:
            await db.delete(await db.get(Member, (identity['workspace'], identity['user_id'])))
    profiles.action = revoke
    result = await client.post(path(identity)+'/'+data['id']+'/prepare', headers=identity['owner'], json={'version':1})
    assert result.status_code == 403
    async with Session() as db:
        row = await db.get(CliModelConnection, data['id'])
        assert row.status == 'pending' and row.auth_checked_at is None and row.setup_operation_id is None


async def test_unverified_profile_cleanup_keeps_setup_fence(client, identity, profiles):
    profiles.verified = False
    data = await created(client, identity)
    result = await client.post(path(identity)+'/'+data['id']+'/prepare', headers=identity['owner'], json={'version':1})
    assert result.status_code == 503
    again = await client.post(path(identity)+'/'+data['id']+'/prepare', headers=identity['owner'], json={'version':1})
    assert again.status_code == 409 and 'profile_busy' in again.text


async def test_concurrent_profile_setup_is_fenced(client, identity, profiles):
    data = await created(client, identity)
    started, release = asyncio.Event(), asyncio.Event()
    async def pause(pin, mode):
        started.set()
        await release.wait()
    profiles.action = pause
    first = asyncio.create_task(client.post(path(identity)+'/'+data['id']+'/prepare',
        headers=identity['owner'], json={'version':1}))
    await asyncio.wait_for(started.wait(), 5)
    second = await client.post(path(identity)+'/'+data['id']+'/prepare', headers=identity['owner'], json={'version':1})
    release.set()
    assert (await first).status_code == 200
    assert second.status_code == 409 and 'profile_busy' in second.text


async def test_cli_grant_appears_only_for_its_actor(client, identity, cli):
    data = await authenticated_fixture(client, identity)
    activated, saved = await grant(client, identity, data)
    assert activated.status_code == 201
    result = await client.get(f"/v1/workspaces/{identity['workspace']}/model-grants", headers=identity['owner'])
    assert result.status_code == 200, result.text
    assert [item['provider'] for item in result.json()['items']] == ['codex_cli']
    other = await client.get(f"/v1/workspaces/{identity['workspace']}/model-grants", headers=identity['other'])
    assert other.status_code == 200 and other.json()['items'] == []


async def test_cli_grant_cannot_authorize_api_connection_with_same_uuid(client, identity, cli):
    from pao.models import ModelProviderConnection
    data = await authenticated_fixture(client, identity)
    activated, saved = await grant(client, identity, data)
    assert activated.status_code == 201
    async with Session.begin() as db:
        db.add(ModelProviderConnection(id=data['id'], workspace_id=identity['workspace'], provider='openai',
                                      model='synthetic-model', api_key_ciphertext='SYNTHETIC_NOT_A_CREDENTIAL'))
    async with Session() as db:
        with pytest.raises(EngineFailure, match='grant_denied'):
            await choose_config(db, identity['workspace'], 'openai', 'synthetic-model',
                                actor_id=identity['user_id'], grant_id=saved['grant']['id'])


async def test_dispatch_history_cannot_be_deleted_or_reassigned(client, identity, cli):
    _, _, run = await pinned(client, identity)
    one, two = await attempt(run), await attempt(run)
    did, _ = await service.claim(run.id, one)
    for sql in ('DELETE FROM cli_model_dispatches WHERE id=:id',
                'UPDATE cli_model_dispatches SET attempt_id=:other WHERE id=:id'):
        with pytest.raises(DBAPIError):
            async with Session.begin() as db:
                await db.execute(text(sql), {'id':did,'other':two})


async def test_accounted_cancel_closes_native_attempt_and_dispatch(client, identity, cli, monkeypatch):
    _, _, run = await pinned(client, identity)
    started = asyncio.Event()
    class Paused(SyntheticTransport):
        async def invoke(self, pin, aid, prompt, authorize):
            assert await authorize(pin)
            started.set()
            await asyncio.Event().wait()
    monkeypatch.setattr(gateway, 'transport_for', lambda pin: Paused())
    wrapper = AccountingEngine(ManagedEngine(gateway.CliGateway(run.id, run.engine_snapshot), capabilities('codex_cli')), run)
    async def collect():
        return [c async for c in wrapper.stream([{'role':'system','content':'PAO'},{'role':'user','content':run.prompt}])]
    task = asyncio.create_task(collect())
    await asyncio.wait_for(started.wait(), 5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    async with Session() as db:
        row = await db.scalar(select(LlmAttempt).where(LlmAttempt.run_id == run.id))
        dispatch = await db.scalar(select(CliModelDispatch).where(CliModelDispatch.attempt_id == row.id))
        assert row.status == dispatch.status == 'cancelled'
    assert CURRENT_ATTEMPT.get() is None
