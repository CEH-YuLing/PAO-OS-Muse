"""Owned clone restore of actual pre-child Goal transport. Never primary target."""
import asyncio
import json
from uuid import uuid4
from sqlalchemy import select,text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from sqlalchemy.exc import DBAPIError
from pao.config import ROOT,settings
from pao.models import GoalExecution,GoalCommand,GoalEvent,Goal
from pao.modules.goals.dispatcher import verify_command
from pao.modules.goals.evidence import verify_admission
from pao.modules.studio.contracts import digest
from check_p11_migration import docker,snapshot,CONTAINER


async def inspect(url,probe=False):
    engine=create_async_engine(url);factory=async_sessionmaker(engine,expire_on_commit=False)
    try:
        async with factory() as db:
            assert await db.scalar(text('SELECT version_num FROM alembic_version'))=='0041'
            rows=list(await db.scalars(select(GoalExecution)));assert len(rows)==1
            row=rows[0]
            assert row.status=='cancelled' and row.sequence==2 and row.reserved_cost_microusd==0
            assert row.state['iteration']==0 and row.state['cancel_requested'] is True
            assert (await db.get(Goal,row.goal_id)).status=='draft'
            await verify_admission(db,row)
            commands=list(await db.scalars(select(GoalCommand).order_by(GoalCommand.ordinal)))
            assert [c.operation for c in commands]==['start','cancel']
            for command in commands:
                assert command.status=='delivered' and command.attempts==1 and command.delivered_at
                assert command.lease_token is None and command.lease_until is None
                await verify_command(db,row,command)
            events=list(await db.scalars(select(GoalEvent)));assert len(events)==5
            for event in events:
                assert event.content_hash==digest({'action':event.action,'data':event.data,'actor_id':event.actor_id})
            projected=[e for e in events if e.action=='pre_child_projection'];assert len(projected)==2
            assert any(e.data['state']==row.state for e in projected)
            for table in ('studio_executions','task_attempts','runs','llm_attempts','business_events'):
                assert await db.scalar(text('SELECT count(*) FROM '+table))==0
        if probe:
            try:
                async with engine.begin() as db:
                    await db.execute(text("UPDATE goal_events SET data='{}'::json"))
            except DBAPIError:pass
            else:raise AssertionError('Restored immutable audit trigger missing')
    finally:await engine.dispose()


async def main():
    url=make_url(settings().database_url)
    assert url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    source=url.set(database='pao_test');columns,before=await snapshot(source)
    await inspect(source)
    assert (await snapshot(source,columns))[1]==before
    name='pao_p63_dispatch_restore_'+uuid4().hex
    dump=ROOT/'.runtime'/('p63-dispatch-'+uuid4().hex+'.dump')
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
        print(json.dumps({'pass':True,'tables':len(columns),'hash_exact':True,
            'parent_cancelled_pre_child':True,'transport_commands':2,'immutable_audit_verified':True,
            'authority_and_provenance_reverified':True,'child_execution_acceptance':False}))
    finally:
        if created:docker(CONTAINER,'dropdb','-U','pao',name)


if __name__=='__main__':asyncio.run(main())
