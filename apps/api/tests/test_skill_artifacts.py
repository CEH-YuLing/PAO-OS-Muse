import copy
from unittest.mock import AsyncMock

import pytest
pytestmark=pytest.mark.usefixtures('accounted_runs')
from sqlalchemy import select

from pao import runtime, skills
from pao.db import Session
from pao.models import AdReport, Member, Run, RunEvent, TaskAttempt, ToolCall
from pao.skill_artifacts import build_artifact, read_artifact
from test_business_tools import seed
from test_memory import run_chat
from test_skill_router import mock_gateway
from test_skills import make_skill_task, PERIOD

COMMAND = 'Báo cáo doanh nghiệp từ 2026-10-01 đến 2026-10-05'


async def completed_run(client, identity, monkeypatch):
    monkeypatch.setattr(runtime.settings(), 'tools_enabled', True)
    _, rid = await run_chat(client, identity, COMMAND)
    gateway = mock_gateway()
    await runtime.execute_run({'gateway': gateway}, rid)
    gateway.plan.assert_not_awaited()
    gateway.stream.assert_not_called()
    async with Session() as db:
        run = await db.get(Run, rid)
        assert run.status == 'completed', run.error_code
    return rid


async def test_replay_preserves_data_version_after_source_registry_code_change(client, identity, monkeypatch):
    _, report_id = await seed(identity)
    rid = await completed_run(client, identity, monkeypatch)
    url = f'/v1/runs/{rid}/skill-replay'
    first = await client.get(url, headers=identity['owner'])
    assert first.status_code == 200, first.text
    saved = first.json()
    assert saved['result']['status'] == 'insufficient_data'
    assert saved['business_verified'] is False and saved['tools_reexecuted'] is False
    async with Session.begin() as db:
        report = await db.get(AdReport, report_id)
        report.revenue = 999999
    monkeypatch.setitem(skills.REGISTRY, 'daily-business-brief',
        skills.REGISTRY['daily-business-brief'].model_copy(update={'version': '9.9.9'}))
    monkeypatch.setattr(skills, 'EXECUTION_DIGEST', 'new-code')
    tool = AsyncMock(side_effect=AssertionError('Replay must not run tools'))
    monkeypatch.setattr(runtime, 'execute_tool', tool)
    async with Session() as db:
        before_calls = list(await db.scalars(select(ToolCall.id).where(ToolCall.run_id == rid)))
        before_events = list(await db.scalars(select(RunEvent.seq).where(RunEvent.run_id == rid)))
    for _ in range(2):
        replay = await client.get(url, headers=identity['owner'])
        assert replay.status_code == 200 and replay.json() == saved
    tool.assert_not_awaited()
    async with Session() as db:
        assert list(await db.scalars(select(ToolCall.id).where(ToolCall.run_id == rid))) == before_calls
        assert list(await db.scalars(select(RunEvent.seq).where(RunEvent.run_id == rid))) == before_events


async def test_replay_auth_owner_archived_session_and_membership(client, identity, monkeypatch):
    rid = await completed_run(client, identity, monkeypatch)
    url = f'/v1/runs/{rid}/skill-replay'
    assert (await client.get(url)).status_code == 401
    assert (await client.get(url, headers=identity['other'])).status_code == 404
    assert (await client.get(url, headers=identity['outsider'])).status_code == 404
    async with Session.begin() as db:
        member = await db.get(Member, (identity['workspace'], identity['user_id']))
        member.role = 'viewer'
    assert (await client.get(url, headers=identity['owner'])).status_code == 200
    async with Session.begin() as db:
        member = await db.get(Member, (identity['workspace'], identity['user_id']))
        await db.delete(member)
    assert (await client.get(url, headers=identity['owner'])).status_code == 404


@pytest.mark.parametrize('change', ['hash', 'data', 'response', 'scope', 'missing'])
async def test_corrupted_or_legacy_archive_refuses_replay(client, identity, monkeypatch, change):
    rid = await completed_run(client, identity, monkeypatch)
    async with Session.begin() as db:
        run = await db.get(Run, rid)
        plan = copy.deepcopy(run.execution_plan)
        if change == 'hash':
            plan['skill_artifact']['hash'] = '0' * 64
        elif change == 'data':
            plan['skill_artifact']['tools'][0]['data'] = {'fake': 'injected'}
        elif change == 'response':
            run.response = 'changed outside archive'
        elif change == 'scope':
            plan['skill_artifact']['workspace_id'] = 'another-workspace'
        else:
            plan.pop('skill_artifact')
        run.execution_plan = plan
    assert (await client.get(f'/v1/runs/{rid}/skill-replay', headers=identity['owner'])).status_code == 409


