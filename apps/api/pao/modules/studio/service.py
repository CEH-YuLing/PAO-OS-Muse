"""Workspace-scoped, append-only Studio definitions. No execution authority."""
from fastapi import HTTPException
from sqlalchemy import select, func
from ...models import StudioDefinition, StudioVersion, StudioEvent, now
from .contracts import clean, digest, compatible, validate_value


def reject(code, status=422):
    raise HTTPException(status, code)


async def version(db, version_id, workspace_id, kind=None):
    row = await db.get(StudioVersion, version_id)
    if not row or row.workspace_id != workspace_id:
        reject('studio_version_not_found', 404)
    definition = await db.get(StudioDefinition, row.definition_id)
    if definition.seed:
        reject('studio_seed_clone_required')
    if kind and definition.kind != kind:
        reject('studio_link_kind')
    if definition.archived_at or row.status != 'published' or definition.published_version_id != row.id:
        reject('studio_link_not_published')
    if digest(row.payload) != row.content_hash:
        reject('studio_hash_mismatch', 409)
    return row


async def lint(db, definition, payload, actor=None):
    try:
        value = clean(definition.kind, payload)
    except (ValueError, KeyError, TypeError, OverflowError, RecursionError):
        reject('studio_invalid_definition')
    links = []
    if definition.kind == 'agents' and value.get('brain_id'):
        from ...models import Brain
        brain = await db.get(Brain, value['brain_id'])
        if not brain or brain.workspace_id != definition.workspace_id or brain.archived_at:
            reject('studio_brain_scope')
        if actor:
            from ...auth import Principal
            from ..brains.access import require_brain
            await require_brain(db,Principal(actor,0),brain.id)
    if definition.kind == 'skills':
        agent = await version(db, value['agent_version_id'], definition.workspace_id, 'agents')
        if actor:
            agent_definition=await db.get(StudioDefinition,agent.definition_id)
            await lint(db,agent_definition,agent.payload,actor)
        links.append({'id': agent.id, 'hash': agent.content_hash})
        for tool_id in value['allowed_tools']:
            if tool_id.startswith('mcp.'):
                from uuid import UUID
                from ...auth import Principal
                from ..connectors.service import owned,approved_tool
                if not actor:reject('studio_connector_owner_required',403)
                row=await owned(db,str(UUID(tool_id.split('.')[1])),Principal(actor,0))
                if row.workspace_id!=definition.workspace_id or row.status!='connected':reject('studio_connector_scope')
                grant=row.permissions.get(tool_id)
                if not grant:reject('studio_connector_permission_required',403)
                tool=approved_tool(row,tool_id,grant['hash'])
                links.append({'id':row.id,'kind':'connector','hash':row.manifest_hash,'version':row.version,'tool_id':tool_id,'schema_hash':tool['hash']})
    if definition.kind == 'workflows':
        steps = {item['id']: item for item in value['steps']}
        if len(steps) != len(value['steps']):
            reject('studio_duplicate_step')
        schemas = {}
        for key, step in steps.items():
            if len(set(step['depends_on'])) != len(step['depends_on']) or set(step['depends_on']) - set(steps) or key in step['depends_on']:
                reject('studio_dependency_invalid')
            skill = await version(db, step['skill_version_id'], definition.workspace_id, 'skills')
            await version(db, skill.payload['agent_version_id'], definition.workspace_id, 'agents')
            if actor:
                skill_definition=await db.get(StudioDefinition,skill.definition_id)
                await lint(db,skill_definition,skill.payload,actor)
            schemas[key] = skill.payload
            links.append({'id': skill.id, 'hash': skill.content_hash})
        visited, active = set(), set()
        def visit(key):
            if key in active:
                reject('studio_workflow_cycle')
            if key in visited:
                return
            active.add(key)
            for dep in steps[key]['depends_on']:
                visit(dep)
            active.remove(key)
            visited.add(key)
        for key in steps:
            visit(key)
        def source(binding, deps):
            if binding['source'] == 'workflow':
                if binding.get('step') is not None:
                    reject('studio_binding_invalid')
                schema = value['input_schema']
            else:
                target = binding.get('step')
                if target not in deps:
                    reject('studio_binding_dependency')
                schema = schemas[target]['output_schema']
            if binding['field'] not in schema.get('required', []):
                reject('studio_binding_optional_or_missing')
            return schema['properties'][binding['field']]
        def bindings(mapping, target, deps):
            if set(mapping) - set(target['properties']) or set(target.get('required', [])) - set(mapping):
                reject('studio_binding_fields')
            for field, binding in mapping.items():
                if not compatible(source(binding, deps), target['properties'][field]):
                    reject('studio_binding_schema')
        for key, step in steps.items():
            bindings(step['inputs'], schemas[key]['input_schema'], set(step['depends_on']))
        bindings(value['outputs'], value['output_schema'], set(steps))
    return value, links


