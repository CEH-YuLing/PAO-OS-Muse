"""Explicit late-completion reconciliation; no poller/API/worker registration.

Only a verified completed fixture child can discharge a held first-iteration
reservation. Unknown/cancelled/absent children have no such proof yet. Preserve
the stopped status/reason/sequence; never resume or mark a business Goal done.
"""
from uuid import UUID,uuid5

from temporalio import activity

from ...auth import Principal
from ...models import GoalEvent,GoalCommand,now
from ..studio import durable
from ..studio.contracts import digest
from .control import closed,validate
from .evidence import verify_admission
from .ledger import lock_execution,audit
from . import iterations
from .projection import invalid


async def reconcile_completed_first(data,workflow_id,*,db=None):
    try:
        closed(data,{'envelope'});validate(data['envelope'])
        if workflow_id!='p63-'+data['envelope']['execution_id']:raise ValueError()
    except (ValueError,KeyError,TypeError,AttributeError):invalid('goal_recovery_contract_invalid')
    async with iterations.receipt_transaction(db) as db:
        row=await lock_execution(db,data['envelope']['execution_id'])
        if row.temporal_id!=workflow_id or digest(row.envelope)!=digest(data['envelope']):
            invalid('goal_recovery_scope_invalid')
        await verify_admission(db,row)
        claim=await db.get(GoalEvent,iterations.claim_id(row.initial_plan_id))
        if not claim:invalid('goal_recovery_claim_missing')
        iterations.verify_event(claim,row,'iteration_claim',claim.data)
        iterations.verify_event(await db.get(GoalEvent,iterations.slot_id(row.id)),row,'iteration_slot',{'claim_id':claim.id})
        decision=await db.get(GoalCommand,claim.data['decision_id'])
        command_audit=await db.get(GoalEvent,str(uuid5(UUID(decision.id),'audit'))) if decision else None
        command_data={'command_id':decision.id,'operation':'decision','ordinal':decision.ordinal} if decision else {}
        if (not decision or decision.execution_id!=row.id or decision.workspace_id!=row.workspace_id or
                decision.operation!='decision' or set(decision.payload)!={'version','proposal_hash','decision'} or
                type(decision.payload.get('version')) is not int or not 1<=decision.payload['version']<=row.version or
                decision.payload.get('proposal_hash')!=claim.data['proposal_hash'] or decision.payload.get('decision')!='approve' or
                decision.id!=str(uuid5(UUID(row.id),decision.request_key)) or decision.status!='delivered' or
                not decision.delivered_at or decision.attempts<1 or
                decision.content_hash!=digest({'operation':'decision','payload':decision.payload,'actor_id':decision.actor_id}) or
                not command_audit or command_audit.execution_id!=row.id or command_audit.workspace_id!=row.workspace_id or
                command_audit.action!='command' or command_audit.actor_id!=decision.actor_id or command_audit.data!=command_data or
                command_audit.content_hash!=digest({'action':'command','data':command_data,'actor_id':decision.actor_id})):
            invalid('goal_recovery_approval_invalid')
        await durable.authorize(db,row,Principal(decision.actor_id,0))
        if row.status not in ('manual_review','deadline_exceeded') or row.state.get('iteration')!=1:
            invalid('goal_recovery_not_stopped_first')
        event_id=str(uuid5(UUID(row.id),'late-completion:1'))
        previous=await db.get(GoalEvent,event_id)
        if previous:
            iterations.verify_event(previous,row,'late_completion_reconciled',previous.data)
            if (row.reserved_cost_microusd!=0 or digest(row.state)!=digest(previous.data['state_after']) or
                    row.sequence!=previous.data['sequence'] or row.cancel_requested!=previous.data['cancel_requested']):
                invalid('goal_recovery_retry_conflict')
        else:
            projected=await db.get(GoalEvent,str(uuid5(UUID(row.id),'first-projection:'+str(row.sequence))))
            iterations.verify_event(projected,row,'first_iteration_projection',projected.data if projected else {})
            if (row.status!=row.state['status'] or digest(row.state)!=digest(projected.data['state']) or
                    type(row.reserved_cost_microusd) is not int or
                    row.reserved_cost_microusd!=claim.data['reserved_cost_microusd'] or
                    row.state['reserved_cost_microusd']!=row.reserved_cost_microusd or row.state['cost_microusd']!=0 or
                    row.state['deadline_unix_ms']!=claim.data['state']['deadline_unix_ms']):
                invalid('goal_recovery_ledger_changed')
        # This re-reads every completed outcome/lease/attempt/approval in the
        # same transaction. It cannot turn missing/cancelled/UNKNOWN into cost0.
        receipt=await iterations.read_first_receipt({'envelope':row.envelope,
            'state':claim.data['state'],'child_result':{'status':'completed'}},workflow_id,db=db)
        receipt_id=str(uuid5(UUID(row.id),'receipt:1'))
        result={'execution_id':row.id,'status':row.status,'reconciled':True,
            'reserved_cost_microusd':0,'receipt_hash':digest(receipt),'resumed':False,'dry_run':True}
        if previous:
            if previous.data['receipt_id']!=receipt_id or previous.data['receipt_hash']!=digest(receipt):
                invalid('goal_recovery_retry_conflict')
            return result
        after={**row.state,'reserved_cost_microusd':0,'receipt_hash':digest(receipt),
            'cancel_requested':row.cancel_requested}
        value={'sequence':row.sequence,'claim_id':claim.id,'receipt_id':receipt_id,
            'receipt_hash':digest(receipt),'state_before_hash':digest(row.state),'state_after':after,
            'released_ceiling_microusd':row.reserved_cost_microusd,'cancel_requested':row.cancel_requested,
            'resumed':False,'scope':'completed_first_iteration_only'}
        await audit(db,row,row.actor_id,'late_completion_reconciled',value,event_id)
        row.state=after;row.reserved_cost_microusd=0;row.version+=1;row.updated_at=now()
        return result


@activity.defn(name='p63_reconcile_completed_first')
async def reconcile_completed_first_activity(data:dict):
    return await reconcile_completed_first(data,iterations.workflow_origin())
