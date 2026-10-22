"""P6.2A deterministic dry-run kernel; deliberately NOT registered in live workers.

No PAO DB/config/provider imports. Production admission, DB projection and ARQ
activities are separate checkpoints; signals here are not an authorization API.
"""
import asyncio
from datetime import timedelta
from uuid import UUID
from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError,ApplicationError


def validate_command(value: dict) -> None:
    """Strict bounded internal envelope; no arbitrary activity names or code."""
    if not isinstance(value,dict) or set(value)!={'format','plan_id','snapshot_hash','steps','timeout_seconds'}:
        raise ValueError('p62_command_invalid')
    if value['format']!='p62-dryrun-v1':raise ValueError('p62_dryrun_only')
    UUID(value['plan_id'])
    digest=value['snapshot_hash']
    if not isinstance(digest,str) or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):
        raise ValueError('p62_hash_invalid')
    if type(value['timeout_seconds']) is not int or not 1<=value['timeout_seconds']<=86400:
        raise ValueError('p62_deadline_invalid')
    steps=value['steps']
    if not isinstance(steps,list) or not 1<=len(steps)<=32:raise ValueError('p62_steps_invalid')
    seen=set();executions=set()
    for step in steps:
        if not isinstance(step,dict) or set(step)!={'step_id','execution_id','depends_on','approval_required','delay_seconds'}:
            raise ValueError('p62_step_invalid')
        key=step['step_id']
        if not isinstance(key,str) or not 1<=len(key)<=60 or not key.replace('_','').replace('-','').isalnum() or key in seen:
            raise ValueError('p62_step_id_invalid')
        execution=str(UUID(step['execution_id']))
        if execution in executions:raise ValueError('p62_execution_duplicate')
        deps=step['depends_on']
        if not isinstance(deps,list) or not all(isinstance(d,str) for d in deps) or len(set(deps))!=len(deps) or not set(deps)<=seen:
            raise ValueError('p62_dependencies_invalid')
        if type(step['approval_required']) is not bool or type(step['delay_seconds']) is not int or not 0<=step['delay_seconds']<=86400:
            raise ValueError('p62_wait_invalid')
        seen.add(key);executions.add(execution)


@workflow.defn
class PaoPlannedDryRunWorkflow:
    def __init__(self):
        self.cancelled=False
        self.status='starting'
        self.current_step=None
        self.completed=[]
        self.decisions={}
        self.sequence=0
        self.permission_denied=False

    @workflow.signal
    def decide(self,data:dict) -> None:
        # Only the current pending step can receive a first decision. API auth,
        # membership and version checks MUST precede dispatch in P6.2B.
        if not isinstance(data,dict) or set(data)!={'step_id','decision','decision_id'}:return
        if self.status!='waiting_approval' or data['step_id']!=self.current_step:return
        if data['decision'] not in ('approve','reject'):return
        try:UUID(data['decision_id'])
        except (ValueError,TypeError,AttributeError):return
        self.decisions.setdefault(self.current_step,data['decision'])

    @workflow.signal
    def request_cancel(self) -> None:
        self.cancelled=True

    @workflow.query
    def state(self) -> dict:
        return {'status':self.status,'current_step':self.current_step,
                'completed_steps':list(self.completed),'cancel_requested':self.cancelled,'sequence':self.sequence}

    async def project(self,item:dict,status:str,reason:str|None=None) -> dict:
        self.status=status;self.sequence+=1
        result={**self.state(),'plan_id':item['plan_id'],'snapshot_hash':item['snapshot_hash'],
                'reason':reason,'dry_run':True}
        # Projection is an idempotent upsert by (plan_id, sequence). No step
        # side effect belongs in this retryable activity.
        receipt=await workflow.execute_activity('p62_project',result,
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=3))
        if isinstance(receipt,dict):
            self.cancelled=self.cancelled or receipt.get('cancel_requested',False)
            self.permission_denied=receipt.get('allow_next_step') is False and not self.cancelled
        return result

    @workflow.run
    async def run(self,item:dict) -> dict:
        try:validate_command(item)
        except (ValueError,TypeError,AttributeError) as exc:
            raise ApplicationError(str(exc),type='P62InvalidCommand',non_retryable=True)
        deadline=workflow.now()+timedelta(seconds=item['timeout_seconds'])
        for step in item['steps']:
            self.current_step=step['step_id']
            if self.cancelled:return await self.project(item,'cancelled','requested')
            if workflow.now()>=deadline:return await self.project(item,'cancelled','deadline')
            if step['approval_required']:
                await self.project(item,'waiting_approval')
                if self.permission_denied:return await self.project(item,'manual_review','permission_lost')
                try:
                    await workflow.wait_condition(lambda:self.cancelled or self.current_step in self.decisions,
                        timeout=deadline-workflow.now())
                except TimeoutError:return await self.project(item,'cancelled','approval_timeout')
                if self.cancelled:return await self.project(item,'cancelled','requested')
                if self.decisions[self.current_step]=='reject':return await self.project(item,'cancelled','rejected')
            if step['delay_seconds']:
                await self.project(item,'waiting_timer')
                remaining=(deadline-workflow.now()).total_seconds()
                if remaining<=0:return await self.project(item,'cancelled','deadline')
                wait=min(step['delay_seconds'],remaining)
                try:await workflow.wait_condition(lambda:self.cancelled,timeout=timedelta(seconds=wait))
                except TimeoutError:pass
                if self.cancelled:return await self.project(item,'cancelled','requested')
                if workflow.now()>=deadline:return await self.project(item,'cancelled','deadline')
            await self.project(item,'running')
            if self.cancelled:return await self.project(item,'cancelled','requested')
            if self.permission_denied:return await self.project(item,'manual_review','permission_lost')
            # Fixed activity name, no automatic retry of uncertain execution.
            # A durable ARQ bridge/evidence validation is NOT provided here.
            remaining=(deadline-workflow.now()).total_seconds()
            if remaining<=0:return await self.project(item,'cancelled','deadline')
            task=workflow.start_activity('p62_dryrun_step',{'plan_id':item['plan_id'],**step},
                activity_id=step['execution_id'],start_to_close_timeout=timedelta(seconds=min(30,remaining)),
                heartbeat_timeout=timedelta(seconds=5),
                cancellation_type=workflow.ActivityCancellationType.WAIT_CANCELLATION_COMPLETED,
                retry_policy=RetryPolicy(maximum_attempts=1))
            cancelled=asyncio.create_task(workflow.wait_condition(lambda:self.cancelled))
            done,_=await workflow.wait([task,cancelled],return_when=asyncio.FIRST_COMPLETED)
            if cancelled in done:
                task.cancel()
                try:await task
                except (asyncio.CancelledError,ActivityError):pass
                return await self.project(item,'cancelled','requested_during_step')
            cancelled.cancel()
            try:result=await task
            except ActivityError:return await self.project(item,'manual_review','activity_uncertain')
            if result!={'execution_id':step['execution_id'],'status':'completed','dry_run':True}:
                return await self.project(item,'manual_review','unverified_step_receipt')
            self.completed.append(self.current_step)
            await self.project(item,'step_completed')
        self.current_step=None
        return await self.project(item,'completed')
