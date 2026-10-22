"""P6.2B DB boundary. Dry-run only; dispatch not registered in live cron."""
from datetime import timedelta
from uuid import UUID,uuid4,uuid5
from typing import Literal
from fastapi import HTTPException
from pydantic import Field
from sqlalchemy import select,func,or_
from temporalio import activity
from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError,ApplicationError
from ...config import settings
from ...db import Session
from ...models import StudioExecution,StudioCommand,StudioEvent,StudioDefinition,Task,TaskDependency,Member,User,now
from ...auth import Principal
from ...access import membership
from .contracts import Closed,digest
from .service import reject,version,lint
from .durable_workflow import PaoPlannedDryRunWorkflow,validate_command

TERMINAL={'completed','cancelled','manual_review'}
class DurableStart(Closed):
    request_key: str
    confirmation_hash: str=Field(pattern=r'^[a-f0-9]{64}$')
    timeout_seconds: int=Field(default=3600,ge=1,le=86400)
    delay_seconds: int=Field(default=0,ge=0,le=86400)

class DurableDecision(Closed):
    request_key: str
    version: int=Field(ge=1)
    step_id: str=Field(min_length=1,max_length=60)
    decision: Literal['approve','reject']

class DurableCancel(Closed):
    request_key: str

def request_uuid(value):
    try:return str(UUID(value))
    except (ValueError,TypeError,AttributeError):reject('durable_request_key_invalid')

def require_admission():
    if not all((settings().studio_enabled,settings().workflow_planning_enabled,
                settings().workflow_durable_enabled,settings().temporal_enabled)):
        reject('durable_admission_disabled',503)

def view(row):
    return {'execution_id':row.id,'plan_id':row.plan_id,'workspace_id':row.workspace_id,
            'status':row.status,'version':row.version,'sequence':row.sequence,'state':row.state,
            'cancel_requested':row.cancel_requested,'snapshot_hash':row.snapshot_hash,'dry_run':True,
            'model_calls':False,'task_attempts_created':False}

async def lock_execution(db,ident):
    row=await db.scalar(select(StudioExecution).where(StudioExecution.id==str(ident)).with_for_update().execution_options(populate_existing=True))
    if not row:reject('durable_execution_not_found',404)
    return row

async def execution_view(db,row):
    from ...models import TaskAttempt
    value=view(row)
    value['task_attempts_created']=bool(await db.scalar(select(TaskAttempt.id).where(
        TaskAttempt.workspace_id==row.workspace_id,
        TaskAttempt.id.in_([s['execution_id'] for s in row.command['steps']])).limit(1)))
    return value

async def authorize(db,row,who):
    member=await membership(db,row.workspace_id,who,True)
    user=await db.get(User,who.id)
    if not user or not user.active or member.role not in ('owner','admin'):reject('durable_owner_required',403)
    return member

async def verify_plan(db,plan,actor):
    if not plan or plan.action!='p61_plan_created':reject('durable_plan_not_found',404)
    definition=await db.get(StudioDefinition,plan.definition_id)
    await authorize(db,plan,Principal(actor,0))
    snapshot=plan.data['snapshot']
    if snapshot['sha256']!=digest({k:v for k,v in snapshot.items() if k!='sha256'}) or snapshot['input_hash']!=digest(snapshot['input']):
        reject('durable_snapshot_invalid',409)
    if snapshot['actor_id']!=actor or plan.actor_id!=actor or snapshot['workspace_id']!=plan.workspace_id or snapshot['workflow']['definition_id']!=definition.id:
        reject('durable_plan_actor_scope',403)
    workflow=await version(db,snapshot['workflow']['version_id'],plan.workspace_id,'workflows')
    if workflow.definition_id!=definition.id or workflow.content_hash!=snapshot['workflow']['hash']:reject('durable_workflow_pin_invalid',409)
    await lint(db,definition,workflow.payload,actor)
    if len(snapshot['steps'])!=len(plan.data['steps']):reject('durable_step_mapping_invalid',409)
    for step,mapping in zip(snapshot['steps'],plan.data['steps']):
        ident=str(uuid5(UUID(plan.id),step['step_id']))
        if mapping!={'step_id':step['step_id'],'task_id':ident,'execution_id':ident}:reject('durable_step_mapping_invalid',409)
        task=await db.get(Task,ident)
        if not task or task.workspace_id!=plan.workspace_id or task.status!='draft' or task.run_id:
            reject('durable_task_invalid',409)
        deps=set(await db.scalars(select(TaskDependency.depends_on_task_id).where(TaskDependency.task_id==ident,TaskDependency.workspace_id==plan.workspace_id)))
        if deps!={str(uuid5(UUID(plan.id),key)) for key in step['depends_on']}:reject('durable_dependencies_invalid',409)
        for kind in ('skill','agent'):
            pin=step[kind];row=await version(db,pin['version_id'],plan.workspace_id,kind+'s')
            if row.content_hash!=pin['hash'] or digest(pin['payload'])!=pin['hash']:reject('durable_pin_invalid',409)
    if plan.data['task_ids']!=[s['task_id'] for s in plan.data['steps']]:reject('durable_task_mapping_invalid',409)
    return snapshot

