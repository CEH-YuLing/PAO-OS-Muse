"""Review-only M4 clone up/down/up; never migrate the live source database."""
import argparse
import asyncio
import json
import os
import subprocess
import sys
from uuid import uuid4
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from pao.config import ROOT, settings
from check_p11_migration import docker, snapshot, CONTAINER


async def main(target):
    url = make_url(settings().database_url)
    assert url.database == 'pao_acos_local' and url.host == '127.0.0.1' and url.port == 15432
    engine = create_async_engine(url)
    try:
        async with engine.connect() as db:
            start = await db.scalar(text('SELECT version_num FROM alembic_version'))
    finally: await engine.dispose()
    assert start == '0035' and target in ('0036', '0037', '0038')
    columns, before = await snapshot(url)
    name = 'pao_m4_migration_' + uuid4().hex
    backup = ROOT / '.runtime' / ('m4-pre-' + uuid4().hex + '.dump')
    created = False
    with backup.open('xb') as file: docker(CONTAINER, 'pg_dump', '-U', 'pao', '-d', url.database, '-Fc', stdout=file)
    try:
        docker(CONTAINER, 'createdb', '-U', 'pao', name); created = True
        with backup.open('rb') as file:
            docker('-i', CONTAINER, 'pg_restore', '-U', 'pao', '-d', name, '--no-owner', '--exit-on-error', stdin=file)
        clone = url.set(database=name)
        env = {**os.environ, 'DATABASE_URL': clone.render_as_string(hide_password=False)}
        def migrate(*args): subprocess.run([sys.executable, '-m', 'alembic', *args], env=env, cwd=ROOT, check=True)
        migrate('upgrade', target)
        assert (await snapshot(clone, columns))[1] == before
        migrate('check')
        migrate('downgrade', start)
        assert await snapshot(clone) == (columns, before)
        migrate('upgrade', target)
        assert (await snapshot(clone, columns))[1] == before
        migrate('check')
        assert (await snapshot(url, columns))[1] == before
        print(json.dumps({'pass': True, 'old_table_hashes': len(columns), 'up_down_up': f'{start}->{target}->{start}->{target}',
                          'source_unchanged': True, 'backup': str(backup)}))
    finally:
        if created: docker(CONTAINER, 'dropdb', '-U', 'pao', name)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--target', required=True)
    asyncio.run(main(parser.parse_args().target))
