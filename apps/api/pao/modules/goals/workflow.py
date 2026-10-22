"""P6.3B1 Temporal kernel, NOT registered in a live worker or exposed by API.

The three p63 activities are mandatory trusted boundaries, not model tools:
projection/auth, DB admission of a pinned P6.2 child, and immutable DB receipts.
This kernel alone does not implement those boundaries. Tests use explicit
fixtures and must not be described as DB/API/business acceptance.
"""
import asyncio
from copy import deepcopy
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy, WorkflowIDReusePolicy
from temporalio.exceptions import ActivityError, ApplicationError, ChildWorkflowError
from .control import GoalControl, TERMINAL, closed, pin
from ..studio.durable_workflow import PaoPlannedDryRunWorkflow, validate_command


@workflow.defn
class PaoBoundedDryRunGoalWorkflow:
    def __init__(self):
        self.control = None
        self.cancel_requested = False
        self.pending_proposal = None
        self.pending_decision = None
        self.sequence = 0
        self.child_id = None
        self.transport_reason = None

    @workflow.signal
    def propose(self, data: dict):
        # Admission/auth is the future DB adapter's responsibility. This signal
        # cannot execute a plan or change policy and has a bounded single slot.
        if not self.control or self.control.snapshot()['status'] != 'waiting_replan':
            return
        if self.pending_proposal is None:
            try:
                closed(data, {'plan_id','snapshot_hash','cost_ceiling_microusd','max_duration_seconds'})
                # Validate with a copy of current deterministic reducer state;
                # a rejected signal must not mutate the actual policy/state.
                candidate = deepcopy(self.control)
                candidate.propose(data, self.now_ms())
            except (ValueError, TypeError, AttributeError):
                return
            self.pending_proposal = deepcopy(data)

    @workflow.signal
    def decide(self, data: dict):
        if not self.control or self.control.snapshot()['status'] != 'waiting_approval':
            return
        try:
            closed(data, {'proposal_hash','decision'})
            pin(data['proposal_hash'])
            if data['proposal_hash'] != self.control.snapshot()['proposal_hash'] or data['decision'] not in ('approve','reject'):
                return
        except (ValueError, TypeError):
            return
        if self.pending_decision is None:
            self.pending_decision = dict(data)  # first decision wins

    @workflow.signal
    def request_cancel(self):
        self.cancel_requested = True

    @workflow.query
    def state(self):
        return {**(self.control.snapshot() if self.control else {'status':'starting'}),
                'sequence':self.sequence, 'child_id':self.child_id,
                'cancel_requested':self.cancel_requested, 'transport_reason':self.transport_reason}

    def now_ms(self):
        return int(workflow.now().timestamp() * 1000)

    async def activity(self, name, data):
        return await workflow.execute_activity(name, data,
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=3))

    async def project(self, envelope):
        self.sequence += 1
        receipt = await self.activity('p63_project', {
            'envelope':envelope, 'state':self.state()})
        # Missing/malformed authorization fails closed. Cancellation is never
        # blocked by lost permission or rollback of admission gates.
        if type(receipt) is not dict or set(receipt) != {'allow_iteration','cancel_requested'} or any(type(v) is not bool for v in receipt.values()):
            self.control.uncertain(self.now_ms())
            self.transport_reason = 'projection_receipt_invalid'
            return False
        self.cancel_requested |= receipt['cancel_requested']
        if self.cancel_requested:
            self.control.cancel(self.now_ms())
        elif not receipt['allow_iteration'] and self.control.snapshot()['status'] not in TERMINAL:
            self.control.uncertain(self.now_ms())
            self.transport_reason = 'permission_or_gate_lost'
        return receipt['allow_iteration']

    async def wait_input(self, predicate):
        remaining = max(0, self.control.snapshot()['deadline_unix_ms'] - self.now_ms())
        try:
            await workflow.wait_condition(lambda:self.cancel_requested or predicate(),
                timeout=timedelta(milliseconds=remaining))
        except TimeoutError:
            self.control.advance(self.now_ms())
        if self.cancel_requested:
            self.control.cancel(self.now_ms())

    async def drain(self, child):
        # P6.2 implements an authenticated-dispatch custom cancel signal, not a
        # generic Temporal cancellation handler. Wait for the child's result;
        # unknown drain never releases a cost reservation or retries execution.
        try:
            await child.signal('request_cancel')
            return await asyncio.wait_for(asyncio.shield(child), timeout=40)
        except (ChildWorkflowError, ApplicationError, TimeoutError):
            self.transport_reason = 'child_drain_unknown'
            return None

    async def iteration(self, envelope):
        state = self.control.snapshot()
        context = {'envelope':envelope, 'state':state}
        command = await self.activity('p63_prepare_iteration', context)
        try:
            validate_command(command)
            proposal = state['proposal']
            if (command['plan_id'] != proposal['plan_id'] or command['snapshot_hash'] != proposal['snapshot_hash'] or
                    command['timeout_seconds'] > proposal['max_duration_seconds'] or
                    any(s['approval_required'] is not True for s in command['steps'])):
                raise ValueError('p63_child_pin_or_approval')
        except (ValueError, TypeError, AttributeError, KeyError):
            self.control.uncertain(self.now_ms())
            self.transport_reason = 'child_command_invalid'
            return
        # Reauthorize after admission and before child start. Browser approval
        # is not sufficient to skip the P6.2 step-level approvals.
        await self.project(envelope)
        self.control.advance(self.now_ms())
        if self.cancel_requested or self.control.snapshot()['status'] in TERMINAL:
            if self.control.snapshot()['status'] == 'running':
                self.control.uncertain(self.now_ms())
                self.transport_reason = 'cancelled_during_admission'
            return
        self.child_id = 'p62-' + command['plan_id']
        child = await workflow.start_child_workflow(PaoPlannedDryRunWorkflow.run, command,
            id=self.child_id, id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
            parent_close_policy=workflow.ParentClosePolicy.ABANDON)
        watcher = asyncio.create_task(workflow.wait_condition(lambda:self.cancel_requested,
            timeout=timedelta(milliseconds=max(0,state['deadline_unix_ms']-self.now_ms()))))
        try:
            done, _ = await workflow.wait([child, watcher], return_when=asyncio.FIRST_COMPLETED)
            if watcher in done:
                # Timer or cancellation: signal + drain before parent closes.
                if self.cancel_requested:
                    self.control.cancel(self.now_ms())
                else:
                    self.control.advance(self.now_ms())
                result = await self.drain(child)
            else:
                result = await child
            if type(result) is not dict or result.get('status') not in ('completed','cancelled'):
                self.control.uncertain(self.now_ms())
                self.transport_reason = 'child_execution_unknown'
                return
            if result['status'] == 'cancelled' and not self.cancel_requested:
                self.control.uncertain(self.now_ms())
                self.transport_reason = 'child_cancelled_without_goal_ack'
                return
            # NEVER accept child output or browser-provided usage as evidence.
            # Trusted adapter must read the immutable DB outcome, including the
            # cancellation ack; late receipts are retained by that DB adapter.
            receipt = await self.activity('p63_read_receipt', {**context,'child_result':result})
            if self.control.snapshot()['status'] not in TERMINAL:
                try:
                    self.control.finish(receipt, self.now_ms())
                except ValueError:
                    self.transport_reason = 'receipt_invalid'
        except asyncio.CancelledError:
            self.cancel_requested = True
            self.control.cancel(self.now_ms())
            await asyncio.shield(self.drain(child))
            self.control.uncertain(self.now_ms())
            raise
        except ChildWorkflowError:
            self.control.uncertain(self.now_ms())
            self.transport_reason = 'child_execution_unknown'
        finally:
            watcher.cancel()
            await asyncio.gather(watcher, return_exceptions=True)

    @workflow.run
    async def run(self, item: dict):
        try:
            closed(item, {'envelope','initial_proposal'})
            envelope = item['envelope']
            self.control = GoalControl(envelope, self.now_ms())
            self.control.propose(item['initial_proposal'], self.now_ms())
        except (ValueError, TypeError, AttributeError):
            raise ApplicationError('p63_initial_contract_invalid', non_retryable=True)
        try:
            while self.control.snapshot()['status'] not in TERMINAL:
                await self.project(envelope)
                status = self.control.snapshot()['status']
                if status in TERMINAL:
                    break
                if status == 'waiting_approval':
                    await self.wait_input(lambda:self.pending_decision is not None)
                    if self.control.snapshot()['status'] in TERMINAL:
                        break
                    decision = self.pending_decision
                    self.pending_decision = None
                    await self.project(envelope)  # permission check at approval
                    if self.control.snapshot()['status'] not in TERMINAL:
                        self.control.decide(decision['proposal_hash'], decision['decision'], self.now_ms())
                elif status == 'waiting_replan':
                    await self.wait_input(lambda:self.pending_proposal is not None)
                    if self.control.snapshot()['status'] in TERMINAL:
                        break
                    proposal = self.pending_proposal
                    self.pending_proposal = None
                    self.control.propose(proposal, self.now_ms())
                elif status == 'running':
                    await self.iteration(envelope)
                else:
                    self.control.uncertain(self.now_ms())
                    self.transport_reason = 'unexpected_state'
        except ActivityError:
            self.control.uncertain(self.now_ms())
            self.transport_reason = 'adapter_unavailable'
        await self.project(envelope)
        return self.state()
