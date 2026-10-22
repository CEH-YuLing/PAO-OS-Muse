"""0048->0049 clone up/down/up; keep primary and legacy credential rows intact."""
import asyncio
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from pao.config import ROOT, settings
from check_p11_migration import CONTAINER, snapshot
from check_s03_restore import schema


def docker(*args, **kwargs):
    subprocess.run(['docker', 'exec', *args], check=True, timeout=120, **kwargs)


async def revision(url):
    engine = create_async_engine(url)
    try:
        async with engine.connect() as db:
            return await db.scalar(text('SELECT version_num FROM alembic_version'))
    finally:
        await engine.dispose()


async def main():
    url = make_url(settings().database_url)
    if ROOT.resolve() != Path('F:/PAO-ACOS') or url.database != 'pao_acos_local' or url.host != '127.0.0.1' or url.port != 15432:
        raise SystemExit('Only ACOS-local source allowed')
    assert await revision(url) == '0048'
    before = await snapshot(url)
    definitions = await schema(url)
    name = 'pao_s21b1_migration_' + uuid4().hex
    assert re.fullmatch(r'pao_s21b1_migration_[0-9a-f]{32}', name)
    admin = create_async_engine(url)
    try:
        async with admin.connect() as db:
            assert not await db.scalar(text('SELECT 1 FROM pg_database WHERE datname=:name'), {'name': name})
    finally:
        await admin.dispose()
    backup = ROOT / '.runtime' / ('s21b1-pre-' + uuid4().hex + '.dump')
    with backup.open('xb') as output:
        docker(CONTAINER, 'pg_dump', '-U', 'pao', '-d', url.database, '-Fc', stdout=output)
    created = False
    try:
        docker(CONTAINER, 'createdb', '-U', 'pao', name); created = True
        with backup.open('rb') as source:
            docker('-i', CONTAINER, 'pg_restore', '-U', 'pao', '-d', name, '--no-owner', '--exit-on-error', stdin=source)
        target = url.set(database=name)
        env = {**os.environ, 'DATABASE_URL': target.render_as_string(hide_password=False)}
        def migrate(*args):
            subprocess.run([sys.executable, '-m', 'alembic', *args], cwd=ROOT, env=env, check=True, timeout=120)
        for step in ('upgrade', 'downgrade', 'upgrade'):
            migrate(step, '0048' if step == 'downgrade' else '0049')
            assert (await snapshot(target, before[0]))[1] == before[1], 'Legacy rows changed'
            if step == 'downgrade':
                assert await snapshot(target) == before
                assert await schema(target) == definitions
            else:
                migrate('check')
                engine = create_async_engine(target)
                try:
                    async with engine.connect() as db:
                        for table in ('tenant_connection_references', 'tenant_connection_grants', 'tenant_connection_audits'):
                            assert await db.scalar(text('SELECT count(*) FROM ' + table)) == 0, 'Automatic mapping forbidden'
                finally:
                    await engine.dispose()
        assert await snapshot(url) == before and await schema(url) == definitions and await revision(url) == '0048'
        print(json.dumps({'pass': True, 'up_down_up': '0048->0049->0048->0049', 'legacy_tables': len(before[0]),
            'legacy_row_hashes_exact': True, 'rollback_schema_equivalent': True, 'automatic_mapping': False,
            'primary_unchanged': True, 'backup': str(backup), 'clone': name, 'external_calls': False}))
    finally:
        if created:
            docker(CONTAINER, 'dropdb', '-U', 'pao', name)
            print('Removed only this invocation-owned migration clone; retained backup.')


if __name__ == '__main__':
    asyncio.run(main())
