"""Browser-independent Goal waits; v1 type never changes legacy histories."""
import asyncio
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy,WorkflowIDReusePolicy
from temporalio.exceptions import ActivityError,ChildWorkflowError
from ..studio.durable_workflow import PaoPlannedDryRunWorkflow,validate_command


@workflow.defn
class PaoGoalRunnerWorkflow:
    def __init__(self):
        self.current={'status':'starting'};self.woken=False;self.child=None

    @workflow.signal
    def wake(self):self.woken=True  # Hint only; DB commands are authority.

    @workflow.query
    def state(self):return self.current

    async def call(self,name,data):
        return await workflow.execute_activity(name,data,start_to_close_timeout=timedelta(seconds=15),
            retry_policy=RetryPolicy(maximum_attempts=3))

    async def poll(self,data):
        value=await self.call('p63r_poll',data);self.current=value['state'];return value

    async def wait(self,seconds=1):
        # Approval/replan signals wake immediately. Long idle waits must not
        # manufacture one activity/timer per second over a 24h policy window.
        # Keep active-child revocation checks frequent and clamp idle timers to
        # the pinned deadline rather than delaying timeout by two minutes.
        remaining=max(.05,self.current['deadline_unix_ms']/1000-workflow.now().timestamp())
        try:await workflow.wait_condition(lambda:self.woken,timeout=timedelta(seconds=min(seconds,remaining)))
        except TimeoutError:pass
        self.woken=False

    async def stop(self,data,child):
        await self.call('p63r_stop',data)
        await child.signal('request_cancel')
        try:return await asyncio.wait_for(asyncio.shield(child),40)
        except (TimeoutError,ChildWorkflowError):return None

    @workflow.run
    async def run(self,data:dict):
        self.child=None
        try:
            while True:
                value=await self.poll(data)
                if self.current['status'] in ('completed','cancelled','budget_exhausted','deadline_exceeded','manual_review'):
                    return self.current
                if self.current['status']!='running':await self.wait(120);continue
                iteration=self.current['iteration'];context={**data,'iteration':iteration}
                command=await self.call('p63r_launch',context);validate_command(command)
                self.child=await workflow.start_child_workflow(PaoPlannedDryRunWorkflow.run,command,
                    id='p62-'+command['plan_id'],id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
                    parent_close_policy=workflow.ParentClosePolicy.ABANDON)
                while not self.child.done():
                    value=await self.poll(data)
                    if value['stop_child']:
                        await self.stop(context,self.child)
                        self.current=await self.call('p63r_reconcile',context)
                        return self.current
                    await self.wait()
                await self.child  # Transport ACK only; finish reads immutable DB receipts.
                self.current=await self.call('p63r_finish',context)
                self.child=None
        except (ActivityError,ChildWorkflowError):
            if self.child:
                try:await self.stop({**data,'iteration':self.current['iteration']},self.child)
                except ActivityError:pass
            self.current=await self.call('p63r_uncertain',data)
            return self.current
