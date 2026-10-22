"""Owned-clone 0064/0065 roundtrip, data preservation, populated refusal."""
import asyncio,json,os,re,subprocess,sys
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from pao.config import ROOT,settings
from check_s21b1_migration import docker,revision
from check_p11_migration import CONTAINER,snapshot
from check_s03_restore import schema


async def main():
    url=make_url(settings().database_url)
    assert ROOT.resolve().as_posix()=='F:/PAO-ACOS' and url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    assert await revision(url)=='0064'
    before,shape=await snapshot(url),await schema(url)
    name='pao_s4_migration_'+uuid4().hex;assert re.fullmatch('pao_s4_migration_[0-9a-f]{32}',name)
    backup=ROOT/'.runtime'/('s4-migration-'+uuid4().hex+'.dump');created=False
    with backup.open('xb') as out:docker(CONTAINER,'pg_dump','-U','pao','-d',url.database,'-Fc',stdout=out)
    try:
        docker(CONTAINER,'createdb','-U','pao',name);created=True
        with backup.open('rb') as source:docker('-i',CONTAINER,'pg_restore','-U','pao','-d',name,'--no-owner','--exit-on-error',stdin=source)
        target=url.set(database=name);env={**os.environ,'DATABASE_URL':target.render_as_string(hide_password=False)}
        def migrate(action,rev):subprocess.run([sys.executable,'-m','alembic',action,rev],cwd=ROOT,env=env,check=True,timeout=120)
        for action,rev in (('upgrade','0065'),('downgrade','0064'),('upgrade','0065')):
            migrate(action,rev)
            assert (await snapshot(target,before[0]))[1]==before[1]
            if action=='downgrade':assert await snapshot(target)==before and await schema(target)==shape
            else:subprocess.run([sys.executable,'-m','alembic','check'],cwd=ROOT,env=env,check=True,timeout=120)
        engine=create_async_engine(target)
        try:
            async with engine.begin() as db:
                wid=await db.scalar(text('SELECT id FROM workspaces ORDER BY id LIMIT 1'));assert wid
                await db.execute(text("INSERT INTO ads_app_configs(workspace_id,provider,mode,revision) VALUES(:wid,'meta','managed',1)"),{'wid':wid})
            populated,definitions=await snapshot(target),await schema(target)
            refusal=subprocess.run([sys.executable,'-m','alembic','downgrade','0064'],cwd=ROOT,env=env,capture_output=True,text=True,timeout=120)
            assert refusal.returncode and 'Populated S4 app history' in refusal.stderr
            assert await revision(target)=='0065' and await snapshot(target)==populated and await schema(target)==definitions
        finally:await engine.dispose()
        assert await revision(url)=='0064' and await snapshot(url)==before and await schema(url)==shape
        value={'pass':True,'roundtrip':'0064->0065->0064->0065','old_columns_exact':True,'rollback_schema_exact':True,
            'populated_downgrade_refused':True,'primary_unchanged':True,'provider_calls':False,'backup':str(backup)}
        (ROOT/'.runtime/s4-migration.json').write_text(json.dumps(value),encoding='utf-8');print(json.dumps(value))
    finally:
        if created:docker(CONTAINER,'dropdb','-U','pao',name);print('Removed only invocation-owned migration clone; backup retained.')


if __name__=='__main__':asyncio.run(main())
