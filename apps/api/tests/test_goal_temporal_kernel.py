"""Real Temporal ownership/replay with synthetic adapters; NOT DB/API acceptance."""
import asyncio
from tempfile import TemporaryDirectory
from datetime import timedelta, datetime, timezone
from uuid import uuid4
import pytest
import pytest_asyncio
from temporalio import activity
from temporalio.exceptions import ApplicationError, CancelledError as TemporalCancelledError
from temporalio.client import WorkflowFailureError
from temporalio.service import RPCError, RPCStatusCode
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker, Replayer
from pao.config import ROOT
from temporal_fixture import cached_binary
from pao.modules.goals.workflow import PaoBoundedDryRunGoalWorkflow as GoalW
from pao.modules.studio.durable_workflow import PaoPlannedDryRunWorkflow as ChildW
from test_goal_control import envelope, proposal


class Fixture:
    def __init__(self):
        self.allow = True
        self.prepares = []
        self.outputs = ['done']
        self.cost = 0
        self.bad_child = False
        self.fail_child = False
        self.delay = 0
        self.step_calls = 0
        self.prepare_delay = 0
        self.block_step = False
        self.deny_receipt = False

    @activity.defn(name='p63_project')
    async def project(self, data: dict):
        return {'allow_iteration':self.allow, 'cancel_requested':False}

    @activity.defn(name='p63_prepare_iteration')
    async def prepare(self, data: dict):
        if self.prepare_delay:
            await asyncio.sleep(self.prepare_delay)
        p = data['state']['proposal']
        self.prepares.append(p['plan_id'])
        return {'format':'p62-dryrun-v1', 'plan_id':p['plan_id'],
                'snapshot_hash':'c'*64 if self.bad_child else p['snapshot_hash'],
                'timeout_seconds':p['max_duration_seconds'], 'steps':[
                    {'step_id':'echo','execution_id':str(uuid4()),'depends_on':[],
                     'approval_required':True,'delay_seconds':self.delay}]}

    @activity.defn(name='p63_read_receipt')
    async def receipt(self, data: dict):
        if self.deny_receipt:
            raise ApplicationError('fixture_permission_lost_at_receipt', non_retryable=True)
        s = data['state']
        return {'execution_id':data['envelope']['execution_id'], 'iteration':s['iteration'],
                'proposal_hash':s['proposal_hash'], 'output':{'text':self.outputs.pop(0)},
                'cost_microusd':self.cost, 'dry_run':True,'origin':'fixture_echo'}

    @activity.defn(name='p62_project')
    async def child_project(self, data: dict):
        return {'allow_next_step':True,'cancel_requested':False}

    @activity.defn(name='p62_dryrun_step')
    async def step(self, data: dict):
        self.step_calls += 1
        if self.fail_child:
            raise ApplicationError('fixture_uncertain', non_retryable=True)
        while self.block_step:
            activity.heartbeat('fixture_wait')
            await asyncio.sleep(.1)
        return {'execution_id':data['execution_id'],'status':'completed','dry_run':True}

    def activities(self):
        return [self.project,self.prepare,self.receipt,self.child_project,self.step]


@pytest_asyncio.fixture
async def temporal():
    directory = ROOT/'.runtime'/('p63b1-temporal-'+uuid4().hex)
    directory.mkdir()
    binary = cached_binary(ROOT)
    # SQLite scratch on the OS temp disk; keep replay evidence in the project.
    # A fixture does not need to contend with the source/archive disk's I/O.
    with TemporaryDirectory(prefix='pao-p63-temporal-') as scratch:
        async with await WorkflowEnvironment.start_local(ui=False,
                dev_server_existing_path=binary,
                dev_server_database_filename=scratch+'/temporal.sqlite') as env:
            yield env, directory


def worker(env, queue, adapter):
    return Worker(env.client, task_queue=queue, workflows=[GoalW,ChildW],
        activities=adapter.activities(), graceful_shutdown_timeout=timedelta(seconds=2))


async def start(env, queue, *, iterations=2, seconds=60, duration=10):
    e = envelope()
    e['policy'].update(max_iterations=iterations, max_elapsed_seconds=seconds,
        deadline_unix_ms=int(datetime.now(timezone.utc).timestamp()*1000)+seconds*1000)
    p = {**proposal(e),'max_duration_seconds':duration}
    handle = await env.client.start_workflow(GoalW.run, {'envelope':e,'initial_proposal':p},
        id='p63-'+e['execution_id'],task_queue=queue)
    return handle, e, p


