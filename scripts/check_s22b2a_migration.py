"""Own clone0054/0055, exact legacy rollback and refuse erasing admitted jobs."""
import asyncio,json,os,subprocess,sys
from pathlib import Path
from uuid import uuid4
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from pao.config import ROOT,settings
from pao.models import User,Workspace,MetaConnection,MetaSyncJob
from check_s21b1_migration import docker,revision
from check_p11_migration import CONTAINER,snapshot
from check_s03_restore import schema


async def main():
    url=make_url(settings().database_url)
    assert ROOT.resolve()==Path('F:/PAO-ACOS') and url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    assert await revision(url)=='0054'
    before,definitions=await snapshot(url),await schema(url)
    name='pao_s22b2a_migration_'+uuid4().hex;backup=ROOT/'.runtime'/('s22b2a-pre-'+uuid4().hex+'.dump')
    with backup.open('xb') as out:docker(CONTAINER,'pg_dump','-U','pao','-d',url.database,'-Fc',stdout=out)
    created=False
    try:
        docker(CONTAINER,'createdb','-U','pao',name);created=True
        with backup.open('rb') as source:docker('-i',CONTAINER,'pg_restore','-U','pao','-d',name,'--no-owner','--exit-on-error',stdin=source)
        target=url.set(database=name);env={**os.environ,'DATABASE_URL':target.render_as_string(hide_password=False)}
        for command,rev in (('upgrade','0055'),('downgrade','0054'),('upgrade','0055')):
            subprocess.run([sys.executable,'-m','alembic',command,rev],cwd=ROOT,env=env,check=True,timeout=120)
            assert (await snapshot(target,before[0]))[1]==before[1]
            if command=='downgrade':assert await schema(target)==definitions and await snapshot(target)==before
            else:subprocess.run([sys.executable,'-m','alembic','check'],cwd=ROOT,env=env,check=True,timeout=120)
        local=create_async_engine(target);sessions=async_sessionmaker(local)
        try:
            async with sessions.begin() as db:
                user=User(email=uuid4().hex+'@example.test',password_hash='fixture-no-login')
                workspace=Workspace(name='Queue resource clone');db.add_all([user,workspace]);await db.flush()
                conn=MetaConnection(workspace_id=workspace.id,user_id=user.id,status='disconnected');db.add(conn);await db.flush()
                db.add(MetaSyncJob(connection_id=conn.id,connection_version=1,api_version='fixture',
                    request_key=uuid4().hex,kind='accounts',status='completed'))
        finally:await local.dispose()
        populated,shape=await snapshot(target),await schema(target)
        refused=subprocess.run([sys.executable,'-m','alembic','downgrade','0054'],cwd=ROOT,env=env,capture_output=True,text=True,timeout=120)
        assert refused.returncode!=0 and 'tenant read resource history must be preserved' in refused.stderr
        assert await snapshot(target)==populated and await schema(target)==shape and await revision(target)=='0055'
        assert await snapshot(url)==before and await schema(url)==definitions and await revision(url)=='0054'
        print(json.dumps({'pass':True,'up_down_up':'0054->0055->0054->0055','legacy_tables':len(before[0]),
            'row_hashes_exact':True,'rollback_schema_equivalent':True,'populated_downgrade_refused_without_loss':True,
            'primary_unchanged':True,'backup':str(backup)}))
    finally:
        if created:docker(CONTAINER,'dropdb','-U','pao',name);print('Removed only invocation-owned clone; retained source dump.')


if __name__=='__main__':asyncio.run(main())
