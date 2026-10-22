"""Verify0025→0028 and rollback on a NEW restored DB, never the source."""
import asyncio,os,subprocess,sys,json
from pathlib import Path
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from pao.config import ROOT,settings
from check_p11_migration import docker,snapshot,CONTAINER

async def main():
    url=make_url(settings().database_url)
    if ROOT.resolve()!=Path('F:/PAO-ACOS') or url.database!='pao_acos_local' or url.host!='127.0.0.1' or url.port!=15432:
        raise SystemExit('ACOS source only')
    engine=create_async_engine(url)
    try:
        async with engine.connect() as db:assert await db.scalar(text('SELECT version_num FROM alembic_version'))=='0025'
    finally:await engine.dispose()
    name='pao_p1_storage_'+uuid4().hex;backup=ROOT/'.runtime'/('p1-storage-pre-'+uuid4().hex+'.dump');created=False
    with backup.open('xb') as output:docker(CONTAINER,'pg_dump','-U','pao','-d',url.database,'-Fc',stdout=output)
    try:
        docker(CONTAINER,'createdb','-U','pao',name);created=True
        with backup.open('rb') as source:docker('-i',CONTAINER,'pg_restore','-U','pao','-d',name,'--no-owner','--exit-on-error',stdin=source)
        target=url.set(database=name);columns,before=await snapshot(target)
        env={**os.environ,'DATABASE_URL':target.render_as_string(hide_password=False)}
        def migrate(*args):subprocess.run([sys.executable,'-m','alembic',*args],env=env,cwd=ROOT,check=True)
        migrate('upgrade','0028');assert (await snapshot(target,columns))[1]==before
        migrate('check');migrate('downgrade','0025');assert await snapshot(target)==(columns,before)
        migrate('upgrade','0028');assert (await snapshot(target,columns))[1]==before;migrate('check')
        print(json.dumps({'pass':True,'upgrade':'0025->0028','rollback':'0028->0025',
            'legacy_tables':len(columns),'legacy_row_hashes_unchanged':True,'source_changed':False,'backup':str(backup)}))
    finally:
        if created:docker(CONTAINER,'dropdb','-U','pao',name)
if __name__=='__main__':asyncio.run(main())
