"""Restore 0031 into a UUID database; verify 0032 up/down/up, never source migration."""
import asyncio,json,os,subprocess,sys,zipfile
from uuid import uuid4
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from pao.config import ROOT,settings
from pao.main import app
from check_p11_migration import docker,snapshot,CONTAINER

async def main():
    url=make_url(settings().database_url)
    assert url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    db=create_async_engine(url)
    async with db.connect() as conn:assert await conn.scalar(text('SELECT version_num FROM alembic_version'))=='0031'
    await db.dispose()
    baseline=ROOT/'.runtime/checkpoints/p0-20261006T121007-e85b15a9/source.zip'
    with zipfile.ZipFile(baseline) as archive:
        old=json.loads(archive.read('packages/contracts/openapi.json'))
    current=app.openapi()
    for path,operations in old['paths'].items():
        for method,value in operations.items():assert current['paths'][path][method]==value,(path,method)
    for name,schema in old['components']['schemas'].items():assert current['components']['schemas'][name]==schema,name
    name='pao_p3_migration_'+uuid4().hex;backup=ROOT/'.runtime'/('p3-pre-'+uuid4().hex+'.dump');created=False
    with backup.open('xb') as file:docker(CONTAINER,'pg_dump','-U','pao','-d',url.database,'-Fc',stdout=file)
    try:
        docker(CONTAINER,'createdb','-U','pao',name);created=True
        with backup.open('rb') as file:docker('-i',CONTAINER,'pg_restore','-U','pao','-d',name,'--no-owner','--exit-on-error',stdin=file)
        target=url.set(database=name);columns,before=await snapshot(target)
        env={**os.environ,'DATABASE_URL':target.render_as_string(hide_password=False)}
        def migrate(*args):subprocess.run([sys.executable,'-m','alembic',*args],env=env,cwd=ROOT,check=True)
        migrate('upgrade','0032');assert (await snapshot(target,columns))[1]==before;migrate('check')
        migrate('downgrade','0031');assert await snapshot(target)==(columns,before)
        migrate('upgrade','0032');assert (await snapshot(target,columns))[1]==before;migrate('check')
        print(json.dumps({'pass':True,'old_operations':sum(len(v) for v in old['paths'].values()),'old_schemas_unchanged':True,
            'old_table_hashes':len(columns),'up_down_up':'0031->0032->0031->0032','source_database_untouched':True,'backup':str(backup)}))
    finally:
        if created:docker(CONTAINER,'dropdb','-U','pao',name)
if __name__=='__main__':asyncio.run(main())
