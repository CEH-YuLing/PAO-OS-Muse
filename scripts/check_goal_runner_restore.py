"""Restore a populated test runner into one generated clone; never main DB."""
import asyncio,json,re
from uuid import uuid4
from pathlib import Path
from sqlalchemy import select,func,text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from sqlalchemy.exc import DBAPIError
from pao.config import ROOT,settings
from pao.models import GoalExecution,GoalEvent,TaskAttempt,Goal
from pao.modules.goals import runner
from pao.modules.goals.evidence import verify_admission
from check_p11_migration import docker,snapshot,CONTAINER


async def inspect(url,probe=False):
    engine=create_async_engine(url);factory=async_sessionmaker(engine,expire_on_commit=False)
    try:
        async with factory() as db:
            assert await db.scalar(text('SELECT version_num FROM alembic_version'))=='0041'
            rows=list(await db.scalars(select(GoalExecution)));assert len(rows)==1
            row=rows[0];assert row.status=='completed' and row.reserved_cost_microusd==0
            ctl=await runner.reconstruct(db,row);assert ctl.snapshot()['iteration']==2
            await verify_admission(db,row)
            assert (await db.get(Goal,row.goal_id)).status=='draft'
            for iteration in (1,2):
                launch=await db.get(GoalEvent,runner.event_id(row,'launch:'+str(iteration)))
                receipt=await runner.completed(db,row,launch)
                assert receipt['iteration']==iteration and receipt['cost_microusd']==0
                assert await db.get(GoalEvent,runner.event_id(row,'receipt:'+str(iteration)))
            assert await db.scalar(select(func.count(TaskAttempt.id)))==4
        if probe:
            try:
                async with engine.begin() as db:await db.execute(text("UPDATE goal_events SET data='{}'::json"))
            except DBAPIError:pass
            else:raise AssertionError('Restored Goal event immutability missing')
    finally:await engine.dispose()


async def main():
    url=make_url(settings().database_url)
    assert ROOT.resolve()==Path('F:/PAO-ACOS') and url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    _,primary=await snapshot(url)
    source=url.set(database='pao_test');columns,before=await snapshot(source);await inspect(source)
    name='pao_goal_runner_restore_'+uuid4().hex
    assert re.fullmatch('pao_goal_runner_restore_[0-9a-f]{32}',name)
    dump=ROOT/'.runtime'/('goal-runner-'+uuid4().hex+'.dump')
    with dump.open('xb') as output:docker(CONTAINER,'pg_dump','-U','pao','-d','pao_test','-Fc',stdout=output)
    created=False
    try:
        docker(CONTAINER,'createdb','-U','pao',name);created=True
        with dump.open('rb') as data:docker('-i',CONTAINER,'pg_restore','-U','pao','-d',name,'--no-owner','--exit-on-error',stdin=data)
        target=url.set(database=name)
        assert (await snapshot(target,columns))[1]==before
        await inspect(target,True)
        assert (await snapshot(target,columns))[1]==before
        assert (await snapshot(source,columns))[1]==before
        assert (await snapshot(url))[1]==primary
        print(json.dumps({'pass':True,'revision':'0041','tables':len(columns),'hash_exact':True,
            'goal_journal_reconstructed':True,'two_iteration_receipts_verified':True,
            'immutable_trigger_verified':True,'primary_unchanged':True,'dump_retained':True}))
    finally:
        if created:docker(CONTAINER,'dropdb','-U','pao',name)


if __name__=='__main__':asyncio.run(main())
