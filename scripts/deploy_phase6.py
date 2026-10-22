"""Back up and migrate the configured local database, after stopping API/worker."""
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
TABLES = ('users','sessions','messages','runs','agent_runs','memories','tool_calls','tool_audits')

async def snapshot():
    async with engine.connect() as db:
        active = await db.scalar(text("select count(*) from runs where status in ('queued','running')"))
        if active:
            raise RuntimeError('Active runs exist; finish them before deployment')
        return {table: await db.scalar(text(f'SELECT count(*) FROM {table}')) for table in TABLES}

async def main():
    assert settings().database_url.endswith('/apex'), 'This deployment is for the existing apex database only'
    if settings().telegram_enabled:
        raise RuntimeError('Keep Telegram disabled until real bot setup and acceptance')
    before = await snapshot()
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    backup = Path(f'.runtime/pre-phase-6-{stamp}.dump')
    with backup.open('xb') as stream:
        subprocess.run([DOCKER,'exec','pao-postgres-1','pg_dump','-U','apex','-d','apex','-Fc'],stdout=stream,check=True)
    with backup.open('rb') as stream:
        subprocess.run([DOCKER,'exec','-i','pao-postgres-1','pg_restore','--list'],stdin=stream,stdout=subprocess.DEVNULL,check=True)
    subprocess.run([sys.executable,'-m','alembic','upgrade','head'],check=True)
    after = await snapshot()
    assert before == after, 'Table counts changed; inspect backup and migration before starting services'
    async with engine.connect() as db:
        revision = await db.scalar(text('select version_num from alembic_version'))
    report = {'backup':str(backup),'bytes':backup.stat().st_size,'before':before,'after':after,'revision':revision}
    Path('.runtime/phase-6-migration.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))
    await engine.dispose()

asyncio.run(main())
