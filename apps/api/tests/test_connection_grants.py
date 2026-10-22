"""Staged storage/eligibility only; no runtime/provider authority created."""
import asyncio
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from pao.db import Session
from pao.models import (Brain, BrainMember, ConnectorConnection, Member, MetaConnection,
                        ModelProviderConnection, TenantConnectionAudit, TenantConnectionGrant,
                        TenantConnectionReference, User, now)
from pao.modules.connections import grants
from test_connection_inventory import corpus, path, proposal, SECRET


async def stage(client, c, kind='model', change=None):
    base = proposal(c, kind)
    response = await client.post(path(c['workspace'])+'/mapping-preview', headers=c['owner'], json=base)
    assert response.status_code == 200, response.text
    body = {**base, 'preview_hash': response.json()['preview_hash'], 'request_key': str(uuid4()),
            'ttl_minutes': 60, 'manager_id': c['user_id'] if kind == 'model' else None,
            'apply_data_only_ack': True}
    body.update(change or {})
    return await client.post(path(c['workspace'])+'/references', headers=c['owner'], json=body), body


async def eligibility(client, c, saved, headers=None, change=None):
    ref, grant = saved['reference'], saved['grant']
    body = {'reference_revision': ref['revision'], 'grant_id': grant['id'],
            'brand_id': grant['brand_id'], 'account_id': grant['account_id']}
    body.update(change or {})
    return await client.post(path(c['workspace'])+f"/references/{ref['id']}/eligibility",
                             headers=headers or c['other'], json=body)


@pytest.mark.parametrize('kind', ['model', 'mcp', 'meta_ads', 'google_ads'])
async def test_staged_roundtrip_idempotent_no_credentials_or_execution(client, corpus, kind):
    async with Session.begin() as db:
        if kind == 'mcp':
            row = await db.get(ConnectorConnection, corpus['connections']['a'][kind]); row.status = 'connected'
        if kind == 'meta_ads':
            row = await db.get(MetaConnection, corpus['connections']['a'][kind]); row.expires_at = now()+timedelta(hours=1)
    response, body = await stage(client, corpus, kind)
    assert response.status_code == 201, response.text
    assert response.headers['cache-control'] == 'no-store'
    saved = response.json()
    assert saved['reference']['status'] == saved['grant']['status'] == 'staged'
    assert saved['reference']['execution_enabled'] is saved['grant']['execution_enabled'] is False
    assert SECRET not in response.text and 'source_stamp' not in response.text and 'fingerprint' not in response.text
    check = await eligibility(client, corpus, saved)
    assert check.status_code == 200, check.text
    assert check.json()['execution_enabled'] is False
    repeat = await client.post(path(corpus['workspace'])+'/references', headers=corpus['owner'], json=body)
    assert repeat.status_code == 201 and repeat.json()['replayed'] is True
    assert repeat.json()['grant']['id'] == saved['grant']['id']
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(TenantConnectionReference)) == 1
        assert await db.scalar(select(func.count()).select_from(TenantConnectionGrant)) == 1
        assert await db.scalar(select(func.count()).select_from(TenantConnectionAudit)) == 2
        assert (await db.get(ModelProviderConnection, corpus['connections']['a']['model'])).api_key_ciphertext == SECRET


async def test_concurrent_same_request_and_payload_collision(client, corpus):
    first, body = await stage(client, corpus)
    body['request_key'] = str(uuid4())  # Race the first use, not only retries.
    responses = await asyncio.gather(*[client.post(path(corpus['workspace'])+'/references', headers=corpus['owner'], json=body) for _ in range(4)])
    assert all(row.status_code == 201 and row.json()['grant']['id'] == responses[0].json()['grant']['id'] for row in responses)
    assert responses[0].json()['grant']['id'] != first.json()['grant']['id']
    changed = await client.post(path(corpus['workspace'])+'/references', headers=corpus['owner'], json={**body, 'ttl_minutes': 61})
    assert changed.status_code == 409


@pytest.mark.parametrize('kind', ['model', 'google_ads'])
async def test_two_sme_same_provider_account_revoke_a_does_not_touch_b(client, corpus, kind):
    a, _ = await stage(client, corpus, kind)
    b_context = {**corpus, 'workspace': corpus['second'], 'operator_id': corpus['outside_id'],
                 'connections': {'a': corpus['connections']['b']}, 'brands': {'a': corpus['brands']['b']}}
    b, _ = await stage(client, b_context, kind)
    assert a.status_code == b.status_code == 201
    assert a.json()['reference']['id'] != b.json()['reference']['id']
    assert (await eligibility(client, corpus, a.json())).status_code == 200
    assert (await eligibility(client, b_context, b.json(), headers=corpus['outsider'])).status_code == 200
    revoked = await client.post(path(corpus['workspace'])+f"/references/{a.json()['reference']['id']}/revoke",
                               headers=corpus['owner'], json={'reference_revision': 1})
    assert revoked.status_code == 200
    assert (await eligibility(client, corpus, a.json())).status_code == 403
    assert (await eligibility(client, b_context, b.json(), headers=corpus['outsider'])).status_code == 200


