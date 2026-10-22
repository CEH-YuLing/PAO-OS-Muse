"""Restore first-iteration grant evidence in an owned clone, never primary."""
import asyncio
import json
from uuid import uuid4
from sqlalchemy import select,text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from sqlalchemy.exc import DBAPIError
from pao.config import ROOT,settings
from pao.models import GoalExecution,GoalEvent,Goal,StudioExecution
from pao.modules.goals import execution_grants as grants
from pao.modules.studio.contracts import digest
from check_p11_migration import docker,snapshot,CONTAINER


async def inspect(url,probe=False):
    engine=create_async_engine(url);factory=async_sessionmaker(engine,expire_on_commit=False)
    try:
        async with factory() as db:
            assert await db.scalar(text('SELECT version_num FROM alembic_version'))=='0041'
            rows=list(await db.scalars(select(GoalExecution)));assert len(rows)==1
            row=rows[0]
            assert row.status=='running' and row.sequence==2 and row.reserved_cost_microusd==5
            version=row.version;before=row.state
            assert (await db.get(Goal,row.goal_id)).status=='draft'
            child=await db.get(StudioExecution,row.initial_plan_id)
            assert child.status=='starting' and child.sequence==0
            events=list(await db.scalars(select(GoalEvent)));assert len(events)==8
            for event in events:
                assert event.content_hash==digest({'action':event.action,'data':event.data,'actor_id':event.actor_id})
            value={'envelope':row.envelope,'proposal_hash':row.state['proposal_hash']}
            proof=await grants.verify_first_grant(value,row.temporal_id,db=db)
            assert proof['reserved_cost_microusd']==5 and proof['dry_run'] is True
            assert row.version==version and row.state==before
            for table in ('task_attempts','runs','llm_attempts','business_events'):
                assert await db.scalar(text('SELECT count(*) FROM '+table))==0
        if probe:
            try:
                async with engine.begin() as db:
                    await db.execute(text("UPDATE goal_events SET data='{}'::json WHERE action='execution_grant'"))
            except DBAPIError:pass
            else:raise AssertionError('Restored immutable grant trigger missing')
    finally:await engine.dispose()


async def main():
    config=settings();url=make_url(config.database_url)
    assert url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    # Process-only verification of synthetic test data/owned clone. No .env or
    # API/runtime gate change. Eligibility is time-sensitive: expired grants fail.
    for key in ('goal_iterations_enabled','goal_admission_enabled','studio_enabled',
                'workflow_planning_enabled','workflow_durable_enabled','temporal_enabled'):
        setattr(config,key,True)
    source=url.set(database='pao_test');columns,before=await snapshot(source)
    await inspect(source);assert (await snapshot(source,columns))[1]==before
    name='pao_p63_grant_restore_'+uuid4().hex
    dump=ROOT/'.runtime'/('p63-grant-'+uuid4().hex+'.dump')
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
        print(json.dumps({'pass':True,'tables':len(columns),'hash_exact':True,'immutable_grant_verified':True,
            'authority_budget_deadline_source_reverified':True,'reserved_cost_microusd':5,
            'child_started':False,'goal_m1_draft':True,'transport_fixture':True}))
    finally:
        if created:docker(CONTAINER,'dropdb','-U','pao',name)


if __name__=='__main__':asyncio.run(main())