async def audit(db,row,actor,action,data):
    plan=await db.get(StudioEvent,row.plan_id)
    db.add(StudioEvent(workspace_id=row.workspace_id,definition_id=row.definition_id,version_id=plan.version_id,
                       actor_id=actor,action=action,data={'execution_id':row.id,**data}))

async def command(db,row,actor,key,operation,payload):
    key=request_uuid(key);ident=str(uuid5(UUID(row.id),key));fingerprint=digest({'operation':operation,'payload':payload,'actor_id':actor})
    existing=await db.get(StudioCommand,ident)
    if existing:
        if existing.content_hash!=fingerprint:reject('durable_request_conflict',409)
        return existing,True
    ordinal=(await db.scalar(select(func.max(StudioCommand.ordinal)).where(StudioCommand.execution_id==row.id)) or 0)+1
    item=StudioCommand(id=ident,execution_id=row.id,workspace_id=row.workspace_id,actor_id=actor,request_key=key,
        ordinal=ordinal,operation=operation,payload=payload,content_hash=fingerprint)
    db.add(item);await audit(db,row,actor,'p62_command',{'command_id':ident,'operation':operation,'ordinal':ordinal})
    await db.flush();return item,False

async def admit(db,plan_id,who,body):
    require_admission();request_uuid(body.request_key)
    plan=await db.get(StudioEvent,str(plan_id))
    if not plan or plan.action!='p61_plan_created':reject('durable_plan_not_found',404)
    # Serializes starts of the same plan across transactions.
    await db.scalar(select(StudioDefinition).where(StudioDefinition.id==plan.definition_id).with_for_update())
    await authorize(db,plan,who)
    from ...models import GoalExecution,GoalEvent
    if await db.scalar(select(GoalExecution.id).where(GoalExecution.initial_plan_id==plan.id)):
        reject('durable_plan_owned_by_goal',409)
    if await db.get(GoalEvent,str(uuid5(UUID(plan.id),'p63-plan-owner'))):
        reject('durable_plan_owned_by_goal',409)
    existing=await db.get(StudioExecution,plan.id)
    if existing:
        payload={'confirmation_hash':body.confirmation_hash,'timeout_seconds':body.timeout_seconds,'delay_seconds':body.delay_seconds}
        item=await db.get(StudioCommand,str(uuid5(UUID(existing.id),request_uuid(body.request_key))))
        if not item or item.operation!='start' or item.content_hash!=digest({'operation':'start','payload':payload,'actor_id':who.id}):reject('durable_plan_already_started',409)
        return existing
    snapshot=await verify_plan(db,plan,who.id)
    if snapshot['sha256']!=body.confirmation_hash:reject('durable_confirmation_stale',409)
    envelope={'format':'p62-dryrun-v1','plan_id':plan.id,'snapshot_hash':snapshot['sha256'],
        'timeout_seconds':body.timeout_seconds,'steps':[{'step_id':s['step_id'],'execution_id':m['execution_id'],
            'depends_on':s['depends_on'],'approval_required':True,'delay_seconds':body.delay_seconds}
            for s,m in zip(snapshot['steps'],plan.data['steps'])]}
    try:validate_command(envelope)
    except ValueError:reject('durable_envelope_invalid')
    row=StudioExecution(id=plan.id,workspace_id=plan.workspace_id,definition_id=plan.definition_id,plan_id=plan.id,
        actor_id=who.id,temporal_id='p62-'+plan.id,snapshot_hash=snapshot['sha256'],command=envelope)
    db.add(row);await db.flush()
    await command(db,row,who.id,body.request_key,'start',{'confirmation_hash':body.confirmation_hash,
        'timeout_seconds':body.timeout_seconds,'delay_seconds':body.delay_seconds})
    return row

