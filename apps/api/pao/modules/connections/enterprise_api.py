"""Owner-managed AI policy. Saving never calls a provider or exposes a secret."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, StrictBool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ...auth import Principal, principal
from ...access import membership
from ...db import database
from ...models import (Workspace, ModelProviderConnection, EnterpriseAIPolicy,
                       EnterpriseAIRevision)
from ..engines.contract import EngineFailure
from ..engines.service import digest
from . import enterprise_ai as service

router = APIRouter(prefix='/v1/workspaces/{workspace_id}/enterprise-ai', tags=['enterprise-ai'])


class Save(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_key: UUID
    expected_revision: int = Field(ge=0, strict=True)
    enabled: StrictBool
    connection_ids: list[UUID] = Field(max_length=100)
    default_connection_id: UUID | None = None
    allow_enterprise_inference_ack: StrictBool = False


async def view(db, wid, member):
    row = await service.policy(db, wid)
    connections = []
    # No provider discovery, credential values, connection IDs from another SME,
    # profile IDs, auth caches or another user's private model grants.
    for source in await db.scalars(select(ModelProviderConnection).where(
            ModelProviderConnection.workspace_id == wid).order_by(ModelProviderConnection.provider)):
        selected = next((v for v in (row.content['sources'] if row else []) if v['source_id'] == source.id), None)
        current = None
        try:
            current = await service.source(db, wid, source.id)
        except EngineFailure:
            pass
        ready = bool(service.enabled(row) and selected and current == selected)
        connections.append({'id': source.id, 'provider': source.provider, 'model': source.model,
            'status': source.status, 'selected': selected is not None, 'available': ready,
            'is_default': bool(row and row.content.get('default_source_id') == source.id)})
    return {'workspace_id': wid, 'revision': row.revision if row else 0,
            'enabled': service.enabled(row), 'can_manage': member.role in ('owner', 'admin'),
            'member_ai_access': service.enabled(row) and any(v['available'] for v in connections), 'connections': connections,
            'default_connection_id': row.content.get('default_source_id') if row else None,
            'roles': list(service.ROLES), 'tools_granted': False, 'provider_calls': False,
            'cli_sharing': 'requires_enterprise_profile_adapter',
            'personal_cli_profiles_unchanged': True}


@router.get('')
async def get_policy(workspace_id: UUID, response: Response, who: Principal = Depends(principal),
                     db: AsyncSession = Depends(database)):
    response.headers['Cache-Control'] = 'no-store'
    wid = str(workspace_id)
    member = await membership(db, wid, who)
    return await view(db, wid, member)


@router.put('')
async def save_policy(workspace_id: UUID, body: Save, response: Response,
                      who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    response.headers['Cache-Control'] = 'no-store'
    wid = str(workspace_id)
    await membership(db, wid, who)
    await db.scalar(select(Workspace.id).where(Workspace.id == wid).with_for_update())
    try:
        member = await service.actor(db, wid, who.id, managing=True)
    except EngineFailure:
        raise HTTPException(403, 'Chỉ chủ sở hữu hoặc quản trị viên được cấu hình AI doanh nghiệp') from None
    fingerprint = digest(body.model_dump(mode='json'))
    old = await db.scalar(select(EnterpriseAIRevision).where(EnterpriseAIRevision.workspace_id == wid,
        EnterpriseAIRevision.actor_id == who.id, EnterpriseAIRevision.request_key == str(body.request_key)))
    if old:
        if old.fingerprint != fingerprint:
            raise HTTPException(409, 'enterprise_ai_request_conflict')
        return {**await view(db, wid, member), 'replayed': True, 'saved_revision': old.revision}
    row = await service.policy(db, wid)
    if body.expected_revision != (row.revision if row else 0):
        raise HTTPException(409, 'enterprise_ai_revision_conflict')
    ids = list(map(str, body.connection_ids))
    default = str(body.default_connection_id) if body.default_connection_id else None
    if len(set(ids)) != len(ids) or (default and default not in ids):
        raise HTTPException(422, 'enterprise_ai_selection_invalid')
    if body.enabled and (not ids or default is None or not body.allow_enterprise_inference_ack):
        raise HTTPException(422, 'enterprise_ai_consent_required')
    sources = []
    if body.enabled:
        try:
            for source_id in ids:
                sources.append(await service.source(db, wid, source_id))
        except EngineFailure as error:
            raise HTTPException(409, error.code) from None
    else:
        default = None  # Disabling must work after disconnect/rotation too.
    content = {'version': service.VERSION, 'enabled': body.enabled,
               'default_source_id': default, 'sources': sources}
    if row:
        row.revision += 1
        row.content = content
    else:
        row = EnterpriseAIPolicy(workspace_id=wid, revision=1, content=content)
        db.add(row)
    db.add(EnterpriseAIRevision(workspace_id=wid, actor_id=who.id, revision=row.revision,
        request_key=str(body.request_key), fingerprint=fingerprint, content=content))
    await db.commit()
    return {**await view(db, wid, member), 'replayed': False, 'saved_revision': row.revision}


@router.get('/history')
async def history(workspace_id: UUID, response: Response, who: Principal = Depends(principal),
                  db: AsyncSession = Depends(database)):
    response.headers['Cache-Control'] = 'no-store'
    wid = str(workspace_id)
    await membership(db, wid, who)
    try:
        await service.actor(db, wid, who.id, managing=True)
    except EngineFailure:
        raise HTTPException(403, 'Chỉ chủ sở hữu hoặc quản trị viên được xem lịch sử cấu hình') from None
    rows = list(await db.scalars(select(EnterpriseAIRevision).where(EnterpriseAIRevision.workspace_id == wid)
        .order_by(EnterpriseAIRevision.revision.desc()).limit(50)))
    return {'items': [{'revision': v.revision, 'actor_id': v.actor_id, 'created_at': v.created_at,
                      'enabled': v.content['enabled'], 'connections': len(v.content['sources'])} for v in rows]}
