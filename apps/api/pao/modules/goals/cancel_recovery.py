"""Explicit native cancellation proofs; no dispatcher/poller registration.

Locks Goal then child, observes immutable cancel/projection evidence and absence
of ALL native claim/attempt rows in the no-claim entry point. A separate fixed
echo entry point checks every immutable cancellation outcome and bound attempt.
The persistent child cancellation/terminal
fence prevents a queued native job from claiming later. The two native entry
points do not claim queue ACK. The separate queue entry point additionally
requires immutable ARQ cancellation ACKs for every reserved step. None accepts
partially-executed or UNKNOWN children; those remain held.
"""
from datetime import timedelta
from uuid import UUID,uuid5

from sqlalchemy import select
from temporalio import activity

from ...auth import Principal
from ...models import GoalEvent,GoalCommand,StudioEvent,StudioCommand,TaskAttempt,now
from ..studio import durable,step_jobs as jobs,queue_cancel
from ..studio.contracts import digest
from .control import closed,validate
from .evidence import verify_admission
from .ledger import lock_execution,audit
from . import iterations
from .projection import invalid


async def cancel_command(db,row,goal):
    model=GoalCommand if goal else StudioCommand
    candidates=list(await db.scalars(select(model).where(model.execution_id==row.id,
        model.operation=='cancel',model.status=='delivered').order_by(model.ordinal)))
    if not candidates:invalid('goal_cancel_proof_command_missing')
    command=candidates[0]
    if (command.workspace_id!=row.workspace_id or command.payload!={} or command.attempts<1 or not command.delivered_at or
            command.id!=str(uuid5(UUID(row.id),command.request_key)) or
            command.content_hash!=digest({'operation':'cancel','payload':{},'actor_id':command.actor_id})):
        invalid('goal_cancel_proof_command_invalid')
    await durable.authorize(db,row,Principal(command.actor_id,0))
    value={'command_id':command.id,'operation':'cancel','ordinal':command.ordinal}
    if goal:
        event=await db.get(GoalEvent,str(uuid5(UUID(command.id),'audit')))
        if (not event or event.execution_id!=row.id or event.workspace_id!=row.workspace_id or
                event.actor_id!=command.actor_id or event.action!='command' or event.data!=value or
                event.content_hash!=digest({'action':'command','data':value,'actor_id':command.actor_id})):
            invalid('goal_cancel_proof_command_invalid')
    else:
        plan=await db.get(StudioEvent,row.plan_id)
        events=list(await db.scalars(select(StudioEvent).where(StudioEvent.action=='p62_command',
            StudioEvent.data['command_id'].as_string()==command.id)))
        if (len(events)!=1 or events[0].workspace_id!=row.workspace_id or events[0].actor_id!=command.actor_id or
                events[0].definition_id!=row.definition_id or events[0].version_id!=plan.version_id or
                events[0].data!={'execution_id':row.id,**value}):
            invalid('goal_cancel_proof_command_invalid')
    return command.id


async def verify_cancelled_claim(db,row,child,plan,snapshot,step,ident,reserved,claimed,outcome,attempt):
    """Fixed echo only: a native terminal outcome fences subsequent finish.

    This is not a queue/process ACK or a receipt for an arbitrary adapter.
    Missing mutable evidence and expired/UNKNOWN claims remain held.
    """
    if not all((reserved,claimed,outcome,attempt)):
        invalid('goal_cancel_native_evidence_missing')
    r=iterations.studio_event(reserved,child,plan,'p62_step_reserved')
    c=iterations.studio_event(claimed,child,plan,'p62_step_claimed')
    o=iterations.studio_event(outcome,child,plan,'p62_step_outcome')
    try: iterations.uuid(c['token'])
    except (ValueError,KeyError,TypeError): invalid('goal_cancel_native_claim_invalid')
    env=r['envelope']
    input_value=await jobs.resolve_input(db,child,snapshot,step)
    expected_env={'step_id':step['step_id'],'snapshot_hash':child.snapshot_hash,'input':input_value,
        'contract_hash':step['skill']['hash'],'dry_run':True,'adapter':'fixture_echo'}
    if (any(v.get('execution_id')!=ident for v in (r,c,o)) or c.get('step_id')!=step['step_id'] or
            digest(env)!=digest(expected_env) or r.get('hash')!=digest(expected_env) or
            c.get('envelope_hash')!=digest(env) or c.get('lease_seconds')!=jobs.LEASE_SECONDS or
            not reserved.created_at<=claimed.created_at<=outcome.created_at or
            outcome.created_at>claimed.created_at+timedelta(seconds=jobs.LEASE_SECONDS)):
        invalid('goal_cancel_native_claim_invalid')
    expected={'plan_id':child.id,'execution_id':ident,'step_id':step['step_id'],
        'status':'cancelled','error_code':'cancel_requested','dry_run':True,'origin':'fixture_echo'}
    if o!=expected: invalid('goal_cancel_native_outcome_invalid')
    if (attempt.workspace_id!=row.workspace_id or attempt.task_id!=ident or attempt.request_key!='p62:'+ident or
            attempt.status!='cancelled' or attempt.error_code!='cancel_requested' or attempt.finished_at is None or
            not claimed.created_at<=attempt.finished_at<=outcome.created_at or
            attempt.input_fingerprint!=digest(env) or digest(attempt.input)!=digest(env['input']) or
            attempt.result!={} or attempt.evidence!=[] or attempt.attempt_no!=1 or
            attempt.skill_snapshot.get('dry_run') is not True or
            attempt.skill_snapshot!={'dry_run':True,'studio_skill_version_id':step['skill']['version_id'],
                                    'studio_contract_hash':step['skill']['hash']}):
        invalid('goal_cancel_native_attempt_invalid')
    return {'step_id':step['step_id'],'execution_id':ident,'claim_id':claimed.id,'outcome_id':outcome.id}