def event(db, definition, actor, action, row=None, **data):
    db.add(StudioEvent(workspace_id=definition.workspace_id, definition_id=definition.id,
        version_id=row.id if row else None, actor_id=actor, action=action,
        data={'hash': row.content_hash if row else None, **data}))


async def append(db, definition, payload, actor):
    value, _ = await lint(db, definition, payload, actor)
    ordinal = (await db.scalar(select(func.max(StudioVersion.ordinal)).where(
        StudioVersion.definition_id == definition.id)) or 0) + 1
    row = StudioVersion(workspace_id=definition.workspace_id, definition_id=definition.id,
        author_id=actor, ordinal=ordinal, payload=value, content_hash=digest(value), status='draft')
    db.add(row)
    await db.flush()
    definition.revision += 1
    event(db, definition, actor, 'draft_created', row)
    return row


def definition_view(row):
    return {'id': row.id, 'workspace_id': row.workspace_id, 'owner_id': row.owner_id,
        'kind': row.kind, 'slug': row.slug, 'name': row.name, 'revision': row.revision,
        'seed': row.seed, 'published_version_id': row.published_version_id,
        'archived': row.archived_at is not None}


def version_view(row):
    return {'id': row.id, 'definition_id': row.definition_id, 'ordinal': row.ordinal,
        'author_id': row.author_id, 'status': row.status, 'hash': row.content_hash,
        'payload': row.payload}


async def transition(db, definition, row, actor, action, self_review=False):
    if definition.seed or definition.archived_at:
        reject('studio_definition_read_only', 409)
    _, links = await lint(db, definition, row.payload, actor)
    if digest(row.payload) != row.content_hash:
        reject('studio_hash_mismatch', 409)
    if action == 'validate':
        if row.status != 'draft':
            reject('studio_transition_invalid', 409)
        row.status = 'validated'
    elif action == 'review':
        if row.status != 'validated':
            reject('studio_transition_invalid', 409)
        if actor == row.author_id and not self_review:
            reject('studio_independent_review_or_ack_required', 409)
        if definition.kind != 'agents' and not await db.scalar(select(StudioEvent.id).where(
            StudioEvent.version_id == row.id, StudioEvent.action == 'fixture_passed')):
            reject('studio_schema_fixture_required',409)
        row.status = 'reviewed'
    elif action in ('publish', 'rollback'):
        if row.status not in (('reviewed',) if action == 'publish' else ('deprecated',)):
            reject('studio_transition_invalid', 409)
        if action == 'rollback' and not await db.scalar(select(StudioEvent.id).where(
            StudioEvent.version_id == row.id, StudioEvent.action == 'review')):
            reject('studio_review_missing', 409)
        review=await db.scalar(select(StudioEvent).where(StudioEvent.version_id==row.id,StudioEvent.action=='review').order_by(StudioEvent.created_at.desc()).limit(1))
        if not review or review.data.get('links')!=links:reject('studio_review_scope_changed',409)
        if definition.published_version_id:
            old = await db.get(StudioVersion, definition.published_version_id)
            old.status = 'deprecated'
        row.status = 'published'
        definition.published_version_id = row.id
    definition.revision += 1
    event(db, definition, actor, action, row, links=links, self_review=self_review if action == 'review' else False)
    return row
