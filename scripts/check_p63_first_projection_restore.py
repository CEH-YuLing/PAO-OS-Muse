"""Restore a completed first-projection fixture; never touch primary rows.

Seed test_atomic_running_completion_idempotent_releases_once_not_m1 first.
Parent/dispatch projections and ACKs remain explicit test fixtures.
"""
import asyncio
import json
from uuid import uuid4

from sqlalchemy import select,text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from sqlalchemy.exc import DBAPIError

from pao.config import ROOT,settings
from pao.models import Goal,GoalExecution,GoalEvent,TaskAttempt
from pao.modules.goals import first_projection,iterations
from pao.modules.goals.evidence import verify_admission
from pao.modules.studio.contracts import digest
from check_p11_migration import docker,snapshot,CONTAINER


async def inspect(url,probe=False):
    engine=create_async_engine(url);factory=async_sessionmaker(engine,expire_on_commit=False)
    previous=first_projection.Session
    try:
        async with factory() as db:
            assert await db.scalar(text('SELECT version_num FROM alembic_version'))=='0041'
            rows=list(await db.scalars(select(GoalExecution)));assert len(rows)==1
            row=rows[0];await verify_admission(db,row)
            assert row.status=='completed' and row.sequence==3 and row.reserved_cost_microusd==0
            assert (await db.get(Goal,row.goal_id)).status=='draft'
            assert len(list(await db.scalars(select(TaskAttempt))))==2
            events=list(await db.scalars(select(GoalEvent)));assert len(events)==9
            assert len([e for e in events if e.action=='first_iteration_projection'])==2
            for event in events:
                assert event.content_hash==digest({'action':event.action,'data':event.data,'actor_id':event.actor_id})
            claim=next(e for e in events if e.action=='iteration_claim')
            receipt=await iterations.read_first_receipt({'envelope':row.envelope,'state':claim.data['state'],
                'child_result':{'status':'completed'}},row.temporal_id,db=db)
            assert digest(receipt)==row.state['receipt_hash'] and all(c['passed'] for c in row.state['checks'])
            data={'envelope':row.envelope,'state':row.state};ident=row.temporal_id
            for table in ('runs','llm_attempts','business_events'):
                assert await db.scalar(text('SELECT count(*) FROM '+table))==0
        first_projection.Session=factory
        assert await first_projection.project_first(data,ident)=={'allow_iteration':False,'cancel_requested':False}
        if probe:
            try:
                async with engine.begin() as db:
                    await db.execute(text("UPDATE goal_events SET data='{}'::json WHERE action='first_iteration_projection'"))
            except DBAPIError:pass
            else:raise AssertionError('Restored projection trigger missing')
    finally:
        first_projection.Session=previous
        await engine.dispose()


async def main():
    url=make_url(settings().database_url)
    assert url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    source=url.set(database='pao_test');columns,before=await snapshot(source)
    await inspect(source);assert (await snapshot(source,columns))[1]==before
    name='pao_p63_first_restore_'+uuid4().hex
    dump=ROOT/'.runtime'/('p63-first-'+uuid4().hex+'.dump')
    with dump.open('xb') as output:docker(CONTAINER,'pg_dump','-U','pao','-d','pao_test','-Fc',stdout=output)
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
            'completed_first_iteration':1,'goal_m1_draft':True,'reservation_released_once':True,
            'immutable_projection_verified':True,'receipt_reverified':True,
            'parent_and_dispatch_fixture':True,'model_calls':0,'temporal_jobs':0}))
    finally:
        if created:docker(CONTAINER,'dropdb','-U','pao',name)


if __name__=='__main__':asyncio.run(main())
