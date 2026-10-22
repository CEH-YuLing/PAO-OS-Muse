"""Data-only Studio APIs; published definitions do not grant execution rights."""
from uuid import UUID
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ...access import membership
from ...auth import Principal, principal
from ...config import settings
from ...db import database
from ...models import StudioDefinition, StudioVersion, StudioEvent, Workspace, now
from .contracts import Closed, Kind, RESERVED, digest, shadow
from .service import append, lint, event, transition, definition_view, version_view, reject
from . import planning,durable
from .results import verify_result

router = APIRouter(prefix='/v1/studio')


@router.get('/durable/status')
async def durable_status(workspace_id: UUID,request:Request,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    await scope(db,workspace_id,who)
    ready=False
    if settings().workflow_worker_enabled:
        import asyncio
        from .arq_bridge import worker_marker
        try:
            values=await asyncio.wait_for(request.app.state.redis.mget(
                'pao:studio:arq:health','pao:studio:temporal:health'),timeout=1)
            ready=all(v and v.decode()==worker_marker() for v in values)
        except Exception:
            ready=False
    return {'admission_enabled':settings().workflow_durable_enabled,
            'dispatch_enabled':settings().workflow_dispatch_enabled,'dry_run_only':True,
            'arq_bridge_ready':ready,'model_calls':False}


@router.post('/plans/{plan_id}/execution',status_code=202)
async def durable_start(plan_id:UUID,body:durable.DurableStart,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    row=await durable.admit(db,plan_id,who,body);await db.commit();return await durable.execution_view(db,row)


@router.get('/executions/{execution_id}')
async def durable_read(execution_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    from ...models import StudioExecution,StudioCommand
    from ...access import membership
    row=await db.get(StudioExecution,str(execution_id))
    if not row:reject('durable_execution_not_found',404)
    await membership(db,row.workspace_id,who)
    commands=list(await db.scalars(select(StudioCommand).where(StudioCommand.execution_id==row.id).order_by(StudioCommand.ordinal)))
    return {**(await durable.execution_view(db,row)),'commands':[{'id':c.id,'operation':c.operation,'status':c.status,
            'attempts':c.attempts,'error_code':c.error_code} for c in commands]}


@router.post('/executions/{execution_id}/decision')
async def durable_decision(execution_id:UUID,body:durable.DurableDecision,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    row=await durable.lock_execution(db,execution_id);await durable.decide(db,row,who,body)
    await db.commit();return await durable.execution_view(db,row)


@router.post('/executions/{execution_id}/cancel')
async def durable_cancel(execution_id:UUID,body:durable.DurableCancel,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    row=await durable.lock_execution(db,execution_id);await durable.cancel(db,row,who,body)
    await db.commit();return await durable.execution_view(db,row)


@router.get('/planning/status')
async def planning_status(workspace_id: UUID, who: Principal=Depends(principal), db: AsyncSession=Depends(database)):
    await scope(db,workspace_id,who)
    return {'enabled':settings().workflow_planning_enabled,'execution_enabled':False,'model_calls':False}


@router.post('/definitions/{definition_id}/plan-preview')
async def plan_preview(definition_id: UUID, body: planning.PlanInput, who: Principal=Depends(principal), db: AsyncSession=Depends(database)):
    row,_=await owned(db,definition_id,who,True)
    planning.identity(row,who.id,body)
    return await planning.compile_plan(db,row,who.id,body)


@router.post('/definitions/{definition_id}/plans',status_code=201)
async def create_plan(definition_id: UUID, body: planning.PlanCreate, who: Principal=Depends(principal), db: AsyncSession=Depends(database)):
    row,_=await owned(db,definition_id,who,True)
    result=await planning.save_plan(db,row,who.id,body)
    await db.commit()
    return result


@router.get('/plans/{plan_id}')
async def read_plan(plan_id: UUID,who: Principal=Depends(principal),db: AsyncSession=Depends(database)):
    planning.require_planning()
    row=await db.get(StudioEvent,str(plan_id))
    if not row or row.action!='p61_plan_created':reject('workflow_plan_not_found',404)
    await scope(db,row.workspace_id,who)
    snapshot=row.data['snapshot']
    if snapshot['sha256']!=digest({key:value for key,value in snapshot.items() if key!='sha256'}):
        reject('workflow_plan_hash_mismatch',409)
    return row.data


class Create(Closed):
    workspace_id: str
    kind: Kind
    slug: str = Field(pattern=r'^[a-z][a-z0-9-]{2,59}$')
    name: str = Field(min_length=1, max_length=120)
    payload: dict
    category: Literal['design','marketing','editor','ads','content','analysis','operations','other'] | None = None


class Edit(Closed):
    revision: int = Field(ge=1)
    payload: dict


class Action(Closed):
    revision: int = Field(ge=1)
    self_review: bool = False


class Fixture(Closed):
    input: dict
    expected_output: dict


class Import(Closed):
    definition: Create
    confirmation_hash: str | None = None


class Bootstrap(Closed):
    workspace_id: str


async def scope(db, workspace_id, who, write=False):
    if not settings().studio_enabled:
        reject('studio_disabled', 503)
    try:
        UUID(str(workspace_id))
    except ValueError:
        reject('studio_workspace_invalid')
    return await membership(db, str(workspace_id), who, write)


async def owned(db, definition_id, who, write=False, revision=None):
    query = select(StudioDefinition).where(StudioDefinition.id == str(definition_id))
    if write:
        query = query.with_for_update().execution_options(populate_existing=True)
    row = await db.scalar(query)
    if not row:
        reject('studio_not_found', 404)
    member = await scope(db, row.workspace_id, who, write)
    if write and row.owner_id != who.id and member.role not in ('owner', 'admin'):
        reject('studio_write_denied', 403)
    if revision is not None and row.revision != revision:
        reject('studio_revision_conflict', 409)
    return row, member


@router.get('/definitions')
async def catalog(workspace_id: UUID, kind: Kind | None = None, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    await scope(db, workspace_id, who)
    query = select(StudioDefinition).where(StudioDefinition.workspace_id == str(workspace_id))
    if kind:
        query = query.where(StudioDefinition.kind == kind)
    rows = list(await db.scalars(query.order_by(StudioDefinition.created_at).limit(200)))
    return {'definitions': [definition_view(row) for row in rows], 'skill_execution': 'llm_text', 'workflow_execution_enabled': False}


@router.post('/bootstrap')
async def bootstrap(body: Bootstrap, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    member = await scope(db, body.workspace_id, who, True)
    if member.role not in ('owner','admin'):
        reject('studio_reviewer_denied',403)
    await db.scalar(select(Workspace).where(Workspace.id == body.workspace_id).with_for_update())
    from ...agents import REGISTRY as agents
    from ...skills import REGISTRY as skills
    entries = [('agents', key.replace('_','-'), value.name,
        {'seed_registry':'agent-config','key':key,'config':{'instruction':value.system_prompt,'prompt_version':value.prompt_version}})
        for key,value in agents.items()]
    entries += [('skills', key, key, {'seed_registry':'skill-config','key':key,'config':value.model_dump(mode='json')})
        for key,value in skills.items()]
    imported = 0
    for kind,slug,name,payload in entries:
        row = await db.scalar(select(StudioDefinition).where(StudioDefinition.workspace_id == body.workspace_id,
            StudioDefinition.kind == kind, StudioDefinition.slug == slug))
        if row:
            if not row.seed:
                reject('studio_seed_slug_conflict',409)
            seed = await db.get(StudioVersion,row.published_version_id)
            if not seed or seed.content_hash != digest(payload):
                reject('studio_seed_drift',409)
            continue
        row = StudioDefinition(workspace_id=body.workspace_id,owner_id=who.id,kind=kind,slug=slug,name=name,revision=1,seed=True)
        db.add(row)
        await db.flush()
        seed = StudioVersion(workspace_id=row.workspace_id,definition_id=row.id,author_id=who.id,
            ordinal=1,payload=payload,content_hash=digest(payload),status='published')
        db.add(seed)
        await db.flush()
        row.published_version_id=seed.id
        event(db,row,who.id,'seed_mirror_imported',seed,execution_authority='immutable_file_registry')
        imported += 1
    await db.commit()
    return {'imported':imported,'seed_count':len(entries),'mutable_execution_registry':False}


@router.post('/definitions/{definition_id}/clone', status_code=201)
async def clone(definition_id: UUID, body: Create, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    row,_ = await owned(db,definition_id,who)
    if body.workspace_id != row.workspace_id or body.kind != row.kind:
        reject('studio_clone_scope')
    # Explicit new draft, not a mutation of the defaults or inherited approval.
    return await create_definition(body,who,db)


async def create_definition(body, who, db):
    await scope(db, body.workspace_id, who, True)
    if body.category is not None and body.kind != 'skills':
        reject('studio_category_requires_skill')
    # Workspace lock serializes slug uniqueness and bounded creation.
    await db.scalar(select(Workspace).where(Workspace.id == body.workspace_id).with_for_update())
    if body.slug in RESERVED:
        reject('studio_reserved_slug')
    if await db.scalar(select(StudioDefinition.id).where(StudioDefinition.workspace_id == body.workspace_id,
            StudioDefinition.kind == body.kind, StudioDefinition.slug == body.slug)):
        reject('studio_slug_conflict', 409)
    if len(list(await db.scalars(select(StudioDefinition.id).where(StudioDefinition.workspace_id == body.workspace_id).limit(200)))) >= 200:
        reject('studio_definition_limit', 409)
    row = StudioDefinition(workspace_id=body.workspace_id, owner_id=who.id, kind=body.kind,
        slug=body.slug, name=body.name, revision=1, seed=False)
    db.add(row)
    await db.flush()
    version = await append(db, row, body.payload, who.id)
    if body.category is not None:
        event(db,row,who.id,'catalog_categorized',category=body.category)
    await db.commit()
    return {'definition': definition_view(row), 'version': version_view(version)}


@router.post('/definitions', status_code=201)
async def create(body: Create, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    return await create_definition(body, who, db)


@router.get('/definitions/{definition_id}')
async def detail(definition_id: UUID, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    row, _ = await owned(db, definition_id, who)
    versions = list(await db.scalars(select(StudioVersion).where(StudioVersion.definition_id == row.id).order_by(StudioVersion.ordinal.desc()).limit(100)))
    events = list(await db.scalars(select(StudioEvent).where(StudioEvent.definition_id == row.id).order_by(StudioEvent.created_at.desc()).limit(100)))
    return {'definition': definition_view(row), 'versions': [version_view(v) for v in versions],
        'events': [{'id': e.id, 'actor_id': e.actor_id, 'action': e.action, 'data': e.data} for e in events]}


@router.post('/definitions/{definition_id}/versions', status_code=201)
async def edit(definition_id: UUID, body: Edit, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    row, _ = await owned(db, definition_id, who, True, body.revision)
    if row.seed or row.archived_at:
        reject('studio_definition_read_only', 409)
    version = await append(db, row, body.payload, who.id)
    await db.commit()
    return {'definition': definition_view(row), 'version': version_view(version)}


@router.post('/definitions/{definition_id}/versions/{version_id}/actions/{action}')
async def move(definition_id: UUID, version_id: UUID, action: Literal['validate','review','publish','rollback'], body: Action,
        who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    row, member = await owned(db, definition_id, who, True, body.revision)
    if action != 'validate' and member.role not in ('owner', 'admin'):
        reject('studio_reviewer_denied', 403)
    version = await db.get(StudioVersion, str(version_id))
    if not version or version.definition_id != row.id:
        reject('studio_version_not_found', 404)
    await transition(db, row, version, who.id, action, body.self_review)
    await db.commit()
    return {'definition': definition_view(row), 'version': version_view(version)}


@router.post('/definitions/{definition_id}/versions/{version_id}/fixture')
async def fixture(definition_id: UUID, version_id: UUID, body: Fixture, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    row, _ = await owned(db, definition_id, who, True)
    version = await db.get(StudioVersion, str(version_id))
    if not version or version.definition_id != row.id:
        reject('studio_version_not_found', 404)
    value, links = await lint(db, row, version.payload, who.id)
    if row.kind == 'agents':
        reject('studio_fixture_requires_schema')
    try:
        receipt = verify_result(value, body.input, body.expected_output)
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        reject('studio_fixture_invalid')
    event(db,row,who.id,'fixture_passed',version,mode='schema_only',model_executed=False,receipt=receipt)
    await db.commit()
    return {'valid': True, 'mode': 'schema_only', 'model_executed': False, 'hash': version.content_hash, 'links': links}


@router.post('/definitions/{definition_id}/archive')
async def archive(definition_id: UUID, body: Action, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    row, _ = await owned(db, definition_id, who, True, body.revision)
    if row.seed:
        reject('studio_seed_read_only', 409)
    row.archived_at = now()
    row.revision += 1
    event(db, row, who.id, 'archived')
    await db.commit()
    return definition_view(row)


@router.get('/definitions/{definition_id}/export')
async def export(definition_id: UUID, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    row, _ = await owned(db, definition_id, who)
    versions = list(await db.scalars(select(StudioVersion).where(StudioVersion.definition_id == row.id).order_by(StudioVersion.ordinal.desc()).limit(1)))
    if row.seed or not versions:
        reject('studio_export_clone_only')
    body = Create(workspace_id=row.workspace_id, kind=row.kind, slug=row.slug, name=row.name, payload=versions[0].payload)
    data = body.model_dump(exclude_none=True)
    return {'definition': data, 'confirmation_hash': digest(data), 'portable_links': False}


@router.post('/import')
async def import_definition(body: Import, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    data = body.definition.model_dump(exclude_none=True)
    await scope(db, body.definition.workspace_id, who, bool(body.confirmation_hash))
    scratch = StudioDefinition(workspace_id=body.definition.workspace_id, kind=body.definition.kind)
    await lint(db, scratch, body.definition.payload, who.id)
    checksum = digest(data)
    if body.confirmation_hash is None:
        return {'valid': True, 'mode': 'dry_run', 'confirmation_hash': checksum, 'creates_status': 'draft'}
    if body.confirmation_hash != checksum:
        reject('studio_import_hash_conflict', 409)
    return await create_definition(body.definition, who, db)


@router.get('/routing-shadow')
async def routing_shadow(workspace_id: UUID, text: str = '', who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    await scope(db, workspace_id, who)
    if len(text) > 2000:
        reject('studio_shadow_input_limit')
    rows = list(await db.scalars(select(StudioDefinition).where(StudioDefinition.workspace_id == str(workspace_id),
        StudioDefinition.kind == 'skills', StudioDefinition.archived_at.is_(None), StudioDefinition.published_version_id.is_not(None)).limit(200)))
    return shadow(text, rows)
