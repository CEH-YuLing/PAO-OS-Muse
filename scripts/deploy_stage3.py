"""Back up, restore-check, and apply the additive Stage 3 migration locally."""
import asyncio
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import make_url

from pao.config import settings
from pao.db import engine


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / '.runtime'
ACTIVE = {
    'runs': ('status', ('queued', 'running')),
    'tool_calls': ('status', ('queued', 'running')),
    'memory_jobs': ('status', ('queued', 'running')),
    'telegram_deliveries': ('status', ('queued', 'sending')),
    'meta_sync_jobs': ('status', ('queued', 'running')),
    'google_ads_sync_jobs': ('status', ('queued', 'running')),
    'ads_actions': ('execution_status', ('queued', 'executing')),
    'automation_outbox': ('status', ('processing',)),
    'task_attempts': ('status', ('running',)),
}


async def snapshot() -> dict[str, int]:
    async with engine.connect() as db:
        tables = list(await db.scalars(text(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' "
            "AND tablename <> 'alembic_version' ORDER BY tablename"
        )))
        for table, (column, states) in ACTIVE.items():
            if table not in tables:
                continue
            quoted = ','.join(f"'{state}'" for state in states)
            count = await db.scalar(text(f'SELECT count(*) FROM "{table}" WHERE "{column}" IN ({quoted})'))
            if count:
                raise RuntimeError(f'Wait until {table} is idle ({count} active)')
        return {table: await db.scalar(text(f'SELECT count(*) FROM "{table}"')) for table in tables}


def run(command: list[str], **kwargs):
    return subprocess.run(command, cwd=ROOT, check=True, **kwargs)


async def main():
    url = make_url(settings().database_url)
    if url.database != 'apex':
        raise RuntimeError('Stage 3 deploy only accepts the local apex database')
    docker = shutil.which('docker')
    if not docker:
        raise RuntimeError('Docker CLI was not found')
    container = run([docker, 'compose', '--env-file', '.env', '-f', 'infra/compose.yaml',
                     'ps', '-q', 'postgres'], capture_output=True, text=True).stdout.strip()
    if not container:
        raise RuntimeError('PostgreSQL container is not running')
    before = await snapshot()
    if '--check' in sys.argv:
        print(json.dumps({'idle': True, 'revision_target': '0022', 'tables': len(before)}))
        await engine.dispose()
        return

    RUNTIME.mkdir(exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    user = url.username or 'apex'

    def backup_and_restore(source_db: str, minimum_tables: int) -> dict:
        label = source_db.replace('_', '-')
        backup = RUNTIME / f'pre-stage-3-{label}-{stamp}.dump'
        with backup.open('xb') as stream:
            run([docker, 'exec', container, 'pg_dump', '-U', user, '-d', source_db, '-Fc'], stdout=stream)
        with backup.open('rb') as stream:
            run([docker, 'exec', '-i', container, 'pg_restore', '--list'], stdin=stream,
                stdout=subprocess.DEVNULL)
        restore_db = f'pao_restore_stage3_{source_db}_{stamp.replace("-", "_")}'
        if source_db not in ('apex', 'temporal', 'temporal_visibility') or not restore_db.startswith('pao_restore_stage3_'):
            raise RuntimeError('Unsafe restore database name')
        created = False
        try:
            run([docker, 'exec', container, 'createdb', '-U', user, restore_db])
            created = True
            with backup.open('rb') as stream:
                run([docker, 'exec', '-i', container, 'pg_restore', '--exit-on-error',
                     '-U', user, '-d', restore_db], stdin=stream)
            restored_tables = int(run(
                [docker, 'exec', container, 'psql', '-U', user, '-d', restore_db,
                 '-Atc', "SELECT count(*) FROM pg_tables WHERE schemaname='public'"],
                capture_output=True, text=True).stdout.strip())
            if restored_tables < minimum_tables:
                raise RuntimeError(f'Isolated restore is missing tables for {source_db}')
        finally:
            if created:
                run([docker, 'exec', container, 'dropdb', '-U', user, restore_db])
        return {'database': source_db, 'path': str(backup), 'bytes': backup.stat().st_size,
                'restore_check': 'passed', 'restored_tables': restored_tables}

    backups = [backup_and_restore(url.database, len(before))]
    backups.extend(backup_and_restore(name, 1) for name in ('temporal', 'temporal_visibility'))
    run([sys.executable, '-m', 'alembic', 'upgrade', 'head'])
    after = await snapshot()
    for table, count in before.items():
        if after.get(table) != count:
            raise RuntimeError(f'Row count changed during migration: {table}')
    report = {'backups': backups, 'revision': '0022',
              'tables_before': len(before), 'tables_after': len(after)}
    (RUNTIME / 'stage-3-migration.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))
    await engine.dispose()


asyncio.run(main())