async def test_apply_and_eligibility_never_resolve_credential_or_provider(client, corpus, monkeypatch):
    import pao.model_router as models
    import pao.modules.connectors.service as mcp
    def forbidden(*args, **kwargs):
        raise AssertionError('Staged grant must not resolve/probe credential')
    monkeypatch.setattr(models, 'decrypt_key', forbidden)
    monkeypatch.setattr(models, 'fetch_models', forbidden)
    monkeypatch.setattr(mcp, 'token', forbidden)
    response, _ = await stage(client, corpus)
    assert response.status_code == 201
    for _ in range(3):
        checked = await eligibility(client, corpus, response.json())
        assert checked.status_code == 200 and checked.json()['execution_enabled'] is False
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(TenantConnectionAudit)) == 2


async def test_explicit_model_manager_preview_fence_and_atomic_rollback(client, corpus):
    response, _ = await stage(client, corpus, change={'manager_id': None})
    assert response.status_code == 422
    response, _ = await stage(client, corpus, change={'preview_hash': '0'*64})
    assert response.status_code == 409
    response, body = await stage(client, corpus, change={'manager_id': corpus['operator_id']})
    assert response.status_code == 422
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(TenantConnectionReference)) == 0
        assert await db.scalar(select(func.count()).select_from(TenantConnectionGrant)) == 0


@pytest.mark.parametrize('change', ['rotate', 'model', 'disconnect', 'status', 'grantee_removed', 'grantee_viewer', 'manager_removed', 'manager_viewer', 'inactive', 'expiry'])
async def test_eligibility_fresh_recheck_no_fallback(client, corpus, change, monkeypatch):
    response, _ = await stage(client, corpus)
    saved = response.json()
    assert (await eligibility(client, corpus, saved)).status_code == 200
    async with Session.begin() as db:
        native = await db.get(ModelProviderConnection, corpus['connections']['a']['model'])
        if change == 'rotate': native.api_key_ciphertext = 'changed-fixture-ciphertext'
        elif change == 'model': native.model = 'changed-model'
        elif change == 'disconnect': await db.delete(native)
        elif change == 'status': native.status = 'error'
        elif change in ('grantee_removed', 'manager_removed'):
            actor = corpus['operator_id'] if change.startswith('grantee') else corpus['user_id']
            await db.delete(await db.get(Member, (corpus['workspace'], actor)))
        elif change in ('grantee_viewer', 'manager_viewer'):
            actor = corpus['operator_id'] if change.startswith('grantee') else corpus['user_id']
            member = await db.get(Member, (corpus['workspace'], actor)); member.role = 'viewer'
        elif change == 'inactive':
            actor = await db.get(User, corpus['operator_id']); actor.active = False
    if change == 'expiry':
        later = now()+timedelta(hours=2)
        monkeypatch.setattr(grants, 'now', lambda: later)
    assert (await eligibility(client, corpus, saved)).status_code in (401, 403)
    async with Session() as db:
        # Native delete must preserve a tombstone, not fall back to unregistered access.
        assert await db.scalar(select(func.count()).select_from(TenantConnectionReference)) == 1


@pytest.mark.parametrize('change', [{'brand_id': None}, {'account_id': '123'}, {'reference_revision': 2}, {'grant_id': str(uuid4())}])
async def test_scope_pin_mismatch(client, corpus, change):
    response, _ = await stage(client, corpus)
    assert (await eligibility(client, corpus, response.json(), change=change)).status_code in (403, 404)


async def test_foreign_sme_and_nonmanager_cannot_manage_or_check(client, corpus):
    response, body = await stage(client, corpus)
    saved = response.json()
    ref = saved['reference']['id']
    assert (await client.get(path(corpus['workspace'])+'/references', headers=corpus['other'])).status_code == 403
    assert (await client.post(path(corpus['workspace'])+'/references', headers=corpus['other'], json=body)).status_code == 403
    foreign = await client.post(path(corpus['second'])+f'/references/{ref}/revoke', headers=corpus['owner'], json={'reference_revision': 1})
    assert foreign.status_code == 404
    assert (await eligibility(client, corpus, saved, headers=corpus['owner'])).status_code == 404
    assert (await client.get(path(corpus['second'])+f'/references/{ref}/audit', headers=corpus['owner'])).status_code == 404
    foreign = await client.post(path(corpus['second'])+'/references', headers=corpus['owner'], json=body)
    assert foreign.status_code == 404


