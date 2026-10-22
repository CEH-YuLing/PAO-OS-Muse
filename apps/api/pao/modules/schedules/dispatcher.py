"""Single cron owner; slot + plan + native start commit in one DB transaction.

No external side effect while holding the DB lock. Existing Studio dispatcher
delivers the command after commit. Lost tick/worker restart reuses the ledger.
"""
from uuid import UUID,uuid5
from datetime import timedelta
from fastapi import HTTPException
from sqlalchemy import select
from ...db import Session
from ...auth import Principal
from ...models import StudioSchedule,StudioScheduleSlot,StudioEvent,StudioDefinition,now
from ...skills import execution_binding
from ..studio import planning,durable
from . import store,goals
from .policy import timestamp

async def check(db,row,stamp):
    await store.verify(db,row)
    if stamp<row.cursor_at:store.reject('schedule_clock_regressed',409)
    # Sparse schedules may legitimately have no slot for weeks. The immutable
    # next_at pin proves the first possible occurrence, not server uptime.
    horizon=stamp-timedelta(days=7)
    if row.next_at<=horizon:store.reject('schedule_recovery_window_exceeds_7_days',409)
    if goals.is_goal(row):await goals.verify(db,row)
    source=await db.get(StudioEvent,row.spec['template_plan_id'])
    snapshot=await durable.verify_plan(db,source,row.actor_id)
    if snapshot['sha256']!=row.spec['snapshot_hash'] or row.spec['source_binding']!=execution_binding()['sha256']:
        store.reject('schedule_source_pin_stale',409)
    result=store.evaluate(row.spec,max(row.cursor_at,horizon),stamp)
    occurrences=result['occurrences']
    if len(occurrences)>20:store.reject('schedule_recovery_batch_requires_review',409)
    busy=bool(await store.active(db,row))
    admitted=[]
    # Fixed overlap policy: skip slots while an earlier execution is unresolved.
    # Never interpret manual_review as completed or retry it with a new run.
    if not busy:
        for occurrence in occurrences:
            slot=timestamp(occurrence['utc']).isoformat()
            ident=str(uuid5(UUID(row.id),'slot:'+slot))
            existing=await db.get(goals.GoalScheduleSlot if goals.is_goal(row) else StudioScheduleSlot,ident)
            if existing:
                if existing.slot_key!=slot or existing.spec_hash!=row.spec_hash:store.reject('schedule_slot_conflict',409)
                continue
            # No multiple overlapping children on a large skip-grace backlog.
            # Only the newest eligible slot is admitted; audit records the skip.
            if occurrence is not occurrences[-1]:continue
            definition=await db.scalar(select(StudioDefinition).where(StudioDefinition.id==source.definition_id).with_for_update())
            body=planning.PlanInput(version_id=source.version_id,request_key=ident,input=snapshot['input'])
            compiled=await planning.compile_plan(db,definition,row.actor_id,body)
            if compiled['sha256']!=row.spec['snapshot_hash']:store.reject('schedule_compiler_pin_stale',409)
            plan=await planning.save_plan(db,definition,row.actor_id,planning.PlanCreate(**body.model_dump(),confirmation_hash=compiled['sha256']))
            if goals.is_goal(row):execution=await goals.admit(db,row,plan,ident,slot)
            else:
                execution=await durable.admit(db,plan['plan_id'],Principal(row.actor_id,0),durable.DurableStart(
                    request_key=ident,confirmation_hash=compiled['sha256'],timeout_seconds=row.spec['timeout_seconds']))
                db.add(StudioScheduleSlot(id=ident,schedule_id=row.id,workspace_id=row.workspace_id,
                    slot_key=slot,spec_hash=row.spec_hash,execution_id=execution.id))
            admitted.append(execution.id)
    row.cursor_at=stamp;row.next_at=timestamp(result['next_at']) if result['next_at'] else None
    row.status='enabled' if row.next_at else 'completed';row.version+=1;row.error_code=None
    await store.audit(db,row,row.actor_id,'checked',details={'admitted':admitted,
        'skipped':result['due_count']-len(admitted),'busy':busy,'due_count':result['due_count'],
        'coalesced_count':result['coalesced_count']})
    # Immutable event projection proves both selected slot and conservative skip.
    # Native start still awaits per-step approval in the existing runner.
    return {'admitted':admitted,'skipped':result['due_count']-len(admitted),'busy':busy}

async def dispatch_studio_schedules(ctx=None,stamp=None):
    from ..business_planning.reports import dispatch_owned
    await dispatch_owned(stamp)
    if not store.ready():return {'admitted':0,'checked':0,'errors':0}
    stamp=stamp or now();report={'admitted':0,'checked':0,'errors':0}
    async with Session() as db:
        query=select(StudioSchedule.id).where(StudioSchedule.status=='enabled',StudioSchedule.next_at<=stamp)
        if not goals.ready():query=query.where(StudioSchedule.spec['kind'].as_string().is_distinct_from('bounded_goal'))
        ids=list(await db.scalars(query.order_by(StudioSchedule.next_at,StudioSchedule.id).limit(10)))
    for ident in ids:
        revision=None;trusted=False
        try:
            async with Session.begin() as db:
                row=await db.scalar(select(StudioSchedule).where(StudioSchedule.id==ident,
                    StudioSchedule.status=='enabled',StudioSchedule.next_at<=stamp).with_for_update(skip_locked=True))
                if not row:continue
                if goals.is_goal(row) and not goals.ready():continue
                await store.verify(db,row);trusted=True;revision=row.version
                value=await check(db,row,stamp)
                report['admitted']+=len(value['admitted']);report['checked']+=1
        except HTTPException as error:
            report['errors']+=1
            if not trusted:continue  # never whitewash a forged projection
            async with Session.begin() as db:
                row=await db.scalar(select(StudioSchedule).where(StudioSchedule.id==ident).with_for_update())
                if row.version!=revision:continue
                await store.verify(db,row)
                row.status='manual_review';row.version+=1
                row.error_code=str(error.detail)[:64]
                await store.audit(db,row,row.actor_id,'blocked')
    return report
