from unittest.mock import AsyncMock
import pytest
from sqlalchemy import select, func
from redis.exceptions import ConnectionError
from pao.db import Session
from pao.config import settings
from pao.models import Member, TaskAttempt
from pao.modules.studio import arq_bridge as bridge
from test_durable_admission import gates
from test_studio_step_jobs import ready

@pytest.mark.parametrize('case', ['enabled','disabled','lost_permission','redis_loss','cancel'])
async def test_dispatch_recovery_gates_and_no_orphan_claim(client, identity, gates, monkeypatch, case):
    value, ident = await ready(client, identity)
    args = (value['plan_id'], 'first', ident)
    await bridge.jobs.reserve(*args)
    redis = AsyncMock()
    monkeypatch.setattr(settings(),'workflow_worker_enabled',case != 'disabled')
    if case == 'lost_permission':
        async with Session.begin() as db:
            member = await db.get(Member,(identity['workspace'],identity['user_id'])); member.role='viewer'
    elif case == 'redis_loss':
        redis.enqueue_job.side_effect=ConnectionError('synthetic disconnect')
    elif case == 'cancel':
        await bridge.cancel_and_drain(*args)
    await bridge.dispatch_studio({'redis':redis})
    if case in ('enabled','redis_loss'):
        redis.enqueue_job.assert_awaited_once()
        assert (await bridge.jobs.recover(*args))['status']=='pending'
    else:
        redis.enqueue_job.assert_not_awaited()
    if case == 'lost_permission':
        assert (await bridge.jobs.recover(*args))['status']=='failed'
    async with Session() as db:
        assert await db.scalar(select(func.count(TaskAttempt.id)))==0

async def test_status_requires_both_current_worker_leases(client,identity,gates,monkeypatch):
    from pao.main import app
    monkeypatch.setattr(settings(),'workflow_worker_enabled',True)
    marker=bridge.worker_marker()
    keys=('pao:studio:arq:health','pao:studio:temporal:health')
    try:
        await app.state.redis.set(keys[0],marker,ex=20)
        response=await client.get('/v1/studio/durable/status',headers=identity['owner'],params={'workspace_id':identity['workspace']})
        assert response.json()['arq_bridge_ready'] is False
        await app.state.redis.set(keys[1],marker,ex=20)
        response=await client.get('/v1/studio/durable/status',headers=identity['owner'],params={'workspace_id':identity['workspace']})
        assert response.json()['arq_bridge_ready'] is True
        await app.state.redis.set(keys[1],'stale-executable',ex=20)
        response=await client.get('/v1/studio/durable/status',headers=identity['owner'],params={'workspace_id':identity['workspace']})
        assert response.json()['arq_bridge_ready'] is False
    finally:
        await app.state.redis.delete(*keys)
