"""Owned populated0058->0059->0058->0059 clone; no primary migration/mapping."""
import asyncio,json,os,re,subprocess,sys
from pathlib import Path
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from pao.config import ROOT,settings
from pao.models import User,Workspace,TelegramConnection
from check_s21b1_migration import docker,revision
from check_p11_migration import CONTAINER,snapshot
from check_s03_restore import schema

async def seed_legacy(url):
    local=create_async_engine(url);sessions=async_sessionmaker(local)
    try:
        async with sessions.begin() as db:
            user=User(email=uuid4().hex+'@example.test',password_hash='fixture-no-login')
            space=Workspace(name='Owned migration fixture');db.add_all([user,space]);await db.flush()
            peer,binding=str(uuid4()),str(uuid4());values={'pid':peer,'bid':binding,'uid':user.id,'wid':space.id,'did':str(uuid4())}
            await db.execute(text("INSERT INTO telegram_peers(id,created_at,telegram_user_id,chat_id,user_id,workspace_id,enabled) VALUES(:pid,now(),'999999999','999999999',:uid,:wid,true)"),values)
            await db.execute(text("INSERT INTO telegram_updates(update_id,peer_id,created_at) VALUES(876543210,:pid,now())"),values)
            await db.execute(text("""INSERT INTO telegram_deliveries(id,created_at,peer_id,dedup_key,payload,status,updated_at)
                VALUES(:did,now(),:pid,'clone:legacy:0','{"chat_id":"999999999","text":"Synthetic legacy"}','unknown',now())"""),values)
            await db.execute(text("""INSERT INTO channel_bindings(id,created_at,workspace_id,actor_id,channel,identity_hash,peer_id,kind,mode,enabled,outbound_confirmed,retention_days,version)
                VALUES(:bid,now(),:wid,:uid,'telegram',repeat('a',64),:pid,'personal','quiet',true,false,7,1)"""),values)
            for table,key,extra in (
                ('channel_inbounds','external_key',"body,status"),('channel_outbox','request_key',"body,kind,status,attempts,available_at,updated_at"),
                ('channel_audits','request_key',"actor_id,data")):
                body="'Synthetic','quiet'" if table=='channel_inbounds' else "'Synthetic','manual','unknown',1,now(),now()" if table=='channel_outbox' else ":uid,'{}'"
                await db.execute(text(f"INSERT INTO {table}(id,created_at,workspace_id,binding_id,{key},content_hash,{extra}) VALUES(:id,now(),:wid,:bid,'fixture',repeat('b',64),{body})"),{**values,'id':str(uuid4())})
            return space.id,user.id
    finally:await local.dispose()

async def main():
    url=make_url(settings().database_url)
    assert ROOT.resolve()==Path('F:/PAO-ACOS') and url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    assert await revision(url)=='0058'
    primary,definitions=await snapshot(url),await schema(url)
    name='pao_s31a_migration_'+uuid4().hex;assert re.fullmatch(r'pao_s31a_migration_[0-9a-f]{32}',name)
    backup=ROOT/'.runtime'/('s31a-pre-'+uuid4().hex+'.dump');created=False
    with backup.open('xb') as out:docker(CONTAINER,'pg_dump','-U','pao','-d',url.database,'-Fc',stdout=out)
    try:
        docker(CONTAINER,'createdb','-U','pao',name);created=True
        with backup.open('rb') as source:docker('-i',CONTAINER,'pg_restore','-U','pao','-d',name,'--no-owner','--exit-on-error',stdin=source)
        target=url.set(database=name);wid,uid=await seed_legacy(target)
        before=await snapshot(target);shape=await schema(target)
        env={**os.environ,'DATABASE_URL':target.render_as_string(hide_password=False)}
        for action,rev in (('upgrade','0059'),('downgrade','0058'),('upgrade','0059')):
            subprocess.run([sys.executable,'-m','alembic',action,rev],cwd=ROOT,env=env,check=True,timeout=120)
            assert (await snapshot(target,before[0]))[1]==before[1]
            if action=='downgrade':assert await snapshot(target)==before and await schema(target)==shape
            else:
                subprocess.run([sys.executable,'-m','alembic','check'],cwd=ROOT,env=env,check=True,timeout=120)
                local=create_async_engine(target)
                try:
                    async with local.connect() as db:
                        assert await db.scalar(text('SELECT count(*) FROM telegram_connections'))==0
                        for table in ('telegram_peers','telegram_updates','telegram_deliveries','channel_bindings','channel_inbounds','channel_outbox','channel_audits'):
                            assert await db.scalar(text(f'SELECT count(*) FROM {table} WHERE connection_id IS NOT NULL'))==0
                finally:await local.dispose()
        local=create_async_engine(target);sessions=async_sessionmaker(local)
        try:
            async with sessions.begin() as db:db.add(TelegramConnection(workspace_id=wid,owner_id=uid,bot_user_id='123456'))
            populated,shape=await snapshot(target),await schema(target)
            refused=subprocess.run([sys.executable,'-m','alembic','downgrade','0058'],cwd=ROOT,env=env,capture_output=True,text=True,timeout=120)
            assert refused.returncode!=0 and 'Telegram connection history must be preserved' in refused.stderr
            assert await revision(target)=='0059' and await snapshot(target)==populated and await schema(target)==shape
        finally:await local.dispose()
        assert await snapshot(url)==primary and await schema(url)==definitions and await revision(url)=='0058'
        print(json.dumps({'pass':True,'up_down_up':'0058->0059->0058->0059','legacy_rows_seeded':True,'old_rows_exact':True,
            'rollback_schema_equivalent':True,'populated_downgrade_refused':True,'automatic_mapping':False,'primary_unchanged':True,'backup':str(backup)}))
    finally:
        if created:docker(CONTAINER,'dropdb','-U','pao',name);print('Removed only invocation-owned S31A clone; retained backup.')

if __name__=='__main__':asyncio.run(main())
