import asyncio
import time
from uuid import UUID

import anyio

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import Principal, dummy_hash, issue_token, passwords, principal, rate_limit
from .config import settings
from .access import membership, owned_session, owned_run
from .db import Session, database
from .models import ChatSession, Member, Message, Run, RunEvent, User, Workspace, now
from .modules.conversations.state import TERMINAL, emit, finish
from .schemas import (EventOut, Login, Me, Membership, MessageOut, RunCreate, RunOut,
                      SessionCreate, SessionDetail, SessionOut, Token)


router = APIRouter()


@router.get('/health')
def health():
    return {'status': 'ok'}


@router.get('/ready')
async def ready(request: Request, db: AsyncSession = Depends(database)):
    try:
        await db.execute(text('SELECT 1'))
        await db.execute(text('SELECT version_num FROM alembic_version'))
        await request.app.state.redis.ping()
        return {'status': 'ready'}
    except Exception:
        raise HTTPException(503, 'Database hoặc Redis chưa sẵn sàng')


@router.post('/v1/auth/token', response_model=Token)
async def login(body: Login, request: Request, db: AsyncSession = Depends(database)):
    email = body.email.strip().lower()
    await rate_limit(request.app.state.redis, 'login-ip', request.client.host, 20, 60)
    await rate_limit(request.app.state.redis, 'login-user', email, 10, 60)
    user = await db.scalar(select(User).where(User.email == email))
    # Argon2 is CPU bound, do not block streaming event loop.
    valid = await asyncio.to_thread(passwords.verify, body.password, user.password_hash if user else dummy_hash)
    if not user or not user.active or not valid:
        raise HTTPException(401, 'Email hoặc mật khẩu không đúng')
    from datetime import timedelta
    from hashlib import sha256
    from .models import LoginSession
    user = await db.scalar(select(User).where(User.id == user.id).with_for_update().execution_options(populate_existing=True))
    if not user.active:
        raise HTTPException(401, 'Email hoặc mật khẩu không đúng')
    token = issue_token(user.id, user.auth_version)
    db.add(LoginSession(user_id=user.id, token_hash=sha256(token.encode()).hexdigest(),
                        auth_version=user.auth_version, expires_at=now()+timedelta(minutes=settings().jwt_minutes)))
    await db.commit()
    from .modules.operations.request_trace import bind_actor
    bind_actor(user.id)
    return Token(access_token=token, expires_in=settings().jwt_minutes * 60)


