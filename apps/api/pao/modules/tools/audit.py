"""Append-only tool audit; caller owns transaction and redacted data policy."""
from ...models import ToolAudit


def audit(db, run, user_id, event, call=None, **data):
    db.add(ToolAudit(workspace_id=run.workspace_id,run_id=run.id,actor_id=user_id,
        tool_call_id=call.id if call else None,event=event,data=data))
