"""Real PostgreSQL durable ledger tests; no ARQ/model/provider registration."""
import asyncio
from datetime import timedelta
from uuid import uuid4
import pytest
from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.exc import DBAPIError
from pao.db import Session
from pao.models import StudioEvent, StudioExecution, TaskAttempt, Task, Member, now
from pao.config import settings
from pao.modules.studio import durable, step_jobs as jobs
from test_durable_admission import gates, plan, start, state, BASE


async def ready(client, identity):
    value = await plan(client, identity)
    _, response = await start(client, identity, value)
    assert response.status_code == 202
    await durable.project_state(state(value, 1, 'running'))
    return value, value['task_ids'][0]


async def test_reserve_claim_concurrent_finish_and_binding(client, identity, gates):
    value, ident = await ready(client, identity)
    args = (value['plan_id'], 'first', ident)
    reservations = await asyncio.gather(*(jobs.reserve(*args) for _ in range(2)))
    assert reservations[0] == reservations[1]
    claims = await asyncio.gather(*(jobs.claim(*args) for _ in range(2)))
    assert sum(item['claimed'] for item in claims) == 1
    claimed = next(item for item in claims if item['claimed'])
    url = BASE + '/executions/' + value['plan_id']
    assert (await client.get(url, headers=identity['owner'])).json()['task_attempts_created'] is True
    # The normal Task API must not be able to finalize these controlled attempts.
    response = await client.patch(f'/v1/tasks/{ident}/attempts/{ident}', headers=identity['owner'],
        json={'version': 1, 'status': 'failed', 'error_code': 'forged'})
    assert response.status_code == 409 and response.json()['detail'] == 'workflow_plan_tasks_frozen_no_runner'
    finished = await jobs.finish(*args, claimed['token'], claimed['input'])
    assert finished['status'] == 'completed' and not finished['receipt']['model_executed']
    assert finished == await jobs.finish(*args, claimed['token'], claimed['input'])
    assert await jobs.recover(*args) == {'status': 'completed'}
    with pytest.raises(HTTPException, match='409'):
        await jobs.finish(*args, claimed['token'], {'text': 'Conflicting result'})
    await durable.project_state(state(value, 2, 'step_completed', completed_steps=['first']))
    await durable.project_state(state(value, 3, 'running', current_step='second', completed_steps=['first']))
    second = (value['plan_id'], 'second', value['task_ids'][1])
    await jobs.reserve(*second)
    next_claim = await jobs.claim(*second)
    assert next_claim['input'] == {'text': 'Fixture planning'}
    assert (await jobs.finish(*second, next_claim['token'], next_claim['input']))['status'] == 'completed'
    await durable.project_state(state(value, 4, 'step_completed', current_step='second', completed_steps=['first','second']))
    await durable.project_state(state(value, 5, 'completed', current_step=None, completed_steps=['first','second']))
    async with Session() as db:
        assert await db.scalar(select(func.count(TaskAttempt.id))) == 2
        assert all(task.status == 'draft' and task.run_id is None for task in await db.scalars(select(Task)))
        events = list(await db.scalars(select(StudioEvent).where(StudioEvent.action.like('p62_step_%'))))
        assert len(events) == 6
        events[-1].data = {'forged': True}
        with pytest.raises(DBAPIError):
            await db.commit()
        await db.rollback()


async def test_reserved_no_claim_is_known_no_effect_and_scope_fails(client, identity, gates):
    value, ident = await ready(client, identity)
    args = (value['plan_id'], 'first', ident)
    assert await jobs.recover(*args) == {'status': 'absent', 'known_no_effect': True}
    with pytest.raises(HTTPException):
        await jobs.claim(*args)
    await jobs.reserve(*args)
    assert await jobs.recover(*args) == {'status': 'pending', 'known_no_effect': True}
    with pytest.raises(HTTPException):
        await jobs.reserve(value['plan_id'], 'first', str(uuid4()))
    settings().workflow_durable_enabled = False
    with pytest.raises(HTTPException):
        await jobs.claim(*args)
    async with Session() as db:
        assert await db.scalar(select(func.count(TaskAttempt.id))) == 0


