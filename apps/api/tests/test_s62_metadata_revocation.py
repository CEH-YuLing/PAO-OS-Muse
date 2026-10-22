"""Session revocation during catalogue I/O must never publish stale results."""
import pytest
from sqlalchemy import update
from pao.db import Session
from pao.models import User, ChatSession, TenantMetadataLease
from pao.modules.engines import api
from test_engine_contract import engines, session
from test_local_metadata_resources import catalog, choose
from test_connectors import connectors, connected


@pytest.mark.parametrize('action', ['catalogue', 'selection'])
async def test_logout_all_during_local_metadata_io(client, identity, engines, monkeypatch, action):
    sid = await session(client, identity)

    async def tags():
        async with Session.begin() as db:
            await db.execute(update(User).where(User.id == identity['user_id'])
                             .values(auth_version=User.auth_version + 1))
        return ['local-a', 'must-not-publish']

    monkeypatch.setattr(api, 'local_models', tags)
    result = await (catalog(client, identity) if action == 'catalogue'
                    else choose(client, identity, sid))
    assert result.status_code == 401 and 'must-not-publish' not in result.text
    async with Session() as db:
        assert (await db.get(ChatSession, sid)).engine_version == 1
        from sqlalchemy import select
        assert (await db.scalar(select(TenantMetadataLease))).status == 'released'


@pytest.mark.parametrize('kind', ['local', 'cloud'])
async def test_metadata_publication_rechecks_individual_session(client, identity, monkeypatch, kind):
    from pao.auth import principal
    from fastapi.security import HTTPAuthorizationCredentials
    from fastapi import HTTPException
    from pao.modules.engines.metadata import actor
    from pao.modules.connections.model_metadata import manager
    token = identity['owner']['Authorization'].split()[1]
    async with Session() as db:
        who = await principal(HTTPAuthorizationCredentials(scheme='Bearer', credentials=token), db)
        await db.commit()
        assert (await client.post('/v1/auth/sessions/revoke-current', headers=identity['owner'])).status_code == 200
        with pytest.raises(HTTPException) as error:
            await (actor(db, identity['workspace'], who) if kind == 'local'
                   else manager(db, identity['workspace'], who))
        assert error.value.status_code == 401


async def test_logout_during_connector_probe_preserves_domain_denial(client, identity, connectors, monkeypatch):
    from pao.modules.connectors import service
    from pao.models import ConnectorConnection
    row = await connected(client, identity)

    async def exchange():
        assert (await client.post('/v1/auth/sessions/revoke-current', headers=identity['owner'])).status_code == 200
        return {'protocol': '2025-11-25', 'tools': {}, 'capability_hash': 'must-not-publish'}

    class Fake:
        pass
    Fake.exchange = staticmethod(exchange)
    monkeypatch.setattr(service, 'Client', lambda *args: Fake())
    result = await client.post(f"/v1/connectors/connections/{row['id']}/test",
                              headers=identity['owner'], json={'version': row['version']})
    assert result.status_code == 403 and 'must-not-publish' not in result.text
    async with Session() as db:
        saved = await db.get(ConnectorConnection, row['id'])
        assert saved.manifest_hash == row['manifest_hash'] and saved.failures == 0
