"""Isolated populated0059 clone:0060 roundtrip/journal downgrade guard; primary untouched."""
import asyncio,json,os,re,subprocess,sys
from pathlib import Path
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from pao.config import ROOT,settings
from pao.auth import Principal
from pao.models import User,Workspace,Member,TelegramPeer,TelegramUpdate,TelegramDelivery,ChannelBinding,ChannelOutbox
from pao.modules.channels.legacy_mapping import snapshot as preview,apply
from pao.modules.channels.legacy_mapping_api import TelegramLegacyApply
from check_s21b1_migration import docker,revision
from check_p11_migration import CONTAINER,snapshot
from check_s03_restore import schema

async def seed_legacy(url):
    local=create_async_engine(url);sessions=async_sessionmaker(local,expire_on_commit=False)
    try:
        async with sessions.begin() as db:
            user=User(email=uuid4().hex+'@example.test',password_hash='fixture-no-login');space=Workspace(name='Owned mapping fixture')
            db.add_all([user,space]);await db.flush();db.add(Member(workspace_id=space.id,user_id=user.id,role='owner'))
            peer=TelegramPeer(workspace_id=space.id,user_id=user.id,telegram_user_id='999999999',chat_id='999999999');db.add(peer);await db.flush()
            binding=ChannelBinding(workspace_id=space.id,actor_id=user.id,channel='telegram',identity_hash='a'*64,peer_id=peer.id,
                kind='personal',mode='quiet',enabled=True,outbound_confirmed=False,retention_days=7,version=1);db.add(binding);await db.flush()
            #0059 changed update identity to UUID; do not reuse0058 fixture SQL.
            db.add(TelegramUpdate(peer_id=peer.id,update_id=876543210))
            db.add(TelegramDelivery(peer_id=peer.id,dedup_key='clone:legacy:0',payload={'chat_id':'999999999','text':'Synthetic legacy'},status='unknown'))
            db.add(ChannelOutbox(workspace_id=space.id,binding_id=binding.id,request_key='fixture',content_hash='b'*64,body='Synthetic',kind='manual',status='unknown'))
            return space.id,user.id
    finally:await local.dispose()

async def main():
    url=make_url(settings().database_url)
    assert ROOT.resolve()==Path('F:/PAO-ACOS') and url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    assert await revision(url)=='0059' and not settings().telegram_enabled
    primary,definitions=await snapshot(url),await schema(url)
    name='pao_s31b_migration_'+uuid4().hex;assert re.fullmatch(r'pao_s31b_migration_[0-9a-f]{32}',name)
    backup=ROOT/'.runtime'/('s31b-pre-'+uuid4().hex+'.dump');created=False
    with backup.open('xb') as out:docker(CONTAINER,'pg_dump','-U','pao','-d',url.database,'-Fc',stdout=out)
    try:
        docker(CONTAINER,'createdb','-U','pao',name);created=True
        with backup.open('rb') as source:docker('-i',CONTAINER,'pg_restore','-U','pao','-d',name,'--no-owner','--exit-on-error',stdin=source)
        target=url.set(database=name);wid,uid=await seed_legacy(target)
        before=await snapshot(target);shape=await schema(target)
        env={**os.environ,'DATABASE_URL':target.render_as_string(hide_password=False)}
        for action,rev in (('upgrade','0060'),('downgrade','0059'),('upgrade','0060')):
            subprocess.run([sys.executable,'-m','alembic',action,rev],cwd=ROOT,env=env,check=True,timeout=120)
            assert (await snapshot(target,before[0]))[1]==before[1]
            if action=='downgrade':assert await snapshot(target)==before and await schema(target)==shape
            else:
                subprocess.run([sys.executable,'-m','alembic','check'],cwd=ROOT,env=env,check=True,timeout=120)
                local=create_async_engine(target)
                try:
                    async with local.connect() as db:
                        for table in ('telegram_legacy_mappings','telegram_legacy_peer_maps','telegram_legacy_mapping_audits'):
                            assert await db.scalar(text('SELECT count(*) FROM '+table))==0
                finally:await local.dispose()
        local=create_async_engine(target);sessions=async_sessionmaker(local,expire_on_commit=False)
        try:
            # Clone-only synthetic consent. Never select a real SME automatically.
            async with sessions() as db:
                proposed,_,_,_=await preview(db,wid,Principal(uid,0));assert proposed['eligible'],proposed['reason']
                await apply(db,wid,Principal(uid,0),TelegramLegacyApply(request_key=uuid4(),expected_version=0,
                    preview_hash=proposed['preview_hash'],data_only_ack=True,no_history_replay_ack=True))
            populated,shape=await snapshot(target),await schema(target)
            refused=subprocess.run([sys.executable,'-m','alembic','downgrade','0059'],cwd=ROOT,env=env,capture_output=True,text=True,timeout=120)
            assert refused.returncode!=0 and 'Telegram legacy mapping history must be preserved' in refused.stderr
            assert await revision(target)=='0060' and await snapshot(target)==populated and await schema(target)==shape
        finally:await local.dispose()
        assert await snapshot(url)==primary and await schema(url)==definitions and await revision(url)=='0059'
        result={'pass':True,'up_down_up':'0059->0060->0059->0060','legacy_rows_seeded':True,'old_rows_exact':True,
            'rollback_schema_equivalent':True,'populated_downgrade_refused':True,'automatic_mapping':False,'primary_unchanged':True,'provider_calls':False,'backup':str(backup)}
        (ROOT/'.runtime'/'s31b-migration.json').write_text(json.dumps(result),encoding='utf-8');print(json.dumps(result))
    finally:
        if created:docker(CONTAINER,'dropdb','-U','pao',name);print('Removed only invocation-owned S31B clone; retained backup.')

if __name__=='__main__':asyncio.run(main())