@pytest.mark.parametrize('operation', ['finish', 'recover', 'claim'])
async def test_lost_claim_becomes_unknown_never_retries(client, identity, gates, monkeypatch, operation):
    value, ident = await ready(client, identity)
    args = (value['plan_id'], 'first', ident)
    await jobs.reserve(*args); claimed = await jobs.claim(*args)
    future = now() + timedelta(seconds=jobs.LEASE_SECONDS + 1)
    monkeypatch.setattr(jobs, 'now', lambda: future)
    # Renewing the mutable projection cannot extend the immutable claim lease.
    async with Session.begin() as db:
        attempt = await db.get(TaskAttempt, ident); attempt.updated_at = future
    if operation == 'finish':
        result = await jobs.finish(*args, claimed['token'], claimed['input'])
    else:
        result = await getattr(jobs, operation)(*args)
    assert result['status'] == 'failed'
    async with Session() as db:
        attempt = await db.get(TaskAttempt, ident)
        assert attempt.error_code == 'worker_lost_unknown'
        assert (await db.get(StudioExecution, value['plan_id'])).status == 'manual_review'
        assert await db.scalar(select(func.count(TaskAttempt.id))) == 1
    assert await jobs.recover(*args) == {'status': 'failed'}
    with pytest.raises(HTTPException):
        await jobs.claim(*args)


@pytest.mark.parametrize('loss', ['permission', 'flag', 'cancel', 'output'])
async def test_permission_cancel_output_and_token_fences(client, identity, gates, loss):
    value, ident = await ready(client, identity)
    args = (value['plan_id'], 'first', ident)
    await jobs.reserve(*args); claimed = await jobs.claim(*args)
    with pytest.raises(HTTPException):
        await jobs.finish(*args, str(uuid4()), claimed['input'])
    if loss == 'permission':
        async with Session.begin() as db:
            member = await db.scalar(select(Member).where(Member.user_id == identity['user_id']))
            member.role = 'operator'
    elif loss == 'flag':
        settings().workflow_durable_enabled = False
    elif loss == 'cancel':
        async with Session.begin() as db:
            row = await db.get(StudioExecution, value['plan_id']); row.cancel_requested = True
        settings().workflow_durable_enabled = False
    output = {'text': 'Model output not allowed'} if loss == 'output' else claimed['input']
    result = await jobs.finish(*args, claimed['token'], output)
    assert result['status'] == ('cancelled' if loss == 'cancel' else 'failed')
    assert await jobs.recover(*args) == {'status': result['status']}


async def test_dependency_projection_without_receipt_cannot_supply_input(client, identity, gates):
    value, _ = await ready(client, identity)
    await durable.project_state(state(value, 2, 'step_completed', completed_steps=['first']))
    await durable.project_state(state(value, 3, 'running', current_step='second', completed_steps=['first']))
    with pytest.raises(HTTPException):
        await jobs.reserve(value['plan_id'], 'second', value['task_ids'][1])
    async with Session() as db:
        assert await db.scalar(select(func.count(TaskAttempt.id))) == 0


async def test_cancel_reserved_drains_without_claim_with_flags_off(client, identity, gates):
    value, ident = await ready(client, identity)
    args = (value['plan_id'], 'first', ident)
    await jobs.reserve(*args)
    async with Session.begin() as db:
        row = await db.get(StudioExecution, value['plan_id']); row.cancel_requested = True
    settings().workflow_durable_enabled = False
    assert await jobs.recover(*args) == {'status': 'cancelled', 'known_no_effect': True}
    assert await jobs.recover(*args) == {'status': 'cancelled'}
    async with Session() as db:
        assert await db.scalar(select(func.count(TaskAttempt.id))) == 0
