"""Owned-clone P7 roundtrip/populated restore; primary rollout needs exact backup."""
import argparse,asyncio,json,os,re,subprocess,sys
from pathlib import Path
from uuid import uuid4
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.exc import DBAPIError
from pao.config import ROOT,settings
from pao.skills import execution_binding
from pao.modules.operations.checkpoint import digest,verify
from check_p11_migration import docker,snapshot,CONTAINER
from check_studio_schedule_restore import revision,migrate
from check_s03_restore import SUPPORTED_REVISIONS

NEW={'channel_bindings','channel_inbounds','channel_outbox','channel_audits','voice_turns'}

async def probe(url):
    engine=create_async_engine(url)
    try:
        async with engine.connect() as db:
            for name in NEW:assert await db.scalar(text('SELECT count(*) FROM '+name))>0,name
            assert await db.scalar(text("SELECT count(*) FROM channel_outbox WHERE status='unknown'"))==1
            assert await db.scalar(text("SELECT count(*) FROM voice_turns WHERE status='ready'"))==1
        for sql in ("UPDATE channel_bindings SET kind='customer'",'DELETE FROM channel_audits',"UPDATE voice_turns SET request_key=gen_random_uuid()"):
            try:
                async with engine.begin() as db:await db.execute(text(sql))
            except DBAPIError:pass
            else:raise AssertionError('Restored identity/audit trigger missing')
    finally:await engine.dispose()

async def clone(source,action,dump_path=None):
    name='pao_p7_restore_'+uuid4().hex;assert re.fullmatch('pao_p7_restore_[0-9a-f]{32}',name)
    dump=dump_path or ROOT/'.runtime'/('p7-'+uuid4().hex+'.dump');created=False
    if not dump_path:
        with dump.open('xb') as out:docker(CONTAINER,'pg_dump','-U','pao','-d',source.database,'-Fc',stdout=out)
    try:
        docker(CONTAINER,'createdb','-U','pao',name);created=True
        with dump.open('rb') as data:docker('-i',CONTAINER,'pg_restore','-U','pao','-d',name,'--no-owner','--exit-on-error',stdin=data)
        await action(source.set(database=name))
    finally:
        if created:docker(CONTAINER,'dropdb','-U','pao',name)

async def main(populated=False,manifest=None):
    global CONTAINER,docker
    configured=make_url(settings().database_url)
    if os.environ.get('PAO_WINDOWS_CANDIDATE_RESTORE'):
        from windows_candidate_restore import PgTools
        docker=PgTools(ROOT,configured,os.environ,populated,manifest)
        url=configured  # Exact candidate / pao_test only, never a primary URL.
    elif os.environ.get('PAO_LINUX_LOCAL_RESTORE'):
        from linux_local_restore import PgTools
        docker=PgTools(ROOT,configured,os.environ,populated,manifest)
        url=configured
    elif os.environ.get('PAO_CI_RESTORE'):
        from ci_restore_profile import service_container
        CONTAINER=service_container(ROOT,configured,os.environ,populated=populated,manifest=manifest)
        url=configured  # CI never addresses or constructs a primary database URL.
    else:
        url=configured.set(database='pao_acos_local')
        assert ROOT.resolve()==Path('F:/PAO-ACOS') and configured.database in ('pao_acos_local','pao_test') and url.host=='127.0.0.1' and url.port==15432
    primary=await snapshot(url)
    if manifest:
        path=Path(manifest).resolve();assert path.is_relative_to((ROOT/'.runtime/checkpoints').resolve())
        saved=json.loads(path.read_text(encoding='utf-8'));assert saved['database']['revision_before']=='0046' and saved['binding']==execution_binding()
        dump=Path(saved['database']['backup']).resolve();archive=Path(saved['source']['path']).resolve()
        assert dump.is_relative_to((ROOT/'.runtime').resolve()) and archive.is_relative_to(path.parent)
        assert digest(dump)==saved['database']['sha256'] and digest(archive)==saved['source']['sha256'];verify(archive,saved['source']['files'])
        assert await revision(url)=='0046'
        async def checkpoint_match(target):
            assert await revision(target)=='0046' and await snapshot(target)==primary
        await clone(url,checkpoint_match,dump)
        migrate(url,'upgrade','0048');migrate(url,'check')
        columns,rows=await snapshot(url);assert set(columns)-set(primary[0])==NEW and all(rows[n]['count']==0 for n in NEW)
        assert (await snapshot(url,primary[0]))[1]==primary[1]
        print(json.dumps({'pass':True,'mode':'verified_primary_rollout','revision':'0048','old_row_hash_exact':True,'new_tables_empty':True,'external_send':False}));return
    source=url.set(database='pao_test') if populated else url
    before=await snapshot(source);source_revision=await revision(source)
    assert source_revision in SUPPORTED_REVISIONS if populated else source_revision=='0046'
    if populated:await probe(source)
    async def action(target):
        assert await snapshot(target)==before and await revision(target)==source_revision
        if populated:
            await probe(target)
            code="""import asyncio
from sqlalchemy import select
from pao.db import Session,engine
from pao.models import ChannelBinding,ChannelInbound
from pao.modules.channels.service import ingest,send_one
async def forbidden(payload):raise AssertionError('No provider resend permitted')
async def main():
 async with Session.begin() as db:
  binding=await db.scalar(select(ChannelBinding).with_for_update());saved=await db.scalar(select(ChannelInbound))
  replay=await ingest(db,binding,'restore-fixture',saved.body,None)
  assert replay.id==saved.id and replay.run_id==saved.run_id
 await send_one(forbidden,'local');await engine.dispose()
asyncio.run(main())"""
            env={**os.environ,'DATABASE_URL':target.render_as_string(hide_password=False),'CHANNELS_ENABLED':'true'}
            subprocess.run([sys.executable,'-c',code],env=env,check=True,timeout=30)
            assert await snapshot(target)==before and await revision(target)==source_revision
        else:
            migrate(target,'upgrade','0048');migrate(target,'check')
            after=await snapshot(target);assert set(after[0])-set(before[0])==NEW and all(after[1][n]['count']==0 for n in NEW)
            assert (await snapshot(target,before[0]))[1]==before[1]
            migrate(target,'downgrade','0046');assert await snapshot(target)==before
            migrate(target,'upgrade','0048');migrate(target,'check');assert (await snapshot(target,before[0]))[1]==before[1]
    await clone(source,action)
    assert await snapshot(source)==before and await snapshot(url)==primary
    assert await revision(source)==source_revision
    print(json.dumps({'pass':True,'mode':'populated_restart_dedup_no_resend' if populated else '0046_0048_clone_roundtrip','old_tables':len(before[0]),'exact_hashes':True,'primary_unchanged':True,'external_send':False,'dump_retained':True}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--populated',action='store_true');p.add_argument('--apply-manifest');a=p.parse_args()
    if a.populated and a.apply_manifest:p.error('Choose one mode')
    asyncio.run(main(a.populated,a.apply_manifest))
