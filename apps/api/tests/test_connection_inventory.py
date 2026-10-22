"""S2.1A: metadata-only inventory + preview, never executable grants."""
import pytest
import pytest_asyncio
from sqlalchemy import event, select

from pao.auth import issue_token
from pao.db import Session, engine
from pao.models import (
    Brain, BrainMember, Brand, ConnectorConnection, ConnectorSecret,
    GoogleAdsConnection, GoogleAdsSyncJob, Member, MetaConnection, MetaSnapshot,
    MetaSyncJob, ModelProviderConnection, User, Workspace, now,
)
from pao.modules.connections.inventory import projection

SECRET = 'inventory-fixture-secret-never-rendered'


@pytest_asyncio.fixture
async def corpus(identity):
    async with Session.begin() as db:
        other = await db.scalar(select(User).where(User.email == 'other@example.test'))
        outside = await db.scalar(select(User).where(User.email == 'outside@example.test'))
        second = Workspace(name='Same SME label')
        db.add(second)
        await db.flush()
        db.add(Member(workspace_id=second.id, user_id=identity['user_id'], role='owner'))
        db.add(Member(workspace_id=second.id, user_id=outside.id, role='admin'))
        brands, connections = {}, {}
        for label, wid in (('a', identity['workspace']), ('b', second.id)):
            brand = Brand(workspace_id=wid, name='Same brand')
            db.add(brand)
            await db.flush()
            brands[label] = brand.id
            connections[label] = {}
            model = ModelProviderConnection(workspace_id=wid, provider='openai',
                api_key_ciphertext=SECRET, model='local-fixture', status='connected')
            meta = MetaConnection(workspace_id=wid, user_id=identity['user_id'],
                token_ciphertext=SECRET, status='connected', version=3)
            google = GoogleAdsConnection(workspace_id=wid, user_id=identity['user_id'],
                refresh_token_ciphertext=SECRET, status='connected', version=4)
            mcp = ConnectorConnection(workspace_id=wid, owner_id=identity['user_id'],
                endpoint='https://fixture.invalid/' + SECRET, version=2)
            db.add_all([model, meta, google, mcp])
            await db.flush()
            db.add(ConnectorSecret(workspace_id=wid, connection_id=mcp.id, ciphertext=SECRET))
            job = MetaSyncJob(connection_id=meta.id, connection_version=3, api_version='fixture',
                request_key='accounts', kind='accounts', status='completed')
            g_job = GoogleAdsSyncJob(connection_id=google.id, connection_version=4, api_version='fixture',
                request_key='accounts', kind='accounts', status='completed')
            db.add_all([job, g_job])
            await db.flush()
            db.add(MetaSnapshot(job_id=job.id, kind='accounts', remote_key='act_123', payload={'token': SECRET}))
            from pao.models import AdEntity
            db.add(AdEntity(google_connection_id=google.id, connection_version=4, platform='google',
                account_id='1234567890', remote_id='1234567890', kind='account', currency='USD',
                timezone='UTC', google_source_job_id=g_job.id, name=SECRET))
            connections[label] = {kind: row.id for kind, row in (
                ('model', model), ('meta_ads', meta), ('google_ads', google), ('mcp', mcp))}
    return {**identity, 'second': second.id, 'brands': brands, 'connections': connections,
            'operator_id': other.id, 'outside_id': outside.id}


def path(wid):
    return f'/v1/workspaces/{wid}/connection-inventory'


def proposal(corpus, kind='meta_ads'):
    return {'kind': kind, 'connection_id': corpus['connections']['a'][kind],
            'expected_version': {'meta_ads': 3, 'google_ads': 4, 'mcp': 2, 'model': None}[kind],
            'brand_id': corpus['brands']['a'], 'grantee_id': corpus['operator_id'],
            'permission': 'read_only', 'account_id': {
                'meta_ads': 'act_123', 'google_ads': '1234567890', 'mcp': None, 'model': None}[kind]}


async def post(client, corpus, body):
    return await client.post(path(corpus['workspace']) + '/mapping-preview', headers=corpus['owner'], json=body)


