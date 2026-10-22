"""Versioned SME routing authoring and preflight. No enqueue, discovery or LLM."""
from sqlalchemy import select
from ...models import BusinessRoutingVersion, StudioDefinition, TenantConnectionReference
from .contracts import digest
from .routing_contracts import RoutingContent, resolve
from .access import reject, brand_scope


async def latest(db, wid, revision=None):
    query = select(BusinessRoutingVersion).where(BusinessRoutingVersion.workspace_id == wid)
    if revision is not None:
        query = query.where(BusinessRoutingVersion.revision == revision)
    row = await db.scalar(query.order_by(BusinessRoutingVersion.revision.desc()).limit(1))
    if row and digest(row.content) != row.content_hash:
        reject('business_routing_integrity_failed')
    return row


def public(row):
    return {'id': row.id, 'workspace_id': row.workspace_id, 'revision': row.revision,
            'content': row.content, 'content_hash': row.content_hash, 'actor_id': row.actor_id,
            'created_at': row.created_at.isoformat(), 'execution_enabled': False,
            'scope': 'configuration_only', 'fallback_enabled': False}


async def skill(db, wid, who, version_id):
    from ..studio.service import version, lint
    from ...config import settings
    if not settings().studio_enabled:
        reject('business_routing_studio_disabled', 503)
    row = await version(db, str(version_id), wid, 'skills')
    definition = await db.get(StudioDefinition, row.definition_id)
    await lint(db, definition, row.payload, who.id)
    # The first business adapter is intentionally text only and tool free.
    if row.payload.get('mode') != 'llm_text' or row.payload.get('allowed_tools'):
        reject('business_routing_text_only_skill_required', 422)
    agent = await version(db, row.payload['agent_version_id'], wid, 'agents')
    return row, agent


async def validate_links(db, wid, who, content):
    from ..studio.service import version, lint
    for target in content.targets:
        if target.installation_resource_id:
            from ..installation_ai.service import config
            from ..engines.contract import EngineFailure
            try:
                chosen=await config(db,wid,who.id,None,str(target.installation_resource_id),target.model,target.reasoning_effort)
                if chosen['provider']!=target.provider:reject('business_routing_resource_mismatch',422)
            except EngineFailure:reject('business_routing_resource_unavailable',422)
        if target.reference_id:
            ref = await db.scalar(select(TenantConnectionReference).where(TenantConnectionReference.id==str(target.reference_id),TenantConnectionReference.workspace_id==wid))
            if not ref:reject('connection_reference_not_found',404)
            # Shared routing is not credential management or inference consent.
            # Every actor still needs their own activated grant at job admission.
            if ref.kind != 'model' or ref.provider != target.provider or ref.status != 'staged':
                reject('business_routing_reference_unavailable', 422)
    for mapping in content.specialists:
        await skill(db, wid, who, mapping.skill_version_id)
    for layer in content.layers:
        if layer.kind == 'brand':
            await brand_scope(db, wid, str(layer.scope_id))
        else:
            row = await version(db, str(layer.scope_id), wid, 'agents' if layer.kind == 'agent' else 'workflows')
            definition = await db.get(StudioDefinition, row.definition_id)
            await lint(db, definition, row.payload, who.id)
            if layer.kind == 'step' and not any(s['id'] == layer.step_id for s in row.payload['steps']):
                reject('business_routing_step_not_found', 404)


async def save(db, wid, who, body):
    current = await latest(db, wid)
    content = body.content.model_dump(mode='json', exclude_none=True); hashed = digest(content)
    prior = await db.scalar(select(BusinessRoutingVersion).where(
        BusinessRoutingVersion.workspace_id == wid, BusinessRoutingVersion.request_key == str(body.request_key)))
    if prior:
        if (prior.content_hash != hashed or prior.actor_id != who.id
                or prior.revision != body.expected_revision + 1 or prior.id != current.id):
            reject('business_routing_request_conflict')
        return public(prior)
    if (current.revision if current else 0) != body.expected_revision:
        reject('business_routing_revision_conflict')
    await validate_links(db, wid, who, body.content)
    row = BusinessRoutingVersion(workspace_id=wid, revision=body.expected_revision + 1,
        actor_id=who.id, request_key=str(body.request_key), content=content, content_hash=hashed)
    db.add(row); await db.flush(); result = public(row); await db.commit(); return result


