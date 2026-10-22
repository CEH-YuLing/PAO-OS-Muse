"""M4.2 lease fencing/dedup/retry/permission gates; fixed internal consumer only."""
import asyncio
from datetime import timedelta
import os
import subprocess
import sys
import pytest
from sqlalchemy import select, func, text
from pao.config import settings
from pao.db import Session
from pao.models import BusinessOutbox, BusinessReceipt, Member, User, now, uid
from pao.modules.events import delivery


@pytest.fixture
def delivery_on(monkeypatch):
    monkeypatch.setattr(settings(), 'business_events_enabled', True)
    monkeypatch.setattr(settings(), 'business_event_delivery_enabled', True)


async def seed(client, identity):
    response = await client.post('/v1/tasks', headers=identity['owner'], json={
        'workspace_id': identity['workspace'], 'title': 'Synthetic delivery', 'status': 'completed',
        'success_criteria': ['Synthetic criteria'], 'evidence': [{'text': 'Synthetic evidence'}]})
    assert response.status_code == 201


async def state():
    async with Session() as db:
        row = await db.scalar(select(BusinessOutbox))
        return row, await db.scalar(select(func.count()).select_from(BusinessReceipt))


async def test_flag_off_no_claim(client, identity, monkeypatch):
    monkeypatch.setattr(settings(), 'business_events_enabled', True)
    await seed(client, identity)
    assert await delivery.claim() == []
    assert (await state())[0].attempts == 0


async def test_concurrent_claim_single_receipt_and_duplicate_ack(client, identity, delivery_on):
    await seed(client, identity)
    batches = await asyncio.gather(delivery.claim(), delivery.claim())
    pairs = [pair for batch in batches for pair in batch]
    assert len(pairs) == 1
    assert await delivery.consume(*pairs[0])
    assert not await delivery.consume(*pairs[0])
    row, count = await state()
    assert row.status == 'delivered' and row.delivered_at and count == 1
    # Re-delivery after a lost acknowledgement cannot duplicate the receipt.
    async with Session.begin() as db:
        row = await db.get(BusinessOutbox, row.id)
        row.status, row.delivered_at = 'pending', None
    assert await delivery.consume(*(await delivery.claim())[0])
    assert (await state())[1] == 1


async def test_expired_lease_stale_worker_fenced(client, identity, delivery_on):
    await seed(client, identity)
    old = (await delivery.claim())[0]
    async with Session.begin() as db:
        row = await db.get(BusinessOutbox, old[0]); row.lease_until = now() - timedelta(seconds=1)
    new = (await delivery.claim())[0]
    assert new[1] != old[1]
    assert not await delivery.consume(*old)
    await delivery.failed(*old)
    assert (await state())[0].lease_token == new[1]
    assert await delivery.consume(*new)


@pytest.mark.parametrize('loss', ['viewer', 'removed', 'inactive'])
async def test_permission_loss_after_claim(client, identity, delivery_on, loss):
    await seed(client, identity); pair = (await delivery.claim())[0]
    async with Session.begin() as db:
        member = await db.get(Member, (identity['workspace'], identity['user_id']))
        if loss == 'removed': await db.delete(member)
        elif loss == 'viewer': member.role = 'viewer'
        else: (await db.get(User, identity['user_id'])).active = False
    assert not await delivery.consume(*pair)
    row, count = await state()
    assert row.status == 'dead_letter' and row.error_code == 'actor_permission_changed' and count == 0


async def test_bounded_failure_backoff_and_no_error_payload(client, identity, delivery_on, monkeypatch):
    await seed(client, identity)
    async def explode(*args): raise RuntimeError('must-not-save-private-error')
    monkeypatch.setattr(delivery, 'consume', explode)
    for attempt in range(1, 6):
        pair = (await delivery.claim())[0]
        assert not await delivery.deliver_business_event({}, *pair)
        row, count = await state()
        assert row.attempts == attempt and row.error_code == 'consumer_failed' and count == 0
        if attempt < 5:
            assert row.status == 'pending' and row.available_at > now()
            assert await delivery.claim() == []
            async with Session.begin() as db:
                (await db.get(BusinessOutbox, row.id)).available_at = now() - timedelta(seconds=1)
    assert row.status == 'dead_letter' and await delivery.claim() == []