async def test_inventory_auth_roles_and_revocation(client, corpus):
    url = path(corpus['workspace'])
    assert (await client.get(url)).status_code == 401
    assert (await client.get(url, headers=corpus['outsider'])).status_code == 404
    assert (await client.get(url, headers=corpus['other'])).status_code == 403
    async with Session.begin() as db:
        member = await db.get(Member, (corpus['workspace'], corpus['user_id']))
        member.role = 'viewer'
    assert (await client.get(url, headers=corpus['owner'])).status_code == 403
    assert (await client.get(path(corpus['second']), headers=corpus['owner'])).status_code == 200
    async with Session.begin() as db:
        await db.delete(await db.get(Member, (corpus['workspace'], corpus['user_id'])))
    assert (await client.get(url, headers=corpus['owner'])).status_code == 404


async def test_two_sme_inventory_no_secret_no_network_no_mutation(client, corpus, monkeypatch):
    import pao.model_router as model_router
    import pao.modules.connectors.service as connectors
    import pao.integrations.meta.client as meta
    import pao.integrations.google_ads.client as google
    def forbidden(*args, **kwargs):
        raise AssertionError('Inventory must not decrypt, probe, or commit')
    for module, name in ((model_router, 'decrypt_key'), (model_router, 'fetch_models'),
                         (connectors, 'token'), (meta, 'decrypt'), (google, 'decrypt')):
        monkeypatch.setattr(module, name, forbidden)
    statements = []
    def record(conn, cursor, statement, params, context, many):
        statements.append(statement.strip().split()[0].upper())
    event.listen(engine.sync_engine, 'before_cursor_execute', record)
    try:
        for label, wid in (('a', corpus['workspace']), ('b', corpus['second'])):
            response = await client.get(path(wid), headers=corpus['owner'])
            assert response.status_code == 200 and response.headers['cache-control'] == 'no-store'
            body = response.json()
            assert {row['identity']['connection_id'] for row in body['items']} == set(corpus['connections'][label].values())
            assert all(row['identity']['workspace_id'] == wid for row in body['items'])
            assert all(row['credential_present'] for row in body['items'])
            assert SECRET not in response.text and 'fixture.invalid' not in response.text
            assert body['external_calls'] is body['credentials_loaded'] is body['mutation_applied'] is False
            model = next(row for row in body['items'] if row['identity']['kind'] == 'model')
            assert model['manager_id'] is model['config_version'] is None
            assert model['ownership'] == 'workspace_unassigned_manager'
        for kind in corpus['connections']['a']:
            async with Session() as db:
                rows = list((await db.execute(projection(kind, corpus['workspace'], corpus['user_id']))).mappings())
                assert all(not any('ciphertext' in key for key in row) for row in rows)
        assert statements and set(statements) == {'SELECT'}
    finally:
        event.remove(engine.sync_engine, 'before_cursor_execute', record)


async def test_native_creator_and_private_brain_fences(client, corpus):
    async with Session.begin() as db:
        member = await db.get(Member, (corpus['workspace'], corpus['operator_id']))
        member.role = 'admin'
        private = Brain(workspace_id=corpus['workspace'], owner_id=corpus['operator_id'], name='Private')
        db.add(private)
        await db.flush()
        conn = await db.get(ConnectorConnection, corpus['connections']['a']['mcp'])
        conn.brain_id = private.id
        private_id = private.id
    # Same tenant admin cannot see another creator's MCP/Meta/Google connection.
    response = await client.get(path(corpus['workspace']), headers=corpus['other'])
    assert {row['identity']['kind'] for row in response.json()['items']} == {'model'}
    # Owner's own MCP also remains hidden without access to its private Brain.
    response = await client.get(path(corpus['workspace']), headers=corpus['owner'])
    assert 'mcp' not in {row['identity']['kind'] for row in response.json()['items']}
    assert (await post(client, corpus, proposal(corpus, 'mcp'))).status_code == 404
    async with Session.begin() as db:
        db.add(BrainMember(brain_id=private_id, workspace_id=corpus['workspace'],
                           user_id=corpus['user_id'], role='reader'))
    assert (await post(client, corpus, proposal(corpus, 'mcp'))).status_code == 200
    async with Session.begin() as db:
        brain = await db.get(Brain, private_id)
        brain.archived_at = now()
    assert (await post(client, corpus, proposal(corpus, 'mcp'))).status_code == 404


