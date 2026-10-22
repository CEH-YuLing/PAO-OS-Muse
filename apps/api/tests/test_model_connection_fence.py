"""B2a real admission/worker fences; no active grant or external provider."""
import asyncio
import signal
from types import SimpleNamespace
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import event, select

from pao.config import settings
from pao.db import Session, engine
from pao.gateway import Chunk
from pao.model_router import encrypt_key, gateway_for_workspace
from pao.models import AgentRun, ChatSession, MemoryJob, Message, ModelProviderConnection, Run, RunEvent, Member, User
from pao.modules.connections import model_fence
from pao.modules.engines.contract import EngineFailure
from pao.modules.engines.service import gateway_for_run, digest, public
from pao.runtime import execute_run
from test_connection_inventory import corpus, path
from test_connection_grants import stage
from test_engine_contract import engines


@pytest_asyncio.fixture
async def fenced(corpus, engines, monkeypatch):
    async with Session.begin() as db:
        for label in ('a', 'b'):
            row = await db.get(ModelProviderConnection, corpus['connections'][label]['model'])
            row.is_default = True
            row.api_key_ciphertext = encrypt_key('local-fence-fixture')
    calls = {'factory': 0, 'stream': 0, 'plan': 0, 'extract': 0, 'closed': 0}
    class Fake:
        provider_name, model_name = 'openai', 'local-fixture'
        async def stream(self, messages, max_tokens=None):
            calls['stream'] += 1
            try:
                yield Chunk(text='safe-fixture-response')
            finally:
                calls['closed'] += 1
        async def plan(self, messages):
            from pao.agents import ExecutionPlan
            calls['plan'] += 1
            return ExecutionPlan(goal='fixture', steps=[])
        async def extract(self, prompt):
            from pao.memory_schemas import ExtractedFacts
            calls['extract'] += 1
            return ExtractedFacts(facts=[])
    fake = Fake()
    def factory(*args):
        calls['factory'] += 1
        return fake
    monkeypatch.setattr('pao.modules.engines.service.cloud_gateway', factory)
    monkeypatch.setattr('pao.model_router.cloud_gateway', factory)
    return corpus, calls, fake


async def queued(client, c, *, workspace=None, headers=None):
    response = await client.post('/v1/sessions', headers=headers or c['owner'],
        json={'workspace_id': workspace or c['workspace'], 'memory_enabled': False})
    assert response.status_code == 201, response.text
    sid = response.json()['id']
    profile=await client.put(f'/v1/sessions/{sid}/chat',headers=headers or c['owner'],json={'version':1,'policy':{'privacy':'cloud_allowed'}})
    assert profile.status_code==200,profile.text
    response = await client.post('/v1/runs', headers=headers or c['owner'], json={
        'session_id': sid, 'message': 'model fence fixture question', 'request_key': uuid4().hex})
    assert response.status_code == 202, response.text
    return response.json()['id'], sid


async def saved_run(rid):
    async with Session() as db:
        row = await db.get(Run, rid)
        events = list(await db.scalars(select(RunEvent).where(RunEvent.run_id == rid)))
        return row, events


async def mapped(client, c, state='staged'):
    response, body = await stage(client, c)
    assert response.status_code == 201, response.text
    saved = response.json()
    if state in ('grant_revoked', 'reference_revoked'):
        ref, grant = saved['reference']['id'], saved['grant']['id']
        suffix = f'/grants/{grant}/revoke' if state == 'grant_revoked' else '/revoke'
        result = await client.post(path(c['workspace'])+f'/references/{ref}'+suffix,
            headers=c['owner'], json={'reference_revision': 1, 'grant_revision': 1})
        assert result.status_code == 200
    if state == 'source_deleted':
        async with Session.begin() as db:
            await db.delete(await db.get(ModelProviderConnection, c['connections']['a']['model']))
    return saved


