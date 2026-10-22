"""S1.2: real HTTP/SSE/export with pao_test events; no model or external writes."""
import asyncio
from uuid import uuid4

from pao.config import ROOT, settings
from pao.db import Session
from pao.main import app
from pao.models import Member, Message, Run, Workspace, now
from pao.modules.conversations.state import emit
from p6_browser_harness import browser


async def test_client_scope_stream_export_membership(client, identity, monkeypatch):
    monkeypatch.setattr(settings(), 'chat_features_enabled', True)
    monkeypatch.setattr(settings(), 'engine_contract_enabled', True)
    directory = ROOT / '.runtime' / ('s12-handshake-' + uuid4().hex)
    directory.mkdir()
    async with Session.begin() as db:
        second = Workspace(name='S12 enterprise B')
        db.add(second)
        await db.flush()
        second_id = second.id
        db.add(Member(workspace_id=second_id, user_id=identity['user_id'], role='owner'))
    chats = {}
    for label, workspace in (('stream A', identity['workspace']), ('export A', identity['workspace']), ('chat B', second_id)):
        result = await client.post('/v1/sessions', headers=identity['owner'], json={
            'workspace_id': workspace, 'title': 'S12 ' + label, 'memory_enabled': False})
        assert result.status_code == 201
        chats[label] = result.json()['id']
    async with Session.begin() as db:
        stream = Run(workspace_id=identity['workspace'], session_id=chats['stream A'],
                     request_key=uuid4().hex, prompt='Synthetic S12 stream', status='running',
                     response='S12 initial private A', started_at=now())
        export = Run(workspace_id=identity['workspace'], session_id=chats['export A'],
                     request_key=uuid4().hex, prompt='Synthetic S12 export', status='completed')
        db.add_all([stream, export])
        await db.flush()
        emit(db, stream, 'run.started')
        emit(db, stream, 'response.delta', {'text': stream.response})
        db.add(Message(workspace_id=identity['workspace'], session_id=export.session_id,
                       run_id=export.id, role='user', content='S12 private export A ' + 'x' * 131072))
        run_id = stream.id

    profile = await client.get(f"/v1/sessions/{chats['export A']}/chat", headers=identity['owner'])
    assert profile.status_code == 200 and profile.json()['available'] is True

    async def wait_marker(name, timeout=240):
        async with asyncio.timeout(timeout):
            while not (directory / name).exists():
                await asyncio.sleep(.05)

    async def changes():
        await wait_marker('late')
        async with Session.begin() as db:
            run = await db.get(Run, run_id, with_for_update=True)
            assert run.workspace_id == identity['workspace'] and not run.cancel_requested
            run.response += ' S12 late private A'
            emit(db, run, 'response.delta', {'text': ' S12 late private A'})
        (directory / 'late.done').touch()
        await wait_marker('role')
        async with Session.begin() as db:
            member = await db.get(Member, (identity['workspace'], identity['user_id']))
            member.role = 'viewer'
        (directory / 'role.done').touch()
        await wait_marker('revoke')
        async with Session.begin() as db:
            member = await db.get(Member, (identity['workspace'], identity['user_id']))
            await db.delete(member)
        (directory / 'revoke.done').touch()

    # Forward the genuine export, but pause its body after the first 64 KiB.
    # No route.fulfill/mock JSON: Next's rewrite and browser fetch stay streaming.
    original = app.middleware_stack
    async def slow_export(scope, receive, send):
        held = False
        async def delayed(message):
            nonlocal held
            if scope.get('path') == f"/v1/sessions/{chats['export A']}/export" and message['type'] == 'http.response.body' and not held:
                held = True
                body = message.get('body', b'')
                assert len(body) > 65536
                await send({**message, 'body': body[:65536], 'more_body': True})
                (directory / 'export.ready').touch()
                await wait_marker('export.release')
                await send({**message, 'body': body[65536:]})
            else:
                await send(message)
        await original(scope, receive, delayed)
    monkeypatch.setattr(app, 'middleware_stack', slow_export)
    task = asyncio.create_task(changes())
    try:
        report = await browser('scripts/verify_s12_browser.cjs', 'PAO_S12_BROWSER_FIXTURE', {
            'workspace': identity['workspace'], 'second': second_id, 'actor': identity['user_id'],
            'stream': chats['stream A'], 'export': chats['export A'], 'run': run_id,
            'markers': str(directory),
        }, 's12', direct_proxy=True)
        await asyncio.wait_for(task,5)
        assert report['stream_scope'] and report['raw_body_discarded'] and report['membership_revoked']
    finally:
        (directory / 'export.release').touch()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        async with Session.begin() as db:
            run = await db.get(Run, run_id, with_for_update=True)
            run.status = 'completed'
            run.finished_at = now()
            emit(db, run, 'run.completed')
