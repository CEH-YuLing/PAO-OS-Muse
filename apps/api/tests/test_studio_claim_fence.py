"""Immutable claims survive a lost mutable projection; no models or queues."""
import pytest
from fastapi import HTTPException
from sqlalchemy import select, func

from pao.config import settings
from pao.db import Session
from pao.models import StudioEvent, StudioExecution, TaskAttempt
from pao.modules.studio import step_jobs as jobs
from test_studio_step_jobs import ready, gates


@pytest.mark.parametrize('operation,cancel', [
    ('claim', False), ('recover', False), ('recover', True),
    ('fail_pending', False), ('fail_pending', True),
])
async def test_missing_attempt_never_erases_immutable_claim(client, identity, gates, operation, cancel):
    value, ident = await ready(client, identity)
    args = (value['plan_id'], 'first', ident)
    await jobs.reserve(*args)
    original = await jobs.claim(*args)
    assert original['claimed'] is True
    async with Session.begin() as db:
        await db.delete(await db.get(TaskAttempt, ident))
        row = await db.get(StudioExecution, value['plan_id'])
        row.cancel_requested = cancel
        version = row.version
        claim = await db.get(StudioEvent, jobs.event_id(ident, 'claimed'))
        original_data = claim.data
    if operation != 'claim':
        settings().workflow_durable_enabled = False
    with pytest.raises(HTTPException) as error:
        await getattr(jobs, operation)(*args)
    assert error.value.status_code == 409
    assert error.value.detail == 'durable_step_projection_invalid'
    # A duplicate cannot generate a replacement attempt/token or no-effect proof.
    with pytest.raises(HTTPException):
        await getattr(jobs, operation)(*args)
    with pytest.raises(HTTPException):
        await jobs.finish(*args, original['token'], original['input'])
    async with Session() as db:
        assert await db.scalar(select(func.count(TaskAttempt.id))) == 0
        assert await db.get(StudioEvent, jobs.event_id(ident, 'outcome')) is None
        assert (await db.get(StudioEvent, jobs.event_id(ident, 'claimed'))).data == original_data
        row = await db.get(StudioExecution, value['plan_id'])
        assert row.status == 'running' and row.version == version
        assert row.cancel_requested is cancel


async def test_completed_outcome_cannot_mint_replacement_claim(client, identity, gates):
    value, ident = await ready(client, identity)
    args = (value['plan_id'], 'first', ident)
    await jobs.reserve(*args)
    original = await jobs.claim(*args)
    assert (await jobs.finish(*args, original['token'], original['input']))['status'] == 'completed'
    async with Session.begin() as db:
        await db.delete(await db.get(TaskAttempt, ident))
        outcome = (await db.get(StudioEvent, jobs.event_id(ident, 'outcome'))).data
    with pytest.raises(HTTPException) as error:
        await jobs.claim(*args)
    assert error.value.detail == 'durable_step_projection_invalid'
    # Existing terminal outcome can still be observed, but never re-executed.
    assert await jobs.recover(*args) == {'status': 'completed'}
    await jobs.fail_pending(*args)
    async with Session() as db:
        assert await db.scalar(select(func.count(TaskAttempt.id))) == 0
        assert (await db.get(StudioEvent, jobs.event_id(ident, 'outcome'))).data == outcome