async def decide(db,row,who,body):
    await authorize(db,row,who);require_admission()
    payload={'version':body.version,'step_id':body.step_id,'decision':body.decision}
    ident=str(uuid5(UUID(row.id),request_uuid(body.request_key)))
    existing=await db.get(StudioCommand,ident)
    if existing:
        if existing.content_hash!=digest({'operation':'decision','payload':payload,'actor_id':who.id}):reject('durable_request_conflict',409)
        return row
    if row.version!=body.version or row.status!='waiting_approval' or row.state.get('current_step')!=body.step_id or row.cancel_requested:
        reject('durable_decision_stale',409)
    # Same pending step cannot accept a competing decision at a later version.
    prior=list(await db.scalars(select(StudioCommand).where(StudioCommand.execution_id==row.id,StudioCommand.operation=='decision')))
    if any(p.payload['step_id']==body.step_id for p in prior):reject('durable_step_already_decided',409)
    await verify_plan(db,await db.get(StudioEvent,row.plan_id),row.actor_id)
    await command(db,row,who.id,body.request_key,'decision',payload);row.version+=1;row.updated_at=now()
    return row

async def cancel(db,row,who,body):
    await authorize(db,row,who)  # admission flag deliberately not required
    item,replay=await command(db,row,who.id,body.request_key,'cancel',{})
    if replay:return row
    if row.status in TERMINAL:
        item.status='delivered';item.delivered_at=now();return row
    row.cancel_requested=True;row.version+=1;row.updated_at=now()
    start=await db.scalar(select(StudioCommand).where(StudioCommand.execution_id==row.id,StudioCommand.operation=='start').with_for_update())
    if start.status=='pending' and start.attempts==0:
        start.status='dead';start.error_code='cancelled_before_dispatch'
        item.status='delivered';item.delivered_at=now();row.status='cancelled'
        row.state={'reason':'cancelled_before_dispatch','dry_run':True}
    return row

@activity.defn(name='p62_project')
async def project_state(data:dict):
    async with Session.begin() as db:
        row=await lock_execution(db,data['plan_id'])
        if data.get('snapshot_hash')!=row.snapshot_hash or data.get('dry_run') is not True:raise ApplicationError('projection_scope',non_retryable=True)
        sequence=data.get('sequence')
        if type(sequence) is not int or sequence<1:raise ApplicationError('projection_sequence',non_retryable=True)
        event_id=str(uuid5(UUID(row.id),'projection:'+str(sequence)))
        prior=await db.get(StudioEvent,event_id)
        if prior:
            if prior.data['state']!=data:raise ApplicationError('projection_conflict',non_retryable=True)
            permitted=prior.data['receipt']['allow_next_step']
            try:await verify_plan(db,await db.get(StudioEvent,row.plan_id),row.actor_id)
            except HTTPException:permitted=False
            return {'allow_next_step':permitted and settings().workflow_durable_enabled and not row.cancel_requested,
                    'cancel_requested':row.cancel_requested}
        if row.status in TERMINAL or sequence<=row.sequence:
            return {'allow_next_step':False,'cancel_requested':row.cancel_requested}
        if sequence!=row.sequence+1:raise ApplicationError('projection_gap',non_retryable=True)
        command_steps={s['step_id'] for s in row.command['steps']}
        current=data.get('current_step');completed=data.get('completed_steps')
        if current is not None and current not in command_steps:raise ApplicationError('projection_step',non_retryable=True)
        if not isinstance(completed,list) or len(set(completed))!=len(completed) or not set(completed)<=command_steps:raise ApplicationError('projection_completed',non_retryable=True)
        ordered=[s['step_id'] for s in row.command['steps']]
        if completed!=ordered[:len(completed)]:raise ApplicationError('projection_order',non_retryable=True)
        status=data.get('status')
        if status not in {'waiting_approval','waiting_timer','running','step_completed'}|TERMINAL:raise ApplicationError('projection_status',non_retryable=True)
        if status=='completed' and (completed!=ordered or current is not None):raise ApplicationError('projection_incomplete',non_retryable=True)
        if status=='step_completed' and (not completed or current!=completed[-1]):raise ApplicationError('projection_receipt_step',non_retryable=True)
        if status in ('waiting_approval','waiting_timer','running') and (len(completed)>=len(ordered) or current!=ordered[len(completed)]):raise ApplicationError('projection_next_step',non_retryable=True)
        permitted=True
        try:await verify_plan(db,await db.get(StudioEvent,row.plan_id),row.actor_id)
        except HTTPException:permitted=False
        receipt={'allow_next_step':permitted and settings().workflow_durable_enabled and not row.cancel_requested,'cancel_requested':row.cancel_requested}
        row.sequence=sequence;row.state=data;row.status=status;row.version+=1;row.updated_at=now()
        plan=await db.get(StudioEvent,row.plan_id)
        db.add(StudioEvent(id=event_id,workspace_id=row.workspace_id,definition_id=row.definition_id,
            version_id=plan.version_id,actor_id=row.actor_id,action='p62_projection',data={'state':data,'receipt':receipt}))
        return receipt

