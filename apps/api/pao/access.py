from fastapi import HTTPException
from .models import Member, ChatSession, Run


async def membership(db, workspace_id, who, write=False):
    from .auth import check_session
    await check_session(db, who)
    member = await db.get(Member, (workspace_id, who.id), populate_existing=True)
    if not member:
        raise HTTPException(404, 'Không tìm thấy workspace')
    if write and member.role == 'viewer':
        raise HTTPException(403, 'Workspace chỉ cho phép đọc')
    from .modules.operations.request_trace import bind_workspace
    bind_workspace(workspace_id)
    return member


async def owned_session(db, session_id, who, write=False):
    session = await db.get(ChatSession, str(session_id))
    if not session or session.user_id != who.id or session.archived_at is not None:
        raise HTTPException(404, 'Không tìm thấy hội thoại')
    await membership(db, session.workspace_id, who, write)
    return session


async def owned_run(db, run_id, who, write=False):
    run = await db.get(Run, str(run_id))
    if not run:
        raise HTTPException(404, 'Không tìm thấy run')
    await owned_session(db, run.session_id, who, write)
    return run


