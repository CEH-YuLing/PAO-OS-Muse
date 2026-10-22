"""S1.3 executable corpus: two SMEs, shared owner, A-only and B-only actors.

Fixtures persist in pao_test; gateways/transports are spies, never external APIs.
Explicitly authorized A reads by the shared owner are allowed, not an IDOR.
"""
import asyncio
from uuid import uuid4
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from pao.config import settings
from pao.db import Session
from pao.models import (Brand, Brain, ChatSession, BusinessOutbox, BusinessReceipt,
                        ChannelOutbox, KnowledgeIngestion, Member, MemoryJob, Run,
                        Message, User, Workspace)
from pao.memory import extract_memory
from pao.runtime import execute_run
from pao.modules.conversations.state import emit
from pao.modules.knowledge import worker, service
from pao.modules.events import delivery
from pao.modules.channels import service as channels
from test_brain_manager import create, brains_on
from test_brain_files import upload
from test_knowledge_sources import make_file_source, sources_on
from test_knowledge_workspace import source, p2_on
from test_business_delivery import seed, delivery_on
from test_channels import binding, control, channels_on
from test_durable_admission import gates
from test_result_outbox import pending


@pytest_asyncio.fixture
async def two_smes(identity):
    async with Session.begin() as db:
        b = Workspace(name='S13 SME B')
        db.add(b)
        await db.flush()
        b_only = await db.scalar(select(User).where(User.email == 'outside@example.test'))
        db.add_all([Member(workspace_id=b.id, user_id=identity['user_id'], role='owner'),
                    Member(workspace_id=b.id, user_id=b_only.id, role='owner')])
        b_id = b.id
    return {**identity, 'workspace': b_id}


async def revoke(workspace, user_id, loss):
    async with Session.begin() as db:
        member = await db.get(Member, (workspace, user_id))
        if loss == 'removed':
            await db.delete(member)
        else:
            member.role = 'viewer'


async def chat_record(client, who, marker, status='completed'):
    row = await client.post('/v1/sessions', headers=who['owner'], json={
        'workspace_id': who['workspace'], 'title': 'S13 same keyword', 'memory_enabled': False})
    assert row.status_code == 201
    async with Session.begin() as db:
        run = Run(workspace_id=who['workspace'], session_id=row.json()['id'], request_key=uuid4().hex,
                  prompt=marker, status=status, response=marker)
        db.add(run)
        await db.flush()
        db.add(Message(workspace_id=who['workspace'], session_id=run.session_id, run_id=run.id,
                       role='user', content=marker))
        emit(db, run, 'response.delta', {'text': marker})
        return run.session_id, run.id


async def test_shared_actor_lists_search_export_and_tasks_remain_scoped(client, identity, two_smes, monkeypatch):
    monkeypatch.setattr(settings(), 'engine_contract_enabled', True)
    monkeypatch.setattr(settings(), 'chat_features_enabled', True)
    a_session, a_run = await chat_record(client, identity, 'TENANT_A_SENTINEL')
    b_session, _ = await chat_record(client, two_smes, 'TENANT_B_SENTINEL')
    for who, sid, wanted, denied in ((identity, a_session, 'TENANT_A_SENTINEL', 'TENANT_B_SENTINEL'),
                                    (two_smes, b_session, 'TENANT_B_SENTINEL', 'TENANT_A_SENTINEL')):
        h = who['owner']
        assert [r['id'] for r in (await client.get('/v1/sessions', headers=h,
                params={'workspace_id': who['workspace']})).json()] == [sid]
        assert [r['id'] for r in (await client.get('/v1/chat/sessions', headers=h,
                params={'workspace_id': who['workspace'], 'q': 'same keyword'})).json()] == [sid]
        exported = await client.get(f'/v1/sessions/{sid}/export', headers=h)
        assert exported.status_code == 200 and wanted in exported.text and denied not in exported.text
        made = await client.post('/v1/tasks', headers=h, json={'workspace_id': who['workspace'], 'title': wanted})
        assert made.status_code == 201
        tasks = await client.get('/v1/tasks', headers=h, params={'workspace_id': who['workspace']})
        assert wanted in tasks.text and denied not in tasks.text
    # Authorized explicit A reads remain valid even when the actor also belongs to B.
    assert (await client.get(f'/v1/runs/{a_run}', headers=two_smes['owner'])).status_code == 200
    # A-only cannot enumerate B; B-only cannot see A, including export/usage/history.
    for actor, who, sid, rid in ((identity['other'], two_smes, b_session, None),
                                 (identity['outsider'], identity, a_session, a_run)):
        paths = [f"/v1/sessions?workspace_id={who['workspace']}", f'/v1/sessions/{sid}',
                 f'/v1/sessions/{sid}/export', f'/v1/sessions/{sid}/compactions',
                 f"/v1/chat/usage?workspace_id={who['workspace']}", f"/v1/tasks?workspace_id={who['workspace']}"]
        if rid:
            paths += [f'/v1/runs/{rid}', f'/v1/runs/{rid}/events', f'/v1/runs/{rid}/usage']
        for path in paths:
            response = await client.get(path, headers=actor)
            assert response.status_code == 404, path
            assert 'TENANT_' not in response.text


