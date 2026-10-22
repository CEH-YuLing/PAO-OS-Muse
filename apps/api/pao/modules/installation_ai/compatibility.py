"""Read-only, caller-scoped legacy inventory; not an authority migration executor."""
from collections import Counter
from sqlalchemy import select, case, func
from ...models import ChatSession, Run, PersonalCliPolicy, EnterpriseAIPolicy


def mode(value):
    authority = value.get('connection_authority') if isinstance(value,dict) else None
    authority = authority if isinstance(authority,dict) else {}
    value = authority.get('mode')
    return value if value in ('installation_resource', 'personal_cli', 'enterprise_policy', 'model_grant') else 'legacy_or_local'


async def preview(db, wid, uid):
    # A host manager is not entitled to inspect another person's private chats.
    # Only counts for their own sessions in the selected SME are projected.
    modes=('installation_resource','personal_cli','enterprise_policy','model_grant')
    def category(column):
        value=column['connection_authority']['mode'].as_string()
        return case((value.in_(modes),value),else_='legacy_or_local')
    chat_kind=category(ChatSession.engine_config)
    chats = await db.execute(select(chat_kind,func.count()).where(
        ChatSession.workspace_id == wid, ChatSession.user_id == uid).group_by(chat_kind))
    sessions = dict(chats.all())
    run_kind=category(Run.engine_snapshot)
    runs = await db.execute(select(run_kind, Run.status,func.count()).join(
        ChatSession, ChatSession.id == Run.session_id).where(
        Run.workspace_id == wid, ChatSession.workspace_id == wid, ChatSession.user_id == uid).group_by(run_kind,Run.status))
    history, queued = Counter(), 0
    for kind, status, count in runs:
        history[kind] += count
        queued += count if status in ('queued', 'running') else 0
    personal = await db.scalar(select(PersonalCliPolicy.id).where(
        PersonalCliPolicy.workspace_id == wid, PersonalCliPolicy.actor_id == uid))
    enterprise = await db.scalar(select(EnterpriseAIPolicy.id).where(EnterpriseAIPolicy.workspace_id == wid))
    return {'version': 'installation-ai-compatibility-preview-v1', 'read_only': True,
            'scope': 'caller_sessions_selected_workspace', 'provider_calls': False,
            'sessions_by_authority': dict(sessions), 'runs_by_authority': dict(history),
            'active_runs': queued, 'personal_policy_present': personal is not None,
            'enterprise_policy_present': enterprise is not None,
            'automatic_migration': False, 'credentials_copied': False,
            'history_repin': False, 'deletion_allowed': False,
            'next_action': 'new_selections_use_explicit_source_old_pins_remain'}
