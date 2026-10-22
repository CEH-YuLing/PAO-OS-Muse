import pytest
pytestmark=pytest.mark.usefixtures('accounted_runs')
from unittest.mock import AsyncMock
from sqlalchemy import select
from pao.config import settings
from pao.db import Session
from pao.models import Run, ToolCall, ToolAudit, Member
from pao.runtime import execute_run
from pao.skill_router import select_skill
from test_memory import run_chat
from test_business_tools import seed


def mock_gateway():
    gateway = AsyncMock()
    gateway.model_name = settings().ollama_model
    gateway.provider_name = 'ollama'
    return gateway


@pytest.mark.parametrize('prompt,status,skill', [
    ('Báo cáo doanh nghiệp từ 2026-10-01 đến 2026-10-05', 'ready', 'daily-business-brief'),
    ('Hãy báo cáo doanh nghiệp từ 2026-10-01 đến 2026-10-05.', 'ready', 'daily-business-brief'),
    ('daily business brief from 2026-10-01 to 2026-10-05', 'ready', 'daily-business-brief'),
    ('bao cao doanh nghiep 2026-10-01 - 2026-10-05', 'ready', 'daily-business-brief'),
    ('Báo cáo doanh nghiệp hôm nay', 'needs_input', 'daily-business-brief'),
    ('Báo cáo doanh nghiệp từ 2026-10-05 đến 2026-10-01', 'needs_input', 'daily-business-brief'),
    ('Báo cáo doanh nghiệp từ 2026-02-30 đến 2026-10-01', 'needs_input', 'daily-business-brief'),
    ('Báo cáo doanh nghiệp từ 2026-10-01 đến 2026-10-05 và gửi email', 'needs_input', 'daily-business-brief'),
    ('Điều tra hiệu quả quảng cáo giảm', 'needs_input', 'investigate-ads-drop'),
    ('Đánh giá creative fatigue', 'needs_input', 'creative-fatigue-review'),
    ('Điều tra hiệu quả quảng cáo giảm meta act_1 từ 2026-10-01 đến 2026-10-05', 'ready', 'investigate-ads-drop'),
    ('Đánh giá creative fatigue meta act_1 từ 2026-10-01 đến 2026-10-05', 'ready', 'creative-fatigue-review'),
    ('Đánh giá creative fatigue google_ads 1234567890 từ 2026-10-01 đến 2026-10-05', 'ready', 'creative-fatigue-review'),
    ('Đánh giá creative fatigue meta act_1 từ 2026-10-01 đến 2026-10-05 rồi tắt Ads', 'needs_input', 'creative-fatigue-review'),
])
def test_standard_command_routes(prompt, status, skill):
    route = select_skill(prompt)
    assert route['skill_id'] == skill and route['status'] == status


@pytest.mark.parametrize('prompt', ['Xin chào', 'Tắt quảng cáo act_1',
    'Dịch câu: Báo cáo doanh nghiệp từ 2026-10-01 đến 2026-10-05',
    '"Báo cáo doanh nghiệp từ 2026-10-01 đến 2026-10-05"',
    'Không báo cáo doanh nghiệp hôm nay'])
def test_noncommands_do_not_route(prompt):
    assert select_skill(prompt) is None


