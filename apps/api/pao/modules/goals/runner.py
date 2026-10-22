"""Versioned DB-owned dry-run Goal runner. Legacy projection denials stay intact.

Temporal owns waits/children; PostgreSQL owns approval, budget and provenance.
Every reducer mutation is replayed from immutable, sequential transition events.
No model output, browser signal or transport ACK is accepted as a receipt.
"""
from datetime import timedelta
from uuid import UUID, uuid5
from fastapi import HTTPException
from sqlalchemy import select
from temporalio import activity
from ...auth import Principal
from ...config import settings
from ...db import Session
from ...models import GoalEvent,GoalCommand,StudioEvent,StudioExecution,StudioDefinition,StudioCommand,TaskAttempt,now
from ...skills import execution_binding
from ..studio import durable,step_jobs as jobs,queue_cancel
from ..studio.contracts import digest
from ..studio.durable_workflow import validate_command
from .control import GoalControl,TERMINAL
from .evidence import verify_admission
from . import ledger,iterations
from .projection import invalid

PROFILE='p63-runner-v1'


def event_id(row,key):return str(uuid5(UUID(row.id),'runner:'+key))


def enabled():
    c=settings()
    return all((c.goal_runner_enabled,c.goal_iterations_enabled,c.goal_admission_enabled,
        c.studio_enabled,c.workflow_planning_enabled,c.workflow_durable_enabled,c.temporal_enabled,
        c.workflow_worker_enabled,c.workflow_dispatch_enabled))


async def bound(db,row):
    marker=await db.get(GoalEvent,event_id(row,'bound'))
    if not marker:invalid('goal_runner_not_bound')
    iterations.verify_event(marker,row,'runner_bound',{'profile':PROFILE})
    return marker


def apply(control,operation,value,stamp):
    if operation=='propose':control.propose(value,stamp)
    elif operation=='decide':control.decide(value['proposal_hash'],value['decision'],stamp)
    elif operation=='finish':control.finish(value,stamp)
    elif operation=='cancel':control.cancel(stamp)
    elif operation=='advance':control.advance(stamp)
    elif operation=='uncertain':control.uncertain(stamp)
    elif operation=='drained':control.drained(value,stamp)
    else:invalid('goal_runner_transition_unknown')


async def reconstruct(db,row):
    await bound(db,row)
    events=list(await db.scalars(select(GoalEvent).where(GoalEvent.execution_id==row.id,
        GoalEvent.action=='runner_transition')))
    events.sort(key=lambda e:e.data.get('sequence',-1))
    if not events:return None
    first=events[0].data
    control=GoalControl(row.envelope,first['started_ms'])
    for sequence,event in enumerate(events,1):
        data=event.data
        iterations.verify_event(event,row,'runner_transition',data)
        if (event.id!=event_id(row,'transition:'+str(sequence)) or data['sequence']!=sequence or
                data['started_ms']!=first['started_ms']):invalid('goal_runner_journal_gap')
        apply(control,data['operation'],data['input'],data['stamp_ms'])
        if digest(control.snapshot())!=digest(data['state']):invalid('goal_runner_journal_invalid')
    if row.sequence!=len(events) or digest(row.state)!=digest(control.snapshot()):invalid('goal_runner_projection_changed')
    if row.status!=row.state['status'] or row.reserved_cost_microusd!=row.state['reserved_cost_microusd']:
        invalid('goal_runner_budget_changed')
    return control


async def transition(db,row,control,operation,value,stamp,*,proof=None,started_ms=None):
    old=control.snapshot();apply(control,operation,value,stamp);state=control.snapshot()
    if state==old and row.sequence:return state
    first=await db.get(GoalEvent,event_id(row,'transition:1'))
    sequence=row.sequence+1
    data={'sequence':sequence,'started_ms':first.data['started_ms'] if first else started_ms,
        'operation':operation,'input':value,'stamp_ms':stamp,'state':state,'proof':proof}
    await ledger.audit(db,row,row.actor_id,'runner_transition',data,event_id(row,'transition:'+str(sequence)))
    row.state=state;row.status=state['status'];row.sequence=sequence;row.version+=1
    row.reserved_cost_microusd=state['reserved_cost_microusd'];row.updated_at=now()
    await db.flush()
    return state


