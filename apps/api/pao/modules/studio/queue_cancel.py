"""Explicit fixed-Echo ARQ cancellation ACK, not registered in live runtime.

Redis is transport evidence, never business/usage evidence. ACKs require the
matching immutable native cancellation outcome; no cost is released here.
"""
import asyncio
from uuid import UUID,uuid5

from arq.jobs import Job
from arq.constants import in_progress_key_prefix,job_key_prefix
from fastapi import HTTPException
from redis.exceptions import RedisError
from sqlalchemy import select

from ...auth import Principal
from ...db import Session
from ...models import StudioCommand,StudioEvent,TaskAttempt
from . import durable,step_jobs as jobs
from .contracts import digest
from .service import reject


def ack_id(execution_id):
    return jobs.event_id(execution_id,'queue_cancel_ack')


async def scope(db,args):
    row,plan,snapshot,step=await jobs.context(db,*args,admission=False)
    if row.cancel_requested is not True:reject('queue_cancel_not_requested',409)
    await durable.verify_plan(db,plan,row.actor_id)
    commands=list(await db.scalars(select(StudioCommand).where(StudioCommand.execution_id==row.id,
        StudioCommand.operation=='cancel').order_by(StudioCommand.ordinal)))
    if not commands:reject('queue_cancel_command_missing',409)
    command=commands[0]
    if (command.workspace_id!=row.workspace_id or command.payload!={} or command.status not in ('pending','processing','delivered') or
            command.id!=str(uuid5(UUID(row.id),command.request_key)) or command.content_hash!=digest({
                'operation':'cancel','payload':{},'actor_id':command.actor_id})):
        reject('queue_cancel_command_invalid',409)
    await durable.authorize(db,row,Principal(command.actor_id,0))
    audits=list(await db.scalars(select(StudioEvent).where(StudioEvent.action=='p62_command',
        StudioEvent.data['command_id'].as_string()==command.id)))
    if (len(audits)!=1 or audits[0].workspace_id!=row.workspace_id or audits[0].definition_id!=row.definition_id or
            audits[0].version_id!=plan.version_id or audits[0].actor_id!=command.actor_id or
            audits[0].data!={'execution_id':row.id,'command_id':command.id,'operation':'cancel','ordinal':command.ordinal}):
        reject('queue_cancel_command_invalid',409)
    reserved=await db.get(StudioEvent,jobs.event_id(args[2],'reserved'))
    if (not reserved or reserved.workspace_id!=row.workspace_id or reserved.definition_id!=row.definition_id or
            reserved.version_id!=plan.version_id or reserved.actor_id!=row.actor_id or reserved.action!='p62_step_reserved' or
            reserved.data.get('plan_id')!=row.id or reserved.data.get('execution_id')!=args[2]):
        reject('queue_cancel_reservation_missing',409)
    value=reserved.data;env=value['envelope']
    if (value['hash']!=digest(env) or env.get('adapter')!='fixture_echo' or env.get('dry_run') is not True or
            env.get('snapshot_hash')!=snapshot['sha256'] or env.get('step_id')!=args[1] or env.get('contract_hash')!=step['skill']['hash']):
        reject('queue_cancel_reservation_invalid',409)
    return row,plan,command


async def native_evidence(db,row,plan,args):
    outcome=await db.get(StudioEvent,jobs.event_id(args[2],'outcome'))
    claimed=await db.get(StudioEvent,jobs.event_id(args[2],'claimed'))
    attempt=await db.get(TaskAttempt,args[2])
    code='cancel_requested' if claimed else 'cancelled_before_claim'
    expected={'plan_id':row.id,'execution_id':args[2],'step_id':args[1],
        'status':'cancelled','error_code':code,'dry_run':True,'origin':'fixture_echo'}
    if (not outcome or outcome.action!='p62_step_outcome' or outcome.workspace_id!=row.workspace_id or
            outcome.definition_id!=row.definition_id or outcome.version_id!=plan.version_id or
            outcome.actor_id!=row.actor_id or outcome.data!=expected):
        reject('queue_cancel_native_unknown',409)
    if claimed:
        if (not attempt or attempt.status!='cancelled' or attempt.error_code!=code or
                attempt.workspace_id!=row.workspace_id or attempt.task_id!=args[2] or attempt.finished_at is None):
            reject('queue_cancel_native_unknown',409)
    elif attempt:reject('queue_cancel_native_unknown',409)
    return outcome,claimed


