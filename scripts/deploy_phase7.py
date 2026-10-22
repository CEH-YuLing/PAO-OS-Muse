"""Verify idle local DB; back up before additive Phase 7 migration.

Run --check before stopping API/worker/Telegram; then run without flags.
"""
import asyncio
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from sqlalchemy import text
from pao.db import engine
from pao.config import settings

DOCKER = os.environ.get("DOCKER_EXECUTABLE") or shutil.which("docker") or "docker"
TABLES=('users','workspaces','sessions','messages','runs','agent_runs','memories','tool_calls','tool_audits','telegram_peers','telegram_updates','telegram_deliveries')


async def snapshot():
    async with engine.connect() as db:
        for table,states in [('runs',"'queued','running'"),('tool_calls',"'queued','running'"),('memory_jobs',"'queued','running'"),('telegram_deliveries',"'queued','sending'")]:
            if await db.scalar(text(f'SELECT count(*) FROM {table} WHERE status IN ({states})')):
                raise RuntimeError(f'Wait until {table} work is idle before deployment')
        return {table:await db.scalar(text(f'SELECT count(*) FROM {table}')) for table in TABLES}


async def main():
    assert settings().database_url.endswith('/apex'),'Expected existing local apex database'
    before=await snapshot()
    if '--check' in sys.argv:
        print(json.dumps({'idle':True,'counts':before}));await engine.dispose();return
    stamp=datetime.now().strftime('%Y%m%d-%H%M%S')
    backup=Path(f'.runtime/pre-phase-7-{stamp}.dump')
    with backup.open('xb') as stream:
        subprocess.run([DOCKER,'exec','pao-postgres-1','pg_dump','-U','apex','-d','apex','-Fc'],stdout=stream,check=True)
    with backup.open('rb') as stream:
        subprocess.run([DOCKER,'exec','-i','pao-postgres-1','pg_restore','--list'],stdin=stream,stdout=subprocess.DEVNULL,check=True)
    subprocess.run([sys.executable,'-m','alembic','upgrade','head'],check=True)
    after=await snapshot()
    assert before==after,'Counts changed; inspect backup before restarting services'
    report={'backup':str(backup),'bytes':backup.stat().st_size,'before':before,'after':after,'revision':'0006'}
    Path('.runtime/phase-7-migration.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report));await engine.dispose()


asyncio.run(main())