@pytest.mark.parametrize('state', ['staged', 'grant_revoked', 'reference_revoked', 'source_deleted'])
async def test_registered_default_deny_before_credentials_and_admission_rollback(client, fenced, monkeypatch, state):
    c, calls, _ = fenced
    await mapped(client, c, state)
    def forbidden(*args):
        raise AssertionError('Must not decrypt registered source')
    monkeypatch.setattr('pao.modules.engines.service.decrypt_key', forbidden)
    response = await client.post('/v1/sessions', headers=c['owner'], json={'workspace_id':c['workspace']})
    sid = response.json()['id']
    sql = []
    def record(conn, cursor, statement, parameters, context, executemany):
        sql.append(statement)
    event.listen(engine.sync_engine, 'before_cursor_execute', record)
    try:
        denied = await client.post('/v1/runs', headers=c['owner'], json={
            'session_id':sid, 'message':'fixture', 'request_key':uuid4().hex})
    finally:
        event.remove(engine.sync_engine, 'before_cursor_execute', record)
    assert denied.status_code == 503 and denied.json()['detail'] == model_fence.DENIED
    assert not any('api_key_ciphertext' in query.lower() for query in sql)
    assert calls['factory'] == calls['stream'] == 0
    async with Session() as db:
        chat = await db.get(ChatSession, sid)
        assert chat.engine_config is None and chat.engine_version == 1
        assert not await db.scalar(select(Run.id).where(Run.session_id == sid))
    selected = await client.get(f'/v1/sessions/{sid}/engine', headers=c['owner'])
    assert selected.status_code == 200 and selected.json()['error'] == model_fence.DENIED
    choice = await client.put(f'/v1/sessions/{sid}/engine', headers=c['owner'], json={
        'provider':'openai','model':'local-fixture','version':1})
    assert choice.status_code == 409 and choice.json()['detail'] == (
        'engine_connection_unavailable' if state == 'source_deleted' else model_fence.DENIED)


@pytest.mark.parametrize('state', ['staged', 'grant_revoked', 'reference_revoked', 'source_deleted'])
async def test_mapping_after_enqueue_deny_no_repin_no_legacy_fallback(client, fenced, monkeypatch, state):
    c, calls, _ = fenced
    rid, _ = await queued(client, c)
    original, _ = await saved_run(rid)
    await mapped(client, c, state)
    def forbidden(*args):
        raise AssertionError('Deny before decrypt')
    monkeypatch.setattr('pao.modules.engines.service.decrypt_key', forbidden)
    await execute_run({}, rid)
    result, events = await saved_run(rid)
    assert result.status == 'failed' and result.error_code == model_fence.DENIED
    assert result.engine_snapshot == original.engine_snapshot and result.response == ''
    assert calls['factory'] == calls['stream'] == 0
    assert not any(row.type in ('run.started','response.delta','response.completed') for row in events)
    async with Session() as db:
        assert not await db.scalar(select(AgentRun.id).where(AgentRun.run_id == rid))


async def test_new_immutable_legacy_pin_is_scoped_and_never_public(client, fenced):
    c, calls, _ = fenced
    rid, _ = await queued(client, c)
    row, _ = await saved_run(rid)
    pin = row.engine_snapshot['connection_authority']
    assert pin == {'version':model_fence.VERSION,'mode':'legacy_unregistered',
        'workspace_id':c['workspace'],'actor_id':c['user_id'],'brand_id':None,
        'source_id':c['connections']['a']['model']}
    assert 'connection_authority' not in public(row.engine_snapshot)
    async with Session() as db:
        for field in ('actor_id','workspace_id','source_id','mode','brand_id'):
            payload = {**row.engine_snapshot,'connection_authority':{**pin,field:uuid4().hex}}
            payload['sha256'] = digest({k:v for k,v in payload.items() if k!='sha256'})
            bad = SimpleNamespace(id=row.id,engine_snapshot=payload,workspace_id=row.workspace_id,
                                  session_id=row.session_id,brain_id=None)
            with pytest.raises(EngineFailure, match='engine_snapshot_incompatible'):
                await gateway_for_run(db, bad)
    assert calls['factory'] == 0
    await execute_run({}, rid)
    assert (await saved_run(rid))[0].status == 'completed'
    assert calls['stream'] == 1


