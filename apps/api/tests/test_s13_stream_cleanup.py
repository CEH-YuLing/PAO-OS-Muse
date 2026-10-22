"""Real PostgreSQL cancellation probes; never a model or production database."""
import asyncio
import logging
import socket
import time
from contextlib import aclosing
from uuid import UUID, uuid4

import anyio
import httpx
import pytest
import pytest_asyncio
import uvicorn
from sqlalchemy import text

from pao import core_api
from pao.auth import Principal
from pao.db import Session, engine
from pao.main import app
from pao.models import Member, Run, Workspace, now
from pao.modules.conversations.state import emit
from p63_browser_acceptance import OwnedServer


@pytest.fixture
def sql_probe_pins():
    return []


async def pin_sql_probe(connection, pins, query):
    row = (await connection.execute(text(
        'SELECT pid,backend_start FROM pg_stat_activity WHERE pid=pg_backend_pid()'))).one()
    pins.append((row.pid, row.backend_start, query))


async def cleanup_sql_probes(pins):
    # A deliberately failing regression must not leave an orphan transaction
    # blocking the next fixture's TRUNCATE. Never terminate an arbitrary session.
    assert engine.url.database == 'pao_test'
    async with asyncio.timeout(5), engine.connect() as db:
        for pid, started, query in pins:
            await db.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE pid=:pid AND backend_start=:started AND datname=current_database() "
                "AND usename=current_user AND query=:query "
                "AND state IN ('active','idle in transaction')"),
                {'pid': pid, 'started': started, 'query': query})


@pytest_asyncio.fixture(autouse=True)
async def cleanup_owned_sql_probes(sql_probe_pins, client):
    yield
    if sql_probe_pins:
        await cleanup_sql_probes(sql_probe_pins)


async def live_run(client, identity):
    response = await client.post('/v1/sessions', headers=identity['owner'],
                                 json={'workspace_id': identity['workspace']})
    assert response.status_code == 201
    async with Session.begin() as db:
        run = Run(workspace_id=identity['workspace'], session_id=response.json()['id'],
                  request_key=uuid4().hex, prompt='Synthetic S13', status='running', started_at=now())
        db.add(run)
        await db.flush()
        emit(db, run, 'response.delta', {'text': 'S13_ALLOWED_INITIAL'})
        return run.id


class Connected:
    headers = {}

    async def is_disconnected(self):
        return False


async def test_cancel_scope_during_database_poll_returns_connection(client, identity, monkeypatch, caplog, sql_probe_pins):
    """Deterministically cancel WHILE asyncpg is in use, as an ASGI disconnect does."""
    rid = await live_run(client, identity)
    who = Principal(identity['user_id'], int(time.time()) + 60)
    async with Session() as db:
        response = await core_api.events(UUID(rid), Connected(), after=0, who=who, db=db)
    original = core_api.owned_run
    caplog.set_level(logging.ERROR, logger='sqlalchemy.pool')
    # Repeat rather than rely on racing a browser's timing against a tiny SQL query.
    for _ in range(6):
        entered = asyncio.Event()

        async def delayed(connection, *args, **kwargs):
            value = await original(connection, *args, **kwargs)
            await pin_sql_probe(connection, sql_probe_pins, 'SELECT pg_sleep(0.15)')
            entered.set()
            await connection.execute(text('SELECT pg_sleep(0.15)'))
            return value

        monkeypatch.setattr(core_api, 'owned_run', delayed)

        async def drain():
            async with aclosing(response.body_iterator) as iterator:
                async for _ in iterator:
                    await asyncio.sleep(0)

        async with anyio.create_task_group() as group:
            group.start_soon(drain)
            await asyncio.wait_for(entered.wait(), 3)
            group.cancel_scope.cancel()
        await asyncio.sleep(.05)
        assert engine.pool.checkedout() == 0
        # Obtain a fresh iterator using the actual route, not synthetic event JSON.
        monkeypatch.setattr(core_api, 'owned_run', original)
        async with Session() as db:
            response = await core_api.events(UUID(rid), Connected(), after=0, who=who, db=db)
    await response.body_iterator.aclose()
    assert not [r for r in caplog.records if r.name.startswith('sqlalchemy.pool') and r.levelno >= logging.ERROR]
    async with Session() as db:
        assert await db.scalar(text('SELECT 1')) == 1


