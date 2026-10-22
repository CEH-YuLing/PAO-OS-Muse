from uuid import uuid4

import pytest
from pao.db import Session
from pao.models import Brand, Member, Workspace


@pytest.mark.asyncio
async def test_context_requires_membership_and_auth(client, identity):
    path = f"/v1/workspaces/{identity['workspace']}/context"
    assert (await client.get(path)).status_code == 401
    assert (await client.get(path, headers=identity['outsider'])).status_code == 404
    assert (await client.get(f'/v1/workspaces/{uuid4()}/context', headers=identity['owner'])).status_code == 404
    result = await client.get(path, headers=identity['owner'])
    assert result.headers['cache-control'] == 'no-store'
    assert result.json() == {'id': identity['workspace'], 'name': 'Test workspace', 'role': 'owner'}


@pytest.mark.asyncio
async def test_two_enterprises_keep_roles_sessions_and_brand_parent(client, identity):
    async with Session.begin() as db:
        second = Workspace(name='SME B')
        db.add(second)
        await db.flush()
        db.add(Member(workspace_id=second.id, user_id=identity['user_id'], role='viewer'))
        brand = Brand(workspace_id=second.id, name='Brand B')
        db.add(brand)
        await db.flush()
        second_id, brand_id = second.id, brand.id
    headers = identity['owner']
    assert (await client.get(f'/v1/workspaces/{second_id}/context', headers=headers)).json()['role'] == 'viewer'
    profile = (await client.get('/v1/me', headers=headers)).json()
    assert {row['id']: row['role'] for row in profile['workspaces']} == {
        identity['workspace']: 'owner', second_id: 'viewer'}
    made = await client.post('/v1/sessions', headers=headers, json={'workspace_id': identity['workspace']})
    assert made.status_code == 201
    assert (await client.get(f'/v1/sessions?workspace_id={second_id}', headers=headers)).json() == []
    assert (await client.post('/v1/sessions', headers=headers, json={'workspace_id': second_id})).status_code == 403
    assert (await client.post('/v1/sessions', headers=headers,
        json={'workspace_id': identity['workspace'], 'brand_id': brand_id})).status_code == 404
    # Selecting B does not repin an existing session in A.
    detail = await client.get(f"/v1/sessions/{made.json()['id']}", headers=headers)
    assert detail.json()['workspace_id'] == identity['workspace']


@pytest.mark.asyncio
async def test_selection_does_not_survive_membership_revocation(client, identity):
    path = f"/v1/workspaces/{identity['workspace']}/context"
    assert (await client.get(path, headers=identity['owner'])).status_code == 200
    async with Session.begin() as db:
        member = await db.get(Member, (identity['workspace'], identity['user_id']))
        await db.delete(member)
    assert (await client.get(path, headers=identity['owner'])).status_code == 404
    assert (await client.get('/v1/me', headers=identity['owner'])).json()['workspaces'] == []
    assert (await client.get(f"/v1/sessions?workspace_id={identity['workspace']}", headers=identity['owner'])).status_code == 404