async def authorize_step(plan_id,step_id,execution_id):
    """Must be called by the future ARQ bridge immediately before claiming work."""
    async with Session.begin() as db:
        row=await lock_execution(db,plan_id)
        require_admission()
        if row.cancel_requested or row.status!='running' or row.state.get('current_step')!=step_id:reject('durable_step_not_running',409)
        await verify_plan(db,await db.get(StudioEvent,row.plan_id),row.actor_id)
        if not any(s['step_id']==step_id and s['execution_id']==execution_id for s in row.command['steps']):reject('durable_step_scope',404)
        return {'authorized':True,'dry_run':True}

class Gateway:
    client=None
    async def connect(self):
        if self.client is None:self.client=await Client.connect(settings().temporal_address,namespace=settings().temporal_namespace)
        return self.client
    async def deliver(self,row,item):
        client=await self.connect()
        if item.operation=='start':
            try:await client.start_workflow(PaoPlannedDryRunWorkflow.run,row.command,id=row.temporal_id,
                task_queue=settings().workflow_temporal_task_queue,id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
                execution_timeout=timedelta(seconds=row.command['timeout_seconds']+120))
            except WorkflowAlreadyStartedError:pass
        else:
            handle=client.get_workflow_handle(row.temporal_id)
            if item.operation=='cancel':await handle.signal(PaoPlannedDryRunWorkflow.request_cancel)
            else:await handle.signal(PaoPlannedDryRunWorkflow.decide,{'step_id':item.payload['step_id'],
                'decision':item.payload['decision'],'decision_id':item.id})

gateway=Gateway()

async def dispatch_commands() -> int:
    """Explicit dispatcher only: leased, ordered, after-commit delivery."""
    async with Session() as db:
        ids=list(await db.scalars(select(StudioCommand.id).where(StudioCommand.status.in_(['pending','processing']),
            StudioCommand.available_at<=now(),or_(StudioCommand.lease_until.is_(None),StudioCommand.lease_until<now())).order_by(StudioCommand.created_at).limit(50)))
    delivered=0
    for ident in ids:
        async with Session.begin() as db:
            lookup=await db.get(StudioCommand,ident)
            row=await lock_execution(db,lookup.execution_id)
            item=await db.scalar(select(StudioCommand).where(StudioCommand.id==ident).with_for_update().execution_options(populate_existing=True))
            if item.status not in ('pending','processing') or item.available_at>now() or (item.lease_until and item.lease_until>now()):continue
            earlier=await db.scalar(select(StudioCommand.id).where(StudioCommand.execution_id==row.id,StudioCommand.ordinal<item.ordinal,StudioCommand.status.in_(['pending','processing'])).limit(1))
            if earlier:continue
            if item.attempts>=8:
                item.status='dead';item.error_code='delivery_exhausted'
                if row.status not in TERMINAL:
                    row.status='manual_review';row.version+=1;row.updated_at=now()
                continue
            if item.operation!='cancel':
                if not all((settings().workflow_dispatch_enabled,settings().workflow_durable_enabled,
                            settings().studio_enabled,settings().workflow_planning_enabled,settings().temporal_enabled)):continue
                try:
                    await verify_plan(db,await db.get(StudioEvent,row.plan_id),row.actor_id)
                    await authorize(db,row,Principal(item.actor_id,0))
                except HTTPException:
                    item.status='dead';item.error_code='permission_lost'
                    if item.operation=='start' and item.attempts==0:
                        row.status='manual_review';row.version+=1;row.updated_at=now()
                    continue
                if row.cancel_requested or row.status in TERMINAL:
                    item.status='dead';item.error_code='execution_stopped';continue
            token=str(uuid4());item.status='processing';item.attempts+=1;item.lease_token=token;item.lease_until=now()+timedelta(seconds=30)
        # Never hold DB locks while waiting on Temporal network.
        error=None
        try:await gateway.deliver(row,item)
        except Exception as exc:error=type(exc).__name__[:64]
        async with Session.begin() as db:
            row=await lock_execution(db,row.id)
            saved=await db.scalar(select(StudioCommand).where(StudioCommand.id==ident).with_for_update())
            if saved.lease_token!=token or saved.status!='processing':continue
            saved.lease_token=None;saved.lease_until=None
            if error:
                saved.status='dead' if saved.attempts>=8 else 'pending';saved.error_code=error
                saved.available_at=now()+timedelta(seconds=min(60,2**saved.attempts))
                if saved.status=='dead' and row.status not in TERMINAL:
                    row.status='manual_review';row.version+=1;row.updated_at=now()
            else:
                saved.status='delivered';saved.delivered_at=now();saved.error_code=None;delivered+=1
    return delivered
