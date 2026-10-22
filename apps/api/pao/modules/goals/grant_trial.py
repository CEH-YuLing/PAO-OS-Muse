"""Isolated opt-in experiment; never registered in production workers.

Temporal owns exactly one actual child. Existing Goal projections remain denied.
No decision forwarding: child must wait for approvals and is only cancelled here.
"""
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import ApplicationError
from ..studio.durable_workflow import PaoPlannedDryRunWorkflow,validate_command


@workflow.defn
class PaoGrantChildTrialWorkflow:
    def __init__(self):
        self.cancelled=False

    @workflow.signal
    def request_cancel(self):
        self.cancelled=True

    @workflow.run
    async def run(self,data:dict):
        if workflow.info().workflow_id!='p63-grant-trial-'+data['envelope']['execution_id']:
            raise ApplicationError('goal_grant_trial_origin_invalid',non_retryable=True)
        if self.cancelled:return {'status':'cancelled_before_consume','child_started':False}
        # Deliberately no retries: ambiguous DB commit/ACK cannot start again.
        value=await workflow.execute_activity('p63_trial_consume_grant',data,
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=1))
        command=value['command'];validate_command(command)
        if any(step['approval_required'] is not True for step in command['steps']):
            raise ApplicationError('goal_trial_approval_required',non_retryable=True)
        remaining=value['deadline_unix_ms']-int(workflow.now().timestamp()*1000)
        if self.cancelled or remaining<command['timeout_seconds']*1000:
            return {'status':'consumed_without_start','child_started':False}
        child=await workflow.start_child_workflow(PaoPlannedDryRunWorkflow.run,command,
            id='p62-'+command['plan_id'],id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
            parent_close_policy=workflow.ParentClosePolicy.REQUEST_CANCEL)
        # This trial never approves steps. Always drain through the child's
        # supported custom signal, including bounded deadline expiry.
        try:
            await workflow.wait_condition(lambda:self.cancelled,
                timeout=timedelta(milliseconds=remaining))
        except TimeoutError:pass
        await child.signal('request_cancel')
        result=await child
        return {'status':result['status'],'child_started':True,'dry_run':True}
