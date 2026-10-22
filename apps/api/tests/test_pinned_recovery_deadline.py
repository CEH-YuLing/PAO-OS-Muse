"""Pinned cleanup deadlines do not depend on the restarted worker config."""
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from pao import runtime, skills
from pao.db import Session
from pao.models import Run
from test_memory import run_chat


def plan(timeout=10):
    return {'skill_snapshot': skills.snapshot('daily-business-brief'),
            'resource_guard': {'timeout_seconds': timeout}}


def test_pinned_budget_survives_registry_config_and_executable_change(monkeypatch):
    pinned = plan()
    monkeypatch.setattr(runtime.settings(), 'run_timeout_seconds', 120)
    monkeypatch.setattr(skills, 'EXECUTION_DIGEST', 'new-code')
    monkeypatch.setitem(skills.REGISTRY, 'daily-business-brief',
                        skills.REGISTRY['daily-business-brief'].model_copy(update={'timeout_seconds': 1}))
    assert runtime.recovery_timeout(SimpleNamespace(execution_plan=pinned)) == 10
    with pytest.raises(skills.SkillVersionMismatch):
        skills.require_snapshot_execution(pinned['skill_snapshot'])


@pytest.mark.parametrize('timeout', [True, '10', 0, -1, 601, None, 1.5])
def test_invalid_guard_uses_global_lease(monkeypatch, timeout):
    monkeypatch.setattr(runtime.settings(), 'run_timeout_seconds', 120)
    assert runtime.recovery_timeout(SimpleNamespace(execution_plan=plan(timeout))) == 120


@pytest.mark.parametrize('invalid', [None, [], {}, {'resource_guard': []},
                                    {'skill_snapshot': {}, 'resource_guard': {'timeout_seconds': 1}}])
def test_legacy_and_malformed_plans_use_global_lease(monkeypatch, invalid):
    monkeypatch.setattr(runtime.settings(), 'run_timeout_seconds', 120)
    assert runtime.recovery_timeout(SimpleNamespace(execution_plan=invalid)) == 120


def test_corrupt_snapshot_cannot_shorten_lease(monkeypatch):
    pinned = plan(1)
    pinned['skill_snapshot']['timeout_seconds'] = 1  # Hash is now invalid.
    monkeypatch.setattr(runtime.settings(), 'run_timeout_seconds', 120)
    assert runtime.recovery_timeout(SimpleNamespace(execution_plan=pinned)) == 120


@pytest.mark.parametrize('age,cancel,status', [(69, False, 'running'),
                                             (71, False, 'failed'),
                                             (71, True, 'cancelled')])
async def test_dispatch_respects_pinned_deadline_and_cancel(client, identity, monkeypatch,
                                                          age, cancel, status):
    _, rid = await run_chat(client, identity, 'test cleanup deadline')
    checkpoint = runtime.now()
    monkeypatch.setattr(runtime, 'now', lambda: checkpoint)
    monkeypatch.setattr(runtime.settings(), 'run_timeout_seconds', 120)
    async with Session.begin() as db:
        run = await db.get(Run, rid)
        run.status = 'running'
        run.started_at = checkpoint - timedelta(seconds=age)
        run.cancel_requested = cancel
        run.execution_plan = plan()
    redis = AsyncMock()
    await runtime.dispatch({'redis': redis})
    await runtime.dispatch({'redis': redis})
    redis.enqueue_job.assert_not_awaited()
    async with Session() as db:
        run = await db.get(Run, rid)
        assert run.status == status
        assert run.error_code == ('worker_lost' if status == 'failed' else None)
        assert not run.response
        assert run.execution_plan == plan()