async def test_incomplete_run_has_no_success_archive(client, identity):
    _, rid = await run_chat(client, identity, COMMAND)
    assert (await client.get(f'/v1/runs/{rid}/skill-replay', headers=identity['owner'])).status_code == 409


async def test_attempt_archive_survives_version_change_and_is_immutable(client, identity, monkeypatch):
    task = await make_skill_task(client, identity)
    base = f"/v1/tasks/{task['id']}/attempts"
    attempt = (await client.post(base, headers=identity['owner'],
        json={'request_key': 'archive-attempt-01', 'input': PERIOD})).json()
    url = f"{base}/{attempt['id']}"
    result = {'status': 'completed', 'summary': 'Fixture report only', 'source_references': ['report:fixture']}
    patch = {'version': 1, 'status': 'completed', 'result': result,
             'evidence': [{'type': 'report', 'reference': 'report:fixture'}]}
    completed = await client.patch(url, headers=identity['owner'], json=patch)
    assert completed.status_code == 200, completed.text
    replay = await client.get(url + '/skill-replay', headers=identity['owner'])
    assert replay.status_code == 200, replay.text
    pinned = replay.json()
    monkeypatch.setattr(skills, 'EXECUTION_DIGEST', 'new-code')
    monkeypatch.setitem(skills.REGISTRY, 'daily-business-brief',
        skills.REGISTRY['daily-business-brief'].model_copy(update={'version': '9.9.9'}))
    assert (await client.get(url + '/skill-replay', headers=identity['owner'])).json() == pinned
    assert (await client.get(url + '/skill-replay', headers=identity['outsider'])).status_code == 404
    assert (await client.patch(url, headers=identity['owner'], json={**patch, 'version': 2})).status_code == 409
    async with Session() as db:
        row = await db.get(TaskAttempt, attempt['id'])
        assert row.skill_artifact['hash'] == pinned['hash']


def test_artifact_size_and_unread_sources_rejected():
    pinned = skills.snapshot('daily-business-brief')
    result = {'status': 'insufficient_data', 'summary': 'Missing',
              'source_references': ['invented:source'], 'missing_data': ['connector']}
    guard = {'execution_mode': 'deterministic_read_only', 'llm_generated_tokens': 0,
             'token_budget': pinned['token_budget'], 'max_tools': 2}
    tools = [{'tool': name, 'source_references': [], 'data': {}}
             for name in ['business.kpi.read', 'business.tasks.read']]
    with pytest.raises(ValueError):
        build_artifact('run', 'id', 'workspace', pinned, PERIOD, result, tools=tools, guard=guard)
    result['source_references'] = []
    tools[0]['data'] = {'too_big': 'x' * 256001}
    with pytest.raises(ValueError):
        build_artifact('run', 'id', 'workspace', pinned, PERIOD, result, tools=tools, guard=guard)


async def test_unsupported_llm_skill_mode_fails_closed(client, identity, monkeypatch):
    monkeypatch.setitem(skills.REGISTRY, 'daily-business-brief',
        skills.REGISTRY['daily-business-brief'].model_copy(update={'execution_mode': 'llm'}))
    _, rid = await run_chat(client, identity, COMMAND)
    gateway = mock_gateway()
    await runtime.execute_run({'gateway': gateway}, rid)
    gateway.plan.assert_not_awaited()
    gateway.stream.assert_not_called()
    async with Session() as db:
        run = await db.get(Run, rid)
        assert run.status == 'failed' and run.error_code == 'skill_execution_mode_unsupported'
        assert not run.response and not run.execution_plan.get('skill_artifact')


@pytest.mark.parametrize('tokens', [1, True, '0'])
def test_nonzero_or_invalid_llm_usage_cannot_be_archived(tokens):
    pinned = skills.snapshot('daily-business-brief')
    result = {'status': 'insufficient_data', 'summary': 'Missing',
              'source_references': [], 'missing_data': ['connector']}
    tools = [{'tool': name, 'source_references': []}
             for name in ['business.kpi.read', 'business.tasks.read']]
    with pytest.raises(ValueError):
        build_artifact('run', 'id', 'workspace', pinned, PERIOD, result, tools=tools,
            guard={'execution_mode': 'deterministic_read_only', 'llm_generated_tokens': tokens,
                   'token_budget': pinned['token_budget'], 'max_tools': 2})
