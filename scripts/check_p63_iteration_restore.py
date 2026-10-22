"""Restore first-iteration fixture receipts to an invocation-owned clone.

Seed test_goal_iterations' receipt test first. No parent/Temporal/ARQ execution;
start/decision ACKs are explicitly simulated in the fixture.
"""
import asyncio
import json
from uuid import uuid4
from sqlalchemy import select,text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from sqlalchemy.exc import DBAPIError

from pao.config import ROOT,settings
from pao.models import Goal,GoalExecution,GoalCommand,GoalEvent,StudioExecution,TaskAttempt
from pao.modules.goals import iterations
from pao.modules.goals.evidence import verify_admission
from pao.modules.studio.contracts import digest
from check_p11_migration import docker,snapshot,CONTAINER


async def inspect(url,probe=False):
    engine=create_async_engine(url)
    factory=async_sessionmaker(engine,expire_on_commit=False)
    previous=iterations.Session
    try:
        async with factory() as db:
            assert await db.scalar(text('SELECT version_num FROM alembic_version'))=='0041'
            executions=list(await db.scalars(select(GoalExecution)));assert len(executions)==1
            row=executions[0];await verify_admission(db,row)
            assert row.status=='waiting_approval' and row.reserved_cost_microusd==5
            assert (await db.get(Goal,row.goal_id)).status=='draft'
            events=list(await db.scalars(select(GoalEvent)));assert len(events)==7
            assert len(list(await db.scalars(select(GoalCommand))))==2
            assert len(list(await db.scalars(select(StudioExecution))))==1
            assert len(list(await db.scalars(select(TaskAttempt))))==2
            for e in events:
                assert e.content_hash==digest({'action':e.action,'data':e.data,'actor_id':e.actor_id})
            claim=next(e for e in events if e.action=='iteration_claim')
            receipt=next(e for e in events if e.action=='iteration_receipt')
            data={'envelope':row.envelope,'state':claim.data['state'],'child_result':{'status':'completed'}}
            expected=receipt.data['receipt'];ident=row.id
            for table in ('runs','llm_attempts','business_events'):
                assert await db.scalar(text('SELECT count(*) FROM '+table))==0
        # Redirect ONLY this adapter's transaction factory to the owned source
        # test DB/clone; never use its original primary Session for the probe.
        iterations.Session=factory
        assert await iterations.read_first_receipt(data,'p63-'+ident)==expected
        if probe:
            try:
                async with engine.begin() as db:
                    await db.execute(text("UPDATE goal_events SET data='{}'::json WHERE action='iteration_receipt'"))
            except DBAPIError:pass
            else:raise AssertionError('Restored immutable receipt trigger missing')
    finally:
        iterations.Session=previous
        await engine.dispose()


async def main():
    url=make_url(settings().database_url)
    assert url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    source=url.set(database='pao_test')
    columns,before=await snapshot(source)
    await inspect(source)
    assert (await snapshot(source,columns))[1]==before
    name='pao_p63_iteration_restore_'+uuid4().hex
    dump=ROOT/'.runtime'/('p63-iteration-'+uuid4().hex+'.dump')
    with dump.open('xb') as output:
        docker(CONTAINER,'pg_dump','-U','pao','-d','pao_test','-Fc',stdout=output)
    created=False
    try:
        docker(CONTAINER,'createdb','-U','pao',name);created=True
        with dump.open('rb') as data:
            docker('-i',CONTAINER,'pg_restore','-U','pao','-d',name,'--no-owner','--exit-on-error',stdin=data)
        target=url.set(database=name)
        assert (await snapshot(target,columns))[1]==before
        await inspect(target,True)
        assert (await snapshot(target,columns))[1]==before
        assert (await snapshot(source,columns))[1]==before
        print(json.dumps({'pass':True,'tables':len(columns),'hash_exact':True,
            'goal_claims':1,'goal_receipts':1,'step_outcomes':2,'immutable_receipt_verified':True,
            'admission_and_receipt_reauthorized':True,'reserved_cost_retained':True,
            'parent_and_dispatch_fixture':True,'model_calls':0,'temporal_jobs':0}))
    finally:
        if created:docker(CONTAINER,'dropdb','-U','pao',name)


if __name__=='__main__':asyncio.run(main())
