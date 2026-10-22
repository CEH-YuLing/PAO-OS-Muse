"""First-iteration launch evidence only. No worker/endpoint or child start.

The immutable grant never changes old projection denials into permission. It
must be revalidated at the future child-start boundary; it is not a bearer token.
"""
from uuid import UUID,uuid5
from sqlalchemy import select
from temporalio import activity
from ...auth import Principal
from ...config import settings
from ...models import GoalEvent,GoalCommand,StudioEvent,StudioCommand,TaskAttempt,now
from ...skills import execution_binding
from ..studio import durable,step_jobs
from ..studio.contracts import digest
from . import iterations,first_projection
from .control import closed,validate,GoalControl
from .dispatcher import verify_command
from .evidence import verify_admission
from .ledger import lock_execution,audit
from .projection import invalid


def grant_id(execution_id):return str(uuid5(UUID(execution_id),'execution-grant:1'))


async def evidence(db,data,workflow_id):
    try:
        closed(data,{'envelope','proposal_hash'});validate(data['envelope'])
        if workflow_id!='p63-'+data['envelope']['execution_id']:raise ValueError()
    except (ValueError,KeyError,TypeError,AttributeError):invalid('goal_grant_contract_invalid')
    c=settings()
    if not all((c.goal_iterations_enabled,c.goal_admission_enabled,c.studio_enabled,
                c.workflow_planning_enabled,c.workflow_durable_enabled,c.temporal_enabled)):
        invalid('goal_grant_gates_disabled')
    row=await lock_execution(db,data['envelope']['execution_id'])
    if workflow_id!=row.temporal_id or digest(data['envelope'])!=digest(row.envelope):invalid('goal_grant_scope_invalid')
    snapshot=await verify_admission(db,row)
    if row.cancel_requested or row.status!='running':invalid('goal_grant_not_running')
    first_projection.frame({'envelope':row.envelope,'state':row.state},workflow_id)
    claim=await db.get(GoalEvent,iterations.claim_id(row.initial_plan_id))
    iterations.verify_event(claim,row,'iteration_claim',claim.data if claim else {})
    value=claim.data
    try:
        closed(value,{'iteration','plan_id','proposal_hash','state','command','command_hash','decision_id','reserved_cost_microusd'})
        if (type(value['iteration']) is not int or value['iteration']!=1 or value['plan_id']!=row.initial_plan_id or
                data['proposal_hash']!=value['proposal_hash'] or value['command_hash']!=digest(value['command'])):raise ValueError()
        core=value['state']
        iterations.context({'envelope':row.envelope,'state':core},workflow_id)
        start=max(0,core['deadline_unix_ms']-row.envelope['policy']['max_elapsed_seconds']*1000)
        reducer=GoalControl(row.envelope,start);pending=reducer.propose(row.initial_proposal,start)
        expected=reducer.decide(pending['proposal_hash'],'approve',int(claim.created_at.timestamp()*1000))
        if expected['status']!='running' or digest(core)!=digest(expected):raise ValueError()
        if digest({key:row.state[key] for key in first_projection.CORE})!=digest(expected):raise ValueError()
        if (row.state['child_id'] is not None or row.state['transport_reason'] is not None or
                type(row.reserved_cost_microusd) is not int or
                row.reserved_cost_microusd!=core['reserved_cost_microusd'] or
                value['reserved_cost_microusd']!=core['reserved_cost_microusd']):raise ValueError()
        stamp=int(now().timestamp()*1000)
        if stamp+row.initial_proposal['max_duration_seconds']*1000>core['deadline_unix_ms']:raise ValueError()
    except (ValueError,KeyError,TypeError,AttributeError):invalid('goal_grant_budget_or_state_invalid')
    slot=await db.get(GoalEvent,iterations.slot_id(row.id))
    iterations.verify_event(slot,row,'iteration_slot',{'claim_id':claim.id})
    projected=await db.get(GoalEvent,str(uuid5(UUID(row.id),'first-projection:'+str(row.sequence))))
    iterations.verify_event(projected,row,'first_iteration_projection',projected.data if projected else {})
    if (digest(projected.data['state'])!=digest(row.state) or projected.data['claim_id']!=claim.id or
            projected.data['permission_error'] is not None or projected.data['receipt_id'] is not None or
            projected.data['scope']!='first_iteration_only' or
            projected.data['receipt']!={'allow_iteration':False,'cancel_requested':False}):
        invalid('goal_grant_projection_invalid')
    start_command=await db.scalar(select(GoalCommand).where(GoalCommand.execution_id==row.id,GoalCommand.operation=='start'))
    decision=await db.get(GoalCommand,value['decision_id'])
    for command in (start_command,decision):
        if (not command or command.status!='delivered' or command.attempts<1 or not command.delivered_at or
                command.lease_token is not None or command.lease_until is not None):invalid('goal_grant_transport_not_acknowledged')
        await verify_command(db,row,command)
        await durable.authorize(db,row,Principal(command.actor_id,0))
    if (decision.operation!='decision' or set(decision.payload)!={'version','proposal_hash','decision'} or
            type(decision.payload['version']) is not int or not 1<=decision.payload['version']<=row.version or
            decision.payload['proposal_hash']!=core['proposal_hash'] or decision.payload['decision']!='approve' or
            not start_command.created_at<=decision.created_at<=claim.created_at<=projected.created_at):
        invalid('goal_grant_approval_invalid')
    child=await durable.lock_execution(db,row.initial_plan_id)
    command={'format':'p62-dryrun-v1','plan_id':child.id,'snapshot_hash':snapshot['sha256'],
        'timeout_seconds':row.initial_proposal['max_duration_seconds'],'steps':[
            {'step_id':step['step_id'],'execution_id':mapping['execution_id'],'depends_on':step['depends_on'],
             'approval_required':True,'delay_seconds':0}
            for step,mapping in zip(snapshot['steps'],(await db.get(StudioEvent,row.initial_plan_id)).data['steps'])]}
    if (child.workspace_id!=row.workspace_id or child.actor_id!=row.actor_id or child.plan_id!=row.initial_plan_id or
            child.temporal_id!='p62-'+child.id or child.snapshot_hash!=snapshot['sha256'] or
            digest(child.command)!=digest(command) or digest(value['command'])!=digest(command) or
            child.status!='starting' or child.sequence!=0 or child.cancel_requested or child.state!={}):
        invalid('goal_grant_child_not_inert')
    start_key=str(uuid5(UUID(row.id),'child-start:1'))
    child_start=await db.get(StudioCommand,str(uuid5(UUID(child.id),start_key)))
    payload={'confirmation_hash':snapshot['sha256'],'timeout_seconds':command['timeout_seconds'],'delay_seconds':0}
    if (not child_start or child_start.workspace_id!=row.workspace_id or child_start.execution_id!=child.id or
            child_start.actor_id!=row.actor_id or child_start.operation!='start' or child_start.request_key!=start_key or
            child_start.payload!=payload or child_start.content_hash!=digest({'operation':'start','payload':payload,'actor_id':row.actor_id}) or
            child_start.status!='dead' or child_start.error_code!='goal_parent_owned_start' or
            child_start.ordinal!=1 or child_start.attempts!=0 or child_start.delivered_at is not None or
            child_start.lease_token is not None or child_start.lease_until is not None):invalid('goal_grant_child_start_invalid')
    plan=await db.get(StudioEvent,row.initial_plan_id)
    child_audits=list(await db.scalars(select(StudioEvent).where(StudioEvent.action=='p62_command',
        StudioEvent.data['command_id'].as_string()==child_start.id)))
    if (len(child_audits)!=1 or child_audits[0].workspace_id!=row.workspace_id or
            child_audits[0].definition_id!=child.definition_id or child_audits[0].version_id!=plan.version_id or
            child_audits[0].actor_id!=row.actor_id or child_audits[0].data!={
                'execution_id':child.id,'command_id':child_start.id,'operation':'start','ordinal':1}):
        invalid('goal_grant_child_start_audit_invalid')
    ids=[step['execution_id'] for step in command['steps']]
    if (await db.scalar(select(TaskAttempt.id).where(TaskAttempt.id.in_(ids)).limit(1)) or
            await db.scalar(select(StudioEvent.id).where(StudioEvent.action.like('p62_step_%'),
                StudioEvent.data['plan_id'].as_string()==child.id).limit(1)) or
            await db.scalar(select(StudioEvent.id).where(StudioEvent.action=='p62_projection',
                StudioEvent.data['state']['plan_id'].as_string()==child.id).limit(1))):
        invalid('goal_grant_child_history_exists')
    proof={'iteration':1,'claim_id':claim.id,'slot_id':slot.id,'start_command_id':start_command.id,
        'decision_id':decision.id,'projection_id':projected.id,'projection_hash':digest(projected.data),
        'child_id':child.temporal_id,'child_start_command_id':child_start.id,'command_hash':digest(command),
        'proposal_hash':core['proposal_hash'],'deadline_unix_ms':core['deadline_unix_ms'],
        'reserved_cost_microusd':row.reserved_cost_microusd,'source_binding':execution_binding(),
        'dry_run':True,'model_executed':False}
    return row,proof


