"""Backup ACOS only, restore to a new isolated DB, check counts and skill archives.

Optional migration after verified backup/restore. Never drop an existing DB.
The only removed DB is the exact generated test DB created by this invocation.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from pao.config import ROOT, settings
from pao.skill_artifacts import read_artifact

CONTAINER = 'pao-acos-local-postgres-1'


def docker(*args, **kwargs):
    return subprocess.run(['docker', 'exec', *args], check=True, **kwargs)


async def inspect(url):
    engine = create_async_engine(url)
    try:
        async with engine.connect() as db:
            tables = list(await db.scalars(text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")))
            counts = {name: await db.scalar(text('SELECT count(*) FROM "' + name.replace('"', '""') + '"')) for name in tables}
            revision = await db.scalar(text('SELECT version_num FROM alembic_version'))
            artifacts = []
            for rid, workspace, plan, response in await db.execute(text('SELECT id, workspace_id, execution_plan, response FROM runs WHERE status=\'completed\'')):
                archive = (plan or {}).get('skill_artifact')
                if archive:
                    value = read_artifact(archive, 'run', str(rid), str(workspace))
                    if value.response != response:
                        raise RuntimeError('Restored run response differs from archive')
                    artifacts.append(value.hash)
            # Later additive revisions must still verify old Task archives.
            if await db.scalar(text("SELECT count(*) FROM information_schema.columns WHERE table_schema='public' AND table_name='task_attempts' AND column_name='skill_artifact'")):
                for aid, workspace, archive in await db.execute(text('SELECT id, workspace_id, skill_artifact FROM task_attempts WHERE skill_artifact IS NOT NULL')):
                    artifacts.append(read_artifact(archive, 'attempt', str(aid), str(workspace)).hash)
            return {'revision': revision, 'counts': counts, 'artifact_hashes': sorted(artifacts)}
    finally:
        await engine.dispose()


async def main(migrate):
    url = make_url(settings().database_url)
    if url.database != 'pao_acos_local' or url.port != 15432 or url.host not in ('127.0.0.1', 'localhost') or url.username != 'pao':
        raise SystemExit('Requires isolated ACOS local DB on 15432')
    before = await inspect(url)
    if migrate and before['revision'] != '0023':
        raise SystemExit('Migration checkpoint expects revision 0023')
    runtime = ROOT / '.runtime'
    runtime.mkdir(exist_ok=True)
    name = 'pao_m2_restore_' + uuid4().hex
    backup = runtime / ('m2-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid4().hex[:8] + '.dump')
    with backup.open('xb') as output:
        docker(CONTAINER, 'pg_dump', '-U', 'pao', '-d', url.database, '-Fc', stdout=output)
    created = False
    try:
        docker(CONTAINER, 'createdb', '-U', 'pao', name)
        created = True
        with backup.open('rb') as source:
            docker('-i', CONTAINER, 'pg_restore', '-U', 'pao', '-d', name,
                   '--no-owner', '--exit-on-error', stdin=source)
        restored = await inspect(url.set(database=name))
        if restored != before:
            raise RuntimeError('Restored counts/revision/artifact hashes differ')
        print(f'PASS backup/restore: {len(before["counts"])} tables; {len(before["artifact_hashes"])} skill archives; revision {before["revision"]}')
    finally:
        if created:
            docker(CONTAINER, 'dropdb', '-U', 'pao', name)
            print('Removed only the isolated restore-test DB created by this check; retained backup.')
    if migrate:
        subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', '0024'], check=True)
        after = await inspect(url)
        if after['revision'] != '0024' or before['counts'] != after['counts'] or before['artifact_hashes'] != after['artifact_hashes']:
            raise RuntimeError('Migration changed existing rows; inspect retained backup')
        print('PASS migration 0023 -> 0024; existing row counts and artifacts unchanged')
    report = {'backup': str(backup), 'bytes': backup.stat().st_size,
              'revision_before': before['revision'], 'migrated': migrate,
              'table_count': len(before['counts']), 'artifact_count': len(before['artifact_hashes'])}
    print(json.dumps(report))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--migrate', action='store_true')
    asyncio.run(main(parser.parse_args().migrate))
