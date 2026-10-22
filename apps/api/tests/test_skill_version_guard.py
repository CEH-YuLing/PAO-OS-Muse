import hashlib
import json

import pytest
pytestmark=pytest.mark.usefixtures('accounted_runs')
from sqlalchemy import select

from pao import runtime, skills, tool_gateway
from pao.config import settings
from pao.db import Session
from pao.models import Run, ToolCall
from test_memory import run_chat
from test_skill_router import mock_gateway
from test_skills import make_skill_task, PERIOD

COMMAND = 'Báo cáo doanh nghiệp từ 2026-10-01 đến 2026-10-05'
RESULT = {'status': 'completed', 'summary': 'Fixture only', 'source_references': ['report:fixture']}


def rehash(payload):
    payload = {key: value for key, value in payload.items() if key != 'hash'}
    value = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return {**payload, 'hash': hashlib.sha256(value.encode()).hexdigest()}


@pytest.mark.parametrize('change', ['legacy', 'different', 'tampered'])
def test_evaluator_rejects_unbound_or_incompatible_executable(change):
    pinned = skills.snapshot('daily-business-brief')
    assert skills.evaluate_result(pinned, RESULT)['status'] == 'completed'
    if change == 'legacy':
        pinned.pop('execution_binding')
        pinned = rehash(pinned)
    elif change == 'different':
        pinned['execution_binding'] = {'policy': 'exact-backend-source-v1', 'sha256': '0' * 64}
        pinned = rehash(pinned)
    else:
        pinned['version'] = '9.9.9'
    with pytest.raises(ValueError):
        skills.evaluate_result(pinned, RESULT)


@pytest.mark.parametrize('drift', [False, True])
async def test_previously_pinned_queued_run_is_not_replanned(client, identity, monkeypatch, drift):
    _, rid = await run_chat(client, identity, COMMAND)
    pinned = skills.snapshot('daily-business-brief')
    async with Session.begin() as db:
        run = await db.get(Run, rid)
        run.execution_plan = {'skill_route': {'skill_id': 'daily-business-brief'}, 'skill_snapshot': pinned}
    if drift:
        monkeypatch.setattr(skills, 'EXECUTION_DIGEST', '0' * 64)
    await runtime.execute_run({'gateway': mock_gateway()}, rid)
    async with Session() as db:
        run = await db.get(Run, rid)
        assert run.status == 'failed'
        assert run.error_code == ('skill_version_incompatible' if drift else 'skill_resume_not_supported')
        assert run.execution_plan['skill_snapshot'] == pinned and not run.response
        assert list(await db.scalars(select(ToolCall).where(ToolCall.run_id == rid))) == []


async def test_queued_business_call_rejects_new_executable(client, identity, monkeypatch):
    monkeypatch.setattr(settings(), 'tools_enabled', True)
    _, rid = await run_chat(client, identity, 'Standalone tool fixture')
    call = await tool_gateway.propose(rid, identity['user_id'], 'version-tool-01',
                                    {'name': 'business.tasks.read', 'arguments': PERIOD})
    monkeypatch.setattr(skills, 'EXECUTION_DIGEST', '0' * 64)
    await tool_gateway.execute_tool({}, call.id)
    async with Session() as db:
        saved = await db.get(ToolCall, call.id)
        assert saved.status == 'cancelled' and saved.error_code == 'skill_version_incompatible'
        assert not saved.result


async def test_version_change_during_read_cannot_publish_result(client, identity, monkeypatch):
    monkeypatch.setattr(settings(), 'tools_enabled', True)
    _, rid = await run_chat(client, identity, 'Standalone tool fixture')
    call = await tool_gateway.propose(rid, identity['user_id'], 'version-tool-02',
                                    {'name': 'business.tasks.read', 'arguments': PERIOD})

    async def drift_during_read(*args):
        monkeypatch.setattr(skills, 'EXECUTION_DIGEST', '0' * 64)
        return {'untrusted_result': 'must not publish'}

    monkeypatch.setattr(tool_gateway, 'read_tasks', drift_during_read)
    await tool_gateway.execute_tool({}, call.id)
    async with Session() as db:
        saved = await db.get(ToolCall, call.id)
        assert saved.status == 'failed' and saved.error_code == 'skill_version_incompatible'
        assert not saved.result


async def test_version_change_between_tools_stops_command(client, identity, monkeypatch):
    monkeypatch.setattr(settings(), 'tools_enabled', True)
    _, rid = await run_chat(client, identity, COMMAND)
    execute = runtime.execute_tool

    async def drift_after_first(ctx, call_id):
        await execute(ctx, call_id)
        monkeypatch.setattr(skills, 'EXECUTION_DIGEST', '0' * 64)

    monkeypatch.setattr(runtime, 'execute_tool', drift_after_first)
    await runtime.execute_run({'gateway': mock_gateway()}, rid)
    async with Session() as db:
        run = await db.get(Run, rid)
        assert run.status == 'failed' and run.error_code == 'skill_version_incompatible'
        assert not run.response and not run.execution_plan.get('skill_result')
        calls = list(await db.scalars(select(ToolCall).where(ToolCall.run_id == rid)))
        assert len(calls) == 1 and calls[0].status == 'completed'


async def test_attempt_cannot_complete_with_new_evaluator_but_can_fail(client, identity, monkeypatch):
    task = await make_skill_task(client, identity)
    start = await client.post(f"/v1/tasks/{task['id']}/attempts", headers=identity['owner'],
                              json={'request_key': 'version-attempt-01', 'input': PERIOD})
    assert start.status_code == 201
    attempt = start.json()
    monkeypatch.setattr(skills, 'EXECUTION_DIGEST', '0' * 64)
    url = f"/v1/tasks/{task['id']}/attempts/{attempt['id']}"
    rejected = await client.patch(url, headers=identity['owner'], json={
        'version': 1, 'status': 'completed', 'result': RESULT,
        'evidence': [{'type': 'report', 'reference': 'report:fixture'}]})
    assert rejected.status_code == 409 and 'skill_version_incompatible' in rejected.text
    saved = (await client.get(f"/v1/tasks/{task['id']}/attempts", headers=identity['owner'])).json()[0]
    assert saved['status'] == 'running' and saved['skill_snapshot'] == attempt['skill_snapshot']
    failed = await client.patch(url, headers=identity['owner'], json={
        'version': 1, 'status': 'failed', 'error_code': 'skill_version_incompatible'})
    assert failed.status_code == 200 and failed.json()['status'] == 'failed'