async def issue_first_grant(data,workflow_id,*,db=None):
    async with iterations.receipt_transaction(db) as db:
        row,proof=await evidence(db,data,workflow_id)
        ident=grant_id(row.id);previous=await db.get(GoalEvent,ident)
        if previous:iterations.verify_event(previous,row,'execution_grant',proof)
        else:await audit(db,row,row.actor_id,'execution_grant',proof,ident)
        return {'execution_id':row.id,'grant_id':ident,'iteration':1,'child_id':proof['child_id'],
            'command_hash':proof['command_hash'],'dry_run':True,'child_started':False}


async def verify_first_grant(data,workflow_id,*,db=None):
    async with iterations.receipt_transaction(db) as db:
        row,proof=await evidence(db,data,workflow_id)
        saved=await db.get(GoalEvent,grant_id(row.id))
        iterations.verify_event(saved,row,'execution_grant',proof)
        return proof


async def consume_first_grant(data,workflow_id,*,experiment_id,db=None):
    """At-most-once experimental start intent, never a reusable launch token.

    A lost activity completion ACK intentionally leaves the grant consumed:
    recovery requires inspection, not retry/remint. No reservation is released.
    The trial is NOT the existing Goal kernel and has no live registration.
    """
    if experiment_id!='p63-grant-trial-'+data.get('envelope',{}).get('execution_id',''):
        invalid('goal_grant_trial_origin_invalid')
    async with iterations.receipt_transaction(db) as db:
        row,proof=await evidence(db,data,workflow_id)
        iterations.verify_event(await db.get(GoalEvent,grant_id(row.id)),row,'execution_grant',proof)
        ident=str(uuid5(UUID(row.id),'execution-grant-consumed:1'))
        if await db.get(GoalEvent,ident):invalid('goal_grant_already_consumed')
        await audit(db,row,row.actor_id,'execution_grant_consumed',{
            'grant_id':grant_id(row.id),'grant_hash':digest(proof),
            'experiment_id':experiment_id,'child_id':proof['child_id'],
            'command_hash':proof['command_hash'],'source_binding':proof['source_binding'],
            'dry_run':True,'model_executed':False},ident)
        claim=await db.get(GoalEvent,proof['claim_id'])
        return {'command':claim.data['command'],'deadline_unix_ms':proof['deadline_unix_ms']}


@activity.defn(name='p63_trial_consume_grant')
async def consume_trial_activity(data:dict):
    info=activity.info();c=settings()
    if (info.workflow_type!='PaoGrantChildTrialWorkflow' or
            info.workflow_namespace!=c.temporal_namespace or
            info.task_queue!=c.workflow_temporal_task_queue):
        invalid('goal_grant_trial_origin_invalid')
    return await consume_first_grant(data,'p63-'+data['envelope']['execution_id'],experiment_id=info.workflow_id)


@activity.defn(name='p63_issue_first_grant')
async def issue_first_grant_activity(data:dict):
    return await issue_first_grant(data,iterations.workflow_origin())
