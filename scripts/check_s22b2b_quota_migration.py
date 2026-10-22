"""Owned0055/0056 clone: exact legacy rollback and populated refusal."""
import asyncio,json,os,subprocess,sys
from pathlib import Path
from uuid import uuid4
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from sqlalchemy import delete
from pao.config import ROOT,settings
from pao.models import User,Workspace,TenantMetadataPolicy,TenantMetadataLease,now
from datetime import timedelta
from check_s21b1_migration import docker,revision
from check_p11_migration import CONTAINER,snapshot
from check_s03_restore import schema


async def main():
    url=make_url(settings().database_url)
    assert ROOT.resolve()==Path('F:/PAO-ACOS') and url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    assert await revision(url)=='0055'
    before,definitions=await snapshot(url),await schema(url)
    name='pao_s22b2b_metadata_'+uuid4().hex;backup=ROOT/'.runtime'/('s22b2b-metadata-pre-'+uuid4().hex+'.dump')
    with backup.open('xb') as out:docker(CONTAINER,'pg_dump','-U','pao','-d',url.database,'-Fc',stdout=out)
    created=False
    try:
        docker(CONTAINER,'createdb','-U','pao',name);created=True
        with backup.open('rb') as source:docker('-i',CONTAINER,'pg_restore','-U','pao','-d',name,'--no-owner','--exit-on-error',stdin=source)
        target=url.set(database=name);env={**os.environ,'DATABASE_URL':target.render_as_string(hide_password=False)}
        for command,rev in (('upgrade','0056'),('downgrade','0055'),('upgrade','0056')):
            subprocess.run([sys.executable,'-m','alembic',command,rev],cwd=ROOT,env=env,check=True,timeout=120)
            assert (await snapshot(target,before[0]))[1]==before[1]
            if command=='downgrade':assert await schema(target)==definitions and await snapshot(target)==before
            else:subprocess.run([sys.executable,'-m','alembic','check'],cwd=ROOT,env=env,check=True,timeout=120)
        local=create_async_engine(target);sessions=async_sessionmaker(local)
        try:
            async with sessions.begin() as db:
                user=User(email=uuid4().hex+'@example.test',password_hash='fixture-no-login')
                workspace=Workspace(name='Metadata resource clone');db.add_all([user,workspace]);await db.flush()
                uid,wid=user.id,workspace.id
                db.add(TenantMetadataPolicy(workspace_id=wid,version=1,daily_metadata_requests=10,concurrent_metadata=2,updated_by=uid))
            populated,shape=await snapshot(target),await schema(target)
            refused=subprocess.run([sys.executable,'-m','alembic','downgrade','0055'],cwd=ROOT,env=env,capture_output=True,text=True,timeout=120)
            assert refused.returncode!=0 and 'tenant metadata history must be preserved' in refused.stderr
            assert await snapshot(target)==populated and await schema(target)==shape and await revision(target)=='0056'
            # Remove only the invocation-created policy fixture in this owned
            # clone to independently prove admission history blocks downgrade.
            async with sessions.begin() as db:
                await db.execute(delete(TenantMetadataPolicy).where(TenantMetadataPolicy.workspace_id==wid))
                stamp=now();db.add(TenantMetadataLease(workspace_id=wid,actor_id=uid,kind='model_catalogue',
                    request_key=str(uuid4()),target_hash='0'*64,policy_version=0,created_at=stamp,
                    expires_at=stamp+timedelta(seconds=90)))
            populated,shape=await snapshot(target),await schema(target)
            refused=subprocess.run([sys.executable,'-m','alembic','downgrade','0055'],cwd=ROOT,env=env,capture_output=True,text=True,timeout=120)
            assert refused.returncode!=0 and 'tenant metadata history must be preserved' in refused.stderr
            assert await snapshot(target)==populated and await schema(target)==shape and await revision(target)=='0056'
        finally:await local.dispose()
        assert await snapshot(url)==before and await schema(url)==definitions and await revision(url)=='0055'
        print(json.dumps({'pass':True,'up_down_up':'0055->0056->0055->0056','legacy_tables':len(before[0]),
            'row_hashes_exact':True,'rollback_schema_equivalent':True,'populated_policy_and_lease_refuse_independently':True,
            'primary_unchanged':True,'backup':str(backup)}))
    finally:
        if created:docker(CONTAINER,'dropdb','-U','pao',name);print('Removed only invocation-owned clone; retained dump.')


if __name__=='__main__':asyncio.run(main())