async def verify_ack(db,row,plan,args,event,queue=None):
    outcome,claimed=await native_evidence(db,row,plan,args)
    value=event.data if event else {}
    if (not event or event.id!=ack_id(args[2]) or event.action!='p62_step_queue_cancel_ack' or
            event.workspace_id!=row.workspace_id or event.definition_id!=row.definition_id or
            event.version_id!=plan.version_id or event.actor_id!=row.actor_id or value.get('plan_id')!=row.id or
            value.get('execution_id')!=args[2] or value.get('step_id')!=args[1] or value.get('job_id')!='p62:'+args[2] or
            value.get('function')!='execute_studio_echo' or value.get('snapshot_hash')!=row.snapshot_hash or
            value.get('native_outcome_id')!=outcome.id or value.get('native_outcome_hash')!=digest(outcome.data) or
            value.get('native_claim_id')!=(claimed.id if claimed else None) or value.get('dry_run') is not True or
            value.get('queue_drained') is not True or value.get('ack') not in ('arq_aborted','arq_finished_cancelled') or
            not isinstance(value.get('queue'),str) or (queue is not None and value['queue']!=queue)):
        reject('queue_cancel_ack_invalid',409)
    command=await db.get(StudioCommand,value.get('cancel_command_id'))
    if not command or command.execution_id!=row.id or command.operation!='cancel':reject('queue_cancel_ack_invalid',409)
    return value


def transport_matches(info,args,queue=None):
    return bool(info and info.function=='execute_studio_echo' and info.args==tuple(args) and info.kwargs=={} and
        (info.job_id is None or info.job_id=='p62:'+args[2]) and
        (queue is None or getattr(info,'queue_name',None)==queue))


async def cancel_queue_step(redis,plan_id,step_id,execution_id,*,timeout_seconds=5):
    """Bounded abort/wait; explicit injected server pool, not an API input.

    Absence, lost result, timeout or disconnect is UNKNOWN, never an ACK.
    Immutable ACK retries survive Redis result expiry. Sticky DB fencing remains
    authoritative if a later duplicate delivery is attempted.
    """
    if type(timeout_seconds) is not int or not 1<=timeout_seconds<=10:
        reject('queue_cancel_timeout_invalid',422)
    queue=redis.default_queue_name
    if not isinstance(queue,str) or not queue or len(queue)>160:reject('queue_cancel_scope_invalid',422)
    args=(plan_id,step_id,execution_id)
    async with Session.begin() as db:
        row,plan,command=await scope(db,args)
        previous=await db.get(StudioEvent,ack_id(execution_id))
        if previous:
            await verify_ack(db,row,plan,args,previous,queue)
            return {'status':'cancelled','queue_ack_verified':True,'ack_id':previous.id,'dry_run':True}
    unknown={'status':'unknown','queue_ack_verified':False,'dry_run':True}
    job_id='p62:'+execution_id;job=Job(job_id,redis,_queue_name=queue)
    try:
        info=await asyncio.wait_for(job.info(),timeout_seconds)
        if not transport_matches(info,args):return {**unknown,'reason':'job_absent_or_mismatched'}
        if await asyncio.wait_for(job.result_info(),timeout_seconds) is None and await asyncio.wait_for(redis.zscore(queue,job_id),timeout_seconds) is None:
            return {**unknown,'reason':'queue_scope_unknown'}
        await asyncio.wait_for(job.abort(timeout=timeout_seconds,poll_delay=.05),timeout_seconds+.5)
        result=await asyncio.wait_for(job.result_info(),timeout_seconds)
        if not transport_matches(result,args,queue):return {**unknown,'reason':'result_absent_or_mismatched'}
        aborted=result.success is False and type(result.result) is asyncio.CancelledError
        finished=result.success is True and result.result in ({'status':'cancelled'},{'status':'cancelled','receipt':None})
        if not (aborted or finished):return {**unknown,'reason':'not_cancelled'}
        async with redis.pipeline(transaction=True) as pipe:
            pipe.exists(in_progress_key_prefix+job_id);pipe.exists(job_key_prefix+job_id);pipe.zscore(queue,job_id)
            active,payload,queued=await asyncio.wait_for(pipe.execute(),timeout_seconds)
        if active or payload or queued is not None:return {**unknown,'reason':'queue_not_drained'}
    except (RedisError,OSError,TimeoutError):return {**unknown,'reason':'queue_unreachable_or_timeout'}
    # No Redis operation while holding a DB lock; the worker's abort handler
    # needs that lock. Reauthorize/revalidate all pins after transport returns.
    try:await jobs.recover(*args)
    except HTTPException:return {**unknown,'reason':'native_unknown'}
    async with Session.begin() as db:
        row,plan,command=await scope(db,args)
        outcome,claimed=await native_evidence(db,row,plan,args)
        previous=await db.get(StudioEvent,ack_id(execution_id))
        if previous:await verify_ack(db,row,plan,args,previous,queue)
        else:
            jobs.append(db,row,plan,execution_id,'queue_cancel_ack',{
                'step_id':step_id,'job_id':job_id,'queue':queue,'function':'execute_studio_echo',
                'snapshot_hash':row.snapshot_hash,'cancel_command_id':command.id,
                'ack':'arq_aborted' if aborted else 'arq_finished_cancelled','queue_drained':True,
                'native_outcome_id':outcome.id,'native_outcome_hash':digest(outcome.data),
                'native_claim_id':claimed.id if claimed else None,'dry_run':True,
                'enqueue_time':result.enqueue_time.isoformat(),'finish_time':result.finish_time.isoformat()})
    return {'status':'cancelled','queue_ack_verified':True,'ack_id':ack_id(execution_id),'dry_run':True}