@pytest.mark.parametrize('kind', ['model', 'mcp', 'meta_ads', 'google_ads'])
async def test_preview_valid_but_never_applied(client, corpus, kind):
    first = await post(client, corpus, proposal(corpus, kind))
    second = await post(client, corpus, proposal(corpus, kind))
    assert first.status_code == 200 and first.headers['cache-control'] == 'no-store'
    assert first.json() == second.json()
    body = first.json()
    assert len(body['preview_hash']) == 64
    assert body['validated_local_references'] is True
    assert body['executable'] is body['grant_applied'] is body['external_calls'] is False
    assert body['requires_apply_checkpoint'] == 'S2.1B'
    assert SECRET not in first.text
    if kind == 'model':
        assert 'model_config_version_and_manager_missing' in body['blockers']


@pytest.mark.parametrize('field,value,status', [
    ('brand_id', 'foreign_brand', 404), ('connection_id', 'foreign_connection', 404),
    ('grantee_id', 'foreign_member', 404), ('expected_version', 2, 409),
    ('account_id', 'act_999', 404), ('account_id', None, 422),
    ('permission', 'manage', 422), ('expected_version', True, 422),
])
async def test_preview_foreign_or_stale_references_denied(client, corpus, field, value, status):
    foreign = {'foreign_brand': corpus['brands']['b'],
               'foreign_connection': corpus['connections']['b']['meta_ads'],
               'foreign_member': corpus['outside_id']}
    body = proposal(corpus)
    body[field] = foreign.get(value, value)
    assert (await post(client, corpus, body)).status_code == status


async def test_account_provenance_and_grantee_rechecked(client, corpus):
    async with Session.begin() as db:
        job = await db.scalar(select(MetaSyncJob).where(MetaSyncJob.connection_id == corpus['connections']['a']['meta_ads']))
        job.connection_version = 2  # Same account is current only in B now.
    assert (await post(client, corpus, proposal(corpus))).status_code == 404
    async with Session.begin() as db:
        job = await db.scalar(select(MetaSyncJob).where(MetaSyncJob.connection_id == corpus['connections']['a']['meta_ads']))
        job.connection_version = 3
        await db.delete(await db.get(Member, (corpus['workspace'], corpus['operator_id'])))
    assert (await post(client, corpus, proposal(corpus))).status_code == 404


@pytest.mark.parametrize('role', ['viewer', 'inactive'])
async def test_grantee_cannot_be_readonly_viewer_or_inactive(client, corpus, role):
    async with Session.begin() as db:
        if role == 'viewer':
            member = await db.get(Member, (corpus['workspace'], corpus['operator_id']))
            member.role = role
        else:
            user = await db.get(User, corpus['operator_id'])
            user.active = False
    assert (await post(client, corpus, proposal(corpus))).status_code == 404


async def test_bounded_pagination_and_validation_never_echo_input(client, corpus):
    response = await client.get(path(corpus['workspace']) + '?limit=0', headers=corpus['owner'])
    assert response.status_code == 422
    response = await client.get(path(corpus['workspace']) + '?limit=1&offset=1', headers=corpus['owner'])
    assert response.status_code == 200 and response.json()['items'] == []
    body = {**proposal(corpus), 'token': SECRET}
    response = await post(client, corpus, body)
    assert response.status_code == 422 and SECRET not in response.text
    body['token'] = SECRET * 300
    response = await post(client, corpus, body)
    assert response.status_code == 413 and SECRET not in response.text
    body = proposal(corpus, 'mcp')
    body['account_id'] = '123'
    assert (await post(client, corpus, body)).status_code == 422


async def test_preview_requests_are_select_only(client, corpus):
    statements = []
    def record(conn, cursor, statement, params, context, many):
        statements.append(statement.strip().split()[0].upper())
    event.listen(engine.sync_engine, 'before_cursor_execute', record)
    try:
        for kind in corpus['connections']['a']:
            assert (await post(client, corpus, proposal(corpus, kind))).status_code == 200
        assert statements and set(statements) == {'SELECT'}
    finally:
        event.remove(engine.sync_engine, 'before_cursor_execute', record)