async def preview(db, wid, who, plan, version, body):
    from .access import profile_scope, profile_version
    from ..studio.service import version as studio_version
    from ..engines.contract import EngineFailure
    from ..connections.model_authority import pin
    from ...models import ModelProviderConnection
    routing = await latest(db, wid)
    if not routing or routing.revision != body.routing_revision or plan.revision != body.plan_revision:
        reject('business_routing_source_changed')
    if digest(version.content) != version.content_hash:
        reject('business_planning_integrity_failed')
    profile = await profile_scope(db, wid, plan.profile_id); source = await profile_version(db, profile)
    if source.id != version.profile_version_id:
        reject('business_planning_profile_changed')
    item = next((v for v in version.content['deliverables'] if v['key'] == body.item_key), None)
    if item is None:
        reject('business_routing_item_not_found', 404)
    content = RoutingContent.model_validate(routing.content)
    mapping = next((v for v in content.specialists if v.kind == item['specialist']), None)
    if not mapping:
        reject('business_routing_specialist_not_configured', 422)
    selected, agent = await skill(db, wid, who, mapping.skill_version_id)
    workflow = None
    if body.workflow_version_id:
        workflow = await studio_version(db, str(body.workflow_version_id), wid, 'workflows')
        step = next((v for v in workflow.payload['steps'] if v['id'] == body.step_id), None)
        if not step or step['skill_version_id'] != selected.id:
            reject('business_routing_step_skill_mismatch', 422)
    try:
        effective, target, trace = resolve(content, brand_id=profile.brand_id, agent_id=agent.id,
            workflow_id=workflow.id if workflow else None, step_id=body.step_id, job=body.job)
    except ValueError:
        reject('business_routing_override_denied', 422)
    preference = agent.payload.get('model_preference')
    expected={'provider':target.provider,'model':target.model}
    if target.installation_resource_id:expected['installation_resource_id']=str(target.installation_resource_id)
    if target.reasoning_effort is not None:expected['reasoning_effort']=target.reasoning_effort
    if preference and {k:v for k,v in preference.items() if v is not None} != expected:
        reject('business_routing_agent_model_mismatch', 422)
    brain_id = agent.payload.get('brain_id')
    if brain_id:
        from ...auth import Principal
        from ..brains.access import require_brain
        brain = await require_brain(db, Principal(who.id, 0), brain_id)
        if brain.workspace_id != wid or brain.brand_id != profile.brand_id:
            reject('business_routing_brain_scope_denied', 403)
        # No private Brain content leaves its local context via a routing choice.
        if target.provider != 'ollama':
            reject('business_routing_private_cloud_context_not_supported', 403)
    authority = None
    if target.provider == 'ollama':
        if body.grant_id:
            reject('business_routing_local_grant_not_applicable', 422)
    elif target.installation_resource_id:
        if body.grant_id:reject('business_routing_mixed_authority',422)
        from ..installation_ai.service import config
        try:
            value=await config(db,wid,who.id,profile.brand_id,str(target.installation_resource_id),target.model,target.reasoning_effort)
            if value['provider']!=target.provider:reject('business_routing_resource_mismatch',422)
            authority=value['connection_authority']
        except EngineFailure:reject('business_routing_resource_unavailable',403)
    else:
        try:
            if body.grant_id:
                authority = await pin(db, wid, who.id, profile.brand_id, str(body.grant_id))
            else:
                from ..connections import enterprise_ai
                if not enterprise_ai.enabled(await enterprise_ai.policy(db, wid)):
                    reject('business_routing_model_grant_required', 403)
                ref = await db.get(TenantConnectionReference, str(target.reference_id))
                if not ref or ref.workspace_id != wid or ref.kind != 'model':
                    reject('business_routing_model_grant_required', 403)
                authority = await enterprise_ai.pin(db, wid, who.id, profile.brand_id, ref.source_id)
        except EngineFailure:
            reject('business_routing_model_grant_denied', 403)
        ref = await db.get(TenantConnectionReference, str(target.reference_id))
        connection = await db.get(ModelProviderConnection, authority['source_id'])
        if ((authority.get('reference_id', str(target.reference_id))) != str(target.reference_id) or not ref or ref.workspace_id != wid
                or ref.provider != target.provider or not connection or connection.workspace_id != wid
                or connection.status != 'connected' or connection.provider != target.provider or connection.model != target.model):
            reject('business_routing_model_grant_denied', 403)
    # Reviewed skill caps remain an additional ceiling, never overwritten by UI.
    for field in ('token_budget', 'output_tokens', 'timeout_seconds'):
        effective[field] = min(effective[field], selected.payload[field])
    target_value=target.model_dump(mode='json')
    for key in ('installation_resource_id','reasoning_effort'):
        if target_value.get(key) is None:target_value.pop(key,None)
    value = {'workspace_id': wid, 'actor_id': who.id, 'brand_id': profile.brand_id,
        'routing_version_id': routing.id, 'routing_revision': routing.revision, 'routing_hash': routing.content_hash,
        'plan_version_id': version.id, 'plan_hash': version.content_hash,
        'profile_version_id': source.id, 'profile_hash': source.content_hash, 'item_key': item['key'],
        'specialist': item['specialist'], 'skill_version_id': selected.id, 'skill_hash': selected.content_hash,
        'agent_version_id': agent.id, 'agent_hash': agent.content_hash, 'brain_id': brain_id,
        'workflow_version_id': workflow.id if workflow else None, 'workflow_hash': workflow.content_hash if workflow else None,
        'step_id': body.step_id, 'target': target_value, 'limits': effective,
        'connection_authority': authority, 'allowed_tools': [], 'fallback_targets': []}
    return {'selection': value, 'selection_hash': digest(value), 'trace': trace,
        'mode': 'preflight_only', 'execution_enabled': False, 'external_actions_allowed': False,
        'model_availability_verified': False, 'quota_reserved': False, 'provider_calls': False,
        'warning': 'Chỉ xem trước cấu hình. Chưa kiểm tra model đang chạy, chưa giữ hạn mức hoặc tạo Run.'}
