"""Pinned Brain isolation; old runs retain their pre-Brain legacy behavior."""
from ...auth import Principal
from .access import require_brain


async def check_run_brain(db, run, chat):
    if not run.brain_id:
        return None
    return await require_brain(db, Principal(chat.user_id, 0), run.brain_id, True)


async def memory_scope(db, run, chat):
    if not run.brain_id:
        return chat.workspace_id, chat.user_id, chat.brand_id
    await check_run_brain(db, run, chat)
    context = run.brain_context or {}
    if not context.get('legacy'):
        return None
    return run.workspace_id, chat.user_id, context.get('brand_id')


def history_scope(run):
    from sqlalchemy import or_
    from ...models import Run
    own = Run.brain_id == run.brain_id if run.brain_id else Run.brain_id.is_(None)
    if run.brain_id and (run.brain_context or {}).get('legacy'):
        return or_(own, Run.brain_id.is_(None))
    return own
