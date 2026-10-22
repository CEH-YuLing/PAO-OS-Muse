"""First-iteration DB claims/receipts. NOT registered in a live worker.

Preparing records an inert child and reserves a ceiling; it never starts a
workflow/job. Only immutable P6.2 outcomes can produce a fixture echo receipt.
Projection/dispatcher/drain still require completion before live goal execution.
"""
from datetime import timedelta
from contextlib import asynccontextmanager
from uuid import UUID, uuid5

from sqlalchemy import select
from temporalio import activity

from ...auth import Principal
from ...config import settings
from ...db import Session
from ...models import GoalCommand, GoalEvent, StudioDefinition, StudioExecution, StudioEvent, StudioCommand, TaskAttempt, now
from ..studio import durable, step_jobs as jobs
from ..studio.contracts import digest
from ..studio.durable_workflow import validate_command
from ..studio.results import fixture_echo
from ..studio.service import reject
from .control import GoalControl, validate, closed, text, uuid
from .evidence import verify_admission
from .ledger import lock_execution, audit
from .projection import invalid


def claim_id(plan_id):
    return str(uuid5(UUID(plan_id),'p63-plan-owner'))


def slot_id(execution_id):
    return str(uuid5(UUID(execution_id),'iteration:1'))


def verify_event(event,row,action,data):
    if (not event or event.execution_id!=row.id or event.workspace_id!=row.workspace_id or
            event.actor_id!=row.actor_id or event.action!=action or digest(event.data)!=digest(data) or
            event.content_hash!=digest({'action':action,'data':data,'actor_id':row.actor_id})):
        invalid('goal_iteration_evidence_invalid')


def context(data,workflow_id,receipt=False):
    try:
        closed(data,{'envelope','state','child_result'} if receipt else {'envelope','state'})
        validate(data['envelope'])
        if workflow_id!='p63-'+data['envelope']['execution_id']: raise ValueError()
        s=data['state']
        closed(s,{'status','reason','iteration','cost_microusd','reserved_cost_microusd',
            'cancel_requested','proposal','proposal_hash','checks','receipt_hash','execution_id',
            'deadline_unix_ms','dry_run','model_executed'})
        if s['status']!='running' or type(s['iteration']) is not int or s['iteration']!=1:
            raise ValueError()
        if s['dry_run'] is not True or s['model_executed'] is not False: raise ValueError()
        if receipt and (type(data['child_result']) is not dict or data['child_result'].get('status') not in ('completed','cancelled')):
            raise ValueError()
    except (ValueError,KeyError,TypeError,AttributeError): invalid('goal_iteration_contract_invalid')


async def admitted_context(db,data,workflow_id):
    row=await lock_execution(db,data['envelope']['execution_id'])
    if workflow_id!=row.temporal_id or digest(data['envelope'])!=digest(row.envelope):
        invalid('goal_iteration_scope_invalid')
    await verify_admission(db,row)
    return row