@pytest.mark.parametrize('scope', ['grant', 'reference'])
async def test_revoke_cas_and_no_replay_resurrection(client, corpus, scope):
    response, body = await stage(client, corpus)
    saved = response.json(); ref = saved['reference']['id']; gid = saved['grant']['id']
    url = path(corpus['workspace'])+f'/references/{ref}'
    url += f'/grants/{gid}/revoke' if scope == 'grant' else '/revoke'
    bad = await client.post(url, headers=corpus['owner'], json={'reference_revision': 2, 'grant_revision': 1})
    assert bad.status_code == 409
    result = await client.post(url, headers=corpus['owner'], json={'reference_revision': 1, 'grant_revision': 1})
    assert result.status_code == 200, result.text
    assert (await eligibility(client, corpus, saved)).status_code == 403
    repeat = await client.post(path(corpus['workspace'])+'/references', headers=corpus['owner'], json=body)
    assert repeat.status_code == 201 and repeat.json()['grant']['status'] == 'revoked'
    assert repeat.json()['grant']['execution_enabled'] is False
    hist = await client.get(path(corpus['workspace'])+f'/references/{ref}/audit', headers=corpus['owner'])
    assert hist.status_code == 200 and SECRET not in hist.text
    assert any(row['action'] == 'grant_revoked' for row in hist.json()['items'])


async def test_private_brain_never_implicit_from_staged_grant(client, corpus):
    async with Session.begin() as db:
        brain = Brain(workspace_id=corpus['workspace'], owner_id=corpus['user_id'], name='private')
        db.add(brain); await db.flush()
        conn = await db.get(ConnectorConnection, corpus['connections']['a']['mcp'])
        conn.brain_id = brain.id; conn.status = 'connected'; bid = brain.id
    response, _ = await stage(client, corpus, 'mcp')
    saved = response.json()
    assert (await eligibility(client, corpus, saved)).status_code == 403
    async with Session.begin() as db:
        db.add(BrainMember(brain_id=bid, workspace_id=corpus['workspace'], user_id=corpus['operator_id'], role='reader'))
    assert (await eligibility(client, corpus, saved)).status_code == 200
    async with Session.begin() as db:
        await db.delete(await db.get(BrainMember, (bid, corpus['operator_id'])))
    assert (await eligibility(client, corpus, saved)).status_code == 403


@pytest.mark.parametrize('statement', [
    "UPDATE tenant_connection_grants SET permission='manage'",
    "UPDATE tenant_connection_grants SET expires_at=expires_at+interval '1 day'",
    "DELETE FROM tenant_connection_grants",
    "UPDATE tenant_connection_references SET manager_id=gen_random_uuid()",
    "DELETE FROM tenant_connection_references",
    "UPDATE tenant_connection_audits SET data='{}'",
    "DELETE FROM tenant_connection_audits",
])
async def test_database_identity_and_audit_immutable(client, corpus, statement):
    response, _ = await stage(client, corpus)
    assert response.status_code == 201
    with pytest.raises(DBAPIError):
        async with Session.begin() as db:
            await db.execute(text(statement))


async def test_db_denies_foreign_native_source_and_brand_constraint(client, corpus):
    with pytest.raises(DBAPIError):
        async with Session.begin() as db:
            db.add(TenantConnectionReference(workspace_id=corpus['workspace'], kind='model',
                source_id=corpus['connections']['b']['model'], provider='openai', manager_id=corpus['user_id'],
                source_stamp='0'*64, revision=1, status='staged'))
    response, _ = await stage(client, corpus)
    saved = response.json()
    with pytest.raises(DBAPIError):
        async with Session.begin() as db:
            db.add(TenantConnectionGrant(workspace_id=corpus['workspace'], reference_id=saved['reference']['id'],
                reference_revision=1, creator_id=corpus['user_id'], grantee_id=corpus['operator_id'],
                brand_id=corpus['brands']['b'], request_key=str(uuid4()), fingerprint='0'*64,
                permission='read_only', ttl_minutes=60, expires_at=now()+timedelta(hours=1), revision=1, status='staged'))


async def test_invalid_secret_and_oversized_apply_never_echo(client, corpus):
    response, body = await stage(client, corpus)
    for field, value, status in [('token', SECRET, 422), ('token', SECRET*300, 413), ('ttl_minutes', True, 422), ('apply_data_only_ack', False, 422)]:
        response = await client.post(path(corpus['workspace'])+'/references', headers=corpus['owner'], json={**body, field: value})
        assert response.status_code == status and SECRET not in response.text
