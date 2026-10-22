"""Durable run state; callers own row locks and transactions."""
from sqlalchemy import select
from ...config import settings
from ...models import Run, RunEvent, AgentRun, Message, ChatSession, MemoryJob, now

TERMINAL = {'completed', 'failed', 'cancelled'}


def emit(db, run: Run, kind: str, data: dict | None = None):
    # Caller holds the run row lock. Sequence and state commit atomically.
    db.add(RunEvent(run_id=run.id, workspace_id=run.workspace_id,
                    seq=run.next_seq, type=kind, data=data or {}))
    run.next_seq += 1


async def finish(db, run: Run, status: str, error: str | None = None):
    if run.status in TERMINAL:
        return
    run.status, run.error_code, run.finished_at = status, error, now()
    agents = await db.scalars(select(AgentRun).where(AgentRun.run_id == run.id, AgentRun.status == 'running'))
    for agent in agents:
        agent.status = status
        agent.finished_at = now()
        if agent.agent_key == 'chief_of_staff':
            agent.output = run.response
        emit(db, run, f'agent.{status}', {'agent_key': agent.agent_key, 'agent_run_id': agent.id})
    if run.response:
        db.add(Message(workspace_id=run.workspace_id, session_id=run.session_id,
                       run_id=run.id, role='assistant', content=run.response, status=status))
    if status == 'completed' and settings().memory_enabled and not run.studio_snapshot and not (run.brain_context or {}).get('knowledge'):
        chat = await db.get(ChatSession, run.session_id)
        if chat.memory_enabled and (not run.brain_id or (run.brain_context or {}).get('legacy')):
            db.add(MemoryJob(run_id=run.id, workspace_id=run.workspace_id))
    if status == 'completed':
        emit(db, run, 'response.completed')
    emit(db, run, 'core.standby')
    emit(db, run, f'run.{status}', {'error_code': error} if error else {})
