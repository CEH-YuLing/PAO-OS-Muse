"""P6.4 Goal schedule restore/0043 rollout; only exact owned clones are dropped."""
import argparse,asyncio,json,os,re,subprocess,sys
from pathlib import Path
from uuid import uuid4
from sqlalchemy import select,func,text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from sqlalchemy.exc import DBAPIError
from pao.config import ROOT,settings
from pao.models import StudioSchedule,GoalScheduleSlot,GoalExecution,GoalEvent,Goal,TaskAttempt,Run
from pao.modules.schedules import store,goals
from pao.modules.goals import runner
from pao.modules.goals.evidence import verify_admission
from pao.modules.operations.checkpoint import digest
from pao.skills import execution_binding
from check_p11_migration import docker,snapshot,CONTAINER
from check_studio_schedule_restore import revision,migrate

async def populated(url,probe=False):
    engine=create_async_engine(url);factory=async_sessionmaker(engine,expire_on_commit=False)
    try:
        async with factory() as db:
            assert await db.scalar(text('SELECT version_num FROM alembic_version'))=='0043'
            schedules=list(await db.scalars(select(StudioSchedule)));assert len(schedules)==1
            schedule=schedules[0];await store.verify(db,schedule);assert goals.is_goal(schedule) and schedule.status=='completed'
            slots=list(await db.scalars(select(GoalScheduleSlot)));assert len(slots)==1
            slot=slots[0];assert slot.schedule_id==schedule.id and slot.spec_hash==schedule.spec_hash
            row=await db.get(GoalExecution,slot.execution_id)
            assert row.status=='completed' and row.reserved_cost_microusd==0 and row.workspace_id==schedule.workspace_id
            await verify_admission(db,row)
            assert (await runner.reconstruct(db,row)).snapshot()['iteration']==1
            launch=await db.get(GoalEvent,runner.event_id(row,'launch:1'))
            receipt=await runner.completed(db,row,launch);assert receipt['iteration']==1 and receipt['cost_microusd']==0
            assert await db.get(GoalEvent,runner.event_id(row,'receipt:1'))
            assert (await db.get(Goal,row.goal_id)).status=='draft'
            assert await db.scalar(select(func.count()).select_from(TaskAttempt))==2
            assert await db.scalar(select(func.count()).select_from(Run))==0
        if probe:
            try:
                async with engine.begin() as db:await db.execute(text('DELETE FROM goal_schedule_slots'))
            except DBAPIError:pass
            else:raise AssertionError('Restored slot immutability missing')
    finally:await engine.dispose()

async def restored_clone(url,source,dump,action):
    name='pao_goal_schedule_restore_'+uuid4().hex;assert re.fullmatch('pao_goal_schedule_restore_[0-9a-f]{32}',name)
    created=False
    try:
        docker(CONTAINER,'createdb','-U','pao',name);created=True
        with dump.open('rb') as data:docker('-i',CONTAINER,'pg_restore','-U','pao','-d',name,'--no-owner','--exit-on-error',stdin=data)
        await action(url.set(database=name))
    finally:
        if created:docker(CONTAINER,'dropdb','-U','pao',name)

async def check(url,migration):
    _,primary=await snapshot(url);source=url if migration else url.set(database='pao_test')
    columns,before=await snapshot(source);assert await revision(source)==('0042' if migration else '0043')
    if not migration:await populated(source)
    dump=ROOT/'.runtime'/('goal-schedule-'+uuid4().hex+'.dump')
    with dump.open('xb') as output:docker(CONTAINER,'pg_dump','-U','pao','-d',source.database,'-Fc',stdout=output)
    async def action(target):
        assert await snapshot(target)==(columns,before)
        if migration:
            migrate(target,'upgrade','0043');migrate(target,'check')
            assert (await snapshot(target,columns))[1]==before
            new_columns,new_hashes=await snapshot(target)
            assert set(new_columns)-set(columns)=={'goal_schedule_slots'} and new_hashes['goal_schedule_slots']['count']==0
            migrate(target,'downgrade','0042');assert await snapshot(target)==(columns,before)
            assert await revision(target)=='0042'
            migrate(target,'upgrade','0043');assert (await snapshot(target,columns))[1]==before
        else:
            await populated(target,True);assert await snapshot(target)==(columns,before)
    await restored_clone(url,source,dump,action)
    assert await snapshot(source)==(columns,before) and (await snapshot(url))[1]==primary
    print(json.dumps({'pass':True,'mode':'migration_clone_roundtrip' if migration else 'populated_goal_schedule_restore',
        'revision':'0043','tables':len(columns),'hash_exact':True,'primary_unchanged':True,'dump_retained':True}))

async def apply(url,manifest):
    path=Path(manifest).resolve();assert path.is_relative_to((ROOT/'.runtime/checkpoints').resolve())
    value=json.loads(path.read_text(encoding='utf-8'));assert value['database']['revision_before']=='0042'
    assert value['binding']==execution_binding()
    dump=Path(value['database']['backup']).resolve();archive=Path(value['source']['path']).resolve()
    assert dump.is_relative_to((ROOT/'.runtime').resolve()) and archive.is_relative_to(path.parent)
    assert digest(dump)==value['database']['sha256'] and digest(archive)==value['source']['sha256']
    assert await revision(url)=='0042';columns,before=await snapshot(url)
    async def action(target):assert await revision(target)=='0042' and await snapshot(target)==(columns,before)
    await restored_clone(url,url,dump,action)
    assert await snapshot(url)==(columns,before)
    migrate(url,'upgrade','0043');migrate(url,'check')
    all_columns,all_hashes=await snapshot(url)
    assert set(all_columns)-set(columns)=={'goal_schedule_slots'} and all_hashes['goal_schedule_slots']['count']==0
    assert (await snapshot(url,columns))[1]==before and await revision(url)=='0043'
    print(json.dumps({'pass':True,'mode':'primary_additive_rollout','revision':'0043','legacy_tables':len(columns),'old_rows_hash_exact':True,'new_table_empty':True}))

async def main(args):
    url=make_url(settings().database_url)
    assert ROOT.resolve()==Path('F:/PAO-ACOS') and url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    if args.apply:
        if not args.manifest:raise SystemExit('--apply requires a verified current checkpoint')
        await apply(url,args.manifest)
    else:await check(url,args.migration)

if __name__=='__main__':
    parser=argparse.ArgumentParser();mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--migration',action='store_true');mode.add_argument('--apply',action='store_true');parser.add_argument('--manifest')
    asyncio.run(main(parser.parse_args()))