async def _reconcile_cancelled(data,workflow_id,db,claimed_mode,queue_mode=False):
    try:
        closed(data,{'envelope'});validate(data['envelope'])
        if workflow_id!='p63-'+data['envelope']['execution_id']:raise ValueError()
    except (ValueError,KeyError,TypeError,AttributeError):invalid('goal_cancel_proof_contract_invalid')
    async with iterations.receipt_transaction(db) as db:
        row=await lock_execution(db,data['envelope']['execution_id'])
        if workflow_id!=row.temporal_id or digest(data['envelope'])!=digest(row.envelope):invalid('goal_cancel_proof_scope_invalid')
        await verify_admission(db,row)
        if row.status not in ('manual_review','deadline_exceeded') or row.state.get('iteration')!=1 or not row.cancel_requested:
            invalid('goal_cancel_proof_not_stopped')
        claim=await db.get(GoalEvent,iterations.claim_id(row.initial_plan_id))
        if not claim:invalid('goal_cancel_proof_claim_missing')
        iterations.verify_event(claim,row,'iteration_claim',claim.data)
        iterations.verify_event(await db.get(GoalEvent,iterations.slot_id(row.id)),row,'iteration_slot',{'claim_id':claim.id})
        child=await durable.lock_execution(db,claim.data['plan_id'])
        plan=await db.get(StudioEvent,child.plan_id)
        snapshot=await durable.verify_plan(db,plan,row.actor_id)
        if (child.workspace_id!=row.workspace_id or child.actor_id!=row.actor_id or child.temporal_id!='p62-'+child.id or
                child.status!='cancelled' or child.cancel_requested is not True or
                child.snapshot_hash!=snapshot['sha256'] or digest(child.command)!=claim.data['command_hash']):
            invalid('goal_cancel_proof_child_invalid')
        projected=await db.get(StudioEvent,str(uuid5(UUID(child.id),'projection:'+str(child.sequence))))
        if (not projected or projected.action!='p62_projection' or projected.workspace_id!=row.workspace_id or
                projected.definition_id!=child.definition_id or projected.version_id!=plan.version_id or
                projected.actor_id!=row.actor_id or digest(projected.data['state'])!=digest(child.state) or
                child.state.get('status')!='cancelled' or child.state.get('cancel_requested') is not True or
                child.state.get('dry_run') is not True or child.state.get('completed_steps')!=[] or
                projected.data['receipt'].get('cancel_requested') is not True):
            invalid('goal_cancel_proof_projection_invalid')
        parent_cancel=await cancel_command(db,row,True);child_cancel=await cancel_command(db,child,False)
        step_ids=[];claimed_proofs=[];queue_proofs=[]
        for step,mapping in zip(snapshot['steps'],plan.data['steps']):
            ident=mapping['execution_id'];step_ids.append(ident)
            attempt=await db.get(TaskAttempt,ident)
            claimed=await db.get(StudioEvent,jobs.event_id(ident,'claimed'))
            if (attempt or claimed) and not claimed_mode:
                invalid('goal_cancel_proof_step_claimed')
            reserved=await db.get(StudioEvent,jobs.event_id(ident,'reserved'))
            outcome=await db.get(StudioEvent,jobs.event_id(ident,'outcome'))
            if reserved:
                value=iterations.studio_event(reserved,child,plan,'p62_step_reserved')
                env=value['envelope']
                if (value.get('execution_id')!=ident or value.get('hash')!=digest(env) or
                        env.get('step_id')!=step['step_id'] or env.get('snapshot_hash')!=snapshot['sha256'] or
                        env.get('contract_hash')!=step['skill']['hash'] or env.get('adapter')!='fixture_echo' or env.get('dry_run') is not True):
                    invalid('goal_cancel_proof_reserved_invalid')
            if claimed or attempt:
                claimed_proofs.append(await verify_cancelled_claim(db,row,child,plan,snapshot,step,ident,
                    reserved,claimed,outcome,attempt))
            elif outcome:
                value=iterations.studio_event(outcome,child,plan,'p62_step_outcome')
                if (not reserved or value.get('execution_id')!=ident or value.get('step_id')!=step['step_id'] or
                        value.get('status')!='cancelled' or value.get('error_code')!='cancelled_before_claim' or
                        value.get('dry_run') is not True or value.get('origin')!='fixture_echo'):
                    invalid('goal_cancel_proof_outcome_invalid')
            if queue_mode and reserved:
                ack=await db.get(StudioEvent,queue_cancel.ack_id(ident))
                if not ack:invalid('goal_cancel_queue_ack_missing')
                value=await queue_cancel.verify_ack(db,child,plan,(child.id,step['step_id'],ident),ack)
                if value['cancel_command_id']!=child_cancel:invalid('goal_cancel_queue_command_mismatch')
                queue_proofs.append({'execution_id':ident,'ack_id':ack.id,'ack_hash':digest(value)})
            elif queue_mode and await db.get(StudioEvent,queue_cancel.ack_id(ident)):
                invalid('goal_cancel_queue_reservation_missing')
        if queue_mode and not queue_proofs:invalid('goal_cancel_queue_ack_missing')
        if claimed_mode and not queue_mode and not claimed_proofs: invalid('goal_cancel_native_claim_missing')
        key='cancelled-queue:1' if queue_mode else ('cancelled-native:1' if claimed_mode else 'cancel-before-claim:1')
        action='cancelled_queue_reconciled' if queue_mode else ('cancelled_native_reconciled' if claimed_mode else 'cancel_before_claim_reconciled')
        event_id=str(uuid5(UUID(row.id),key))
        previous=await db.get(GoalEvent,event_id)
        proof={'claim_id':claim.id,'child_projection_id':projected.id,'parent_cancel_id':parent_cancel,
            'child_cancel_id':child_cancel,'unclaimed_step_ids':step_ids,'known_no_effect':True,
            'cost_microusd':0,'dry_run':True,'origin':'fixture_echo'}
        if claimed_mode:
            proof={**proof,'known_no_effect':False,'claimed_steps':claimed_proofs,
                'unclaimed_step_ids':[ident for ident in step_ids if ident not in
                    {item['execution_id'] for item in claimed_proofs}],
                'queue_ack_verified':False,'native_finish_fenced':True}
        if queue_mode:
            proof={**proof,'known_no_effect':not bool(claimed_proofs),'queue_ack_verified':True,'queue_acks':queue_proofs}
        if previous:
            iterations.verify_event(previous,row,action,previous.data)
            if (digest(previous.data['proof'])!=digest(proof) or row.reserved_cost_microusd!=0 or
                    digest(row.state)!=digest(previous.data['state_after']) or row.sequence!=previous.data['sequence']):
                invalid('goal_cancel_proof_retry_conflict')
        else:
            before=await db.get(GoalEvent,str(uuid5(UUID(row.id),'first-projection:'+str(row.sequence))))
            iterations.verify_event(before,row,'first_iteration_projection',before.data if before else {})
            if (digest(before.data['state'])!=digest(row.state) or row.status!=row.state['status'] or
                    row.reserved_cost_microusd!=claim.data['reserved_cost_microusd'] or
                    row.state['reserved_cost_microusd']!=row.reserved_cost_microusd):
                invalid('goal_cancel_proof_ledger_changed')
            after={**row.state,'reserved_cost_microusd':0,'receipt_hash':digest(proof),'cancel_requested':True}
            await audit(db,row,row.actor_id,action,{'proof':proof,
                'state_before_hash':digest(row.state),'state_after':after,'sequence':row.sequence,
                'released_ceiling_microusd':row.reserved_cost_microusd,'resumed':False},event_id)
            row.state=after;row.reserved_cost_microusd=0;row.version+=1;row.updated_at=now()
        return {'execution_id':row.id,'status':row.status,'reconciled':True,
            'reserved_cost_microusd':0,'known_no_effect':not bool(claimed_proofs) if queue_mode else not claimed_mode,
            'resumed':False,'dry_run':True,**({'queue_ack_verified':True} if queue_mode else {})}


async def reconcile_cancelled_before_claim(data,workflow_id,*,db=None):
    return await _reconcile_cancelled(data,workflow_id,db,False)


async def reconcile_cancelled_native(data,workflow_id,*,db=None):
    """Stopped first iteration, fixed echo terminal fence; never queue ACK."""
    return await _reconcile_cancelled(data,workflow_id,db,True)


async def reconcile_cancelled_queue(data,workflow_id,*,db=None):
    """Explicit stopped-Goal fixed-Echo reconciliation with durable ARQ ACKs.

    No Redis calls under ledger locks, no resume, no worker registration.
    Parent/child delivered-command and projection evidence remain required.
    """
    return await _reconcile_cancelled(data,workflow_id,db,True,True)


@activity.defn(name='p63_reconcile_cancelled_before_claim')
async def reconcile_cancelled_before_claim_activity(data:dict):
    return await reconcile_cancelled_before_claim(data,iterations.workflow_origin())


@activity.defn(name='p63_reconcile_cancelled_native')
async def reconcile_cancelled_native_activity(data:dict):
    return await reconcile_cancelled_native(data,iterations.workflow_origin())
