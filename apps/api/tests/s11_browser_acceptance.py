"""Explicit S1.1 browser gate: genuine local HTTP/DB; no cloud or production data."""
from pao.db import Session
from pao.models import Member, Workspace
from p6_browser_harness import browser


async def test_enterprise_selection_real_http(client, identity):
    async with Session.begin() as db:
        second = Workspace(name='SME B browser')
        db.add(second)
        await db.flush()
        db.add(Member(workspace_id=second.id, user_id=identity['user_id'], role='owner'))
        second_id = second.id
    for workspace, label in ((identity['workspace'], 'A'), (second_id, 'B')):
        task = await client.post('/v1/tasks', headers=identity['owner'], json={
            'workspace_id': workspace, 'title': f'S11 task only SME {label}'})
        assert task.status_code == 201, task.text
        chat = await client.post('/v1/sessions', headers=identity['owner'], json={
            'workspace_id': workspace, 'title': f'S11 chat only SME {label}', 'memory_enabled': False})
        assert chat.status_code == 201, chat.text
    async with Session.begin() as db:
        member = await db.get(Member, (second_id, identity['user_id']))
        member.role = 'viewer'
    report = await browser('scripts/verify_s11_browser.cjs', 'PAO_S11_BROWSER_FIXTURE', {
        'workspace': identity['workspace'], 'second': second_id,
    }, 's11')
    assert report['per_tenant_role'] and report['selection_reload'] and report['late_response_discarded']
