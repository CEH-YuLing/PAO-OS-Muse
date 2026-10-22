"""First-iteration DB projection; no live dispatcher/worker authorization.

Running is a ledger observation, not proof of a Temporal child start. Completion
requires the existing immutable receipt AND rechecking all native DB evidence in
the same transaction. Unknown/deadline retain the reservation. Never completes
the business Goal or returns allow_iteration=True at this checkpoint.
"""
from uuid import UUID, uuid5

from fastapi import HTTPException

from ...auth import Principal
from ...config import settings
from ...db import Session
from ...models import GoalEvent, GoalCommand, now
from ..studio import durable
from ..studio.contracts import digest
from . import iterations
from .control import GoalControl, closed, integer, validate, TERMINAL
from .evidence import verify_admission
from .ledger import lock_execution, audit
from .projection import invalid


CORE = {'status','reason','iteration','cost_microusd','reserved_cost_microusd',
    'cancel_requested','proposal','proposal_hash','checks','receipt_hash',
    'execution_id','deadline_unix_ms','dry_run','model_executed'}
REASONS = {None,'child_execution_unknown','child_drain_unknown','adapter_unavailable',
    'permission_or_gate_lost','child_cancelled_without_goal_ack','child_command_invalid',
    'cancelled_during_admission','receipt_invalid','projection_receipt_invalid','unexpected_state'}


def frame(data, workflow_id):
    try:
        closed(data, {'envelope','state'})
        validate(data['envelope'])
        state=data['state']; closed(state,CORE|{'sequence','child_id','transport_reason'})
        integer(state['sequence'],1,2147483647)
        integer(state['iteration'],1,1)
        integer(state['cost_microusd'],0,data['envelope']['policy']['max_cost_microusd'])
        integer(state['reserved_cost_microusd'],0,data['envelope']['policy']['max_cost_microusd'])
        if (state['dry_run'] is not True or state['model_executed'] is not False or
                type(state['cancel_requested']) is not bool or workflow_id!='p63-'+data['envelope']['execution_id'] or
                state['transport_reason'] not in REASONS):
            raise ValueError()
    except (ValueError,KeyError,TypeError,AttributeError):
        invalid('goal_first_projection_contract_invalid')


