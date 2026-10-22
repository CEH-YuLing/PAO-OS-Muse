"""Immutable, extractive cache. Originals and tool/approval state are never replaced."""
import hashlib
import json
from fastapi import HTTPException
from sqlalchemy import select, func
from ...models import ChatCompaction, Message, Run
from ..brains.access import require_brain
from ..knowledge.conversations import run_visible


async def visible(db, run, who):
    try:
        if run.brain_id:
            await require_brain(db, who, run.brain_id)
        return await run_visible(db, run, who)
    except HTTPException:
        return False


async def original_messages(db, chat, who, limit=500):
    rows = await db.execute(select(Message, Run).join(Run, Message.run_id == Run.id).where(
        Message.session_id == chat.id).order_by(Message.created_at, Message.id).limit(limit + 1))
    values = list(rows)
    if len(values) > limit:
        raise HTTPException(413, 'chat_history_limit')
    return [(m, r) for m, r in values if await visible(db, r, who)]


def digest(rows):
    return hashlib.sha256(json.dumps([(m.id, m.run_id, m.role, m.content, m.status) for m in rows],
        ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


async def compact(db, chat, who):
    if await db.scalar(select(Run.id).where(Run.session_id == chat.id, Run.status.in_(['queued','running']))):
        raise HTTPException(409, 'chat_run_active')
    if chat.brain_id:
        await require_brain(db, who, chat.brain_id)
    eligible = [m for m, r in await original_messages(db, chat, who)
        if m.status == 'completed' and r.status == 'completed' and r.brain_id == chat.brain_id
        and not (r.brain_context or {}).get('knowledge')]
    # Keep complete short messages only, never invent a semantic summary.
    chosen = []; size = 0
    for message in reversed(eligible[:-4]):
        item = json.dumps({'role':message.role,'text':message.content}, ensure_ascii=False)
        if size + len(item.encode()) > 2048:
            continue
        chosen.append(message); size += len(item.encode())
    chosen.reverse()
    if not chosen:
        raise HTTPException(409, 'chat_compaction_not_needed')
    revision = 1 + (await db.scalar(select(func.max(ChatCompaction.revision)).where(ChatCompaction.session_id == chat.id)) or 0)
    row = ChatCompaction(workspace_id=chat.workspace_id, user_id=who.id, session_id=chat.id,
        brain_id=chat.brain_id, revision=revision, version='extractive-v1', source_hash=digest(chosen),
        message_ids=[m.id for m in chosen], content=json.dumps([{'role':m.role,'text':m.content} for m in chosen], ensure_ascii=False))
    db.add(row); await db.flush()
    return row


async def cached_context(db, run, chat, who):
    row = await db.scalar(select(ChatCompaction).where(ChatCompaction.session_id == chat.id,
        ChatCompaction.brain_id == run.brain_id).order_by(ChatCompaction.revision.desc()).limit(1))
    if not row or row.version != 'extractive-v1':
        return None
    rows = list(await db.scalars(select(Message).where(Message.id.in_(row.message_ids))))
    by_id = {m.id:m for m in rows}
    if set(by_id) != set(row.message_ids):
        return None
    ordered = [by_id[mid] for mid in row.message_ids]
    if digest(ordered) != row.source_hash:
        return None
    for message in ordered:
        source = await db.get(Run, message.run_id)
        if source.status != 'completed' or source.brain_id != run.brain_id or not await visible(db, source, who):
            return None
    return row