async def prepare_first(data,workflow_id):
    context(data,workflow_id)
    c=settings()
    if not all((c.goal_iterations_enabled,c.goal_admission_enabled,c.studio_enabled,
                c.workflow_planning_enabled,c.workflow_durable_enabled,c.temporal_enabled)):
        reject('goal_iteration_adapters_disabled',503)
    async with Session.begin() as db:
        row=await admitted_context(db,data,workflow_id)
        if row.cancel_requested or row.status!='waiting_approval': invalid('goal_iteration_not_approvable')
        s=data['state']; pending=row.state
        try:
            stamp=int(now().timestamp()*1000)
            start=max(0,pending['deadline_unix_ms']-row.envelope['policy']['max_elapsed_seconds']*1000)
            reducer=GoalControl(row.envelope,start)
            expected=reducer.propose(row.initial_proposal,start)
            if digest({k:pending[k] for k in expected})!=digest(expected): raise ValueError()
            projected=await db.get(GoalEvent,str(uuid5(UUID(row.id),'pre-child-projection:'+str(row.sequence))))
            verify_event(projected,row,'pre_child_projection',projected.data if projected else {})
            if digest(projected.data['state'])!=digest(pending): raise ValueError()
            expected=reducer.decide(pending['proposal_hash'],'approve',stamp)
            if expected['status']!='running' or digest(expected)!=digest(s): raise ValueError()
        except (ValueError,KeyError,TypeError,AttributeError): invalid('goal_iteration_state_invalid')
        decisions=list(await db.scalars(select(GoalCommand).where(GoalCommand.execution_id==row.id,
            GoalCommand.operation=='decision',GoalCommand.payload['proposal_hash'].as_string()==s['proposal_hash'])))
        if len(decisions)!=1: invalid('goal_iteration_approval_missing')
        decision=decisions[0]
        if (decision.payload.get('decision')!='approve' or decision.workspace_id!=row.workspace_id or
                decision.content_hash!=digest({'operation':'decision','payload':decision.payload,'actor_id':decision.actor_id}) or
                decision.attempts<1 or decision.status not in ('processing','delivered') or
                (decision.status=='processing' and not decision.lease_token) or
                (decision.status=='delivered' and not decision.delivered_at)):
            invalid('goal_iteration_approval_invalid')
        await durable.authorize(db,row,Principal(decision.actor_id,0))
        command_audit=await db.get(GoalEvent,str(uuid5(UUID(decision.id),'audit')))
        command_data={'command_id':decision.id,'operation':'decision','ordinal':decision.ordinal}
        if (not command_audit or command_audit.execution_id!=row.id or command_audit.workspace_id!=row.workspace_id or
                command_audit.actor_id!=decision.actor_id or command_audit.action!='command' or
                command_audit.data!=command_data or command_audit.content_hash!=digest({
                    'action':'command','data':command_data,'actor_id':decision.actor_id})):
            invalid('goal_iteration_approval_invalid')
        proposal=s['proposal']
        if proposal!=row.initial_proposal: invalid('goal_first_iteration_pin_invalid')
        plan=await db.get(StudioEvent,proposal['plan_id'])
        await db.scalar(select(StudioDefinition).where(StudioDefinition.id==plan.definition_id).with_for_update())
        snapshot=await durable.verify_plan(db,plan,row.actor_id)
        child={'format':'p62-dryrun-v1','plan_id':plan.id,'snapshot_hash':snapshot['sha256'],
            'timeout_seconds':proposal['max_duration_seconds'],'steps':[
                {'step_id':step['step_id'],'execution_id':mapping['execution_id'],
                 'depends_on':step['depends_on'],'approval_required':True,'delay_seconds':0}
                for step,mapping in zip(snapshot['steps'],plan.data['steps'])]}
        validate_command(child)
        value={'iteration':1,'plan_id':plan.id,'proposal_hash':s['proposal_hash'],
            'state':s,'command':child,'command_hash':digest(child),'decision_id':decision.id,
            'reserved_cost_microusd':s['reserved_cost_microusd']}
        existing=await db.get(GoalEvent,claim_id(plan.id))
        owned=await db.get(StudioExecution,plan.id)
        if existing:
            verify_event(existing,row,'iteration_claim',value)
            verify_event(await db.get(GoalEvent,slot_id(row.id)),row,'iteration_slot',{'claim_id':existing.id})
            if (not owned or owned.workspace_id!=row.workspace_id or owned.actor_id!=row.actor_id or
                    owned.snapshot_hash!=snapshot['sha256'] or digest(owned.command)!=digest(child)):
                invalid('goal_child_identity_changed')
            return child
        if owned or await db.get(GoalEvent,slot_id(row.id)): invalid('goal_child_already_owned')
        owned=StudioExecution(id=plan.id,workspace_id=row.workspace_id,definition_id=plan.definition_id,
            plan_id=plan.id,actor_id=row.actor_id,temporal_id='p62-'+plan.id,
            snapshot_hash=snapshot['sha256'],command=child)
        db.add(owned); await db.flush()
        start_key=str(uuid5(UUID(row.id),'child-start:1'))
        start_command,_=await durable.command(db,owned,row.actor_id,start_key,'start',{
            'confirmation_hash':snapshot['sha256'],'timeout_seconds':child['timeout_seconds'],'delay_seconds':0})
        # Parent owns transport. Do NOT claim a Temporal ACK before child start,
        # and never let standalone P6.2 dispatcher start this prepared child.
        start_command.status='dead'; start_command.error_code='goal_parent_owned_start'
        await audit(db,row,row.actor_id,'iteration_claim',value,claim_id(plan.id))
        await audit(db,row,row.actor_id,'iteration_slot',{'claim_id':claim_id(plan.id)},slot_id(row.id))
        row.reserved_cost_microusd=s['reserved_cost_microusd'];row.version+=1;row.updated_at=now()
        return child


def studio_event(event,child,plan,action):
    if (not event or event.action!=action or event.workspace_id!=child.workspace_id or
            event.definition_id!=child.definition_id or event.version_id!=plan.version_id or
            event.actor_id!=child.actor_id or event.data.get('plan_id')!=child.id):
        invalid('goal_child_receipt_scope_invalid')
    return event.data


