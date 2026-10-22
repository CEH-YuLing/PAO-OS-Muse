"""B1 data-only grants; B2 explicit consent is separate and never extends TTL."""
from typing import Literal
from uuid import UUID

from fastapi import Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth import Principal, principal
from ...db import database
from ...models import Brand, ConnectionReadActivation, Member, ModelGrantActivation, TenantConnectionAudit, TenantConnectionGrant, TenantConnectionReference, User
from . import grants
from .inventory import manager

class Closed(BaseModel):
    model_config = ConfigDict(extra='forbid')


# Imported after api's MappingPreview/preview are defined (no second router).
def mount(parent, MappingPreview, preview):
    @parent.get('/options')
    async def options(workspace_id: UUID, response: Response,
                      who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
        response.headers['Cache-Control'] = 'no-store'
        workspace = str(workspace_id)
        await manager(db, workspace, who)
        await grants.active_member(db, workspace, who.id, managing=True)
        members = (await db.execute(select(User.id, User.email, Member.role).join(Member, Member.user_id == User.id)
            .where(Member.workspace_id == workspace, User.active.is_(True), Member.role.in_(('owner','admin','operator','analyst')))
            .order_by(User.id).limit(101))).all()
        brands = (await db.execute(select(Brand.id, Brand.name).where(Brand.workspace_id == workspace)
                                   .order_by(Brand.id).limit(101))).all()
        return {'members': [dict(row._mapping) for row in members[:100]],
                'brands': [dict(row._mapping) for row in brands[:100]],
                'has_more': len(members)>100 or len(brands)>100}

    @parent.get('/references/{reference_id}/grants')
    async def grant_listing(workspace_id: UUID, reference_id: UUID, response: Response,
                            limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0, le=10000),
                            who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
        response.headers['Cache-Control'] = 'no-store'
        workspace = str(workspace_id)
        ref = await grants.managed(db, workspace, str(reference_id), who)
        rows = (await db.execute(select(TenantConnectionGrant, ModelGrantActivation.id, ConnectionReadActivation.id)
            .outerjoin(ModelGrantActivation, ModelGrantActivation.grant_id == TenantConnectionGrant.id)
            .outerjoin(ConnectionReadActivation, ConnectionReadActivation.grant_id == TenantConnectionGrant.id)
            .where(TenantConnectionGrant.workspace_id == workspace, TenantConnectionGrant.reference_id == ref.id)
            .order_by(TenantConnectionGrant.created_at, TenantConnectionGrant.id).offset(offset).limit(limit+1))).all()
        return {'reference': grants.public_reference(ref),
                'items': [{**grants.public_grant(row), 'model_consent_recorded': activation is not None,
                           'read_consent_recorded': read_activation is not None}
                          for row, activation, read_activation in rows[:limit]], 'has_more': len(rows)>limit}

    class ActivateModel(Closed):
        reference_revision: int = Field(ge=1, strict=True)
        grant_revision: int = Field(ge=1, strict=True)
        request_key: UUID
        capability: Literal['model_inference']
        allow_model_inference_ack: Literal[True]

    @parent.post('/references/{reference_id}/grants/{grant_id}/activate-model', status_code=201)
    async def activate_model(workspace_id: UUID, reference_id: UUID, grant_id: UUID,
                             body: ActivateModel, response: Response,
                             who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
        from .model_authority import activate
        response.headers['Cache-Control'] = 'no-store'
        return await activate(db, str(workspace_id), who, str(reference_id), str(grant_id), body)

    class ApplyMapping(MappingPreview):
        preview_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
        request_key: UUID
        ttl_minutes: int = Field(ge=1, le=43200, strict=True)
        manager_id: UUID | None = None
        apply_data_only_ack: Literal[True]

    class ActivateMCP(Closed):
        reference_revision: int = Field(ge=1, strict=True)
        grant_revision: int = Field(ge=1, strict=True)
        request_key: UUID
        capability: Literal['mcp_read']
        allow_mcp_read_ack: Literal[True]

    class Reapply(ApplyMapping):
        reference_revision: int = Field(ge=1,strict=True)
        revoke_old_generation_ack: Literal[True]

    @parent.post('/references/{reference_id}/reapply',status_code=201)
    async def reapply(workspace_id: UUID,reference_id: UUID,body: Reapply,response: Response,
                      who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
        from fastapi import HTTPException
        response.headers['Cache-Control']='no-store'
        workspace=str(workspace_id)
        ref=await grants.managed(db,workspace,str(reference_id),who)
        if ref.kind!=body.kind or ref.source_id!=str(body.connection_id):
            raise HTTPException(422,'connection_generation_identity_mismatch')
        base=MappingPreview.model_validate(body.model_dump(include=set(MappingPreview.model_fields)))
        async def make_preview():return await preview(workspace_id,base,Response(),who,db)
        return await grants.stage(db,workspace,who,body,make_preview,generation_from=ref)

    @parent.post('/references/{reference_id}/grants/{grant_id}/activate-mcp', status_code=201)
    async def activate_mcp(workspace_id: UUID, reference_id: UUID, grant_id: UUID,
                           body: ActivateMCP, response: Response,
                           who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
        from .read_authority import activate
        response.headers['Cache-Control'] = 'no-store'
        return await activate(db, str(workspace_id), who, str(reference_id), str(grant_id), body)

    class Revoke(Closed):
        reference_revision: int = Field(ge=1, strict=True)
        grant_revision: int | None = Field(default=None, ge=1, strict=True)

    class ActivateAds(Closed):
        reference_revision: int = Field(ge=1, strict=True)
        grant_revision: int = Field(ge=1, strict=True)
        request_key: UUID
        capability: Literal['ads_read']
        allow_ads_read_ack: Literal[True]

    @parent.post('/references/{reference_id}/grants/{grant_id}/activate-ads', status_code=201)
    async def activate_ads(workspace_id: UUID, reference_id: UUID, grant_id: UUID,
                           body: ActivateAds, response: Response,
                           who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
        from .read_authority import activate
        response.headers['Cache-Control'] = 'no-store'
        return await activate(db, str(workspace_id), who, str(reference_id), str(grant_id), body)

    class Eligibility(Closed):
        reference_revision: int = Field(ge=1, strict=True)
        grant_id: UUID
        brand_id: UUID | None = None
        account_id: str | None = Field(default=None, min_length=1, max_length=64, pattern=r'^(act_)?[0-9]{1,32}$')

    @parent.post('/references', status_code=201)
    async def apply(workspace_id: UUID, body: ApplyMapping, response: Response,
                    who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
        response.headers['Cache-Control'] = 'no-store'
        base = MappingPreview.model_validate(body.model_dump(include=set(MappingPreview.model_fields)))
        async def make_preview():
            return await preview(workspace_id, base, Response(), who, db)
        return await grants.stage(db, str(workspace_id), who, body, make_preview)

    @parent.get('/references')
    async def listing(workspace_id: UUID, response: Response,
                      limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0, le=10000),
                      who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
        response.headers['Cache-Control'] = 'no-store'
        workspace = str(workspace_id)
        await manager(db, workspace, who)
        rows = list(await db.scalars(select(TenantConnectionReference).where(
            TenantConnectionReference.workspace_id == workspace, TenantConnectionReference.manager_id == who.id)
            .order_by(TenantConnectionReference.created_at, TenantConnectionReference.id).offset(offset).limit(limit+1)))
        return {'items': [grants.public_reference(row) for row in rows[:limit]], 'has_more': len(rows)>limit,
                'execution_enabled': False}

    @parent.post('/references/{reference_id}/eligibility')
    async def eligibility(workspace_id: UUID, reference_id: UUID, body: Eligibility, response: Response,
                          who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
        response.headers['Cache-Control'] = 'no-store'
        return await grants.check_staged_grant(db, str(workspace_id), who, str(reference_id), str(body.grant_id),
            str(body.brand_id) if body.brand_id else None, body.account_id, body.reference_revision)

    @parent.post('/references/{reference_id}/revoke')
    async def revoke_reference(workspace_id: UUID, reference_id: UUID, body: Revoke, response: Response,
                               who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
        response.headers['Cache-Control'] = 'no-store'
        return await grants.revoke(db, str(workspace_id), who, str(reference_id), body.reference_revision)

    @parent.post('/references/{reference_id}/grants/{grant_id}/revoke')
    async def revoke_grant(workspace_id: UUID, reference_id: UUID, grant_id: UUID, body: Revoke, response: Response,
                           who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
        response.headers['Cache-Control'] = 'no-store'
        return await grants.revoke(db, str(workspace_id), who, str(reference_id), body.reference_revision,
                                   str(grant_id), body.grant_revision)

    @parent.get('/references/{reference_id}/audit')
    async def history(workspace_id: UUID, reference_id: UUID, response: Response,
                      limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0, le=10000),
                      who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
        response.headers['Cache-Control'] = 'no-store'
        await grants.managed(db, str(workspace_id), str(reference_id), who)
        rows = list(await db.scalars(select(TenantConnectionAudit).where(
            TenantConnectionAudit.workspace_id == str(workspace_id), TenantConnectionAudit.reference_id == str(reference_id))
            .order_by(TenantConnectionAudit.created_at, TenantConnectionAudit.id).offset(offset).limit(limit+1)))
        return {'items': [{'id': row.id, 'action': row.action, 'grant_id': row.grant_id, 'data': row.data} for row in rows[:limit]],
                'has_more': len(rows)>limit}

