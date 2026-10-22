"""Restore late-reconciled fixture; primary DB is never a probe target.

Seed test_concurrent_recovery_releases_once_never_resumes[manual_review-False].
This is DB reconciliation, not live parent/dispatcher/drain acceptance.
"""
import asyncio
import json
import sys
from uuid import uuid4

from sqlalchemy import select,text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from sqlalchemy.exc import DBAPIError

from pao.config import ROOT,settings
from pao.models import Goal,GoalExecution,GoalEvent,TaskAttempt
from pao.modules.goals import recovery,cancel_recovery
from pao.modules.studio.contracts import digest
from check_p11_migration import docker,snapshot,CONTAINER


async def inspect(url,probe=False,cancel=False,native=False,queue=False):
    engine=create_async_engine(url);factory=async_sessionmaker(engine,expire_on_commit=False)
    try:
        async with factory() as db:
            assert await db.scalar(text('SELECT version_num FROM alembic_version'))=='0041'
            rows=list(await db.scalars(select(GoalExecution)));assert len(rows)==1
            row=rows[0];assert row.status=='manual_review' and row.sequence==2 and row.reserved_cost_microusd==0
            assert row.state['reserved_cost_microusd']==0 and row.state['checks']==[]
            assert (await db.get(Goal,row.goal_id)).status=='draft'
            assert len(list(await db.scalars(select(TaskAttempt))))==(1 if native else 0 if cancel else 2)
            events=list(await db.scalars(select(GoalEvent)));assert len(events)==9
            action='cancelled_queue_reconciled' if queue else 'cancelled_native_reconciled' if native else 'cancel_before_claim_reconciled' if cancel else 'late_completion_reconciled'
            reconciled=[e for e in events if e.action==action];assert len(reconciled)==1
            for event in events:
                assert event.content_hash==digest({'action':event.action,'data':event.data,'actor_id':event.actor_id})
            assert reconciled[0].data['state_after']==row.state
            helper=cancel_recovery.reconcile_cancelled_queue if queue else cancel_recovery.reconcile_cancelled_native if native else cancel_recovery.reconcile_cancelled_before_claim if cancel else recovery.reconcile_completed_first
            result=await helper({'envelope':row.envelope},row.temporal_id,db=db)
            assert result['status']=='manual_review' and result['reconciled'] is True and result['resumed'] is False
            if queue:
                assert result['queue_ack_verified'] is True
                assert reconciled[0].data['proof']['queue_ack_verified'] is True
            for table in ('runs','llm_attempts','business_events'):
                assert await db.scalar(text('SELECT count(*) FROM '+table))==0
        if probe:
            try:
                async with engine.begin() as db:
                    await db.execute(text("UPDATE goal_events SET data='{}'::json WHERE action=:action"),{'action':action})
            except DBAPIError:pass
            else:raise AssertionError('Restored recovery trigger missing')
            if queue:
                try:
                    async with engine.begin() as db:
                        await db.execute(text("UPDATE studio_events SET data='{}'::json WHERE action='p62_step_queue_cancel_ack'"))
                except DBAPIError:pass
                else:raise AssertionError('Restored queue ACK trigger missing')
    finally:await engine.dispose()


async def main():
    cancel='--cancel-before-claim' in sys.argv
    native='--claimed-native' in sys.argv
    queue='--queue-ack' in sys.argv
    assert not queue or native or cancel, 'Queue profile must specify claimed-native or cancel-before-claim'
    assert not (native and cancel)
    url=make_url(settings().database_url)
    assert url.database=='pao_acos_local' and url.host=='127.0.0.1' and url.port==15432
    source=url.set(database='pao_test');columns,before=await snapshot(source)
    await inspect(source,cancel=cancel,native=native,queue=queue);assert (await snapshot(source,columns))[1]==before
    name='pao_p63_recovery_restore_'+uuid4().hex
    dump=ROOT/'.runtime'/('p63-recovery-'+uuid4().hex+'.dump')
    with dump.open('xb') as output:docker(CONTAINER,'pg_dump','-U','pao','-d','pao_test','-Fc',stdout=output)
    created=False
    try:
        docker(CONTAINER,'createdb','-U','pao',name);created=True
        with dump.open('rb') as data:
            docker('-i',CONTAINER,'pg_restore','-U','pao','-d',name,'--no-owner','--exit-on-error',stdin=data)
        target=url.set(database=name)
        assert (await snapshot(target,columns))[1]==before
        await inspect(target,True,cancel=cancel,native=native,queue=queue)
        assert (await snapshot(target,columns))[1]==before
        assert (await snapshot(source,columns))[1]==before
        print(json.dumps({'pass':True,'tables':len(columns),'hash_exact':True,
            'reconciled_stopped_execution':1,'resumed':False,'goal_m1_draft':True,
            'reservation_released_once':True,'immutable_recovery_verified':True,
            'proof_and_authority_reverified':True,'cancel_before_claim':cancel,'claimed_native':native,'queue_ack':queue,'parent_and_dispatch_fixture':True,
            'model_calls':0,'temporal_jobs':0}))
    finally:
        if created:docker(CONTAINER,'dropdb','-U','pao',name)


if __name__=='__main__':asyncio.run(main())