async def wait_state(handle, expected, timeout=25):
    async def poll():
        while True:
            try:
                s = await handle.query('state')
            except RPCError as exc:
                if exc.status != RPCStatusCode.NOT_FOUND:
                    raise
                await asyncio.sleep(.05)
                continue  # signal committed; child may not yet be admitted
            if s['status'] == expected:
                return s
            await asyncio.sleep(.05)
    return await asyncio.wait_for(poll(), timeout)


async def approve(handle):
    s = await wait_state(handle,'waiting_approval')
    await handle.signal('decide',{'proposal_hash':s['proposal_hash'],'decision':'approve'})
    return s


async def approve_child(env, plan_id):
    child = env.client.get_workflow_handle('p62-'+plan_id)
    await wait_state(child,'waiting_approval')
    await child.signal('decide',{'step_id':'echo','decision':'approve','decision_id':str(uuid4())})
    return child


async def replay(handle, directory, label):
    history = await handle.fetch_history()
    await asyncio.wait_for(Replayer(workflows=[GoalW,ChildW]).replay_workflow(history),30)
    (directory/(label+'.json')).write_text(history.to_json(),encoding='utf-8')


async def test_restart_approval_and_replan_preserves_policy_and_separate_step_approval(temporal):
    env,directory = temporal
    f = Fixture(); f.outputs = ['unmet','done']
    queue = 'p63-kernel-'+uuid4().hex
    async with worker(env,queue,f):
        handle,e,p = await start(env,queue)
        before = await wait_state(handle,'waiting_approval')
        assert not f.prepares and not f.step_calls
    # A fresh worker must recover from Temporal history, not Python heap/browser.
    async with worker(env,queue,f):
        assert await wait_state(handle,'waiting_approval') == before
        await handle.signal('decide',{'proposal_hash':before['proposal_hash'],'decision':'approve'})
        child = env.client.get_workflow_handle('p62-'+e['plan_id'])
        await wait_state(child,'waiting_approval')
        assert f.step_calls == 0  # goal approval does not approve the child step
        await approve_child(env,e['plan_id'])
        s = await wait_state(handle,'waiting_replan')
        assert s['iteration'] == 1 and s['reserved_cost_microusd'] == 0
    async with worker(env,queue,f):
        assert await wait_state(handle,'waiting_replan') == s
        p2 = {**p,'plan_id':str(uuid4()),'snapshot_hash':'b'*64}
        # Invalid old plan cannot consume the only pending proposal slot.
        await handle.signal('propose',p)
        await handle.signal('propose',p2)
        await handle.signal('propose',{**p2,'plan_id':str(uuid4())})
        second = await wait_state(handle,'waiting_approval')
        assert second['proposal'] == p2 and second['deadline_unix_ms'] == before['deadline_unix_ms']
        await handle.signal('decide',{'proposal_hash':before['proposal_hash'],'decision':'approve'})
        assert (await handle.query('state'))['iteration'] == 1
        await approve(handle)
        await approve_child(env,p2['plan_id'])
        result = await asyncio.wait_for(handle.result(),15)
        assert result['status'] == 'completed' and result['iteration'] == 2
        assert f.prepares == [e['plan_id'],p2['plan_id']] and f.step_calls == 2
        await replay(handle,directory,'restart-replan-parent')
        await replay(child,directory,'restart-replan-first-child')


@pytest.mark.parametrize('scenario',['reject','cancel','deadline','permission','cost','invalid_child','receipt','unknown','iterations','receipt_permission'])
async def test_terminal_safety_and_replay(temporal,scenario):
    env,directory = temporal
    f = Fixture(); queue = 'p63-kernel-'+uuid4().hex
    async with worker(env,queue,f):
        handle,e,p = await start(env,queue,seconds=10 if scenario=='deadline' else 60,
            duration=1 if scenario=='deadline' else 10, iterations=1)
        state = None if scenario=='deadline' else await wait_state(handle,'waiting_approval')
        expected = scenario
        if scenario == 'reject':
            await handle.signal('decide',{'proposal_hash':state['proposal_hash'],'decision':'reject'})
            await handle.signal('decide',{'proposal_hash':state['proposal_hash'],'decision':'approve'})
            expected = 'cancelled'
        elif scenario == 'cancel':
            await handle.signal('request_cancel'); expected = 'cancelled'
        elif scenario == 'deadline':
            expected = 'deadline_exceeded'
        else:
            if scenario=='permission': f.allow = False
            if scenario=='invalid_child': f.bad_child = True
            if scenario=='receipt': f.cost = 1
            if scenario=='receipt_permission': f.deny_receipt = True
            if scenario=='unknown': f.fail_child = True
            if scenario=='iterations': f.outputs = ['unmet']
            if scenario=='cost':
                # Actual cost is not trusted from a child/model; nonzero fixture
                # usage freezes rather than accepting an unmetered model run.
                f.cost = 100
            await handle.signal('decide',{'proposal_hash':state['proposal_hash'],'decision':'approve'})
            if scenario not in ('permission','invalid_child'):
                await approve_child(env,e['plan_id'])
            expected = 'budget_exhausted' if scenario=='iterations' else 'manual_review'
        result = await asyncio.wait_for(handle.result(),25)
        assert result['status'] == expected, result
        if scenario in ('cost','receipt','unknown','invalid_child'):
            assert result['reserved_cost_microusd'] == 5
        if scenario in ('reject','cancel','deadline','permission'):
            assert f.step_calls == 0
        await replay(handle,directory,scenario)


