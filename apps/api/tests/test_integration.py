import asyncio
import json
from datetime import timedelta
from unittest.mock import AsyncMock
import pytest

from sqlalchemy import select

from pao.db import Session
from pao.config import settings
from pao.gateway import Chunk
from pao.models import AgentRun, Member, Run, RunEvent, User, now
from pao.runtime import dispatch, execute_run
pytestmark=pytest.mark.usefixtures('accounted_runs')


async def make_run(client, identity, key='request-0001'):
    session = await client.post('/v1/sessions', headers=identity['owner'], json={'workspace_id': identity['workspace']})
    assert session.status_code == 201, session.text
    sid = session.json()['id']
    result = await client.post('/v1/runs', headers=identity['owner'], json={
        'session_id': sid, 'message': 'Xin chào', 'request_key': key})
    assert result.status_code == 202, result.text
    return sid, result.json()['id']


class SuccessfulGateway:
    provider_name='ollama'
    @property
    def model_name(self):return settings().ollama_model
    async def stream(self, messages, max_tokens=None):
        assert messages[0]['role'] == 'system'
        assert messages[-1]['content'] == 'Xin chào'
        yield Chunk(text='Chào ')
        yield Chunk(text='bạn!')
        yield Chunk(usage={'eval_count': 3})


async def test_stream_persistence_replay_and_duplicate_delivery(client, identity):
    sid, rid = await make_run(client, identity)
    await execute_run({'gateway': SuccessfulGateway()}, rid)
    await execute_run({'gateway': SuccessfulGateway()}, rid)
    detail = (await client.get(f'/v1/sessions/{sid}', headers=identity['owner'])).json()
    assert [m['content'] for m in detail['messages']] == ['Xin chào', 'Chào bạn!']
    assert detail['active_run'] is None
    stream = await client.get(f'/v1/runs/{rid}/events', headers=identity['owner'])
    assert stream.headers['content-type'].startswith('text/event-stream')
    payloads = [json.loads(line[6:]) for line in stream.text.splitlines() if line.startswith('data: ')]
    assert [e['seq'] for e in payloads] == list(range(1, len(payloads) + 1))
    assert payloads[-1]['type'] == 'run.completed'
    kinds = [e['type'] for e in payloads]
    assert kinds == ['run.queued', 'run.started', 'core.processing', 'agent.started',
                     'core.reasoning', 'core.speaking', 'response.delta', 'response.delta',
                     'agent.completed', 'response.completed', 'core.standby', 'run.completed']
    replay = await client.get(f'/v1/runs/{rid}/events', headers={**identity['owner'], 'Last-Event-ID': '5'})
    assert all(json.loads(line[6:])['seq'] > 5 for line in replay.text.splitlines() if line.startswith('data: '))
    async with Session() as db:
        agent = await db.scalar(select(AgentRun).where(AgentRun.run_id == rid))
        assert agent.status == 'completed' and agent.usage == {'output_tokens': 3}


async def test_auth_scope_and_viewer(client, identity):
    assert (await client.get('/v1/me')).status_code == 401
    bad = await client.post('/v1/auth/token', json={'email': 'owner@example.test', 'password': 'bad'})
    assert bad.status_code == 401
    good = await client.post('/v1/auth/token', json={'email': 'owner@example.test', 'password': 'test-password-123'})
    assert good.status_code == 200
    sid, rid = await make_run(client, identity)
    for who in ['other', 'outsider']:
        for path in [f'/v1/sessions/{sid}', f'/v1/runs/{rid}', f'/v1/runs/{rid}/events']:
            assert (await client.get(path, headers=identity[who])).status_code == 404
        assert (await client.post(f'/v1/runs/{rid}/cancel', headers=identity[who])).status_code == 404
    assert (await client.post('/v1/sessions', headers=identity['outsider'], json={'workspace_id': identity['workspace']})).status_code == 404
    async with Session.begin() as db:
        member = await db.get(Member, (identity['workspace'], identity['user_id']))
        member.role = 'viewer'
    assert (await client.post('/v1/sessions', headers=identity['owner'], json={'workspace_id': identity['workspace']})).status_code == 403


async def test_idempotency_conflict_and_cancel_queued(client, identity):
    sid, rid = await make_run(client, identity)
    body = {'session_id': sid, 'message': 'Xin chào', 'request_key': 'request-0001'}
    same = await client.post('/v1/runs', headers=identity['owner'], json=body)
    assert same.json()['id'] == rid
    assert (await client.post('/v1/runs', headers=identity['owner'], json={**body, 'message': 'Khác'})).status_code == 409
    assert (await client.post('/v1/runs', headers=identity['owner'], json={**body, 'request_key': 'request-0002'})).status_code == 409
    result = await client.post(f'/v1/runs/{rid}/cancel', headers=identity['owner'])
    assert result.json()['status'] == 'cancelled'
    await execute_run({'gateway': SuccessfulGateway()}, rid)
    assert (await client.get(f'/v1/runs/{rid}', headers=identity['owner'])).json()['status'] == 'cancelled'
    assert (await client.get(f'/v1/runs/{rid}/events', headers={**identity['owner'], 'Last-Event-ID': 'invalid'})).status_code == 400