@asynccontextmanager
async def receipt_transaction(db):
    # Internal composition only: reuse the caller's locked transaction so
    # projection cannot validate evidence and release a reservation in two
    # separate transactions. Public activities never accept a DB argument.
    if db is not None:
        yield db
    else:
        async with Session.begin() as session:
            yield session


async def read_first_receipt(data,workflow_id,*,db=None):
    context(data,workflow_id,True)
    async with receipt_transaction(db) as db:
        row=await admitted_context(db,data,workflow_id)
        s=data['state']; plan=await db.get(StudioEvent,s['proposal']['plan_id'])
        claim=await db.get(GoalEvent,claim_id(plan.id)) if plan else None
        if not claim: invalid('goal_iteration_claim_missing')
        verify_event(claim,row,'iteration_claim',claim.data)
        verify_event(await db.get(GoalEvent,slot_id(row.id)),row,'iteration_slot',{'claim_id':claim.id})
        if digest(claim.data['state'])!=digest(s): invalid('goal_iteration_receipt_state_invalid')
        return await verified_completed_child(db,row,s,claim)


async def verified_completed_child(db,row,s,claim,*,completed_prefix=False):
    """Internal strict child evidence validator shared by versioned runners.

    Callers must verify their own immutable admission/journal/iteration claim.
    The existing first-iteration endpoint retains all of its original fences.
    """
    async with receipt_transaction(db) as db:
        plan=await db.get(StudioEvent,s['proposal']['plan_id'])
        child=await durable.lock_execution(db,plan.id)
        if (child.workspace_id!=row.workspace_id or child.actor_id!=row.actor_id or
                child.temporal_id!='p62-'+plan.id or digest(child.command)!=claim.data['command_hash']):
            invalid('goal_child_identity_changed')
        snapshot=await durable.verify_plan(db,plan,row.actor_id)
        if child.snapshot_hash!=snapshot['sha256']: invalid('goal_child_pin_changed')
        final=await db.get(StudioEvent,str(uuid5(UUID(child.id),'projection:'+str(child.sequence))))
        if (not final or final.action!='p62_projection' or final.workspace_id!=row.workspace_id or
                final.actor_id!=row.actor_id or final.definition_id!=child.definition_id or
                final.version_id!=plan.version_id or digest(final.data['state'])!=digest(child.state)):
            invalid('goal_child_final_projection_missing')
        status=final.data['state']['status']
        ordered=[step['step_id'] for step in snapshot['steps']]
        count=len(child.state['completed_steps']) if completed_prefix else len(ordered)
        valid=(status=='cancelled' and child.status=='cancelled' and
            0<count<len(ordered) and child.state['completed_steps']==ordered[:count]) if completed_prefix else (
            status=='completed' and child.status=='completed' and child.state['completed_steps']==ordered)
        if not valid:
            # Cancel/unknown drain receipts need the next checkpoint's explicit
            # ACK/absence proofs. Do not turn missing outcomes into zero cost.
            invalid('goal_child_not_verified_completed')
        outputs=[]; outcome_ids=[]
        for step,mapping in zip(snapshot['steps'][:count],plan.data['steps'][:count]):
            ident=mapping['execution_id']
            reserved=await db.get(StudioEvent,jobs.event_id(ident,'reserved'))
            claimed=await db.get(StudioEvent,jobs.event_id(ident,'claimed'))
            outcome=await db.get(StudioEvent,jobs.event_id(ident,'outcome'))
            r=studio_event(reserved,child,plan,'p62_step_reserved')
            c=studio_event(claimed,child,plan,'p62_step_claimed')
            o=studio_event(outcome,child,plan,'p62_step_outcome')
            input_value=await jobs.resolve_input(db,child,snapshot,step)
            envelope={'step_id':step['step_id'],'snapshot_hash':child.snapshot_hash,
                'input':input_value,'contract_hash':step['skill']['hash'],
                'dry_run':True,'adapter':'fixture_echo'}
            expected=fixture_echo(step['skill']['payload'],input_value)
            try: uuid(c['token'])
            except (ValueError,KeyError): invalid('goal_child_claim_token_invalid')
            if (any(v.get('execution_id')!=ident for v in (r,c,o)) or
                    digest(r['envelope'])!=digest(envelope) or r['hash']!=digest(envelope) or
                    c['step_id']!=step['step_id'] or c['envelope_hash']!=digest(envelope) or c['lease_seconds']!=jobs.LEASE_SECONDS or
                    not reserved.created_at<=claimed.created_at<=outcome.created_at or
                    outcome.created_at>claimed.created_at+timedelta(seconds=jobs.LEASE_SECONDS) or
                    o['step_id']!=step['step_id'] or o['status']!='completed' or
                    o['origin']!='fixture_echo' or o['dry_run'] is not True or
                    digest(o['input'])!=digest(input_value) or digest(o['output'])!=digest(expected['output']) or
                    digest(o['receipt'])!=digest(expected['receipt'])):
                invalid('goal_child_receipt_invalid')
            attempt=await db.get(TaskAttempt,ident)
            if (not attempt or attempt.workspace_id!=row.workspace_id or attempt.task_id!=ident or
                    attempt.request_key!='p62:'+ident or attempt.status!='completed' or
                    attempt.input_fingerprint!=digest(envelope) or digest(attempt.input)!=digest(input_value) or
                    digest(attempt.result)!=digest(expected) or attempt.skill_snapshot.get('dry_run') is not True or
                    attempt.skill_snapshot.get('studio_contract_hash')!=step['skill']['hash'] or
                    attempt.skill_snapshot.get('studio_skill_version_id')!=step['skill']['version_id']):
                invalid('goal_child_attempt_binding_invalid')
            decisions=list(await db.scalars(select(StudioCommand).where(StudioCommand.execution_id==child.id,
                StudioCommand.operation=='decision',StudioCommand.payload['step_id'].as_string()==step['step_id'])))
            if len(decisions)!=1: invalid('goal_child_step_approval_missing')
            d=decisions[0]
            if (d.payload.get('decision')!='approve' or d.status!='delivered' or not d.delivered_at or d.attempts<1 or
                    d.workspace_id!=row.workspace_id or d.content_hash!=digest({
                        'operation':'decision','payload':d.payload,'actor_id':d.actor_id})):
                invalid('goal_child_step_approval_invalid')
            await durable.authorize(db,child,Principal(d.actor_id,0))
            command_events=list(await db.scalars(select(StudioEvent).where(
                StudioEvent.action=='p62_command',StudioEvent.data['command_id'].as_string()==d.id)))
            expected_audit={'execution_id':child.id,'command_id':d.id,'operation':'decision','ordinal':d.ordinal}
            if (len(command_events)!=1 or command_events[0].workspace_id!=row.workspace_id or
                    command_events[0].definition_id!=child.definition_id or command_events[0].version_id!=plan.version_id or
                    command_events[0].actor_id!=d.actor_id or digest(command_events[0].data)!=digest(expected_audit) or
                    d.id!=str(uuid5(UUID(child.id),d.request_key))):
                invalid('goal_child_step_approval_invalid')
            outputs.append(o['output']);outcome_ids.append(outcome.id)
        if completed_prefix:
            return {'completed_steps':ordered[:count],'outcome_ids':outcome_ids,
                'projection_id':final.id,'cost_microusd':0,'dry_run':True}
        output=outputs[-1]
        try: closed(output,{'text'});text(output['text'])
        except (ValueError,TypeError): invalid('goal_child_output_subset_invalid')
        receipt={'execution_id':row.id,'iteration':s['iteration'],'proposal_hash':s['proposal_hash'],
            'output':output,'cost_microusd':0,'dry_run':True,'origin':'fixture_echo'}
        evidence={'receipt':receipt,'receipt_hash':digest(receipt),'claim_id':claim.id,
            'projection_id':final.id,'outcome_ids':outcome_ids}
        event_id=str(uuid5(UUID(row.id),'receipt:'+str(s['iteration'])))
        existing=await db.get(GoalEvent,event_id)
        if existing: verify_event(existing,row,'iteration_receipt',evidence)
        else: await audit(db,row,row.actor_id,'iteration_receipt',evidence,event_id)
        # Observation only. Budget release/success projection must consume this
        # immutable evidence later; do not auto-complete a Goal or clear reserve.
        return receipt


def workflow_origin():
    info=activity.info()
    if (info.workflow_type!='PaoBoundedDryRunGoalWorkflow' or
            info.workflow_namespace!=settings().temporal_namespace or
            info.task_queue!=settings().workflow_temporal_task_queue):
        invalid('goal_iteration_workflow_origin_invalid')
    return info.workflow_id


@activity.defn(name='p63_prepare_iteration')
async def prepare_iteration(data:dict):
    return await prepare_first(data,workflow_origin())


@activity.defn(name='p63_read_receipt')
async def read_receipt(data:dict):
    return await read_first_receipt(data,workflow_origin())
