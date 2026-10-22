import os

# Integration tests must opt into a dedicated database. Never touch development data.
url = os.environ.get('PAO_TEST_DATABASE_URL', '')
if not url.endswith('/pao_test'):
    raise RuntimeError('Set PAO_TEST_DATABASE_URL to a dedicated PostgreSQL /pao_test database')
os.environ['DATABASE_URL'] = url

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from pao.auth import issue_token, passwords
from pao.db import Session, engine
from pao.main import app
from pao.models import Member, User, Workspace


@pytest_asyncio.fixture
async def client():
    async with engine.begin() as connection:
        await connection.execute(text('TRUNCATE users, workspaces RESTART IDENTITY CASCADE'))
        before=(await connection.scalar(text('SELECT version_num FROM alembic_version')),
                tuple(await connection.scalars(text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"))))
    try:
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as c:
                yield c
    finally:
        try:
            async with engine.connect() as connection:
                after=(await connection.scalar(text('SELECT version_num FROM alembic_version')),
                       tuple(await connection.scalars(text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"))))
            if after!=before:
                pytest.exit('Test changed shared schema; stop regression before cascading failures. Restore pao_test explicitly, never production.',returncode=2)
        finally:
            await engine.dispose()


@pytest_asyncio.fixture
async def identity(client, fixture_password_hash):
    async with Session.begin() as db:
        owner = User(email='owner@example.test', password_hash=fixture_password_hash)
        other = User(email='other@example.test', password_hash=fixture_password_hash)
        outsider = User(email='outside@example.test', password_hash=fixture_password_hash)
        workspace = Workspace(name='Test workspace')
        db.add_all([owner, other, outsider, workspace])
        await db.flush()
        db.add_all([Member(workspace_id=workspace.id, user_id=owner.id, role='owner'),
                    Member(workspace_id=workspace.id, user_id=other.id, role='operator')])
    return {'owner': {'Authorization': f'Bearer {issue_token(owner.id)}'},
            'other': {'Authorization': f'Bearer {issue_token(other.id)}'},
            'outsider': {'Authorization': f'Bearer {issue_token(outsider.id)}'},
            'workspace': workspace.id, 'user_id': owner.id}


@pytest.fixture(scope='session')
def fixture_password_hash():
    # Native Argon2 reused only for disposable accounts with this fixed test
    # password. Verification remains real; no production hashing change/mock.
    return passwords.hash('test-password-123')


@pytest.fixture
def accounted_runs(monkeypatch):
    # Positive corpus opts into current accounting; legacy/off tests retain
    # explicit denial fixtures and production feature defaults are untouched.
    from pao.config import settings
    monkeypatch.setattr(settings(),'engine_contract_enabled',True)
    monkeypatch.setattr(settings(),'chat_features_enabled',True)


@pytest.fixture(autouse=True)
def isolated_meta_installer_file(monkeypatch, tmp_path):
    # Managed-app tests must not depend on a developer's private .env existing.
    # Exercise the real file reader with an empty legacy installer file; tests
    # for settings_ui/restart/rotation replace this path with their own corpus.
    from pao.integrations.meta import app_config
    path = tmp_path / '.env'
    path.write_text('# synthetic test installer; no credentials\n', encoding='utf-8')
    monkeypatch.setattr(app_config, 'ENV_PATH', path)


@pytest.fixture(autouse=True)
def foundation_memory_off(monkeypatch):
    # Existing tests do not call local models; Memory tests opt in explicitly.
    from pao.config import settings
    # Preserve the explicit bounded-policy corpus as historical compatibility
    # tests. New provider-managed tests opt into the actual production default.
    monkeypatch.setattr(settings(), 'provider_managed_tokens', False)
    monkeypatch.setattr(settings(), 'installation_ai_enabled', False)
    monkeypatch.setattr(settings(), 'memory_enabled', False)
    monkeypatch.setattr(settings(), 'agent_runtime_enabled', False)
    monkeypatch.setattr(settings(), 'tools_enabled', False)
    monkeypatch.setattr(settings(), 'knowledge_sources_enabled', False)
    monkeypatch.setattr(settings(), 'knowledge_enabled', False)
    monkeypatch.setattr(settings(), 'knowledge_embeddings_enabled', False)
    monkeypatch.setattr(settings(), 'engine_contract_enabled', False)
    monkeypatch.setattr(settings(), 'chat_features_enabled', False)
    monkeypatch.setattr(settings(), 'studio_enabled', False)
    monkeypatch.setattr(settings(), 'workflow_planning_enabled', False)
    monkeypatch.setattr(settings(), 'workflow_durable_enabled', False)
    monkeypatch.setattr(settings(), 'workflow_dispatch_enabled', False)
    monkeypatch.setattr(settings(), 'workflow_worker_enabled', False)
    monkeypatch.setattr(settings(), 'goal_admission_enabled', False)
    monkeypatch.setattr(settings(), 'goal_iterations_enabled', False)
    monkeypatch.setattr(settings(), 'goal_runner_enabled', False)
    monkeypatch.setattr(settings(), 'studio_schedule_manager_enabled', False)
    monkeypatch.setattr(settings(), 'studio_schedule_dispatch_enabled', False)
    monkeypatch.setattr(settings(), 'connectors_enabled', False)
    monkeypatch.setattr(settings(), 'business_events_enabled', False)
    monkeypatch.setattr(settings(), 'business_event_delivery_enabled', False)
    monkeypatch.setattr(settings(), 'unified_approvals_enabled', False)
    monkeypatch.setattr(settings(), 'channels_enabled', False)
    monkeypatch.setattr(settings(), 'channel_autoreply_enabled', False)
    monkeypatch.setattr(settings(), 'channel_retention_enabled', False)
    # Feature tests opt in explicitly, independent of the host's private .env.
    monkeypatch.setattr(settings(), 'business_planning_enabled', False)
    monkeypatch.setattr(settings(), 'voice_turns_enabled', False)