@pytest.mark.parametrize('flag', [True, False])
async def test_workspace_resolver_unscoped_cannot_bypass_or_fallback(client, fenced, monkeypatch, flag):
    c, calls, _ = fenced
    await mapped(client, c, 'reference_revoked')
    monkeypatch.setattr(settings(), 'engine_contract_enabled', flag)
    def forbidden(*args):
        raise AssertionError('Must not decrypt')
    monkeypatch.setattr('pao.model_router.decrypt_key', forbidden)
    async with Session() as db:
        with pytest.raises(EngineFailure, match=model_fence.DENIED):
            await gateway_for_workspace(db, c['workspace'])
    if not flag:
        monkeypatch.setattr(settings(),'chat_features_enabled',False)
        response = await client.post('/v1/sessions', headers=c['owner'], json={'workspace_id':c['workspace']})
        result = await client.post('/v1/runs', headers=c['owner'], json={
            'session_id':response.json()['id'],'message':'fixture','request_key':uuid4().hex})
        assert result.status_code == 503 and result.json()['detail'] == model_fence.DENIED
    assert calls['factory'] == 0


async def test_explicit_local_still_works_not_automatic_cloud_fallback(client, fenced):
    c, _, _ = fenced
    await mapped(client, c)
    response = await client.post('/v1/sessions', headers=c['owner'], json={'workspace_id':c['workspace']})
    sid = response.json()['id']
    result = await client.put(f'/v1/sessions/{sid}/engine', headers=c['owner'], json={
        'provider':'ollama','model':'local-a','version':1})
    assert result.status_code == 200
    result = await client.post('/v1/runs', headers=c['owner'], json={
        'session_id':sid,'message':'explicit local','request_key':uuid4().hex})
    assert result.status_code == 202
    async with Session() as db:
        run = await db.get(Run, result.json()['id'])
        assert run.engine_snapshot['provider'] == 'ollama'
        assert 'connection_authority' not in run.engine_snapshot


@pytest.mark.parametrize('change', ['rotate','status','delete','removed','viewer','inactive'])
async def test_resolved_gateway_rechecks_source_and_actor_before_call(client, fenced, change):
    c,calls,_ = fenced
    rid,_ = await queued(client,c)
    async with Session() as db:
        gateway = await gateway_for_run(db,await db.get(Run,rid))
    async with Session.begin() as db:
        source = await db.get(ModelProviderConnection,c['connections']['a']['model'])
        if change == 'rotate': source.api_key_ciphertext = encrypt_key('changed-fixture')
        elif change == 'status': source.status = 'error'
        elif change == 'delete': await db.delete(source)
        elif change == 'inactive': (await db.get(User,c['user_id'])).active = False
        else:
            member = await db.get(Member,(c['workspace'],c['user_id']))
            if change == 'removed': await db.delete(member)
            else: member.role = 'viewer'
    expected = ('engine_connection_changed' if change == 'rotate' else
        'engine_connection_unavailable' if change in ('status','delete') else 'engine_connection_access_revoked')
    with pytest.raises(EngineFailure,match=expected):
        async for _ in gateway.stream([]): pass
    assert calls['factory'] == 1 and calls['stream'] == 0


@pytest.mark.parametrize('kind', ['stream', 'planner', 'extract'])
async def test_late_registration_result_dropped_and_stream_closed(client, fenced, monkeypatch, kind):
    c, calls, fake = fenced
    rid, _ = await queued(client, c)
    if kind == 'stream':
        async def stream(messages, max_tokens=None):
            calls['stream'] += 1
            try:
                await mapped(client, c)
                yield Chunk(text='late-sentinel-must-not-publish')
            finally:
                calls['closed'] += 1
        fake.stream = stream
    elif kind == 'planner':
        monkeypatch.setattr(settings(), 'agent_runtime_enabled', True)
        async def plan(messages):
            from pao.agents import ExecutionPlan
            calls['plan'] += 1
            await mapped(client, c)
            return ExecutionPlan(goal='late-sentinel',steps=[])
        fake.plan = plan
    else:
        async def extract(prompt):
            await mapped(client, c)
            return 'late-sentinel'
        fake.extract = extract
        async with Session() as db:
            # Isolated source-fence component test, not an unaccounted native
            # workspace resolver. The production runtime wraps this in ledger.
            gateway = (await gateway_for_run(db,await db.get(Run,rid))).gateway
        with pytest.raises(EngineFailure, match=model_fence.DENIED):
            await gateway.extract('fixture')
        return
    await execute_run({}, rid)
    result, events = await saved_run(rid)
    assert result.status == 'failed' and result.error_code == model_fence.DENIED
    assert result.response == '' and set(result.execution_plan or {}) <= {'javis_compat'}
    assert 'late-sentinel' not in str(result.execution_plan)
    assert not any(e.type in ('response.delta','response.completed','plan.created') for e in events)
    if kind == 'stream':
        assert calls['stream'] == calls['closed'] == 1
    else:
        assert calls['plan'] == 1 and calls['stream'] == 0