@pytest.mark.parametrize('phase',['approval','timer','active'])
async def test_parent_cancel_drains_child_and_no_duplicate_execution(temporal,phase):
    env,directory = temporal
    f = Fixture();f.delay = 3 if phase=='timer' else 0
    f.block_step = phase=='active'
    queue = 'p63-kernel-'+uuid4().hex
    async with worker(env,queue,f):
        handle,e,p = await start(env,queue)
        pending = await approve(handle)
        await handle.signal('decide',{'proposal_hash':pending['proposal_hash'],'decision':'approve'})
        child = env.client.get_workflow_handle('p62-'+e['plan_id'])
        await wait_state(child,'waiting_approval')
        if phase in ('timer','active'):
            await approve_child(env,e['plan_id'])
            await wait_state(child,'waiting_timer' if phase=='timer' else 'running')
            if phase=='active':
                for _ in range(100):
                    if f.step_calls:
                        break
                    await asyncio.sleep(.05)
                assert f.step_calls == 1
        await handle.signal('request_cancel')
        await handle.signal('request_cancel')
        result = await asyncio.wait_for(handle.result(),15)
        child_result = await asyncio.wait_for(child.result(),15)
        assert child_result['status'] == 'cancelled'
        assert result['status'] == 'cancelled' and result['reserved_cost_microusd'] == 0
        assert len(f.prepares) == 1 and f.step_calls == (1 if phase=='active' else 0)
        await replay(handle,directory,'cancel-'+phase)
        await replay(child,directory,'cancel-child-'+phase)


async def test_expire_while_child_pending_drains_but_keeps_uncertain_reservation(temporal):
    env,directory = temporal
    f = Fixture();f.prepare_delay = 2;queue = 'p63-kernel-'+uuid4().hex
    async with worker(env,queue,f):
        handle,e,p = await start(env,queue,seconds=20,duration=3)
        pending = await wait_state(handle,'waiting_approval')
        remaining = (pending['deadline_unix_ms']-int(datetime.now(timezone.utc).timestamp()*1000))/1000
        await asyncio.sleep(max(0,remaining-4))
        await handle.signal('decide',{'proposal_hash':pending['proposal_hash'],'decision':'approve'})
        child = env.client.get_workflow_handle('p62-'+e['plan_id'])
        result = await asyncio.wait_for(handle.result(),15)
        assert result['status'] == 'deadline_exceeded' and result['reserved_cost_microusd'] == 5
        assert (await child.result())['status'] == 'cancelled' and f.step_calls == 0
        await replay(handle,directory,'deadline-child')


def test_kernel_is_not_registered_in_live_worker_or_api():
    source = (ROOT/'scripts/studio_temporal_worker.py').read_text(encoding='utf-8')
    assert 'PaoBoundedDryRunGoalWorkflow' not in source
    source = (ROOT/'apps/api/pao/main.py').read_text(encoding='utf-8')
    assert 'pao.modules.goals.workflow' not in source


async def test_direct_temporal_cancel_signals_and_drains_pending_child(temporal):
    env,directory = temporal
    f=Fixture();queue='p63-kernel-'+uuid4().hex
    async with worker(env,queue,f):
        handle,e,p=await start(env,queue)
        await approve(handle)
        child=env.client.get_workflow_handle('p62-'+e['plan_id'])
        await wait_state(child,'waiting_approval')
        await handle.cancel()
        with pytest.raises(WorkflowFailureError) as error:
            await asyncio.wait_for(handle.result(),15)
        assert isinstance(error.value.cause,TemporalCancelledError)
        assert (await asyncio.wait_for(child.result(),15))['status']=='cancelled'
        assert f.step_calls==0
        await replay(handle,directory,'direct-cancel')
