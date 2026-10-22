"""Actual PAO auth/tasks/Brain ACL using disposable pao_test, no Google calls."""
from pathlib import Path
import sys
import pytest
import httpx
from sqlalchemy import delete
from pao.db import Session
from pao.main import app
from pao.models import Member, User, Workspace
from pao.config import settings
from pao.modules.knowledge import worker

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'packages/pao-mcp'))
from pao_mcp.bridge import Bridge, Denied


def config(identity, project=None, brain=None):
    return {'version': 1, 'actor_id': identity['user_id'], 'workspace_id': identity['workspace'],
            'projects': [project] if project else [], 'brains': {brain: None} if brain else {},
            'token': identity['owner']['Authorization'].split(' ', 1)[1], 'consent': True, 'enabled': True}


async def project_task(client, identity):
    h = identity['owner']; workspace = identity['workspace']
    response = await client.post('/v1/projects', headers=h, json={'workspace_id': workspace, 'name': 'Dự án MCP thử nghiệm'})
    assert response.status_code == 201
    project = response.json()['id']
    response = await client.post('/v1/tasks', headers=h, json={'workspace_id': workspace, 'project_id': project,
        'title': 'Viết nội dung thử', 'description': 'Không gọi model hoặc chạy quảng cáo.'})
    assert response.status_code == 201
    return project, response.json()['id']


async def test_mcp_real_api_task_and_project_allowlist(client, identity):
    project, task = await project_task(client, identity)
    other_project, other_task = await project_task(client, identity)
    cfg = config(identity, project)
    bridge = Bridge(lambda: cfg.copy(), httpx.ASGITransport(app=app))
    value = await bridge.call('pao_list_tasks', {'project_id': project})
    assert [v['id'] for v in value['items']] == [task]
    assert (await bridge.call('pao_get_task', {'project_id': project, 'task_id': task}))['items'][0]['description'].startswith('Không gọi')
    with pytest.raises(Denied): await bridge.call('pao_get_task', {'project_id': project, 'task_id': other_task})
    with pytest.raises(Denied): await bridge.call('pao_list_tasks', {'project_id': other_project})


async def test_mcp_real_api_two_workspaces_same_owner_no_cross_read(client, identity):
    project, _ = await project_task(client, identity)
    async with Session.begin() as db:
        other = Workspace(name='MCP second enterprise')
        db.add(other); await db.flush()
        db.add(Member(workspace_id=other.id, user_id=identity['user_id'], role='owner'))
        second = other.id
    response = await client.post('/v1/projects', headers=identity['owner'], json={'workspace_id': second, 'name': 'Private second SME'})
    second_project = response.json()['id']
    response = await client.post('/v1/tasks', headers=identity['owner'], json={'workspace_id': second,
        'project_id': second_project, 'title': 'Không được xuất chéo'})
    second_task = response.json()['id']
    cfg = config(identity, project)
    bridge = Bridge(lambda: cfg.copy(), httpx.ASGITransport(app=app))
    with pytest.raises(Denied): await bridge.call('pao_list_tasks', {'project_id': second_project})
    with pytest.raises(Denied): await bridge.call('pao_get_task', {'project_id': project, 'task_id': second_task})
    # Even a malicious profile cannot turn an out-of-SME project into a query result.
    cfg['projects'] = [second_project]
    result = await bridge.call('pao_list_tasks', {'project_id': second_project})
    assert result['items'] == []


async def test_mcp_real_api_revokes_member_before_delivery(client, identity):
    project, _ = await project_task(client, identity)
    cfg = config(identity, project)
    class Revoking(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            response = await httpx.ASGITransport(app=app).handle_async_request(request)
            if request.url.path == '/v1/tasks':
                async with Session.begin() as db:
                    await db.execute(delete(Member).where(Member.workspace_id == identity['workspace'], Member.user_id == identity['user_id']))
            return response
    with pytest.raises(Denied): await Bridge(lambda: cfg.copy(), Revoking()).call('pao_list_tasks', {'project_id': project})


async def test_mcp_real_api_actor_disabled_and_demoted(client, identity):
    cfg = config(identity)
    bridge = Bridge(lambda: cfg.copy(), httpx.ASGITransport(app=app))
    assert (await bridge.call('pao_scope', {}))['read_only'] is True
    async with Session.begin() as db:
        member = await db.get(Member, (identity['workspace'], identity['user_id']))
        member.role = 'viewer'
    with pytest.raises(Denied): await bridge.call('pao_scope', {})
    async with Session.begin() as db:
        member = await db.get(Member, (identity['workspace'], identity['user_id'])); member.role = 'owner'
        user = await db.get(User, identity['user_id']); user.active = False
    with pytest.raises(Denied): await bridge.call('pao_scope', {})


async def test_mcp_real_api_sources_and_private_brain_acl(client, identity, monkeypatch):
    monkeypatch.setattr(settings(), 'brain_manager_enabled', True)
    monkeypatch.setattr(settings(), 'knowledge_sources_enabled', True)
    h = identity['owner']
    response = await client.post('/v1/brains', headers=h, json={'workspace_id': identity['workspace'], 'name': 'Kho MCP được chọn'})
    assert response.status_code == 201
    brain = response.json()['id']
    base = '/v1/brains/' + brain
    response = await client.post(base + '/files', params={'name': 'test.md'}, headers={**h, 'content-type': 'text/markdown'}, content='Tài liệu tổng hợp.\nDòng hai.'.encode())
    assert response.status_code == 201
    response = await client.post(base + '/sources', headers=h, json={'kind': 'file', 'origin_id': response.json()['id']})
    assert response.status_code == 200
    source = response.json(); await worker.ingest_source({}, source['job_id'])
    cfg = config(identity, brain=brain)
    bridge = Bridge(lambda: cfg.copy(), httpx.ASGITransport(app=app))
    assert (await bridge.call('pao_list_sources', {'brain_id': brain}))['items'][0]['id'] == source['id']
    args = {'brain_id': brain, 'source_id': source['id'], 'version': 1}
    assert (await bridge.call('pao_preview_source', args))['content'].startswith('Tài liệu tổng hợp.')
    # An enterprise admin is not implicitly granted another user's private Brain.
    cfg['actor_id'] = (await client.get('/v1/me', headers=identity['other'])).json()['id']
    cfg['token'] = identity['other']['Authorization'].split(' ', 1)[1]
    async with Session.begin() as db:
        member = await db.get(Member, (identity['workspace'], cfg['actor_id'])); member.role = 'admin'
    with pytest.raises(Denied): await bridge.call('pao_list_sources', {'brain_id': brain})


async def test_mcp_real_api_server_side_session_revoke(client, identity):
    response = await client.post('/v1/auth/token', json={'email': 'owner@example.test', 'password': 'test-password-123'})
    assert response.status_code == 200
    cfg = config(identity); cfg['token'] = response.json()['access_token']
    bridge = Bridge(lambda: cfg.copy(), httpx.ASGITransport(app=app))
    assert (await bridge.call('pao_scope', {}))['actor_id'] == identity['user_id']
    from pao.models import LoginSession
    from sqlalchemy import select
    import hashlib
    async with Session.begin() as db:
        row = await db.scalar(select(LoginSession).where(LoginSession.token_hash == hashlib.sha256(cfg['token'].encode()).hexdigest()))
        row.revoked = True
    with pytest.raises(Denied): await bridge.call('pao_scope', {})