async def test_recheck_between_gateway_and_publication(client, fenced, monkeypatch):
    c, calls, _ = fenced
    rid, _ = await queued(client, c)
    original = model_fence.ModelFenceGateway.check
    checks = 0
    async def delayed(self):
        nonlocal checks
        await original(self)
        checks += 1
        if checks == 2:
            await mapped(client, c)
    monkeypatch.setattr(model_fence.ModelFenceGateway, 'check', delayed)
    await execute_run({}, rid)
    row, events = await saved_run(rid)
    assert row.error_code == model_fence.DENIED and row.status == 'failed'
    assert row.response == '' and not any(e.type == 'response.delta' for e in events)
    assert calls['closed'] == 1


async def test_midstream_keeps_earlier_partial_but_no_late_completed_or_memory(client, fenced):
    c, calls, fake = fenced
    rid, _ = await queued(client, c)
    async def stream(messages, max_tokens=None):
        try:
            yield Chunk(text='earlier-authorized-partial')
            await mapped(client, c)
            yield Chunk(text='late-sentinel')
        finally:
            calls['closed'] += 1
    fake.stream = stream
    await execute_run({}, rid)
    row, events = await saved_run(rid)
    assert row.status == 'failed' and row.error_code == model_fence.DENIED
    assert row.response == 'earlier-authorized-partial'
    assert not any(e.type == 'response.completed' for e in events)
    async with Session() as db:
        assert not await db.scalar(select(MemoryJob.run_id).where(MemoryJob.run_id == rid))
        message = await db.scalar(select(Message).where(Message.run_id == rid, Message.role == 'assistant'))
        assert message.status == 'failed'
    assert calls['closed'] == 1


@pytest.mark.parametrize('when', ['before', 'during'])
async def test_legacy_memory_no_credential_fallback_or_late_fact_publish(client, fenced, monkeypatch, when):
    from pao.memory import extract_memory
    from pao.memory_schemas import ExtractedFacts
    c, calls, fake = fenced
    rid, sid = await queued(client, c)
    await execute_run({}, rid)
    monkeypatch.setattr(settings(),'memory_enabled',True)
    monkeypatch.setattr(settings(),'chat_features_enabled',False)
    async with Session.begin() as db:
        chat = await db.get(ChatSession,sid)
        chat.memory_enabled = True
        db.add(MemoryJob(run_id=rid,workspace_id=c['workspace']))
    if when == 'before':
        await mapped(client,c)
    else:
        async def extract(prompt):
            calls['extract'] += 1
            await mapped(client,c)
            return ExtractedFacts(facts=[])
        fake.extract = extract
    await extract_memory({'memory_gateway':fake},rid)
    async with Session() as db:
        job = await db.get(MemoryJob,rid)
        assert job.status == 'failed' and job.error_code == (model_fence.DENIED if when=='before' else 'tenant_resource_accounting_required')
        assert job.attempts == 1 and job.extracted == 0
    assert calls['extract'] == 0 # Legacy never starts, even before a later revocation.


