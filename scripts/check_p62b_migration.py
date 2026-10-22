"""Test 0038 on generated clone; retain backup, never migrate source here."""
import asyncio,os,json,subprocess,sys
from uuid import uuid4
from sqlalchemy.engine import make_url
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from pao.config import ROOT,settings
from check_p11_migration import docker,snapshot,CONTAINER

async def main():
    url=make_url(settings().database_url);assert url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    columns,before=await snapshot(url);name='pao_p62b_migration_'+uuid4().hex
    backup=ROOT/'.runtime'/('p62b-pre-'+uuid4().hex+'.dump');created=False
    with backup.open('xb') as file:docker(CONTAINER,'pg_dump','-U','pao','-d',url.database,'-Fc',stdout=file)
    try:
        docker(CONTAINER,'createdb','-U','pao',name);created=True
        with backup.open('rb') as file:docker('-i',CONTAINER,'pg_restore','-U','pao','-d',name,'--no-owner','--exit-on-error',stdin=file)
        clone=url.set(database=name);env={**os.environ,'DATABASE_URL':clone.render_as_string(hide_password=False)}
        def run(*args):subprocess.run([sys.executable,'-m','alembic',*args],cwd=ROOT,env=env,check=True)
        run('upgrade','0038');run('check');assert (await snapshot(clone,columns))[1]==before
        run('downgrade','0037');assert await snapshot(clone)==(columns,before)
        run('upgrade','0038');run('check');assert (await snapshot(clone,columns))[1]==before
        assert (await snapshot(url,columns))[1]==before
        print(json.dumps({'pass':True,'old_table_hashes':len(columns),'up_down_up':'0037->0038->0037->0038','source_unchanged':True}))
    finally:
        if created:docker(CONTAINER,'dropdb','-U','pao',name)
if __name__=='__main__':asyncio.run(main())