async def test_foreign_brain_not_visible_even_for_shared_owner(client, corpus):
    async with Session.begin() as db:
        brain = Brain(workspace_id=corpus['second'], owner_id=corpus['user_id'], name='Foreign Brain')
        db.add(brain)
        await db.flush()
        conn = await db.get(ConnectorConnection, corpus['connections']['a']['mcp'])
        conn.brain_id = brain.id  # Legacy FK does not enforce composite workspace.
    body = (await client.get(path(corpus['workspace']), headers=corpus['owner'])).json()
    assert 'mcp' not in {row['identity']['kind'] for row in body['items']}
    assert (await post(client, corpus, proposal(corpus, 'mcp'))).status_code == 404


async def test_account_row_must_have_matching_completed_source_job(client, corpus):
    from pao.models import AdEntity
    async with Session.begin() as db:
        entity = await db.scalar(select(AdEntity).where(AdEntity.google_connection_id == corpus['connections']['a']['google_ads']))
        foreign = await db.scalar(select(GoogleAdsSyncJob).where(GoogleAdsSyncJob.connection_id == corpus['connections']['b']['google_ads']))
        entity.google_source_job_id = foreign.id  # Same remote ID + version, different connection.
    assert (await post(client, corpus, proposal(corpus, 'google_ads'))).status_code == 404


async def test_metadata_missing_credential_not_accepted_and_legacy_not_assigned(client, corpus, monkeypatch):
    from pao.config import settings
    monkeypatch.setattr(settings(), 'telegram_bot_token', SECRET)
    monkeypatch.setattr(settings(), 'meta_app_secret', SECRET)
    async with Session.begin() as db:
        conn = await db.get(MetaConnection, corpus['connections']['a']['meta_ads'])
        conn.status = 'disconnected'
        conn.token_ciphertext = None
    response = await client.get(path(corpus['workspace']), headers=corpus['owner'])
    assert SECRET not in response.text
    body = response.json()
    assert len(body['legacy_installation_sources']) == 4
    assert all(set(row) == {'provider', 'scope', 'next_checkpoint', 'mapping'} for row in body['legacy_installation_sources'])
    meta = next(row for row in body['items'] if row['identity']['kind'] == 'meta_ads')
    assert meta['credential_present'] is False and meta['acceptance'] == 'not_verified_by_inventory'
    preview = await post(client, corpus, proposal(corpus))
    assert preview.status_code == 200
    assert {'credential_missing', 'connection_not_connected'} <= set(preview.json()['blockers'])
    assert preview.json()['executable'] is False


async def test_pagination_has_more_and_stable_next_page(client, corpus):
    async with Session.begin() as db:
        extra = ConnectorConnection(workspace_id=corpus['workspace'], owner_id=corpus['user_id'],
                                    endpoint='https://fixture.invalid/second')
        db.add(extra)
    response = await client.get(path(corpus['workspace']) + '?limit=1', headers=corpus['owner'])
    assert response.json()['page']['has_more']['mcp'] is True
    response = await client.get(path(corpus['workspace']) + '?limit=1&offset=1', headers=corpus['owner'])
    assert [row['identity']['connection_id'] for row in response.json()['items']] == [extra.id]
    assert response.json()['page']['has_more']['mcp'] is False


async def test_preview_rechecks_requesting_manager_role_and_version(client, corpus):
    old = proposal(corpus, 'mcp')
    assert (await post(client, corpus, old)).status_code == 200
    async with Session.begin() as db:
        conn = await db.get(ConnectorConnection, corpus['connections']['a']['mcp'])
        conn.version += 1
        conn.status = 'revoked'
    assert (await post(client, corpus, old)).status_code == 409
    old['expected_version'] = 3
    response = await post(client, corpus, old)
    assert response.status_code == 200 and 'connection_not_connected' in response.json()['blockers']
    async with Session.begin() as db:
        member = await db.get(Member, (corpus['workspace'], corpus['user_id']))
        member.role = 'operator'
    assert (await post(client, corpus, old)).status_code == 403
