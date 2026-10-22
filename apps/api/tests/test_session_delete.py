from pao.db import Session
from pao.models import ChatSession
from test_integration import make_run


async def test_delete_conversation_archives_without_deleting_audit(client, identity):
    sid, rid = await make_run(client, identity, key='delete-session-1')
    # Active runs must be resolved before a conversation can be removed.
    blocked = await client.delete(f'/v1/sessions/{sid}', headers=identity['owner'])
    assert blocked.status_code == 409
    await client.post(f'/v1/runs/{rid}/cancel', headers=identity['owner'])
    deleted = await client.delete(f'/v1/sessions/{sid}', headers=identity['owner'])
    assert deleted.status_code == 204
    assert (await client.get(f'/v1/sessions/{sid}', headers=identity['owner'])).status_code == 404
    rows = (await client.get(f'/v1/sessions?workspace_id={identity["workspace"]}',
                             headers=identity['owner'])).json()
    assert all(row['id'] != sid for row in rows)
    async with Session() as db:
        archived = await db.get(ChatSession, sid)
        assert archived is not None and archived.archived_at is not None


async def test_delete_conversation_is_owner_scoped(client, identity):
    sid, _ = await make_run(client, identity, key='delete-session-scope')
    for actor in ('other', 'outsider'):
        assert (await client.delete(f'/v1/sessions/{sid}', headers=identity[actor])).status_code == 404

