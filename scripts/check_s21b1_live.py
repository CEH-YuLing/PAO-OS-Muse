"""ACOS live staged APIs read-only smoke; never create live grants or network calls."""
import asyncio
import json
from pathlib import Path

import httpx
from sqlalchemy import select, text

from pao.auth import issue_token
from pao.config import ROOT, settings
from pao.db import Session, engine
from pao.models import Member, User, TenantConnectionReference, TenantConnectionGrant, TenantConnectionAudit
from pao.skills import execution_binding


async def main():
    assert ROOT.resolve() == Path('F:/PAO-ACOS') and settings().database_url.endswith('/pao_acos_local')
    checked = 0
    try:
        async with Session() as db, httpx.AsyncClient(base_url='http://127.0.0.1:8100', timeout=10) as client:
            assert await db.scalar(text('SELECT version_num FROM alembic_version')) == '0049'
            for table in (TenantConnectionReference, TenantConnectionGrant, TenantConnectionAudit):
                assert await db.scalar(select(table.id).limit(1)) is None, 'No live mapping in migration checkpoint'
            members = list(await db.scalars(select(Member).join(User, User.id == Member.user_id).where(
                Member.role.in_(('owner', 'admin')), User.active.is_(True))))
            assert members
            for member in members:
                path = f'/v1/workspaces/{member.workspace_id}/connection-inventory/references'
                headers = {'Authorization': 'Bearer '+issue_token(member.user_id)}
                value = await client.get(path, headers=headers)
                assert value.status_code == 200 and value.headers['cache-control'] == 'no-store'
                assert value.json() == {'items': [], 'has_more': False, 'execution_enabled': False}
                assert (await client.get(path)).status_code == 401
                invalid = await client.post(path, headers=headers, json={'token': 'local-validation-marker'})
                assert invalid.status_code == 422 and 'local-validation-marker' not in invalid.text
                checked += 1
            print(json.dumps({'pass': True, 'revision': '0049', 'live_manager_scopes': checked,
                'execution_enabled': False, 'live_mapping_rows': 0, 'auth_and_validation': True,
                'binding': execution_binding(), 'external_calls': False, 'mutation_applied': False}))
    finally:
        await engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