async def verify_command(db,row,item):
    if item.operation not in ('start','decision','proposal','cancel'):invalid('goal_runner_command_operation')
    if (item.execution_id!=row.id or item.workspace_id!=row.workspace_id or
        item.id!=str(uuid5(UUID(row.id),item.request_key)) or
        item.content_hash!=digest({'operation':item.operation,'payload':item.payload,'actor_id':item.actor_id})):
        invalid('goal_runner_command_invalid')
    audit=await db.get(GoalEvent,str(uuid5(UUID(item.id),'audit')))
    value={'command_id':item.id,'operation':item.operation,'ordinal':item.ordinal}
    if (not audit or audit.actor_id!=item.actor_id or audit.execution_id!=row.id or
        audit.workspace_id!=row.workspace_id or audit.action!='command' or audit.data!=value or
        audit.content_hash!=digest({'action':'command','data':value,'actor_id':item.actor_id})):
        invalid('goal_runner_command_audit_invalid')


async def plan(db,row,proposal):
    item=await db.get(StudioEvent,proposal['plan_id'])
    if not item or item.workspace_id!=row.workspace_id:invalid('goal_runner_plan_scope')
    await db.scalar(select(StudioDefinition).where(StudioDefinition.id==item.definition_id).with_for_update())
    snapshot=await durable.verify_plan(db,item,row.actor_id)
    if snapshot['sha256']!=proposal['snapshot_hash']:invalid('goal_runner_plan_pin_changed')
    return item,snapshot


async def approval(db,row,state):
    candidates=list(await db.scalars(select(GoalCommand).where(GoalCommand.execution_id==row.id,
        GoalCommand.operation=='decision',GoalCommand.payload['proposal_hash'].as_string()==state['proposal_hash'])))
    if len(candidates)!=1:invalid('goal_runner_approval_missing')
    item=candidates[0]
    await verify_command(db,row,item)
    if (item.payload.get('decision')!='approve' or item.status not in ('processing','delivered') or item.attempts<1):
        invalid('goal_runner_approval_invalid')
    await durable.authorize(db,row,Principal(item.actor_id,0))
    used=await db.get(GoalEvent,event_id(row,'command:'+item.id))
    iterations.verify_event(used,row,'runner_command_applied',{'command_id':item.id})
    return item


async def poll(execution_id,workflow_id):
    async with Session.begin() as db:
        row=await ledger.lock_execution(db,execution_id)
        if workflow_id!=row.temporal_id:invalid('goal_runner_origin')
        ctl=await reconstruct(db,row);stamp=int(now().timestamp()*1000)
        start=await db.scalar(select(GoalCommand).where(GoalCommand.execution_id==row.id,GoalCommand.operation=='start'))
        await verify_command(db,row,start)
        if start.attempts<1 or start.status not in ('processing','delivered'):invalid('goal_runner_start_not_dispatched')
        permitted=True
        try:
            await verify_admission(db,row)
            if not enabled():permitted=False
        except HTTPException:permitted=False
        if ctl is None:
            ctl=GoalControl(row.envelope,stamp)
            await transition(db,row,ctl,'propose',row.initial_proposal,stamp,started_ms=stamp)
        if row.cancel_requested:
            await transition(db,row,ctl,'cancel',None,stamp)
        elif not permitted and row.status not in TERMINAL:
            await transition(db,row,ctl,'uncertain',None,stamp)
        else:await transition(db,row,ctl,'advance',None,stamp)
        if row.status in ('waiting_approval','waiting_replan'):
            operation='decision' if row.status=='waiting_approval' else 'proposal'
            commands=list(await db.scalars(select(GoalCommand).where(GoalCommand.execution_id==row.id,
                GoalCommand.operation==operation,GoalCommand.status.in_(['processing','delivered']),
                GoalCommand.attempts>=1).order_by(GoalCommand.ordinal)))
            for item in commands:
                used=await db.get(GoalEvent,event_id(row,'command:'+item.id))
                if used:continue
                await verify_command(db,row,item)
                await durable.authorize(db,row,Principal(item.actor_id,0))
                value={k:item.payload[k] for k in ('proposal_hash','decision')} if operation=='decision' else item.payload['proposal']
                if operation=='decision' and value['proposal_hash']!=row.state['proposal_hash']:continue
                if operation=='proposal':await plan(db,row,value)
                await transition(db,row,ctl,'decide' if operation=='decision' else 'propose',value,stamp,
                    proof={'command_id':item.id})
                await ledger.audit(db,row,row.actor_id,'runner_command_applied',{'command_id':item.id},event_id(row,'command:'+item.id))
                break
        return {'state':row.state,'version':row.version,'stop_child':row.cancel_requested or not permitted or row.status in TERMINAL}