async def test_real_http_stream_abort_and_membership_revoke(client, identity):
    rid = await live_run(client, identity)
    async with Session.begin() as db:
        second = Workspace(name='S13 B remains available')
        db.add(second)
        await db.flush()
        db.add(Member(workspace_id=second.id, user_id=identity['user_id'], role='owner'))
        bid = second.id
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    server = OwnedServer(uvicorn.Config(app, host='127.0.0.1', port=port,
                                       lifespan='off', access_log=False, log_level='error'))
    task = asyncio.create_task(server.serve(sockets=[sock]))
    try:
        async with asyncio.timeout(5):
            while not server.started:
                if task.done():
                    await task
                await asyncio.sleep(.05)
        async with httpx.AsyncClient(base_url=f'http://127.0.0.1:{port}', timeout=5) as http:
            path = f'/v1/runs/{rid}/events'
            for _ in range(8):
                async with http.stream('GET', path, headers=identity['owner']) as response:
                    assert response.status_code == 200
                    lines = response.aiter_lines()
                    async with asyncio.timeout(3):
                        while 'S13_ALLOWED_INITIAL' not in await anext(lines):
                            pass
                # Actual transport closes without cancelling the server-side run.
            async with http.stream('GET', path, headers=identity['owner']) as response:
                lines = response.aiter_lines()
                while 'S13_ALLOWED_INITIAL' not in await anext(lines):
                    pass
                async with Session.begin() as db:
                    await db.delete(await db.get(Member, (identity['workspace'], identity['user_id'])))
                    run = await db.get(Run, rid, with_for_update=True)
                    emit(db, run, 'response.delta', {'text': 'S13_DENIED_AFTER_REVOKE'})
                async with asyncio.timeout(3):
                    tail = '\n'.join([line async for line in lines])
                assert 'S13_DENIED_AFTER_REVOKE' not in tail
            assert (await http.get(path, headers=identity['owner'])).status_code == 404
            assert (await http.get(f'/v1/workspaces/{bid}/context', headers=identity['owner'])).status_code == 200
        async with asyncio.timeout(3):
            while engine.pool.checkedout():
                await asyncio.sleep(.05)
        async with Session() as db:
            run = await db.get(Run, rid)
            assert run.status == 'running' and not run.cancel_requested
            assert await db.scalar(text('SELECT 1')) == 1
    finally:
        server.should_exit = True
        try:
            await asyncio.wait_for(task, 5)
        finally:
            sock.close()


async def test_database_poll_timeout_ends_stream_and_cleans_pool(client, identity, monkeypatch, caplog, sql_probe_pins):
    rid = await live_run(client, identity)
    who = Principal(identity['user_id'], int(time.time()) + 60)
    async with Session() as db:
        response = await core_api.events(UUID(rid), Connected(), after=0, who=who, db=db)
    original = core_api.owned_run

    async def stalled(connection, *args, **kwargs):
        await original(connection, *args, **kwargs)
        await pin_sql_probe(connection, sql_probe_pins, 'SELECT pg_sleep(10)')
        await connection.execute(text('SELECT pg_sleep(10)'))

    monkeypatch.setattr(core_api, 'owned_run', stalled)
    caplog.set_level(logging.ERROR, logger='sqlalchemy.pool')
    started = time.monotonic()
    async with asyncio.timeout(8):
        async with aclosing(response.body_iterator) as iterator:
            assert [item async for item in iterator] == []
    assert 4.5 <= time.monotonic() - started < 8
    assert engine.pool.checkedout() == 0
    assert not [r for r in caplog.records if r.name.startswith('sqlalchemy.pool') and r.levelno >= logging.ERROR]
    async with Session() as db:
        assert await db.scalar(text('SELECT 1')) == 1
        assert await db.scalar(text("SELECT count(*) FROM pg_stat_activity "
            "WHERE datname=current_database() AND pid<>pg_backend_pid() "
            "AND state IN ('active','idle in transaction') AND query='SELECT pg_sleep(10)'")) == 0
