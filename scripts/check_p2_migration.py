"""P2 additive/rollback drill on a generated restored database only."""
import asyncio,json,os,subprocess,sys,zipfile
from pathlib import Path
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from pao.config import ROOT,settings
from pao.main import app
from check_p11_migration import docker,snapshot,CONTAINER
async def main():
    url=make_url(settings().database_url)
    assert ROOT.resolve()==Path('F:/PAO-ACOS') and url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    with zipfile.ZipFile(ROOT/'.runtime/checkpoints/p0-20261006T091633-63e171f8/source.zip') as archive:
        names=[n for n in archive.namelist() if n.endswith('packages/contracts/openapi.json')];assert len(names)==1
        before=json.loads(archive.read(names[0]))
    after=app.openapi()
    for path,methods in before['paths'].items():
        for method,value in methods.items():assert after['paths'][path][method]==value,(path,method)
    for name,value in before['components']['schemas'].items():assert after['components']['schemas'][name]==value,name
    assert sum(map(len,before['paths'].values()))==171 and sum(map(len,after['paths'].values()))==195
    engine=create_async_engine(url)
    async with engine.connect() as db:assert await db.scalar(text('SELECT version_num FROM alembic_version'))=='0029'
    await engine.dispose();columns,original=await snapshot(url)
    name='pao_p2_restore_'+uuid4().hex;backup=ROOT/'.runtime'/('p2-pre-'+uuid4().hex+'.dump');created=False
    with backup.open('xb') as file:docker(CONTAINER,'pg_dump','-U','pao','-d',url.database,'-Fc',stdout=file)
    try:
        docker(CONTAINER,'createdb','-U','pao',name);created=True
        with backup.open('rb') as file:docker('-i',CONTAINER,'pg_restore','-U','pao','-d',name,'--no-owner','--exit-on-error',stdin=file)
        target=url.set(database=name);env={**os.environ,'DATABASE_URL':target.render_as_string(hide_password=False)}
        def migrate(*args):subprocess.run([sys.executable,'-m','alembic',*args],cwd=ROOT,env=env,check=True)
        migrate('upgrade','0030');migrate('check');assert (await snapshot(target,columns))[1]==original
        migrate('downgrade','0029');assert await snapshot(target)==(columns,original)
        migrate('upgrade','0030');migrate('check');assert (await snapshot(target,columns))[1]==original
        assert (await snapshot(url,columns))[1]==original
        print(json.dumps({'pass':True,'previous_operations_unchanged':171,'new_operations':24,'legacy_tables':len(columns),'roundtrip':'0029->0030->0029->0030','local_unchanged':True,'backup':str(backup)}))
    finally:
        if created:docker(CONTAINER,'dropdb','-U','pao',name)
if __name__=='__main__':asyncio.run(main())