async def test_private_brain_parent_ids_files_and_archive_do_not_cross_sme(client, identity, two_smes, sources_on):
    a, file_a, src_a = await make_file_source(client, identity)
    b, file_b, _ = await make_file_source(client, two_smes)
    h = identity['owner']
    # Shared owner has both permissions, but a source/file in A cannot be addressed under B.
    wrong = [f'files/{file_a["id"]}/download', f'files/{file_a["id"]}/preview',
             f'sources/{src_a["id"]}/versions', f'sources/{src_a["id"]}/versions/1/preview',
             f'ingestion-jobs/{src_a["job_id"]}']
    for suffix in wrong:
        response = await client.get(f'/v1/brains/{b}/{suffix}', headers=h)
        assert response.status_code == 404 and file_a['sha256'] not in response.text
    assert (await client.post(f'/v1/brains/{b}/sources', headers=h,
            json={'kind': 'file', 'origin_id': file_a['id']})).status_code == 404
    assert (await client.get(f'/v1/brains/{b}/files/{file_b["id"]}/download', headers=h)).status_code == 200
    # A workspace owner does not inherit access to someone else's private Brain.
    async with Session.begin() as db:
        other = await db.scalar(select(User).where(User.email == 'other@example.test'))
        (await db.get(Member, (identity['workspace'], other.id))).role = 'owner'
    for actor, bid, fid in ((identity['other'], a, file_a['id']), (identity['outsider'], a, file_a['id']),
                            (identity['other'], b, file_b['id']), (identity['outsider'], b, file_b['id'])):
        for suffix in ('files', f'files/{fid}/download', f'files/{fid}/preview', 'notes', 'sources', 'export', 'memory'):
            response = await client.get(f'/v1/brains/{bid}/{suffix}', headers=actor)
            assert response.status_code == 404, suffix
            assert file_a['sha256'] not in response.text


async def test_identical_search_terms_retrieve_only_current_brain(client, identity, two_smes, p2_on):
    a, _, src_a, chunks_a, _ = await source(client, identity, content=b'S13 matching term PRIVATE_A')
    b, _, src_b, chunks_b, _ = await source(client, two_smes, content=b'S13 matching term PRIVATE_B')
    for bid, wanted, denied, src in ((a, 'PRIVATE_A', 'PRIVATE_B', src_a), (b, 'PRIVATE_B', 'PRIVATE_A', src_b)):
        response = await client.post(f'/v1/brains/{bid}/retrieval', headers=identity['owner'],
                                     json={'query': 'matching term'})
        assert response.status_code == 200 and wanted in response.text and denied not in response.text
        assert {r['source_id'] for r in response.json()['items']} == {src['id']}
    for bid, foreign in ((a, chunks_b[0]['chunk_id']), (b, chunks_a[0]['chunk_id'])):
        assert (await client.get(f'/v1/brains/{bid}/chunks/{foreign}', headers=identity['owner'])).status_code == 404
    await revoke(identity['workspace'], identity['user_id'], 'removed')
    assert (await client.post(f'/v1/brains/{a}/retrieval', headers=identity['owner'],
                             json={'query': 'matching term'})).status_code == 404
    assert (await client.post(f'/v1/brains/{b}/retrieval', headers=identity['owner'],
                             json={'query': 'matching term'})).status_code == 200


async def test_cross_tenant_parent_constraints_and_brand_binding(client, identity, two_smes, brains_on):
    async with Session.begin() as db:
        brand = Brand(workspace_id=two_smes['workspace'], name='Same brand name')
        db.add(brand)
        await db.flush()
        brand_id = brand.id
    assert (await client.post('/v1/sessions', headers=identity['owner'], json={
        'workspace_id': identity['workspace'], 'brand_id': brand_id})).status_code == 404
    assert (await client.post('/v1/brains', headers=identity['owner'], json={
        'workspace_id': identity['workspace'], 'brand_id': brand_id, 'name': 'Invalid'})).status_code == 404
    sid, _ = await chat_record(client, identity, 'Valid A')
    for model in (Brain(workspace_id=identity['workspace'], owner_id=identity['user_id'], brand_id=brand_id, name='Invalid'),
                  Run(workspace_id=two_smes['workspace'], session_id=sid, request_key=uuid4().hex, prompt='Invalid')):
        async with Session() as db:
            db.add(model)
            with pytest.raises(IntegrityError):
                await db.flush()
            await db.rollback()