async def test_chief_uses_durable_gateway_and_no_model_or_external_provider(client, identity, monkeypatch):
    monkeypatch.setattr(settings(), 'tools_enabled', True)
    _, report_id = await seed(identity)
    _, rid = await run_chat(client, identity, 'Báo cáo doanh nghiệp từ 2026-10-01 đến 2026-10-05')
    gateway = mock_gateway()
    provider = AsyncMock()
    await execute_run({'gateway': gateway, 'tool_invoke': provider}, rid)
    await execute_run({'gateway': gateway}, rid)  # terminal replay has no duplicate calls
    gateway.plan.assert_not_awaited()
    gateway.stream.assert_not_called()
    provider.assert_not_awaited()
    async with Session() as db:
        run = await db.get(Run, rid)
        assert run.status == 'completed', run.error_code
        assert run.execution_plan['skill_snapshot']['version'] == ('1.1.0' if run.execution_plan['skill_route']['skill_id'] == 'investigate-ads-drop' else '1.0.0')
        assert run.execution_plan['skill_result']['status'] == 'insufficient_data'
        assert f'ad-report:{report_id}' in run.response
        assert 'doanh thu do Ads báo cáo' in run.response and 'Chưa đủ dữ liệu' in run.response
        calls = list(await db.scalars(select(ToolCall).where(ToolCall.run_id == rid)))
        assert len(calls) == 2 and all(call.status == 'completed' for call in calls)
        assert all(call.workspace_id == identity['workspace'] for call in calls)
        events = list(await db.scalars(select(ToolAudit.event).where(ToolAudit.run_id == rid)))
        assert events.count('tool.started') == events.count('tool.completed') == 2


@pytest.mark.parametrize('prompt', ['Báo cáo doanh nghiệp hôm nay', 'Đánh giá creative fatigue'])
async def test_missing_input_and_unavailable_do_not_invoke_tools(client, identity, monkeypatch, prompt):
    monkeypatch.setattr(settings(), 'tools_enabled', True)
    _, rid = await run_chat(client, identity, prompt)
    gateway = mock_gateway()
    await execute_run({'gateway': gateway}, rid)
    async with Session() as db:
        run = await db.get(Run, rid)
        assert run.status == 'completed' and run.response
        assert list(await db.scalars(select(ToolCall).where(ToolCall.run_id == rid))) == []
    gateway.stream.assert_not_called()


async def test_tools_off_does_not_read(client, identity):
    _, rid = await run_chat(client, identity, 'Báo cáo doanh nghiệp từ 2026-10-01 đến 2026-10-05')
    await execute_run({'gateway': mock_gateway()}, rid)
    async with Session() as db:
        assert 'đang tắt' in (await db.get(Run, rid)).response
        assert list(await db.scalars(select(ToolCall).where(ToolCall.run_id == rid))) == []


async def test_business_gateway_rechecks_membership_and_blocks_workspace_override(client, identity, monkeypatch):
    from pao.tool_gateway import propose, execute_tool
    from fastapi import HTTPException
    monkeypatch.setattr(settings(), 'tools_enabled', True)
    _, rid = await run_chat(client, identity, 'Gateway permission fixture')
    request = {'name': 'business.kpi.read', 'arguments': {'start_date': '2026-10-01', 'end_date': '2026-10-05'}}
    with pytest.raises(HTTPException) as error:
        await propose(rid, identity['user_id'], 'override-fixture', {**request,
                      'arguments': {**request['arguments'], 'workspace_id': 'other'}})
    assert error.value.status_code == 422
    call = await propose(rid, identity['user_id'], 'safe-fixture', request)
    async with Session.begin() as db:
        (await db.get(Member, (identity['workspace'], identity['user_id']))).role = 'viewer'
    await execute_tool({}, call.id)
    async with Session() as db:
        assert (await db.get(ToolCall, call.id)).status == 'cancelled'


async def test_freeform_model_cannot_invent_business_tool_route(client, identity, monkeypatch):
    from test_agents import Gateway
    from pao.agents import ExecutionPlan
    monkeypatch.setattr(settings(), 'tools_enabled', True)
    monkeypatch.setattr(settings(), 'agent_runtime_enabled', True)

    class InventedBusinessPlan(Gateway):
        async def plan(self, messages):
            return ExecutionPlan.model_validate({'goal': 'Untrusted invented plan', 'steps': [], 'tools': [{
                'name': 'business.kpi.read', 'agent': 'chief_of_staff',
                'arguments': {'start_date': '2026-10-01', 'end_date': '2026-10-05'}}]})

    _, rid = await run_chat(client, identity, 'Xin chào')
    await execute_run({'gateway': InventedBusinessPlan()}, rid)
    async with Session() as db:
        assert (await db.get(Run, rid)).status == 'completed'
        assert list(await db.scalars(select(ToolCall).where(ToolCall.run_id == rid))) == []
