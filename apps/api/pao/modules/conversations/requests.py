"""Single durable Run admission boundary shared by HTTP, channels and voice.

commit=False lets an adapter persist its inbound dedup receipt atomically.
"""
from fastapi import HTTPException
from sqlalchemy import select
from pao.access import owned_session
from pao.auth import rate_limit
from pao.config import settings
from pao.models import ChatSession,Message,Run
from pao.modules.conversations.state import emit

async def admit_run(body, request, who, db, *, commit=True):
    from pao.modules.connections.enterprise_ai import chat_owned
    session = await chat_owned(db, body.session_id, who)
    from pao.modules.business_planning.jobs import session_guard
    await session_guard(db, session.id)
    # Serialize concurrent requests for one conversation (including idempotent retries).
    session = await db.scalar(select(ChatSession).where(ChatSession.id == session.id)
        .with_for_update().execution_options(populate_existing=True))
    from pao.models import ChannelBinding
    binding=await db.scalar(select(ChannelBinding).where(ChannelBinding.session_id==session.id))
    customer=bool(binding and binding.kind=='customer')
    if binding:
        from pao.modules.channels.service import enabled,actor
        enabled();await actor(db,binding)
        if binding.mode!='auto':raise HTTPException(403,'channel_quiet')
        if customer and (not settings().channel_autoreply_enabled or session.brain_id!=binding.brain_id or not session.knowledge_enabled or session.knowledge_scope!='brain' or session.memory_enabled or session.engine_config):
            raise HTTPException(403,'customer_grounding_required')
    if session.knowledge_enabled and not (settings().knowledge_enabled and settings().knowledge_sources_enabled and settings().brain_manager_enabled):
        raise HTTPException(503,'Knowledge đã chọn nhưng feature đang tắt; không fallback')
    existing = await db.scalar(select(Run).where(Run.session_id == session.id, Run.request_key == body.request_key))
    parent_id = getattr(request.state, 'pao_retry_parent', None)
    if existing:
        if existing.parent_run_id != parent_id:
            raise HTTPException(409, 'request_key_retry_conflict')
        if existing.prompt != body.message.strip():
            raise HTTPException(409, 'request_key đã dùng với nội dung khác')
        return existing
    if not body.message.strip():
        raise HTTPException(422, 'Nội dung không được trống')
    studio_pin = None
    read_only = bool((session.chat_profile or {}).get('enterprise_ai_read_only'))
    if read_only and (binding or session.knowledge_enabled or session.brain_id or session.memory_enabled):
        raise HTTPException(403, 'enterprise_ai_read_only_required')
    if settings().studio_enabled and not customer and not read_only:
        from pao.modules.studio.execution import select_command
        studio_pin = await select_command(db, session, who, body.message.strip())
    if settings().chat_features_enabled:
        from pao.modules.chat.commands import parse
        if not studio_pin and parse(body.message.strip()):
            raise HTTPException(422, 'use_command_endpoint')
    active = await db.scalar(select(Run.id).where(Run.session_id == session.id, Run.status.in_(['queued', 'running'])))
    if active:
        raise HTTPException(409, 'Hội thoại đang có yêu cầu chạy')
    await rate_limit(request.app.state.redis, 'runs', who.id, 10, 60)
    brain = None
    if session.brain_id:
        from pao.models import Brain
        if settings().brain_manager_enabled:
            from pao.modules.brains.access import require_brain
            brain = await require_brain(db, who, session.brain_id, True, lock=True)
        else:
            previous_brain = await db.get(Brain, session.brain_id)
            if previous_brain and not previous_brain.legacy_default:
                raise HTTPException(503, 'Brain Manager đang tắt; không fallback sang memory khác')
    run = Run(workspace_id=session.workspace_id, session_id=session.id, prompt=body.message.strip(),
              request_key=body.request_key, parent_run_id=parent_id, status='queued', response='', next_seq=1, cancel_requested=False)
    run.studio_snapshot = studio_pin
    if binding:run.channel_context={'binding_id':binding.id,'version':binding.version,'kind':binding.kind}
    if brain:
        run.brain_id, run.brain_revision = brain.id, brain.revision
        run.brain_context = {'legacy': brain.legacy_default and brain.owner_id == who.id,
                             'brand_id': brain.brand_id}
        if session.knowledge_enabled:
            from pao.modules.knowledge.conversations import snapshot_attachments
            run.brain_context={**run.brain_context,'knowledge':True,'knowledge_scope':session.knowledge_scope,
                'attachment_files':await snapshot_attachments(db,session)}
    from pao.modules.engines.service import pin_run
    from pao.modules.engines.contract import EngineFailure
    try:
        await pin_run(db, run, session)
    except EngineFailure as exc:
        raise HTTPException(503, exc.code) from None
    if binding and binding.connection_id is not None:
        from pao.modules.channels.telegram_scoped import context as scoped_context
        run.channel_context={**run.channel_context,'telegram':await scoped_context(db,binding)}
    db.add(run)
    await db.flush()
    db.add(Message(workspace_id=run.workspace_id, session_id=session.id, run_id=run.id, role='user', content=run.prompt))
    emit(db, run, 'run.queued')
    if not commit:
        return run
    await db.commit()
    try:
        await request.app.state.redis.enqueue_job('execute_run', run.id, _job_id=f'run:{run.id}')
    except Exception:
        pass  # Dispatcher will recover from durable queued row.
    return run
