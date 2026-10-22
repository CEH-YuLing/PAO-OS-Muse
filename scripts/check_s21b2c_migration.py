"""Owned clone only: 0050/0051 rollback and exact legacy row/schema checks."""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4
from sqlalchemy.engine import make_url
from pao.config import ROOT, settings
from check_s21b1_migration import docker, revision
from check_p11_migration import CONTAINER, snapshot
from check_s03_restore import schema


async def main():
    url=make_url(settings().database_url)
    assert ROOT.resolve()==Path('F:/PAO-ACOS') and url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    assert await revision(url)=='0050'
    before,definitions=await snapshot(url),await schema(url)
    name='pao_s21b2c_migration_'+uuid4().hex
    backup=ROOT/'.runtime'/('s21b2c-pre-'+uuid4().hex+'.dump')
    with backup.open('xb') as out:docker(CONTAINER,'pg_dump','-U','pao','-d',url.database,'-Fc',stdout=out)
    created=False
    try:
        docker(CONTAINER,'createdb','-U','pao',name);created=True
        with backup.open('rb') as source:
            docker('-i',CONTAINER,'pg_restore','-U','pao','-d',name,'--no-owner','--exit-on-error',stdin=source)
        target=url.set(database=name);env={**os.environ,'DATABASE_URL':target.render_as_string(hide_password=False)}
        for command,rev in (('upgrade','0051'),('downgrade','0050'),('upgrade','0051')):
            subprocess.run([sys.executable,'-m','alembic',command,rev],cwd=ROOT,env=env,check=True,timeout=120)
            assert (await snapshot(target,before[0]))[1]==before[1]
            if command=='downgrade':assert await schema(target)==definitions and await snapshot(target)==before
            else:subprocess.run([sys.executable,'-m','alembic','check'],cwd=ROOT,env=env,check=True,timeout=120)
        assert await snapshot(url)==before and await schema(url)==definitions and await revision(url)=='0050'
        print(json.dumps({'pass':True,'up_down_up':'0050->0051->0050->0051','legacy_tables':len(before[0]),
            'row_hashes_exact':True,'rollback_schema_equivalent':True,'primary_unchanged':True,'backup':str(backup)}))
    finally:
        if created:
            docker(CONTAINER,'dropdb','-U','pao',name)
            print('Removed only invocation-owned clone; retained source dump.')


if __name__=='__main__':asyncio.run(main())
