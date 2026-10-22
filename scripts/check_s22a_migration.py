"""Own clone only: exact rollback, plus refuse destroying generation history."""
import asyncio,json,os,subprocess,sys
from uuid import uuid4
from pathlib import Path
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from pao.config import ROOT,settings
from pao.models import User,Workspace,Member,ModelProviderConnection,TenantConnectionReference
from check_s21b1_migration import docker,revision
from check_p11_migration import CONTAINER,snapshot
from check_s03_restore import schema


async def populate_history(url):
    engine=create_async_engine(url);sessions=async_sessionmaker(engine,expire_on_commit=False)
    try:
        async with sessions.begin() as db:
            user=User(email='s22-clone-'+uuid4().hex+'@example.test',password_hash='fixture-no-login')
            workspace=Workspace(name='S22 isolated clone fixture');db.add_all([user,workspace]);await db.flush()
            db.add(Member(workspace_id=workspace.id,user_id=user.id,role='owner'))
            source=ModelProviderConnection(workspace_id=workspace.id,provider='openai',model='fixture',
                status='connected',api_key_ciphertext='fixture-ciphertext-not-credential');db.add(source);await db.flush()
            ref=TenantConnectionReference(workspace_id=workspace.id,manager_id=user.id,source_id=source.id,
                kind='model',provider='openai',source_stamp='a'*64,status='staged');db.add(ref);await db.flush()
            ref.status='revoked';ref.revision+=1;await db.flush()
            db.add(TenantConnectionReference(workspace_id=workspace.id,manager_id=user.id,source_id=source.id,
                kind='model',provider='openai',source_stamp='b'*64,status='staged',generation=2,supersedes_id=ref.id))
    finally:await engine.dispose()


async def main():
    url=make_url(settings().database_url)
    assert ROOT.resolve()==Path('F:/PAO-ACOS') and url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    assert await revision(url)=='0052'
    before,definitions=await snapshot(url),await schema(url)
    name='pao_s22a_migration_'+uuid4().hex;backup=ROOT/'.runtime'/('s22a-pre-'+uuid4().hex+'.dump')
    with backup.open('xb') as out:docker(CONTAINER,'pg_dump','-U','pao','-d',url.database,'-Fc',stdout=out)
    created=False
    try:
        docker(CONTAINER,'createdb','-U','pao',name);created=True
        with backup.open('rb') as source:
            docker('-i',CONTAINER,'pg_restore','-U','pao','-d',name,'--no-owner','--exit-on-error',stdin=source)
        target=url.set(database=name);env={**os.environ,'DATABASE_URL':target.render_as_string(hide_password=False)}
        for command,rev in (('upgrade','0053'),('downgrade','0052'),('upgrade','0053')):
            subprocess.run([sys.executable,'-m','alembic',command,rev],cwd=ROOT,env=env,check=True,timeout=120)
            assert (await snapshot(target,before[0]))[1]==before[1]
            if command=='downgrade':assert await schema(target)==definitions and await snapshot(target)==before
            else:subprocess.run([sys.executable,'-m','alembic','check'],cwd=ROOT,env=env,check=True,timeout=120)
        await populate_history(target)
        populated,shape=await snapshot(target),await schema(target)
        refused=subprocess.run([sys.executable,'-m','alembic','downgrade','0052'],cwd=ROOT,env=env,
            capture_output=True,text=True,timeout=120)
        assert refused.returncode!=0 and 'generation history must be preserved' in refused.stderr
        assert await snapshot(target)==populated and await schema(target)==shape and await revision(target)=='0053'
        assert await snapshot(url)==before and await schema(url)==definitions and await revision(url)=='0052'
        print(json.dumps({'pass':True,'up_down_up':'0052->0053->0052->0053','legacy_tables':len(before[0]),
            'row_hashes_exact':True,'rollback_schema_equivalent':True,'populated_downgrade_refused_without_loss':True,
            'primary_unchanged':True,'backup':str(backup)}))
    finally:
        if created:docker(CONTAINER,'dropdb','-U','pao',name);print('Removed only invocation-owned clone; retained source dump.')


if __name__=='__main__':asyncio.run(main())
