"""One SME policy, inherited by active members; no synthetic personal grants.

Each execution pins actor, role, brand, exact policy revision and source stamp.
Personal CLI caches are NOT enterprise identities. They remain self-only.
"""
from fastapi import HTTPException
from sqlalchemy import select
from ...models import (EnterpriseAIPolicy, Member, User, Workspace, Brand,
                       ModelProviderConnection, CliModelConnection)
from ..engines.contract import EngineFailure
from ..engines.service import digest

VERSION = 'enterprise-ai-v1'
ROLES = ('owner', 'admin', 'operator', 'analyst', 'viewer')
DENIED = 'enterprise_ai_access_denied'


async def actor(db, wid, uid, *, managing=False):
    member = await db.scalar(select(Member).join(User, User.id == Member.user_id).where(
        Member.workspace_id == wid, Member.user_id == uid, User.active.is_(True))
        .execution_options(populate_existing=True))
    if not member or member.role not in (('owner', 'admin') if managing else ROLES):
        raise EngineFailure(DENIED)
    return member


async def policy(db, wid):
    return await db.scalar(select(EnterpriseAIPolicy).where(EnterpriseAIPolicy.workspace_id == wid)
        .execution_options(populate_existing=True))


def enabled(row):
    return bool(row and row.content.get('enabled') is True)


async def source(db, wid, source_id):
    row = await db.scalar(select(ModelProviderConnection).where(ModelProviderConnection.id == source_id,
        ModelProviderConnection.workspace_id == wid).execution_options(populate_existing=True))
    if row:
        if row.status != 'connected':
            raise EngineFailure('enterprise_ai_source_unavailable')
        stamp = digest({'id': row.id, 'workspace': wid, 'provider': row.provider, 'model': row.model,
                        'status': row.status, 'credential': digest(row.api_key_ciphertext)})
        return {'source_id': row.id, 'source_kind': 'model', 'provider': row.provider, 'model': row.model, 'stamp': stamp}
    # A saved personal login or a user-supplied ACK is not provider authorization
    # to serve an SME. No endpoint can relabel that profile as enterprise-ready.
    if await db.scalar(select(CliModelConnection.id).where(CliModelConnection.id == source_id,
            CliModelConnection.workspace_id == wid)):
        raise EngineFailure('enterprise_cli_provisioning_required')
    raise EngineFailure('enterprise_ai_source_unavailable')


async def pin(db, wid, uid, brand, source_id=None):
    workspace_epoch = await db.scalar(select(Workspace.lifecycle_version).where(Workspace.id == wid).with_for_update(read=True, key_share=True))
    member = await actor(db, wid, uid)
    auth_version = await db.scalar(select(User.auth_version).where(User.id == uid))
    if brand and not await db.scalar(select(Brand.id).where(Brand.id == brand, Brand.workspace_id == wid)):
        raise EngineFailure(DENIED)
    row = await policy(db, wid)
    if not enabled(row):
        raise EngineFailure(DENIED)
    source_id = source_id or row.content.get('default_source_id')
    selected = next((v for v in row.content['sources'] if v['source_id'] == source_id), None)
    if not selected or selected != await source(db, wid, source_id):
        raise EngineFailure('enterprise_ai_source_changed')
    return {'version': VERSION, 'mode': 'enterprise_policy', 'workspace_id': wid,
            'actor_id': uid, 'actor_role': member.role, 'brand_id': brand,
            'membership_epoch': workspace_epoch, 'auth_version': auth_version,
            'source_id': source_id, 'source_kind': selected['source_kind'],
            'policy_id': row.id, 'policy_revision': row.revision, 'source_stamp': selected['stamp'],
            'capability': 'model_inference'}


async def check(db, run, chat, value):
    selected = value.get('connection_authority')
    if not isinstance(selected, dict) or selected.get('mode') != 'enterprise_policy':
        raise EngineFailure('engine_snapshot_incompatible')
    brand = (run.brain_context or {}).get('brand_id') if run.brain_id else chat.brand_id
    current = await pin(db, run.workspace_id, chat.user_id, brand, value.get('connection_id'))
    if current != selected:
        raise EngineFailure('enterprise_ai_policy_changed')
    if member_read_only(current) and value.get('interaction_mode') != 'read_only_ai':
        raise EngineFailure(DENIED)
    if run.brain_id:
        from ..brains.context import check_run_brain
        await check_run_brain(db, run, chat)


def member_read_only(authority):
    return authority.get('actor_role') == 'viewer'


def read_only(run):
    return (run.engine_snapshot or {}).get('interaction_mode') == 'read_only_ai'


async def chat_access(db, wid, who, chat=None):
    """Allow only personal text-chat mutations for viewers, never app writes."""
    from ...access import membership
    member = await membership(db, wid, who)
    if member.role == 'viewer':
        row = await policy(db, wid)
        from ..installation_ai.service import default_config
        common=await default_config(db,wid,who.id,chat.brand_id if chat else None)
        if ((common is None and (not enabled(row) or not row.content.get('default_source_id')))
                or chat is not None and not (chat.chat_profile or {}).get('enterprise_ai_read_only')):
            raise HTTPException(403, 'Người xem chưa có hội thoại AI chỉ đọc được bật bởi doanh nghiệp')
    return member


async def chat_owned(db, sid, who):
    from ...access import owned_session
    chat = await owned_session(db, sid, who)
    await chat_access(db, chat.workspace_id, who, chat)
    return chat


async def run_actor(db, run, chat):
    member = await actor(db, run.workspace_id, chat.user_id)
    if member.role == 'viewer':
        if not read_only(run):
            raise EngineFailure(DENIED)
        if ((run.engine_snapshot or {}).get('connection_authority') or {}).get('mode')=='installation_resource':
            from ..installation_ai.service import check as common_check
            await common_check(db,run,chat,run.engine_snapshot)
        else:
            await check(db, run, chat, run.engine_snapshot)
    return member
