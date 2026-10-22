"""0028→0029→0028→0029 on a NEW restored DB; original rows untouched."""
import asyncio,os,subprocess,sys,json,zipfile
from pathlib import Path
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from pao.config import ROOT,settings
from pao.main import app
from check_p11_migration import docker,snapshot,CONTAINER

BASELINE=Path('F:/PAO-ACOS/.runtime/checkpoints/p0-20261006T085016-ec509841/source.zip')

def contract():
    with zipfile.ZipFile(BASELINE) as source:
        names=[name for name in source.namelist() if name.endswith('packages/contracts/openapi.json')]
        assert len(names)==1
        before=json.loads(source.read(names[0]))
    after=app.openapi()
    for path,operations in before['paths'].items():
        for method,definition in operations.items():assert after['paths'][path][method]==definition,(path,method)
    for name,value in before['components']['schemas'].items():assert after['components']['schemas'][name]==value,name
    old=sum(len(operations) for operations in before['paths'].values())
    new=sum(len(operations) for operations in after['paths'].values())
    assert old==160 and new==171
    print('PASS all160 previous operations/schemas unchanged;11 Sources operations added',flush=True)

async def main():
    url=make_url(settings().database_url)
    if ROOT.resolve()!=Path('F:/PAO-ACOS') or url.database!='pao_acos_local' or url.host!='127.0.0.1' or url.port!=15432:
        raise SystemExit('ACOS source only')
    engine=create_async_engine(url)
    try:
        async with engine.connect() as db:assert await db.scalar(text('SELECT version_num FROM alembic_version'))=='0028'
    finally:await engine.dispose()
    contract();columns,before=await snapshot(url)
    name='pao_p21_'+uuid4().hex;backup=ROOT/'.runtime'/('p21-pre-'+uuid4().hex+'.dump');created=False
    with backup.open('xb') as output:docker(CONTAINER,'pg_dump','-U','pao','-d',url.database,'-Fc',stdout=output)
    try:
        docker(CONTAINER,'createdb','-U','pao',name);created=True
        with backup.open('rb') as source:docker('-i',CONTAINER,'pg_restore','-U','pao','-d',name,'--no-owner','--exit-on-error',stdin=source)
        target=url.set(database=name);assert (await snapshot(target,columns))[1]==before
        env={**os.environ,'DATABASE_URL':target.render_as_string(hide_password=False)}
        def migrate(*args):subprocess.run([sys.executable,'-m','alembic',*args],env=env,cwd=ROOT,check=True)
        migrate('upgrade','0029');assert (await snapshot(target,columns))[1]==before;migrate('check')
        migrate('downgrade','0028');assert await snapshot(target)==(columns,before)
        migrate('upgrade','0029');assert (await snapshot(target,columns))[1]==before;migrate('check')
        assert (await snapshot(url,columns))[1]==before
        print(json.dumps({'pass':True,'upgrade':'0028->0029','rollback':'0029->0028','legacy_tables':len(columns),
            'legacy_row_hashes_unchanged':True,'source_changed':False,'backup':str(backup)}))
    finally:
        if created:docker(CONTAINER,'dropdb','-U','pao',name)
if __name__=='__main__':asyncio.run(main())
