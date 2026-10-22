"""Bounded P6.4 restore/migration acceptance. Only owned clones may be dropped.

Default: populated pao_test restore. --migration: main clone round-trip only.
--apply: explicitly apply 0042 to main AFTER a verified current checkpoint.
Never call an external provider or write business rows in the primary DB.
"""
import argparse,asyncio,json,os,re,subprocess,sys
from pathlib import Path
from uuid import uuid4
from sqlalchemy import select,func,text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from sqlalchemy.exc import DBAPIError
from pao.config import ROOT,settings
from pao.models import StudioSchedule,StudioScheduleSlot,StudioScheduleEvent,StudioExecution,TaskAttempt,Run
from pao.modules.schedules import store
from pao.modules.operations.checkpoint import digest
from check_p11_migration import docker,snapshot,CONTAINER

TABLES={'studio_schedules','studio_schedule_events','studio_schedule_slots'}

async def revision(url):
    engine=create_async_engine(url)
    try:
        async with engine.connect() as db:return await db.scalar(text('SELECT version_num FROM alembic_version'))
    finally:await engine.dispose()

async def populated(url,probe=False):
    engine=create_async_engine(url);factory=async_sessionmaker(engine,expire_on_commit=False)
    try:
        async with factory() as db:
            assert await db.scalar(text('SELECT version_num FROM alembic_version'))=='0042'
            rows=list(await db.scalars(select(StudioSchedule)));assert len(rows)==1
            row=rows[0];await store.verify(db,row);assert row.status=='completed'
            events=list(await db.scalars(select(StudioScheduleEvent).order_by(StudioScheduleEvent.revision)))
            assert [e.action for e in events]==['created','enable','checked']
            for event in events:
                assert event.content_hash==store.digest({'actor_id':event.actor_id,'action':event.action,'data':event.data})
            slots=list(await db.scalars(select(StudioScheduleSlot)));assert len(slots)==1
            slot=slots[0];assert slot.schedule_id==row.id and slot.spec_hash==row.spec_hash
            native=await db.get(StudioExecution,slot.execution_id)
            assert native.status=='completed' and native.workspace_id==row.workspace_id
            assert native.snapshot_hash==row.spec['snapshot_hash']
            assert await db.scalar(select(func.count()).select_from(TaskAttempt))==2
            assert await db.scalar(select(func.count()).select_from(Run))==0
        if probe:
            for table in ('studio_schedule_events','studio_schedule_slots'):
                try:
                    async with engine.begin() as db:await db.execute(text('DELETE FROM '+table))
                except DBAPIError:pass
                else:raise AssertionError('Restored immutability trigger missing: '+table)
    finally:await engine.dispose()

def migrate(url,*args):
    env={**os.environ,'DATABASE_URL':url.render_as_string(hide_password=False)}
    subprocess.run([sys.executable,'-m','alembic',*args],cwd=ROOT,env=env,check=True,timeout=90)

async def clone_check(url,migration):
    _,primary=await snapshot(url)
    source=url if migration else url.set(database='pao_test')
    columns,before=await snapshot(source)
    assert await revision(source)==('0041' if migration else '0042')
    if not migration:await populated(source)
    name='pao_schedule_restore_'+uuid4().hex
    assert re.fullmatch('pao_schedule_restore_[0-9a-f]{32}',name)
    dump=ROOT/'.runtime'/('schedule-'+uuid4().hex+'.dump')
    with dump.open('xb') as out:docker(CONTAINER,'pg_dump','-U','pao','-d',source.database,'-Fc',stdout=out)
    created=False
    try:
        docker(CONTAINER,'createdb','-U','pao',name);created=True
        with dump.open('rb') as data:docker('-i',CONTAINER,'pg_restore','-U','pao','-d',name,'--no-owner','--exit-on-error',stdin=data)
        target=url.set(database=name)
        assert await snapshot(target)==(columns,before)
        if migration:
            migrate(target,'upgrade','0042');migrate(target,'check')
            assert (await snapshot(target,columns))[1]==before
            all_columns,all_hashes=await snapshot(target)
            assert set(all_columns)-set(columns)==TABLES
            assert all(all_hashes[t]['count']==0 for t in TABLES)
            migrate(target,'downgrade','0041')
            assert await snapshot(target)==(columns,before) and await revision(target)=='0041'
            migrate(target,'upgrade','0042')
            assert (await snapshot(target,columns))[1]==before
        else:
            await populated(target,True)
            assert await snapshot(target)==(columns,before)
        assert await snapshot(source)==(columns,before)
        assert (await snapshot(url))[1]==primary
        print(json.dumps({'pass':True,'mode':'migration_clone_roundtrip' if migration else 'populated_restore',
            'revision':'0042','legacy_tables':len(columns),'hash_exact':True,'primary_unchanged':True,
            'immutable_trigger_verified':not migration,'dump_retained':True}))
    finally:
        if created:docker(CONTAINER,'dropdb','-U','pao',name)

async def apply(url,manifest):
    path=Path(manifest).resolve();assert path.is_relative_to((ROOT/'.runtime/checkpoints').resolve())
    value=json.loads(path.read_text(encoding='utf-8'))
    assert value['database']['revision_before']=='0041'
    assert value['binding']==__import__('pao.skills',fromlist=['execution_binding']).execution_binding()
    assert digest(Path(value['database']['backup']))==value['database']['sha256']
    assert digest(Path(value['source']['path']))==value['source']['sha256']
    assert await revision(url)=='0041'
    columns,before=await snapshot(url)
    # A checkpoint belongs to this exact DB row state, not merely its revision.
    name='pao_schedule_restore_'+uuid4().hex;created=False
    try:
        docker(CONTAINER,'createdb','-U','pao',name);created=True
        with Path(value['database']['backup']).open('rb') as data:
            docker('-i',CONTAINER,'pg_restore','-U','pao','-d',name,'--no-owner','--exit-on-error',stdin=data)
        assert await revision(url.set(database=name))=='0041'
        assert await snapshot(url.set(database=name))==(columns,before)
        assert await snapshot(url)==(columns,before)
    finally:
        if created:docker(CONTAINER,'dropdb','-U','pao',name)
    migrate(url,'upgrade','0042');migrate(url,'check')
    after_columns,after=await snapshot(url)
    assert set(after_columns)-set(columns)==TABLES
    assert (await snapshot(url,columns))[1]==before
    assert all(after[t]['count']==0 for t in TABLES) and await revision(url)=='0042'
    print(json.dumps({'pass':True,'mode':'primary_additive_rollout','revision':'0042',
        'legacy_tables':len(columns),'legacy_rows_hash_exact':True,'new_tables_empty':True}))

async def main(args):
    url=make_url(settings().database_url)
    assert ROOT.resolve()==Path('F:/PAO-ACOS') and url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    if args.apply:
        if not args.manifest:raise SystemExit('--apply requires a verified current --manifest')
        await apply(url,args.manifest)
    else:await clone_check(url,args.migration)

if __name__=='__main__':
    parser=argparse.ArgumentParser();mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--migration',action='store_true');mode.add_argument('--apply',action='store_true')
    parser.add_argument('--manifest');asyncio.run(main(parser.parse_args()))