async def test_receipt_failure_rolls_back_ack(client, identity, delivery_on):
    await seed(client, identity); pair = (await delivery.claim())[0]
    # Scoped test-only trigger models storage failure AFTER receipt insertion.
    async with Session.begin() as db:
        await db.execute(text("CREATE FUNCTION pao_test_receipt_fail() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'synthetic'; END; $$ LANGUAGE plpgsql"))
        await db.execute(text('CREATE TRIGGER pao_test_receipt_fail AFTER INSERT ON business_receipts FOR EACH ROW EXECUTE FUNCTION pao_test_receipt_fail()'))
    try:
        assert not await delivery.deliver_business_event({}, *pair)
        row, count = await state()
        assert row.status == 'pending' and not row.delivered_at and count == 0
    finally:
        async with Session.begin() as db:
            await db.execute(text('DROP TRIGGER pao_test_receipt_fail ON business_receipts'))
            await db.execute(text('DROP FUNCTION pao_test_receipt_fail()'))


async def test_real_process_death_after_commit_recovers(client, identity, delivery_on):
    await seed(client, identity)
    env = {**os.environ, 'BUSINESS_EVENTS_ENABLED': 'true', 'BUSINESS_EVENT_DELIVERY_ENABLED': 'true'}
    code = "import asyncio,os; from pao.modules.events.delivery import claim; asyncio.run(claim(lease_seconds=1)); os._exit(91)"
    result = await asyncio.to_thread(subprocess.run, [sys.executable, '-c', code], env=env, timeout=20,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    assert result.returncode == 91, result.stderr.decode(errors='replace')
    row, count = await state(); assert row.status == 'processing' and count == 0
    await asyncio.sleep(1.2)
    assert await delivery.consume(*(await delivery.claim())[0])
    assert (await state())[1] == 1


async def test_enqueue_failure_durable_retry(client, identity, delivery_on):
    await seed(client, identity)
    class Unavailable:
        async def enqueue_job(self, *args, **kwargs): raise ConnectionError('Synthetic redis outage')
    await delivery.dispatch_business_events({'redis': Unavailable()})
    row, count = await state()
    assert row.status == 'pending' and row.attempts == 1 and count == 0


async def test_real_arq_redis_delivery(client, identity, delivery_on):
    from arq import create_pool
    from arq.connections import RedisSettings
    from arq.worker import create_worker
    from arq.constants import job_key_prefix, in_progress_key_prefix, retry_key_prefix, result_key_prefix
    from uuid import uuid4
    import signal
    await seed(client, identity)
    config = RedisSettings.from_dsn(settings().redis_url); assert config.database == 15
    queue = 'pao-test:m4-events:' + str(uuid4())
    redis = await create_pool(config, default_queue_name=queue); runner = None; jid = None
    class EventWorker:
        functions = [delivery.deliver_business_event]
        redis_settings = config
        queue_name = queue
        handle_signals = False
        burst = True
        max_jobs = max_burst_jobs = 1
        keep_result = 0
        poll_delay = .05
        job_timeout = 20
    try:
        await delivery.dispatch_business_events({'redis': redis})
        row, count = await state(); jid = f'business-event:{row.id}:{row.lease_token}'
        assert await redis.exists(job_key_prefix + jid)
        runner = create_worker(EventWorker)
        await asyncio.wait_for(runner.async_run(), 25)
        row, count = await state(); assert row.status == 'delivered' and count == 1
    finally:
        if runner:
            if not hasattr(signal, 'SIGUSR1'):
                runner.handle_sig(signal.SIGTERM); runner._handle_signals = True
            await runner.close()
        if jid:
            await redis.delete(queue, *(prefix + jid for prefix in
                (job_key_prefix, in_progress_key_prefix, retry_key_prefix, result_key_prefix)))
        await redis.aclose()