async def launch(execution_id,workflow_id,run_id,iteration):
    async with Session.begin() as db:
        row=await ledger.lock_execution(db,execution_id);ctl=await reconstruct(db,row)
        if workflow_id!=row.temporal_id or not enabled():invalid('goal_runner_launch_disabled')
        await verify_admission(db,row)
        state=ctl.snapshot();stamp=int(now().timestamp()*1000)
        if (row.cancel_requested or state['status']!='running' or state['iteration']!=iteration or
            stamp+state['proposal']['max_duration_seconds']*1000>state['deadline_unix_ms']):invalid('goal_runner_launch_stale')
        decision=await approval(db,row,state)
        marker=await db.get(GoalEvent,event_id(row,'launch:'+str(iteration)))
        if marker:
            iterations.verify_event(marker,row,'runner_launch',marker.data)
            if marker.data['run_id']!=run_id or marker.data['source_binding']!=execution_binding()['sha256']:
                invalid('goal_runner_launch_owner_changed')
            return marker.data['command']
        proposal=state['proposal'];item,snapshot=await plan(db,row,proposal)
        if await db.get(StudioExecution,item.id):invalid('goal_runner_plan_already_used')
        owner=await db.get(GoalEvent,iterations.claim_id(item.id))
        if owner:
            iterations.verify_event(owner,row,'runner_plan_reserved',{'plan_id':item.id})
        command={'format':'p62-dryrun-v1','plan_id':item.id,'snapshot_hash':snapshot['sha256'],
            'timeout_seconds':proposal['max_duration_seconds'],'steps':[
                {'step_id':s['step_id'],'execution_id':m['execution_id'],'depends_on':s['depends_on'],
                'approval_required':True,'delay_seconds':0} for s,m in zip(snapshot['steps'],item.data['steps'])]}
        validate_command(command)
        child=StudioExecution(id=item.id,workspace_id=row.workspace_id,definition_id=item.definition_id,
            plan_id=item.id,actor_id=row.actor_id,temporal_id='p62-'+item.id,snapshot_hash=snapshot['sha256'],command=command)
        db.add(child);await db.flush()
        key=str(uuid5(UUID(row.id),'runner-child:'+str(iteration)))
        start,_=await durable.command(db,child,row.actor_id,key,'start',{'confirmation_hash':snapshot['sha256'],
            'timeout_seconds':command['timeout_seconds'],'delay_seconds':0})
        start.status='dead';start.error_code='goal_parent_owned_start'
        proof={'iteration':iteration,'plan_id':item.id,'state':state,'command':command,'command_hash':digest(command),
            'run_id':run_id,'source_binding':execution_binding()['sha256'],'start_id':start.id,'decision_id':decision.id}
        if not owner:await ledger.audit(db,row,row.actor_id,'runner_plan_owner',{'iteration':iteration},iterations.claim_id(item.id))
        await ledger.audit(db,row,row.actor_id,'runner_launch',proof,event_id(row,'launch:'+str(iteration)))
        return command


async def completed(db,row,claim):
    """Reuse the strict legacy receipt validator after verifying v1 runner claim.

    Its trusted core accepts an iteration number; no browser entry point exists.
    """
    return await iterations.verified_completed_child(db,row,claim.data['state'],claim)