@router.get('/v1/me', response_model=Me)
async def me(who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    user = await db.get(User, who.id)
    rows = (await db.execute(select(Workspace, Member.role).join(Member).where(Member.user_id == who.id)
                             .order_by(Workspace.name, Workspace.id))).all()
    return Me(id=user.id, email=user.email, workspaces=[{'id': w.id, 'name': w.name, 'role': role} for w, role in rows])


@router.get('/v1/workspaces/{workspace_id}/context', response_model=Membership)
async def workspace_context(workspace_id: UUID, response: Response, who: Principal = Depends(principal),
                            db: AsyncSession = Depends(database)):
    # Selection is a UI preference, never a JWT permission or global server tenant.
    member = await membership(db, str(workspace_id), who)
    workspace = await db.get(Workspace, str(workspace_id))
    if not workspace:
        raise HTTPException(404, 'Không tìm thấy workspace')
    response.headers['Cache-Control'] = 'no-store'
    return Membership(id=workspace.id, name=workspace.name, role=member.role)


@router.post('/v1/sessions', response_model=SessionOut, status_code=201)
async def create_session(body: SessionCreate, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    from .modules.connections.enterprise_ai import chat_access, policy, enabled
    member = await chat_access(db, str(body.workspace_id), who)
    if body.brand_id:
        from .models import Brand
        brand = await db.get(Brand, str(body.brand_id))
        if not brand or brand.workspace_id != str(body.workspace_id):
            raise HTTPException(404, 'Không tìm thấy brand')
    session = ChatSession(workspace_id=str(body.workspace_id), user_id=who.id,
                          brand_id=str(body.brand_id) if body.brand_id else None, memory_enabled=body.memory_enabled,
                          title=body.title.strip() or 'Hội thoại mới')
    enterprise = await policy(db, session.workspace_id)
    from .modules.cli_connections.personal import default_config as personal_default
    from .modules.engines.contract import EngineFailure
    try:
        personal = await personal_default(db, session.workspace_id, who.id, session.brand_id) if member.role in ('owner','admin') else None
    except EngineFailure as error:
        raise HTTPException(409, error.code) from None
    from .modules.installation_ai.service import default_config as installation_default
    try:common=await installation_default(db,session.workspace_id,who.id,session.brand_id)
    except EngineFailure as error:raise HTTPException(409,error.code) from None
    if enabled(enterprise) or personal is not None or common is not None:
        # One owner activation applies to NEW text chats. Never rewrite an old
        # local-only chat, history, source attachment or immutable run.
        session.chat_profile = {'policy': {'privacy': 'cloud_allowed', 'cloud_references': False}}
    if (personal is not None or common is not None) and 'memory_enabled' not in body.model_fields_set:
        # New personal CLI chats need no hidden local extraction/Ollama call.
        # Explicit opt-in and old chats retain their existing behavior.
        session.memory_enabled = False
    if member.role == 'viewer':
        session.memory_enabled = False
        session.chat_profile = {**session.chat_profile, 'enterprise_ai_read_only': True}
    if settings().brain_manager_enabled and member.role != 'viewer':
        from .modules.brains.access import default_brain
        session.brain_id = (await default_brain(db, who, session.workspace_id, session.brand_id)).id
    db.add(session)
    await db.commit()
    return session


@router.get('/v1/sessions', response_model=list[SessionOut])
async def list_sessions(workspace_id: UUID, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    await membership(db, str(workspace_id), who)
    return list(await db.scalars(select(ChatSession).where(ChatSession.workspace_id == str(workspace_id),
                           ChatSession.user_id == who.id, ChatSession.archived_at.is_(None))
                           .order_by(ChatSession.created_at.desc()).limit(100)))


@router.delete('/v1/sessions/{session_id}', status_code=204)
async def delete_session(session_id: UUID, who: Principal = Depends(principal),
                         db: AsyncSession = Depends(database)):
    session = await owned_session(db, session_id, who, True)
    active = await db.scalar(select(Run.id).where(Run.session_id == session.id,
                                                   Run.status.in_(['queued', 'running'])))
    if active:
        raise HTTPException(409, 'Không thể xóa hội thoại khi PAO đang xử lý')
    # Recoverable deletion keeps run/audit/memory provenance intact.
    session.archived_at = now()
    await db.commit()
    return None


@router.get('/v1/sessions/{session_id}', response_model=SessionDetail)
async def get_session(session_id: UUID, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    session = await owned_session(db, session_id, who)
    # Bound response; keep most recent messages, display chronologically.
    messages = list(await db.scalars(select(Message).where(Message.session_id == session.id)
                      .order_by(Message.created_at.desc(), Message.id.desc()).limit(100)))
    active = await db.scalar(select(Run).where(Run.session_id == session.id, Run.status.in_(['queued', 'running'])))
    from .modules.knowledge.conversations import run_visible
    safe_messages=[]
    for message in reversed(messages):
        linked=await db.get(Run,message.run_id)
        visible=await run_visible(db,linked,who)
        value=MessageOut.model_validate(message)
        if not visible and message.role=='assistant':value=value.model_copy(update={'content':'[Nguồn không còn được phép truy cập]'})
        safe_messages.append(value)
    active_out=RunOut.model_validate(active) if active else None
    if active and not await run_visible(db,active,who):active_out=active_out.model_copy(update={'response':'[Nguồn không còn được phép truy cập]'})
    return SessionDetail(**SessionOut.model_validate(session).model_dump(),
                         messages=safe_messages,
                         active_run=active_out)


@router.post('/v1/runs', response_model=RunOut, status_code=202)
async def create_run(body: RunCreate, request: Request, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    from .modules.conversations.requests import admit_run
    return await admit_run(body,request,who,db)

@router.get('/v1/runs/{run_id}', response_model=RunOut)
async def get_run(run_id: UUID, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    run=await owned_run(db, run_id, who)
    from .modules.knowledge.conversations import run_visible
    if not await run_visible(db,run,who):
        return RunOut.model_validate(run).model_copy(update={'response':'[Nguồn không còn được phép truy cập]'})
    return run


@router.post('/v1/runs/{run_id}/cancel', response_model=RunOut)
async def cancel(run_id: UUID, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    target = await owned_run(db, run_id, who)
    from .modules.connections.enterprise_ai import chat_owned
    await chat_owned(db, target.session_id, who)
    run = await db.scalar(select(Run).where(Run.id == str(run_id)).with_for_update().execution_options(populate_existing=True))
    if run.status not in TERMINAL:
        run.cancel_requested = True
        if run.status == 'queued':
            await finish(db, run, 'cancelled')
        await db.commit()
    return await get_run(run_id,who,db)


@router.get('/v1/runs/{run_id}/events', responses={200: {'content': {'text/event-stream': {}}}})
async def events(run_id: UUID, request: Request, after: int = Query(0, ge=0),
                 who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    await owned_run(db, run_id, who)
    try:
        after = max(after, int(request.headers.get('Last-Event-ID', '0')))
        if after < 0:
            raise ValueError()
    except ValueError:
        raise HTTPException(400, 'Last-Event-ID phải là sequence không âm')
    await db.rollback()  # Do not hold a transaction/connection throughout the stream.

    async def stream():
        cursor = after
        heartbeat = time.monotonic()
        while not await request.is_disconnected():
            if time.time() >= who.expires:
                return
            # ASGI disconnect uses level cancellation. Shield this short DB poll
            # and its rollback/close, not network delivery or the whole stream.
            # End the timeout scope BEFORE session cleanup so a timeout cannot
            # repeatedly cancel asyncpg's rollback/connection termination.
            with anyio.CancelScope(shield=True):
                async with Session() as connection:
                    try:
                        # Edge cancellation lets SQLAlchemy finish invalidating
                        # a timed-out driver call. Nested level cancellation can
                        # interrupt that termination before session cleanup.
                        async with asyncio.timeout(5):
                            await owned_run(connection, run_id, who)
                            user = await connection.get(User, who.id)
                            if not user or not user.active:
                                return
                            from .modules.knowledge.conversations import run_visible
                            if not await run_visible(connection,await connection.get(Run,str(run_id)),who):return
                            batch = list(await connection.scalars(select(RunEvent).where(
                                RunEvent.run_id == str(run_id), RunEvent.seq > cursor).order_by(RunEvent.seq).limit(200)))
                            status = await connection.scalar(select(Run.status).where(Run.id == str(run_id)))
                    except (HTTPException, TimeoutError):
                        return
            for item in batch:
                cursor = item.seq
                yield f'id: {cursor}\nevent: {item.type}\ndata: {EventOut.model_validate(item).model_dump_json()}\n\n'
            if status in TERMINAL and len(batch) < 200:
                return
            if time.monotonic() - heartbeat > 10:
                yield ': heartbeat\n\n'
                heartbeat = time.monotonic()
            await asyncio.sleep(0.2)

    return StreamingResponse(stream(), media_type='text/event-stream', headers={
        'Cache-Control': 'no-cache, no-transform', 'X-Accel-Buffering': 'no'})