async def project_first(data,workflow_id):
    frame(data,workflow_id)
    async with Session.begin() as db:
        row=await lock_execution(db,data['envelope']['execution_id'])
        state=data['state']
        if workflow_id!=row.temporal_id or digest(data['envelope'])!=digest(row.envelope):
            invalid('goal_first_projection_scope_invalid')
        permission_error=None
        try: await verify_admission(db,row)
        except HTTPException as exc: permission_error=exc.detail
        claim=await db.get(GoalEvent,iterations.claim_id(row.initial_proposal['plan_id']))
        if not claim: invalid('goal_first_projection_claim_missing')
        iterations.verify_event(claim,row,'iteration_claim',claim.data)
        iterations.verify_event(await db.get(GoalEvent,iterations.slot_id(row.id)),row,
            'iteration_slot',{'claim_id':claim.id})
        decision=await db.get(GoalCommand,claim.data['decision_id'])
        command_audit=await db.get(GoalEvent,str(uuid5(UUID(decision.id),'audit'))) if decision else None
        command_data={'command_id':decision.id,'operation':'decision','ordinal':decision.ordinal} if decision else {}
        if (not decision or decision.execution_id!=row.id or decision.workspace_id!=row.workspace_id or
                decision.operation!='decision' or set(decision.payload)!={'version','proposal_hash','decision'} or
                type(decision.payload.get('version')) is not int or not 1<=decision.payload['version']<=row.version or
                decision.payload.get('proposal_hash')!=claim.data['proposal_hash'] or decision.payload.get('decision')!='approve' or
                decision.id!=str(uuid5(UUID(row.id),decision.request_key)) or
                decision.content_hash!=digest({'operation':'decision','payload':decision.payload,'actor_id':decision.actor_id}) or
                decision.attempts<1 or decision.status not in ('processing','delivered') or
                (decision.status=='processing' and not decision.lease_token) or
                (decision.status=='delivered' and not decision.delivered_at) or
                not command_audit or command_audit.execution_id!=row.id or command_audit.workspace_id!=row.workspace_id or
                command_audit.actor_id!=decision.actor_id or command_audit.action!='command' or
                command_audit.data!=command_data or command_audit.content_hash!=digest({
                    'action':'command','data':command_data,'actor_id':decision.actor_id})):
            invalid('goal_first_projection_approval_invalid')
        try: await durable.authorize(db,row,Principal(decision.actor_id,0))
        except HTTPException as exc: permission_error=exc.detail
        running=claim.data['state']
        try:
            start=max(0,running['deadline_unix_ms']-row.envelope['policy']['max_elapsed_seconds']*1000)
            reducer=GoalControl(row.envelope,start)
            pending=reducer.propose(row.initial_proposal,start)
            approved_at=int(claim.created_at.timestamp()*1000)
            expected=reducer.decide(pending['proposal_hash'],'approve',approved_at)
            if expected['status']!='running' or digest(expected)!=digest(running): raise ValueError()
            if claim.data['reserved_cost_microusd']!=running['reserved_cost_microusd']: raise ValueError()
        except (ValueError,KeyError,TypeError,AttributeError):
            invalid('goal_first_projection_claim_invalid')
        sequence=state['sequence']; event_id=str(uuid5(UUID(row.id),'first-projection:'+str(sequence)))
        previous=await db.get(GoalEvent,event_id)
        if previous:
            iterations.verify_event(previous,row,'first_iteration_projection',previous.data)
            if digest(previous.data['state'])!=digest(state): invalid('goal_first_projection_retry_conflict')
            # Safe denial on every retry. No duplicate budget release/version bump.
            return {'allow_iteration':False,'cancel_requested':row.cancel_requested}
        if row.status in TERMINAL: invalid('goal_first_projection_terminal')
        if sequence!=row.sequence+1: invalid('goal_first_projection_sequence_invalid')
        # Mutable row must match its latest immutable projection before advancing.
        before=await db.get(GoalEvent,str(uuid5(UUID(row.id),
            ('pre-child-projection:' if row.state.get('iteration')==0 else 'first-projection:')+str(row.sequence))))
        action='pre_child_projection' if row.state.get('iteration')==0 else 'first_iteration_projection'
        iterations.verify_event(before,row,action,before.data if before else {})
        if (digest(before.data['state'])!=digest(row.state) or row.status!=row.state['status'] or
                row.reserved_cost_microusd!=running['reserved_cost_microusd']):
            invalid('goal_first_projection_ledger_changed')
        stamp=int(now().timestamp()*1000)
        receipt_id=None
        try:
            if state['child_id'] not in (None,'p62-'+claim.data['plan_id']): raise ValueError()
            if state['cancel_requested']!=row.cancel_requested: raise ValueError()
            if row.cancel_requested: reducer.cancel(stamp)
            status=state['status']
            if status=='running':
                c=settings()
                if (permission_error or row.cancel_requested or stamp>=running['deadline_unix_ms'] or
                        not all((c.goal_iterations_enabled,c.goal_admission_enabled,c.workflow_durable_enabled,
                            c.studio_enabled,c.workflow_planning_enabled,c.temporal_enabled)) or state['transport_reason'] is not None):
                    raise ValueError()
            elif status=='manual_review':
                reducer.uncertain(stamp)
            elif status=='deadline_exceeded':
                reducer.advance(stamp)
            elif status in ('completed','waiting_replan','budget_exhausted','cancelled'):
                if permission_error or state['child_id']!='p62-'+claim.data['plan_id'] or state['transport_reason'] is not None:
                    raise ValueError()
                receipt_id=str(uuid5(UUID(row.id),'receipt:1'))
                stored=await db.get(GoalEvent,receipt_id)
                if not stored: invalid('goal_first_projection_receipt_missing')
                iterations.verify_event(stored,row,'iteration_receipt',stored.data)
                receipt=await iterations.read_first_receipt({'envelope':row.envelope,'state':running,
                    'child_result':{'status':'completed'}},workflow_id,db=db)
                if digest(receipt)!=stored.data['receipt_hash']: raise ValueError()
                reducer.finish(receipt,stamp)
            else: raise ValueError()
            expected=reducer.snapshot()
            if digest(expected)!=digest({key:state[key] for key in CORE}): raise ValueError()
        except (ValueError,KeyError,TypeError,AttributeError):
            invalid('goal_first_projection_state_invalid')
        receipt={'allow_iteration':False,'cancel_requested':row.cancel_requested}
        await audit(db,row,row.actor_id,'first_iteration_projection',{'state':state,
            'receipt':receipt,'claim_id':claim.id,'receipt_id':receipt_id,
            'scope':'first_iteration_only','permission_error':permission_error},event_id)
        row.state=state;row.status=state['status'];row.sequence=sequence
        row.reserved_cost_microusd=state['reserved_cost_microusd'];row.version+=1;row.updated_at=now()
        return receipt
