"""Restore populated pao_test admission ledger to an invocation-owned clone.

Seed with test_goal_admission's atomic test first. No model/workflow execution.
"""
import asyncio
import json
import sys
from uuid import uuid4
from sqlalchemy import text,select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from pao.config import ROOT,settings
from pao.models import GoalExecution,GoalCommand,GoalEvent
from pao.modules.studio.contracts import digest
from pao.modules.goals.evidence import verify_admission
from check_p11_migration import docker,snapshot,CONTAINER

PRE_CHILD = '--pre-child' in sys.argv


async def inspect(url,probe=False):
    engine=create_async_engine(url)
    try:
        async with async_sessionmaker(engine)() as db:
            assert await db.scalar(text('SELECT version_num FROM alembic_version'))=='0041'
            executions=list(await db.scalars(select(GoalExecution)))
            commands=list(await db.scalars(select(GoalCommand)))
            events=list(await db.scalars(select(GoalEvent)))
            assert len(executions)==1 and len(commands)==1 and len(events)==(3 if PRE_CHILD else 2)
            row=executions[0]
            assert row.status==('waiting_approval' if PRE_CHILD else 'starting')
            assert row.sequence==(1 if PRE_CHILD else 0) and row.reserved_cost_microusd==0
            assert row.admission_hash==digest({'envelope':row.envelope,'initial_proposal':row.initial_proposal,'goal_snapshot':row.goal_snapshot})
            assert commands[0].status==('delivered' if PRE_CHILD else 'pending')
            assert commands[0].attempts==(1 if PRE_CHILD else 0)
            if PRE_CHILD:
                projection=next(e for e in events if e.action=='pre_child_projection')
                assert projection.data['state']==row.state
                assert projection.data['scope']=='pre_child_only'
                assert projection.data['receipt']=={'allow_iteration':False,'cancel_requested':False}
                assert projection.execution_id==row.id and projection.workspace_id==row.workspace_id
            await verify_admission(db,row)
            for c in commands:
                assert c.content_hash==digest({'operation':c.operation,'payload':c.payload,'actor_id':c.actor_id})
            for e in events:
                assert e.content_hash==digest({'action':e.action,'data':e.data,'actor_id':e.actor_id})
            for table in ('studio_executions','studio_commands','runs','task_attempts','llm_attempts','business_events'):
                assert await db.scalar(text('SELECT count(*) FROM '+table))==0
        if probe:
            # Verify restored append-only/identity triggers, only in the clone.
            for sql in ("UPDATE goal_executions SET envelope='{}'::json",
                        "UPDATE goal_commands SET payload='{}'::json",'DELETE FROM goal_events'):
                try:
                    async with engine.begin() as connection:await connection.execute(text(sql))
                except DBAPIError:pass
                else:raise AssertionError('Restored immutable trigger missing')
    finally:await engine.dispose()


async def main():
    url=make_url(settings().database_url)
    assert url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    source=url.set(database='pao_test')
    await inspect(source)
    columns,before=await snapshot(source)
    name='pao_p63_admission_restore_'+uuid4().hex
    backup=ROOT/'.runtime'/('p63-admission-'+uuid4().hex+'.dump')
    with backup.open('xb') as output:
        docker(CONTAINER,'pg_dump','-U','pao','-d','pao_test','-Fc',stdout=output)
    created=False
    try:
        docker(CONTAINER,'createdb','-U','pao',name);created=True
        with backup.open('rb') as data:
            docker('-i',CONTAINER,'pg_restore','-U','pao','-d',name,'--no-owner','--exit-on-error',stdin=data)
        target=url.set(database=name)
        assert (await snapshot(target,columns))[1]==before
        await inspect(target,True)
        assert (await snapshot(target,columns))[1]==before
        assert (await snapshot(source,columns))[1]==before
        print(json.dumps({'pass':True,'tables':len(columns),'hash_exact':True,
            'goal_executions':1,'goal_commands':1,'goal_events':3 if PRE_CHILD else 2,'immutable_triggers_verified':True,
            'admission_provenance_reauthorized':True,
            'pre_child_projection_retained':PRE_CHILD,'dispatcher_ack_simulated':PRE_CHILD,
            'model_calls':0,'temporal_jobs':0,'database':'isolated_restore_clone'}))
    finally:
        if created:docker(CONTAINER,'dropdb','-U','pao',name)


if __name__=='__main__':asyncio.run(main())