@pytest.mark.parametrize('loss', ['removed', 'viewer'])
async def test_queued_run_and_memory_deny_before_provider_with_other_sme_intact(client, identity, two_smes, monkeypatch, loss):
    sid, rid = await chat_record(client, identity, 'Never send to model', status='queued')
    memory_sid, memory_rid = await chat_record(client, identity, 'Completed input awaiting memory extraction')
    async with Session.begin() as db:
        (await db.get(ChatSession, memory_sid)).memory_enabled = True
        run = await db.get(Run, memory_rid)
        db.add(MemoryJob(run_id=run.id, workspace_id=run.workspace_id, status='queued'))
    await revoke(identity['workspace'], identity['user_id'], loss)
    gateway = AsyncMock()
    resolver = AsyncMock(side_effect=AssertionError('Denied actor must not resolve credentials'))
    monkeypatch.setattr('pao.runtime.gateway_for_workspace', resolver)
    monkeypatch.setattr('pao.runtime.gateway_for_run', resolver)
    local_factory=Mock(side_effect=AssertionError('Denied memory actor must not construct pinned adapter'))
    monkeypatch.setattr('pao.memory.OllamaGateway', local_factory)
    await execute_run({'gateway': gateway}, rid)
    monkeypatch.setattr(settings(), 'memory_enabled', True)
    await extract_memory({'memory_gateway': gateway}, memory_rid)
    resolver.assert_not_awaited()
    local_factory.assert_not_called()
    gateway.stream.assert_not_called()
    gateway.extract.assert_not_awaited()
    async with Session() as db:
        run = await db.get(Run, rid)
        job = await db.scalar(select(MemoryJob).where(MemoryJob.run_id == memory_rid))
        assert run.status == job.status == 'failed' and run.error_code == job.error_code == 'access_revoked'
        assert (await db.get(Run, memory_rid)).status == 'completed'
    assert (await client.post('/v1/sessions', headers=identity['owner'], json={
        'workspace_id': two_smes['workspace']})).status_code == 201


@pytest.mark.parametrize('loss', ['removed', 'viewer'])
async def test_queued_ingestion_denies_parser_without_borrowing_other_membership(client, identity, two_smes, sources_on, monkeypatch, loss):
    _, _, src = await make_file_source(client, identity)
    await revoke(identity['workspace'], identity['user_id'], loss)
    parse = Mock(side_effect=AssertionError('Revoked source must not be parsed'))
    monkeypatch.setattr(service, 'parse_text', parse)
    await worker.ingest_source({}, src['job_id'])
    parse.assert_not_called()
    async with Session() as db:
        job = await db.get(KnowledgeIngestion, src['job_id'])
        assert job.status == 'failed' and job.parsed_text is None and job.error_code == 'source_access_unavailable'
    assert (await client.get(f"/v1/workspaces/{two_smes['workspace']}/context", headers=identity['owner'])).status_code == 200


async def test_ingestion_revoke_during_parse_cannot_publish_in_either_sme(client, identity, two_smes, sources_on, monkeypatch):
    _, _, src = await make_file_source(client, identity)
    entered, release = asyncio.Event(), asyncio.Event()
    original = asyncio.to_thread

    async def paused(fn, *args):
        entered.set()
        await release.wait()
        return await original(fn, *args)

    monkeypatch.setattr(worker.asyncio, 'to_thread', paused)
    task = asyncio.create_task(worker.ingest_source({}, src['job_id']))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        await revoke(identity['workspace'], identity['user_id'], 'removed')
        release.set()
        await asyncio.wait_for(task, 5)
    finally:
        release.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    async with Session() as db:
        job = await db.get(KnowledgeIngestion, src['job_id'])
        assert job.status == 'failed' and job.parsed_text is None
        assert await db.scalar(select(func.count()).select_from(KnowledgeIngestion).where(
            KnowledgeIngestion.workspace_id == two_smes['workspace'])) == 0


