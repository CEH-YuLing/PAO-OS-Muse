import asyncio
import json
from datetime import datetime
from uuid import UUID
import pytest
from starlette.routing import Route
from pao.modules.operations.request_trace import RequestTrace, bind_actor, bind_workspace

ACTOR = '11111111-1111-4111-8111-111111111111'
WORKSPACE = '22222222-2222-4222-8222-222222222222'
OTHER = '33333333-3333-4333-8333-333333333333'

async def invoke(app, **overrides):
    messages = []
    scope = {'type': 'http', 'method': 'POST', 'path': '/raw-secret',
             'query_string': b'key=private-key', 'client': ('127.0.0.1', 1234),
             'headers': [(b'authorization', b'Bearer private-token'),
                         (b'x-request-id', b'fake-id'), (b'x-forwarded-for', b'198.51.100.55'),
                         (b'x-workspace-id', OTHER.encode())], **overrides}
    async def receive(): return {'type': 'http.request', 'body': b'private-body'}
    async def send(message): messages.append(message)
    await RequestTrace(app)(scope, receive, send)
    return messages

async def respond(scope, receive, send):
    await send({'type': 'http.response.start', 'status': 200,
                'headers': [(b'x-request-id', b'forged-by-inner-app')]})
    await send({'type': 'http.response.body', 'body': b'private-response'})

def records(caplog):
    return [json.loads(r.message) for r in caplog.records if r.name == 'pao.request']

async def test_verified_identity_route_and_safe_source_only(caplog):
    async def app(scope, receive, send):
        scope['route'] = Route('/v1/workspaces/{workspace_id}/items/{item_id}', respond)
        bind_actor(ACTOR); bind_workspace(WORKSPACE)
        await respond(scope, receive, send)
    with caplog.at_level('INFO', logger='pao.request'):
        messages = await invoke(app)
    record = records(caplog)[-1]
    assert record['actor_id'] == ACTOR and record['workspace_id'] == WORKSPACE
    assert record['route'] == '/v1/workspaces/{workspace_id}/items/{item_id}'
    assert record['client_ip'] == '127.0.0.1' and record['client_source'] == 'asgi_scope'
    assert datetime.fromisoformat(record['timestamp']) >= datetime.fromisoformat(record['started_at'])
    assert UUID(record['request_id']).hex == record['request_id']
    assert (b'x-request-id', record['request_id'].encode()) in messages[0]['headers']
    assert len([h for h in messages[0]['headers'] if h[0] == b'x-request-id']) == 1
    for secret in ('private-key', 'private-token', 'private-body', 'private-response',
                   '/raw-secret', 'fake-id', 'forged-by-inner-app', '198.51.100.55', OTHER):
        assert secret not in caplog.text

async def test_concurrent_context_isolation_and_reset(caplog):
    ready = asyncio.Event()
    async def first(scope, receive, send):
        bind_actor(ACTOR); bind_workspace(WORKSPACE); ready.set()
        await asyncio.sleep(.01)
        await respond(scope, receive, send)
    async def second(scope, receive, send):
        await ready.wait(); bind_actor(OTHER)
        await respond(scope, receive, send)
    with caplog.at_level('INFO', logger='pao.request'):
        await asyncio.gather(invoke(first), invoke(second))
        await invoke(respond)
    by_actor = {r['actor_id']: r for r in records(caplog)}
    assert by_actor[ACTOR]['workspace_id'] == WORKSPACE
    assert by_actor[OTHER]['workspace_id'] is None
    assert by_actor[None]['workspace_id'] is None

async def test_multiple_workspace_not_last_workspace_wins(caplog):
    async def app(scope, receive, send):
        bind_workspace(WORKSPACE); bind_workspace(OTHER); bind_workspace(WORKSPACE)
        await respond(scope, receive, send)
    with caplog.at_level('INFO', logger='pao.request'):
        await invoke(app)
    assert records(caplog)[-1]['multiple_workspaces'] is True
    assert records(caplog)[-1]['workspace_id'] is None

@pytest.mark.parametrize('peer', [None, ('private-host-or-key', 123), (), ('\nsecret', 0)])
async def test_invalid_peer_and_identifiers_are_not_logged(caplog, peer):
    async def app(scope, receive, send):
        bind_actor('private-actor'); bind_workspace('private-workspace')
        await respond(scope, receive, send)
    with caplog.at_level('INFO', logger='pao.request'):
        await invoke(app, client=peer, method='private-method')
    record = records(caplog)[-1]
    assert record['client_ip'] is None and record['actor_id'] is None
    assert record['workspace_id'] is None and record['method'] == 'OTHER'
    assert 'private-' not in caplog.text

async def test_exception_retains_safe_context_then_resets(caplog):
    async def failing(scope, receive, send):
        bind_actor(ACTOR)
        raise RuntimeError('private-exception')
    with caplog.at_level('INFO', logger='pao.request'):
        with pytest.raises(RuntimeError): await invoke(failing)
        await invoke(respond)
    first, last = records(caplog)
    assert first['status'] == 500 and first['actor_id'] == ACTOR
    assert last['actor_id'] is None and 'private-exception' not in caplog.text

async def test_real_auth_membership_and_denial_are_traced(client, identity, caplog):
    url = '/v1/workspaces/' + identity['workspace'] + '/context'
    with caplog.at_level('INFO', logger='pao.request'):
        assert (await client.get(url, headers=identity['owner'])).status_code == 200
        assert (await client.get(url, headers=identity['outsider'])).status_code == 404
        assert (await client.get(url)).status_code == 401
    good, denied, anonymous = records(caplog)[-3:]
    assert good['actor_id'] == identity['user_id'] and good['workspace_id'] == identity['workspace']
    assert denied['actor_id'] is not None and denied['workspace_id'] is None
    assert anonymous['actor_id'] is None and anonymous['workspace_id'] is None
    assert good['route'] == '/v1/workspaces/{workspace_id}/context'

async def test_login_marks_actor_without_logging_password_or_token(client, identity, caplog):
    with caplog.at_level('INFO', logger='pao.request'):
        response = await client.post('/v1/auth/token', json={'email': 'owner@example.test', 'password': 'test-password-123'})
    assert response.status_code == 200
    record = records(caplog)[-1]
    assert record['actor_id'] == identity['user_id'] and record['route'] == '/v1/auth/token'
    assert record['workspace_id'] is None
    for value in ('test-password-123', 'owner@example.test', response.json()['access_token']):
        assert value not in caplog.text