async def finish(execution_id,workflow_id,iteration):
    async with Session.begin() as db:
        row=await ledger.lock_execution(db,execution_id);ctl=await reconstruct(db,row)
        if workflow_id!=row.temporal_id:invalid('goal_runner_origin')
        existing=await db.get(GoalEvent,event_id(row,'receipt:'+str(iteration)))
        if existing:
            iterations.verify_event(existing,row,'runner_receipt',existing.data)
            return row.state
        await verify_admission(db,row)
        claim=await db.get(GoalEvent,event_id(row,'launch:'+str(iteration)))
        if not claim:invalid('goal_runner_launch_missing')
        iterations.verify_event(claim,row,'runner_launch',claim.data)
        if claim.data['source_binding']!=execution_binding()['sha256']:invalid('goal_runner_receipt_binding_changed')
        decision=await approval(db,row,claim.data['state'])
        if decision.id!=claim.data['decision_id']:invalid('goal_runner_approval_changed')
        if row.state['iteration']!=iteration:invalid('goal_runner_iteration_stale')
        receipt=await completed(db,row,claim)
        if row.cancel_requested:await transition(db,row,ctl,'cancel',None,int(now().timestamp()*1000))
        await transition(db,row,ctl,'finish',receipt,int(now().timestamp()*1000),proof={'claim_id':claim.id})
        await ledger.audit(db,row,row.actor_id,'runner_receipt',{'receipt':receipt,'state':row.state},event_id(row,'receipt:'+str(iteration)))
        return row.state


async def request_child_stop(execution_id,workflow_id,iteration):
    """Persist a sticky child fence even on gate/permission rollback.

    The server-owned launch binds cancellation to exactly this child; the user
    does not gain launch authority through this safety-only operation.
    """
    async with Session.begin() as db:
        row=await ledger.lock_execution(db,execution_id);await reconstruct(db,row)
        if workflow_id!=row.temporal_id:invalid('goal_runner_origin')
        claim=await db.get(GoalEvent,event_id(row,'launch:'+str(iteration)))
        if not claim:invalid('goal_runner_launch_missing')
        iterations.verify_event(claim,row,'runner_launch',claim.data)
        child=await durable.lock_execution(db,claim.data['plan_id'])
        if digest(child.command)!=claim.data['command_hash'] or child.workspace_id!=row.workspace_id:
            invalid('goal_runner_child_changed')
        child.cancel_requested=True;child.version+=1;child.updated_at=now()
        command,_=await durable.command(db,child,row.actor_id,str(uuid5(UUID(row.id),'runner-stop:'+str(iteration))),'cancel',{})
        # The parent sends the child's custom cancel signal. No standalone start.
        return child.temporal_id


async def uncertain(execution_id,workflow_id):
    async with Session.begin() as db:
        row=await ledger.lock_execution(db,execution_id);ctl=await reconstruct(db,row)
        if workflow_id!=row.temporal_id:invalid('goal_runner_origin')
        if ctl:await transition(db,row,ctl,'uncertain',None,int(now().timestamp()*1000))
        return row.state