@pytest.mark.parametrize('loss', ['removed', 'viewer'])
async def test_claimed_business_event_does_not_use_other_sme_role(client, identity, two_smes, delivery_on, loss):
    await seed(client, identity)
    pair = (await delivery.claim())[0]
    await revoke(identity['workspace'], identity['user_id'], loss)
    assert not await delivery.consume(*pair)
    async with Session() as db:
        assert (await db.get(BusinessOutbox, pair[0])).error_code == 'actor_permission_changed'
        assert await db.scalar(select(func.count()).select_from(BusinessReceipt)) == 0
    await seed(client, two_smes)
    assert await delivery.consume(*(await delivery.claim())[0])


@pytest.mark.parametrize('loss', ['removed', 'viewer'])
async def test_pending_result_denies_revoked_sender_in_a_b_still_member(client, identity, two_smes, gates, monkeypatch, loss):
    from pao.models import ResultDelivery
    from pao.modules.results import outbox
    _, _, row = await pending(client, identity, monkeypatch)
    await revoke(identity['workspace'], identity['user_id'], loss)
    await outbox.dispatch_results()
    async with Session() as db:
        saved = await db.get(ResultDelivery, row['id'])
        assert saved.status == 'failed' and saved.delivered_at is None
        assert saved.error_code == 'sender_permission_lost'
    assert (await client.get('/v1/results', headers=identity['owner'],
            params={'workspace_id': two_smes['workspace']})).json() == []


@pytest.mark.parametrize('loss', ['removed', 'viewer'])
async def test_channel_pending_send_denied_before_transport_with_b_intact(client, identity, two_smes, channels_on, loss):
    row, _ = await binding(client, identity, external_identity='s13-' + uuid4().hex)
    row = await control(client, identity, row, 'human')
    response = await client.post(f"/v1/channels/bindings/{row['id']}/reply", headers=identity['owner'],
                                 json={'request_key': str(uuid4()), 'text': 'Synthetic private A reply'})
    assert response.status_code == 201
    await revoke(identity['workspace'], identity['user_id'], loss)
    send = AsyncMock(side_effect=AssertionError('Revoked actor must not call transport'))
    await channels.send_one(send, 'local')
    send.assert_not_awaited()
    async with Session() as db:
        assert (await db.get(ChannelOutbox, response.json()['id'])).status == 'cancelled'
    assert (await client.get('/v1/channels/bindings', headers=identity['owner'],
                            params={'workspace_id': two_smes['workspace']})).json() == []


@pytest.mark.parametrize('loss', ['removed', 'viewer'])
async def test_real_arq_queue_revoke_a_before_worker_b_still_parses(client, identity, two_smes, sources_on, monkeypatch, loss):
    """Enqueue first, commit permission change, THEN start the real Redis worker."""
    import signal
    from arq import create_pool
    from arq.connections import RedisSettings
    from arq.worker import create_worker
    from arq.constants import job_key_prefix, in_progress_key_prefix, retry_key_prefix, result_key_prefix
    _, _, a = await make_file_source(client, identity)
    _, _, b = await make_file_source(client, two_smes)
    config = RedisSettings.from_dsn(settings().redis_url)
    assert config.database == 15
    queue = 'pao-test:s13:' + uuid4().hex
    redis = await create_pool(config, default_queue_name=queue)
    runner = None
    ids = [f"source:{row['job_id']}:0" for row in (a, b)]
    parse = Mock(wraps=service.parse_text)
    monkeypatch.setattr(service, 'parse_text', parse)

    class SourceWorker:
        functions = [worker.ingest_source]
        redis_settings = config
        queue_name = queue
        handle_signals = False
        burst = True
        max_jobs = max_burst_jobs = 2
        keep_result = 0
        poll_delay = .05
        job_timeout = 20

    try:
        await worker.dispatch_sources({'redis': redis})
        assert all([await redis.exists(job_key_prefix + jid) for jid in ids])
        await revoke(identity['workspace'], identity['user_id'], loss)
        runner = create_worker(SourceWorker)
        await asyncio.wait_for(runner.async_run(), 25)
        async with Session() as db:
            denied = await db.get(KnowledgeIngestion, a['job_id'])
            allowed = await db.get(KnowledgeIngestion, b['job_id'])
            assert denied.status == 'failed' and denied.parsed_text is None
            assert denied.error_code == 'source_access_unavailable'
            assert allowed.status == 'completed' and allowed.workspace_id == two_smes['workspace']
            assert parse.call_count == 1
    finally:
        if runner:
            if not hasattr(signal, 'SIGUSR1'):
                runner.handle_sig(signal.SIGTERM)
                runner._handle_signals = True
            await runner.close()
        await redis.delete(queue, *(prefix + jid for jid in ids for prefix in
            (job_key_prefix, in_progress_key_prefix, retry_key_prefix, result_key_prefix)))
        await redis.aclose()
