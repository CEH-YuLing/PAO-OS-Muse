"""Task event + pending outbox belong to the caller's business transaction."""
import hashlib
import json
from datetime import timezone
from sqlalchemy import select
from ...access import membership
from ...config import settings
from ...models import BusinessEvent, BusinessOutbox, Task, uid


def checksum(value):
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


async def completed(db, task, who):
    if not settings().business_events_enabled:
        return None
    # API already holds the task lock for transitions; also serialize internal
    # re-publication. Autoflush keeps the business state in this SAME transaction.
    row = await db.scalar(select(Task).where(Task.id == task.id,
        Task.workspace_id == task.workspace_id).with_for_update())
    if not row:
        raise ValueError('business_event_task_missing')
    await membership(db, row.workspace_id, who, True)
    if row.status != 'completed' or not row.completed_at or not row.success_criteria or not row.evidence:
        raise ValueError('business_event_task_not_completed')
    reference = {'kind': 'task', 'id': row.id, 'version': row.version,
        'evidence_sha256': checksum({'criteria': row.success_criteria,
            'evidence': row.evidence, 'result_reference': row.result_reference})}
    envelope = {'workspace_id': row.workspace_id, 'event_type': 'task.completed',
        'schema_version': 1, 'aggregate_type': 'task', 'aggregate_id': row.id,
        'aggregate_version': row.version, 'actor_id': who.id,
        'occurred_at': row.completed_at.astimezone(timezone.utc).isoformat(),
        'correlation_id': row.run_id or row.id, 'causation_id': None,
        'payload_reference': reference}
    digest = checksum(envelope)
    old = await db.scalar(select(BusinessEvent).where(
        BusinessEvent.workspace_id == row.workspace_id,
        BusinessEvent.event_type == 'task.completed', BusinessEvent.aggregate_id == row.id,
        BusinessEvent.aggregate_version == row.version))
    if old:
        if old.content_hash != digest:
            raise ValueError('business_event_content_conflict')
        if not await db.scalar(select(BusinessOutbox.id).where(
            BusinessOutbox.event_id == old.id, BusinessOutbox.workspace_id == row.workspace_id)):
            raise ValueError('business_event_outbox_missing')
        return old
    event = BusinessEvent(id=uid(), task_id=row.id, **{k:v for k,v in envelope.items() if k != 'occurred_at'},
        occurred_at=row.completed_at, content_hash=digest)
    db.add(event)
    await db.flush()
    db.add(BusinessOutbox(workspace_id=row.workspace_id, event_id=event.id, status='pending', attempts=0))
    await db.flush()
    return event  # Never commit here; rollback must roll back task AND both records.


async def requested(db, row, who, kind):
    if not settings().business_events_enabled:
        return None
    from .approvals import pending, expires, input_hash
    if kind not in ('task','tool','ads') or not pending(kind,row):
        raise ValueError('business_event_approval_not_pending')
    return await emit(db, row, who, 'approval.requested',
        {'task':'task','tool':'tool','ads':'ads_action'}[kind], row.version,
        {'kind':kind, 'id':row.id, 'version':row.version,
         'expires_at':expires(kind,row).isoformat(), 'input_sha256':await input_hash(db,kind,row)})


async def analyzed(db, row, who):
    if not settings().business_events_enabled:
        return None
    if not row.summary or 'campaigns_analyzed' not in row.summary:
        raise ValueError('business_event_analysis_incomplete')
    return await emit(db,row,who,'ads.analysis.completed','ads_analysis',1,
        {'kind':'ads_analysis','id':row.id,'version':1,'summary_sha256':checksum(row.summary)})


async def emit(db, row, who, event_type, aggregate_type, version, reference):
    # All callers are trusted domain producers with a locked/new row in this transaction.
    await membership(db,row.workspace_id,who,True)
    from ...models import User
    user = await db.get(User,who.id)
    if not user or not user.active: raise ValueError('business_event_actor_inactive')
    moment = row.created_at if aggregate_type == 'ads_analysis' else row.updated_at
    envelope = {'workspace_id':row.workspace_id,'event_type':event_type,'schema_version':1,
        'aggregate_type':aggregate_type,'aggregate_id':row.id,'aggregate_version':version,
        'actor_id':who.id,'occurred_at':moment.astimezone(timezone.utc).isoformat(),
        'correlation_id':getattr(row,'run_id',None) or row.id,'causation_id':None,'payload_reference':reference}
    digest = checksum(envelope)
    old = await db.scalar(select(BusinessEvent).where(BusinessEvent.workspace_id==row.workspace_id,
        BusinessEvent.event_type==event_type,BusinessEvent.aggregate_id==row.id,BusinessEvent.aggregate_version==version))
    if old:
        if old.content_hash != digest: raise ValueError('business_event_content_conflict')
        if not await db.scalar(select(BusinessOutbox.id).where(BusinessOutbox.event_id==old.id,BusinessOutbox.workspace_id==row.workspace_id)):
            raise ValueError('business_event_outbox_missing')
        return old
    target = {'task':'task_id','tool':'tool_call_id','ads_action':'ad_action_id','ads_analysis':'analysis_id'}[aggregate_type]
    event = BusinessEvent(id=uid(), **{key:value for key,value in envelope.items() if key!='occurred_at'},
        occurred_at=moment,content_hash=digest,**{target:row.id})
    db.add(event); await db.flush()
    db.add(BusinessOutbox(workspace_id=row.workspace_id,event_id=event.id,status='pending',attempts=0))
    await db.flush()
    return event
