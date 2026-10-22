"""0060/0061/0062 isolated roundtrips and identity downgrade guard; no primary writes."""
import asyncio,json,os,re,subprocess,sys
from pathlib import Path
from uuid import uuid4
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from pao.config import ROOT,settings
from pao.models import User,Workspace,Member,TelegramConnection,TelegramBotIdentity
from check_s21b1_migration import docker,revision
from check_p11_migration import CONTAINER,snapshot
from check_s03_restore import schema


async def main():
    url=make_url(settings().database_url)
    assert ROOT.resolve()==Path('F:/PAO-ACOS') and url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    assert await revision(url)=='0060' and not settings().telegram_enabled and not settings().telegram_scoped_runtime_enabled
    before,shape=await snapshot(url),await schema(url)
    name='pao_s32b_identity_'+uuid4().hex;assert re.fullmatch('pao_s32b_identity_[0-9a-f]{32}',name)
    backup=ROOT/'.runtime'/('s32b-identity-pre-'+uuid4().hex+'.dump');created=False
    with backup.open('xb') as out:docker(CONTAINER,'pg_dump','-U','pao','-d',url.database,'-Fc',stdout=out)
    try:
        docker(CONTAINER,'createdb','-U','pao',name);created=True
        with backup.open('rb') as source:docker('-i',CONTAINER,'pg_restore','-U','pao','-d',name,'--no-owner','--exit-on-error',stdin=source)
        target=url.set(database=name);env={**os.environ,'DATABASE_URL':target.render_as_string(hide_password=False)}
        def migrate(action,rev):
            subprocess.run([sys.executable,'-m','alembic',action,rev],cwd=ROOT,env=env,check=True,timeout=120)
        migrate('upgrade','0061');before61,shape61=await snapshot(target),await schema(target)
        for action,rev in (('upgrade','0062'),('downgrade','0061'),('upgrade','0062'),('downgrade','0060'),('upgrade','0062')):
            migrate(action,rev)
            assert (await snapshot(target,before[0]))[1]==before[1]
            if action=='downgrade':
                assert await snapshot(target)==(before61 if rev=='0061' else before)
                assert await schema(target)==(shape61 if rev=='0061' else shape)
            else:subprocess.run([sys.executable,'-m','alembic','check'],cwd=ROOT,env=env,check=True,timeout=120)
        local=create_async_engine(target);sessions=async_sessionmaker(local,expire_on_commit=False)
        try:
            async with sessions.begin() as db:
                user=User(email=uuid4().hex+'@example.test',password_hash='synthetic-no-login');space=Workspace(name='Identity clone')
                db.add_all([user,space]);await db.flush();db.add(Member(workspace_id=space.id,user_id=user.id,role='owner'))
                conn=TelegramConnection(workspace_id=space.id,owner_id=user.id,bot_user_id='123456789');db.add(conn);await db.flush()
                db.add(TelegramBotIdentity(workspace_id=space.id,connection_id=conn.id,owner_id=user.id,connection_version=1,
                    bot_user_id=conn.bot_user_id,request_key=str(uuid4()),content_hash='a'*64))
            populated,definitions=await snapshot(target),await schema(target)
            refused=subprocess.run([sys.executable,'-m','alembic','downgrade','0061'],cwd=ROOT,env=env,capture_output=True,text=True,timeout=120)
            assert refused.returncode and 'Telegram bot identity history must be preserved' in refused.stderr
            assert await revision(target)=='0062' and await snapshot(target)==populated and await schema(target)==definitions
        finally:await local.dispose()
        assert await revision(url)=='0060' and await snapshot(url)==before and await schema(url)==shape
        result={'pass':True,'roundtrips':'0061->0062->0061->0062;0060->0062->0060->0062',
            'old_rows_exact':True,'rollback_schema_equivalent':True,'populated_downgrade_refused':True,
            'primary_unchanged':True,'provider_calls':False,'backup':str(backup)}
        (ROOT/'.runtime'/'s32b-identity-migration.json').write_text(json.dumps(result),encoding='utf-8');print(json.dumps(result))
    finally:
        if created:docker(CONTAINER,'dropdb','-U','pao',name);print('Removed only invocation-owned identity clone; retained backup.')


if __name__=='__main__':asyncio.run(main())