async def test_memory_real_legacy_resolver_denied_before_rotation_not_retried(client, fenced, monkeypatch):
    from pao.memory import extract_memory
    from pao.memory_schemas import ExtractedFacts
    c,calls,fake = fenced
    rid,sid = await queued(client,c)
    await execute_run({},rid)
    monkeypatch.setattr(settings(),'memory_enabled',True)
    monkeypatch.setattr(settings(),'chat_features_enabled',False)
    async with Session.begin() as db:
        (await db.get(ChatSession,sid)).memory_enabled = True
        db.add(MemoryJob(run_id=rid,workspace_id=c['workspace']))
    async def extract(prompt):
        calls['extract'] += 1
        async with Session.begin() as db:
            source = await db.get(ModelProviderConnection,c['connections']['a']['model'])
            source.api_key_ciphertext = encrypt_key('changed-during-extraction')
        return ExtractedFacts(facts=[])
    fake.extract = extract
    await extract_memory({},rid)
    async with Session() as db:
        job = await db.get(MemoryJob,rid)
        assert job.status == 'failed' and job.error_code == 'tenant_resource_accounting_required'
        assert job.attempts == 1 and job.extracted == 0
    assert calls['extract'] == 0 and calls['factory'] == 1


async def test_historical_snapshot_missing_pin_never_rewritten_or_implicit_grant(client, fenced):
    c,calls,_ = fenced
    rid,_ = await queued(client,c)
    row,_ = await saved_run(rid)
    value = {k:v for k,v in row.engine_snapshot.items() if k not in ('sha256','connection_authority')}
    value['sha256'] = digest(value)
    legacy = SimpleNamespace(id=row.id,engine_snapshot=value,workspace_id=row.workspace_id,
                             session_id=row.session_id,brain_id=None)
    async with Session() as db:
        gateway = await gateway_for_run(db,legacy)
    assert 'connection_authority' not in value
    await mapped(client,c)
    with pytest.raises(EngineFailure,match=model_fence.DENIED):
        async for _ in gateway.stream([]): pass
    assert calls['stream'] == 0 and 'connection_authority' not in value


@pytest.mark.parametrize('state', ['staged', 'reference_revoked'])
async def test_real_arq_queue_a_registered_denied_b_same_provider_succeeds(client, fenced, state):
    from arq import create_pool
    from arq.worker import create_worker
    from arq.connections import RedisSettings
    from arq.constants import job_key_prefix, in_progress_key_prefix, retry_key_prefix, result_key_prefix, default_queue_name
    c, calls, _ = fenced
    a, _ = await queued(client, c)
    b, _ = await queued(client, c, workspace=c['second'])
    await mapped(client, c, state)
    config = RedisSettings.from_dsn(settings().redis_url)
    assert config.database == 15
    queue = 'pao-test:s21b2a:'+uuid4().hex
    redis = await create_pool(config, default_queue_name=queue)
    runner = None
    ids = ['run:'+a,'run:'+b]
    class Workers:
        functions = [execute_run]
        redis_settings = config
        queue_name = queue
        handle_signals = False
        burst = True
        max_jobs = max_burst_jobs = 2
        keep_result = 0
        poll_delay = .05
        job_timeout = 20
    try:
        # Use the real admission-created payloads/IDs, moving only these owned
        # queue entries to our isolated worker queue (never rewrite job args).
        for jid in ids:
            assert await redis.exists(job_key_prefix+jid)
            score = await redis.zscore(default_queue_name,jid)
            assert score is not None
            await redis.zrem(default_queue_name,jid)
            await redis.zadd(queue,{jid:score})
        runner = create_worker(Workers)
        await asyncio.wait_for(runner.async_run(),25)
        assert runner.jobs_complete == 2 and runner.jobs_failed == 0
        denied,_ = await saved_run(a)
        allowed,_ = await saved_run(b)
        assert denied.status == 'failed' and denied.error_code == model_fence.DENIED
        assert allowed.status == 'completed' and allowed.response == 'safe-fixture-response'
        assert calls['factory'] == calls['stream'] == 1
    finally:
        if runner:
            if not hasattr(signal,'SIGUSR1'):
                runner.handle_sig(signal.SIGTERM)
                runner._handle_signals = True
            await runner.close()
        await redis.delete(queue,*(prefix+jid for jid in ids for prefix in (
            job_key_prefix,in_progress_key_prefix,retry_key_prefix,result_key_prefix)))
        await redis.aclose()