async def reconcile(execution_id,workflow_id,iteration,redis):
    # Abort/wait outside DB locks so the native worker can commit cancellation.
    async with Session.begin() as db:
        row=await ledger.lock_execution(db,execution_id);await reconstruct(db,row)
        if workflow_id!=row.temporal_id:invalid('goal_runner_origin')
        claim=await db.get(GoalEvent,event_id(row,'launch:'+str(iteration)))
        iterations.verify_event(claim,row,'runner_launch',claim.data if claim else {})
        child=await durable.lock_execution(db,claim.data['plan_id'])
        args=[]
        for s in child.command['steps']:
            outcome=await db.get(StudioEvent,jobs.event_id(s['execution_id'],'outcome'))
            if (not outcome or outcome.data.get('status')!='completed') and await db.get(StudioEvent,jobs.event_id(s['execution_id'],'reserved')):
                args.append((child.id,s['step_id'],s['execution_id']))
    for arg in args:
        try:await queue_cancel.cancel_queue_step(redis,*arg)
        except HTTPException:pass  # Revocation/unknown: retain ceiling, never invent ACK.
    async with Session.begin() as db:
        row=await ledger.lock_execution(db,execution_id);ctl=await reconstruct(db,row)
        if row.state['iteration']!=iteration:invalid('goal_runner_iteration_stale')
        child=await durable.lock_execution(db,claim.data['plan_id'])
        final=await db.get(StudioEvent,str(uuid5(UUID(child.id),'projection:'+str(child.sequence))))
        known=bool(final and final.action=='p62_projection' and final.workspace_id==row.workspace_id and
            final.actor_id==row.actor_id and final.definition_id==child.definition_id and
            final.data.get('state')==child.state and child.status=='cancelled' and child.cancel_requested and
            child.state.get('cancel_requested') and
            digest(child.command)==claim.data['command_hash'])
        proof_ids=[];completed_steps=child.state.get('completed_steps',[])
        if known:
            item=await db.get(StudioEvent,child.plan_id);snapshot=item.data['snapshot']
            if snapshot['sha256']!=digest({k:v for k,v in snapshot.items() if k!='sha256'}):known=False
            if completed_steps:
                try:
                    partial=await iterations.verified_completed_child(db,row,claim.data['state'],claim,completed_prefix=True)
                    proof_ids.extend(partial['outcome_ids'])
                except (HTTPException,ValueError,KeyError):known=False
                except Exception as exc:
                    from temporalio.exceptions import ApplicationError
                    if not isinstance(exc,ApplicationError):raise
                    known=False
            for s,m in zip(snapshot['steps'],item.data['steps']):
                if s['step_id'] in completed_steps:continue
                ident=m['execution_id'];reserved=await db.get(StudioEvent,jobs.event_id(ident,'reserved'))
                claimed=await db.get(StudioEvent,jobs.event_id(ident,'claimed'))
                attempt=await db.get(TaskAttempt,ident);outcome=await db.get(StudioEvent,jobs.event_id(ident,'outcome'))
                try:
                    if not reserved:
                        if claimed or attempt or outcome:known=False
                        continue
                    from .cancel_recovery import verify_cancelled_claim
                    if claimed:
                        await verify_cancelled_claim(db,row,child,item,snapshot,s,ident,reserved,claimed,outcome,attempt)
                    elif attempt:known=False
                    ack=await db.get(StudioEvent,queue_cancel.ack_id(ident))
                    await queue_cancel.verify_ack(db,child,item,(child.id,s['step_id'],ident),ack,redis.default_queue_name)
                    proof_ids.append(ack.id)
                except (HTTPException,ValueError,KeyError):known=False
                except Exception as exc:
                    from temporalio.exceptions import ApplicationError
                    if not isinstance(exc,ApplicationError):raise
                    known=False
        stamp=int(now().timestamp()*1000)
        if known:
            value={'execution_id':row.id,'iteration':iteration,'proposal_hash':row.state['proposal_hash'],'drained':True}
            await transition(db,row,ctl,'drained',value,stamp,proof={'projection_id':final.id,'queue_ack_ids':proof_ids})
        else:await transition(db,row,ctl,'uncertain',None,stamp)
        return row.state


class RunnerActivities:
    def __init__(self,redis):self.redis=redis

    @activity.defn(name='p63r_reconcile')
    async def reconcile(self,data:dict):
        info=origin();return await reconcile(data['execution_id'],info.workflow_id,data['iteration'],self.redis)


def origin():
    info=activity.info();c=settings()
    if (info.workflow_type!='PaoGoalRunnerWorkflow' or info.workflow_namespace!=c.temporal_namespace or
        info.task_queue!=c.workflow_temporal_task_queue):invalid('goal_runner_activity_origin')
    return info


@activity.defn(name='p63r_poll')
async def poll_activity(data:dict):
    info=origin();return await poll(data['execution_id'],info.workflow_id)


@activity.defn(name='p63r_launch')
async def launch_activity(data:dict):
    info=origin();return await launch(data['execution_id'],info.workflow_id,info.workflow_run_id,data['iteration'])


@activity.defn(name='p63r_finish')
async def finish_activity(data:dict):
    info=origin();return await finish(data['execution_id'],info.workflow_id,data['iteration'])


@activity.defn(name='p63r_stop')
async def stop_activity(data:dict):
    info=origin();return await request_child_stop(data['execution_id'],info.workflow_id,data['iteration'])


@activity.defn(name='p63r_uncertain')
async def uncertain_activity(data:dict):
    info=origin();return await uncertain(data['execution_id'],info.workflow_id)