async def test_cancel_running_keeps_partial(client, identity):
    sid, rid = await make_run(client, identity)
    started = asyncio.Event()
    class SlowGateway(SuccessfulGateway):
        async def stream(self, messages, max_tokens=None):
            yield Chunk(text='Một phần')
            started.set()
            await asyncio.sleep(30)
            yield Chunk(text='không được xuất hiện')
    task = asyncio.create_task(execute_run({'gateway': SlowGateway()}, rid))
    await asyncio.wait_for(started.wait(), 5)
    await client.post(f'/v1/runs/{rid}/cancel', headers=identity['owner'])
    await asyncio.wait_for(task, 5)
    result = (await client.get(f'/v1/runs/{rid}', headers=identity['owner'])).json()
    assert result['status'] == 'cancelled' and result['response'] == 'Một phần'
    detail = (await client.get(f'/v1/sessions/{sid}', headers=identity['owner'])).json()
    assert detail['messages'][-1]['status'] == 'cancelled'
    events = await client.get(f'/v1/runs/{rid}/events', headers=identity['owner'])
    kinds = [json.loads(line[6:])['type'] for line in events.text.splitlines() if line.startswith('data: ')]
    assert kinds[-3:] == ['agent.cancelled', 'core.standby', 'run.cancelled']
    assert 'response.completed' not in kinds


async def test_failure_before_output_never_announces_speaking(client, identity):
    _, rid = await make_run(client, identity)
    class Unavailable(SuccessfulGateway):
        async def stream(self, messages, max_tokens=None):
            raise RuntimeError('private provider detail')
            yield  # async generator protocol
    await execute_run({'gateway': Unavailable()}, rid)
    response = await client.get(f'/v1/runs/{rid}/events', headers=identity['owner'])
    kinds = [json.loads(line[6:])['type'] for line in response.text.splitlines() if line.startswith('data: ')]
    assert kinds[-3:] == ['agent.failed', 'core.standby', 'run.failed']
    assert 'core.speaking' not in kinds and 'response.completed' not in kinds
    assert 'private provider detail' not in response.text


async def test_provider_failure_and_outbox_recovery(client, identity):
    _, rid = await make_run(client, identity)
    redis = AsyncMock()
    await dispatch({'redis': redis})
    redis.enqueue_job.assert_awaited_once()
    class FailedGateway(SuccessfulGateway):
        async def stream(self, messages, max_tokens=None):
            yield Chunk(text='Partial')
            raise RuntimeError('sensitive-provider-url')
    await execute_run({'gateway': FailedGateway()}, rid)
    result = (await client.get(f'/v1/runs/{rid}', headers=identity['owner'])).json()
    assert result['status'] == 'failed' and result['error_code'] == 'model_unavailable'
    events = await client.get(f'/v1/runs/{rid}/events', headers=identity['owner'])
    assert 'sensitive-provider-url' not in events.text


async def test_stale_worker_and_concurrent_requests(client, identity):
    sid, rid = await make_run(client, identity)
    async with Session.begin() as db:
        run = await db.get(Run, rid)
        run.status = 'running'
        run.started_at = now() - timedelta(hours=1)
    await dispatch({'redis': AsyncMock()})
    result = (await client.get(f'/v1/runs/{rid}', headers=identity['owner'])).json()
    assert result['status'] == 'failed' and result['error_code'] == 'worker_lost'
    responses = await asyncio.gather(*[client.post('/v1/runs', headers=identity['owner'], json={
        'session_id': sid, 'message': 'Xin chào', 'request_key': f'parallel-{i:04}'}) for i in range(2)])
    assert sorted(r.status_code for r in responses) == [202, 409]


async def test_openapi_and_readiness(client):
    assert (await client.get('/health')).status_code == 200
    assert (await client.get('/ready')).status_code == 200
    schema = (await client.get('/openapi.json')).json()
    assert 'RunEvent' in schema['components']['schemas']
    assert '/v1/runs/{run_id}/events' in schema['paths']


async def test_model_timeout(client, identity, monkeypatch):
    from pao.config import settings
    _, rid = await make_run(client, identity)
    monkeypatch.setattr(settings(), 'run_timeout_seconds', 0.05)
    class HangingGateway(SuccessfulGateway):
        async def stream(self, messages, max_tokens=None):
            await asyncio.sleep(30)
            yield Chunk(text='Too late')
    await asyncio.wait_for(execute_run({'gateway': HangingGateway()}, rid), 2)
    result = (await client.get(f'/v1/runs/{rid}', headers=identity['owner'])).json()
    assert result['status'] == 'failed' and result['error_code'] == 'model_timeout'


async def test_revoked_user_cannot_execute_queued_job(client, identity):
    _, rid = await make_run(client, identity)
    async with Session.begin() as db:
        user = await db.get(User, identity['user_id'])
        user.active = False
    await execute_run({'gateway': SuccessfulGateway()}, rid)
    async with Session() as db:
        run = await db.get(Run, rid)
        assert run.status == 'failed' and run.error_code == 'access_revoked'
    assert (await client.get('/v1/me', headers=identity['owner'])).status_code == 401
