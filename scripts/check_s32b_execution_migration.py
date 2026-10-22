"""0062/0063 and0060/0063 clone roundtrips; no primary schema changes."""
import asyncio,json,os,re,subprocess,sys
from pathlib import Path
from uuid import uuid4
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from pao.config import ROOT,settings
from pao.models import User,Workspace,Member,TelegramConnection,TelegramRuntimeProfile,TelegramRuntimeAudit
from check_s21b1_migration import docker,revision
from check_p11_migration import CONTAINER,snapshot
from check_s03_restore import schema


async def main():
    url=make_url(settings().database_url)
    assert ROOT.resolve()==Path('F:/PAO-ACOS') and url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    assert await revision(url)=='0060' and not settings().telegram_enabled and not settings().telegram_scoped_runtime_enabled
    before,shape=await snapshot(url),await schema(url)
    name='pao_s32b_execution_'+uuid4().hex;assert re.fullmatch('pao_s32b_execution_[0-9a-f]{32}',name)
    backup=ROOT/'.runtime'/('s32b-execution-pre-'+uuid4().hex+'.dump');created=False
    with backup.open('xb') as out:docker(CONTAINER,'pg_dump','-U','pao','-d',url.database,'-Fc',stdout=out)
    try:
        docker(CONTAINER,'createdb','-U','pao',name);created=True
        with backup.open('rb') as source:docker('-i',CONTAINER,'pg_restore','-U','pao','-d',name,'--no-owner','--exit-on-error',stdin=source)
        target=url.set(database=name);env={**os.environ,'DATABASE_URL':target.render_as_string(hide_password=False)}
        def migrate(action,rev):subprocess.run([sys.executable,'-m','alembic',action,rev],cwd=ROOT,env=env,check=True,timeout=120)
        migrate('upgrade','0062');before62,shape62=await snapshot(target),await schema(target)
        for action,rev in (('upgrade','0063'),('downgrade','0062'),('upgrade','0063'),('downgrade','0060'),('upgrade','0063')):
            migrate(action,rev)
            assert (await snapshot(target,before[0]))[1]==before[1]
            if action=='downgrade':
                assert await snapshot(target)==(before62 if rev=='0062' else before)
                assert await schema(target)==(shape62 if rev=='0062' else shape)
            else:subprocess.run([sys.executable,'-m','alembic','check'],cwd=ROOT,env=env,check=True,timeout=120)
        local=create_async_engine(target);sessions=async_sessionmaker(local,expire_on_commit=False)
        try:
            async with sessions.begin() as db:
                user=User(email=uuid4().hex+'@example.test',password_hash='synthetic-no-login');space=Workspace(name='Execution clone')
                db.add_all([user,space]);await db.flush();db.add(Member(workspace_id=space.id,user_id=user.id,role='owner'))
                conn=TelegramConnection(workspace_id=space.id,owner_id=user.id,bot_user_id='123456789');db.add(conn);await db.flush()
                profile=TelegramRuntimeProfile(workspace_id=space.id,connection_id=conn.id,connection_version=1,generation=1,
                    status='disabled',token_ciphertext='synthetic-only-1',next_offset=0)
                db.add(profile);await db.flush()
                db.add(TelegramRuntimeAudit(workspace_id=space.id,connection_id=conn.id,actor_id=user.id,
                    request_key=str(uuid4()),generation=1,action='stored',content_hash='a'*64));await db.flush()
                profile.generation=2;profile.status='enabled';profile.token_ciphertext='synthetic-only-2';await db.flush()
                db.add(TelegramRuntimeAudit(workspace_id=space.id,connection_id=conn.id,actor_id=user.id,
                    request_key=str(uuid4()),generation=2,action='enabled',content_hash='b'*64))
            populated,definitions=await snapshot(target),await schema(target)
            refused=subprocess.run([sys.executable,'-m','alembic','downgrade','0062'],cwd=ROOT,env=env,capture_output=True,text=True,timeout=120)
            assert refused.returncode and 'Telegram scoped execution history must be preserved' in refused.stderr
            assert await revision(target)=='0063' and await snapshot(target)==populated and await schema(target)==definitions
        finally:await local.dispose()
        assert await revision(url)=='0060' and await snapshot(url)==before and await schema(url)==shape
        result={'pass':True,'roundtrips':'0062->0063->0062->0063;0060->0063->0060->0063','old_rows_exact':True,
            'rollback_schema_equivalent':True,'populated_downgrade_refused':True,'primary_unchanged':True,'provider_calls':False,'backup':str(backup)}
        (ROOT/'.runtime'/'s32b-execution-migration.json').write_text(json.dumps(result),encoding='utf-8');print(json.dumps(result))
    finally:
        if created:docker(CONTAINER,'dropdb','-U','pao',name);print('Removed only invocation-owned execution clone; retained backup.')


if __name__=='__main__':asyncio.run(main())
