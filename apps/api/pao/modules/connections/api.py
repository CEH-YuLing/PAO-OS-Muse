"""S2.1A inventory and mapping preview only: no grants, writes or network probes."""
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth import Principal, principal
from ...db import database
from ...models import Brand
from ..studio.contracts import digest
from .inventory import account_known, connection_metadata, grantee, inventory, manager

Kind = Literal['model', 'cli_model', 'mcp', 'meta_ads', 'google_ads']
router = APIRouter(prefix='/v1/workspaces/{workspace_id}/connection-inventory', tags=['connection-inventory'])


class MappingPreview(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Kind
    connection_id: UUID
    expected_version: int | None = Field(ge=1, default=None, strict=True)
    brand_id: UUID | None = None
    account_id: str | None = Field(default=None, min_length=1, max_length=64, pattern=r'^(act_)?[0-9]{1,32}$')
    grantee_id: UUID
    permission: Literal['read_only']


@router.get('')
async def listing(workspace_id: UUID, response: Response,
                  limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0, le=10000),
                  who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    response.headers['Cache-Control'] = 'no-store'
    return await inventory(db, str(workspace_id), who, limit, offset)


@router.post('/mapping-preview')
async def preview(workspace_id: UUID, body: MappingPreview, response: Response,
                  who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    response.headers['Cache-Control'] = 'no-store'
    workspace = str(workspace_id)
    await manager(db, workspace, who)
    source = await connection_metadata(db, workspace, who, body.kind, str(body.connection_id))
    if source['config_version'] != body.expected_version:
        raise HTTPException(409, 'connection_mapping_version_conflict')
    if body.brand_id:
        brand = await db.scalar(select(Brand.id).where(Brand.id == str(body.brand_id), Brand.workspace_id == workspace))
        if brand is None:
            raise HTTPException(404, 'connection_mapping_brand_not_found')
    role = await grantee(db, workspace, str(body.grantee_id))
    if body.kind == 'cli_model' and str(body.grantee_id) != who.id:
        raise HTTPException(422, 'cli_personal_account_self_only')
    if body.account_id:
        if body.kind not in ('meta_ads', 'google_ads'):
            raise HTTPException(422, 'connection_mapping_account_not_supported')
        await account_known(db, workspace, body.kind, str(body.connection_id),
                            body.expected_version, body.account_id)
    elif body.kind in ('meta_ads', 'google_ads'):
        raise HTTPException(422, 'connection_mapping_account_required')
    # This deterministic hash is review evidence, NOT an executable grant/token.
    proposal = {'identity': source['identity'], 'config_version': source['config_version'],
                'legacy_manager_id': source['manager_id'], 'stored_status': source['stored_status'],
                'credential_present': source['credential_present'],
                **({'authentication_ready': source['authentication_ready']} if body.kind == 'cli_model' else {}),
                'brand_id': str(body.brand_id) if body.brand_id else None,
                'account_id': body.account_id, 'grantee_id': str(body.grantee_id),
                'grantee_role': role, 'permission': body.permission, 'requested_by': who.id}
    return {'proposal': proposal, 'preview_hash': digest(proposal),
            'validated_local_references': True, 'grant_applied': False, 'executable': False,
            'external_calls': False, 'requires_apply_checkpoint': 'S2.1B',
            'blockers': ['grant_storage_and_execution_fence_not_implemented'] + (
                ['model_config_version_and_manager_missing'] if body.kind == 'model' else []) + (
                ['connection_not_connected'] if source['stored_status'] != 'connected' else []) + (
                ['authentication_missing' if body.kind == 'cli_model' else 'credential_missing']
                if not source.get('authentication_ready', source['credential_present']) else [])}


from .grants_api import mount
mount(router, MappingPreview, preview)
from .ads_api import mount as mount_ads
mount_ads(router)
