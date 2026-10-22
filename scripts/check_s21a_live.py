"""Read-only acceptance against owned ACOS API; no credentials/IDs printed."""
import asyncio
import json
from pathlib import Path

import httpx
from sqlalchemy import select, text

from pao.auth import Principal, issue_token
from pao.config import ROOT, settings
from pao.db import Session, engine
from pao.models import Member, User
from pao.modules.connections.inventory import inventory


async def main():
    if ROOT.resolve() != Path('F:/PAO-ACOS') or not settings().database_url.endswith('/pao_acos_local'):
        raise SystemExit('ACOS local only')
    count = 0
    try:
        async with Session() as db, httpx.AsyncClient(base_url='http://127.0.0.1:8100', timeout=10) as client:
            members = list(await db.scalars(select(Member).join(User, User.id == Member.user_id).where(
                User.active.is_(True), Member.role.in_(('owner', 'admin')))))
            assert members, 'No active connection manager'
            for member in members:
                headers = {'Authorization': 'Bearer ' + issue_token(member.user_id)}
                path = f'/v1/workspaces/{member.workspace_id}/connection-inventory'
                response = await client.get(path, headers=headers)
                assert response.status_code == 200 and response.headers['cache-control'] == 'no-store'
                assert response.json() == await inventory(db, member.workspace_id, Principal(member.user_id, 0), 50, 0)
                assert (await client.get(path)).status_code == 401
                invalid = await client.post(path + '/mapping-preview', headers=headers,
                    json={'token': 'local-redaction-probe-not-a-secret'})
                assert invalid.status_code == 422 and 'local-redaction-probe-not-a-secret' not in invalid.text
                count += 1
            revision = await db.scalar(text('SELECT version_num FROM alembic_version'))
            assert revision in ('0048', '0049')
        print(json.dumps({'pass': True, 'manager_scopes_checked': count, 'revision': revision,
            'live_equals_source_metadata': True, 'unauthenticated_denied': True, 'invalid_input_redacted': True,
            'credential_values_loaded': False, 'external_provider_calls': False, 'mutation_applied': False}))
    finally:
        await engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
