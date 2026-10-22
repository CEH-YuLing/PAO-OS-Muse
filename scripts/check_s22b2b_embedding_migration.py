"""0056->0057 rollback on invocation-owned clone; primary never migrated here."""
import asyncio,json,os,subprocess,sys
from pathlib import Path
from uuid import uuid4
from datetime import timedelta
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from pao.config import ROOT,settings
from pao.models import User,Workspace,TenantModelLease,now
from check_s21b1_migration import docker,revision
from check_p11_migration import CONTAINER,snapshot
from check_s03_restore import schema

async def main():
    url=make_url(settings().database_url)
    assert ROOT.resolve()==Path('F:/PAO-ACOS') and url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    assert await revision(url)=='0056'
    before,definitions=await snapshot(url),await schema(url)
    name='pao_embedding_migration_'+uuid4().hex
    backup=ROOT/'.runtime'/('embedding-pre-'+uuid4().hex+'.dump');created=False
    with backup.open('xb') as out:docker(CONTAINER,'pg_dump','-U','pao','-d',url.database,'-Fc',stdout=out)
    try:
        docker(CONTAINER,'createdb','-U','pao',name);created=True
        with backup.open('rb') as source:docker('-i',CONTAINER,'pg_restore','-U','pao','-d',name,'--no-owner','--exit-on-error',stdin=source)
        target=url.set(database=name);env={**os.environ,'DATABASE_URL':target.render_as_string(hide_password=False)}
        for command,rev in (('upgrade','0057'),('downgrade','0056'),('upgrade','0057')):
            subprocess.run([sys.executable,'-m','alembic',command,rev],cwd=ROOT,env=env,check=True,timeout=120)
            assert (await snapshot(target,before[0]))[1]==before[1]
            if command=='downgrade':assert await schema(target)==definitions and await snapshot(target)==before
            else:subprocess.run([sys.executable,'-m','alembic','check'],cwd=ROOT,env=env,check=True,timeout=120)
        local=create_async_engine(target);sessions=async_sessionmaker(local)
        try:
            async with sessions.begin() as db:
                actor=User(email=uuid4().hex+'@example.test',password_hash='fixture-no-login')
                space=Workspace(name='Embedding owned clone');db.add_all([actor,space]);await db.flush();stamp=now()
                db.add(TenantModelLease(workspace_id=space.id,actor_id=actor.id,kind='embedding',request_key=uuid4().hex,
                    policy_version=0,reserved_tokens=20,embedding_pin={'model':'local-fixture'},
                    created_at=stamp,expires_at=stamp+timedelta(seconds=15)))
            populated,shape=await snapshot(target),await schema(target)
            refused=subprocess.run([sys.executable,'-m','alembic','downgrade','0056'],cwd=ROOT,env=env,capture_output=True,text=True,timeout=120)
            assert refused.returncode!=0 and 'embedding history must be preserved' in refused.stderr
            assert await snapshot(target)==populated and await schema(target)==shape and await revision(target)=='0057'
        finally:await local.dispose()
        assert await snapshot(url)==before and await schema(url)==definitions and await revision(url)=='0056'
        print(json.dumps({'pass':True,'up_down_up':'0056->0057->0056->0057','legacy_rows_exact':True,
            'rollback_schema_equivalent':True,'populated_downgrade_refused':True,'primary_unchanged':True,'backup':str(backup)}))
    finally:
        if created:docker(CONTAINER,'dropdb','-U','pao',name);print('Removed only this invocation-owned clone; retained dump.')

if __name__=='__main__':asyncio.run(main())
