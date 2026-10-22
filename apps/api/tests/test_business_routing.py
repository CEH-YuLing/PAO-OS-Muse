"""S5 routing preflight: real API/Postgres; never invoke a provider."""
import asyncio
from copy import deepcopy
from uuid import uuid4
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from pao.config import settings
from pao.db import Session
from pao.models import BusinessRoutingVersion, Brand, Member, Workspace
from pao.modules.business_planning.routing_contracts import RoutingContent, Override, resolve
from test_business_planning import base
from test_business_plan_review import draft
from test_studio import make, publish, SCHEMA
from test_model_connection_fence import fenced
from test_connection_inventory import corpus
from test_engine_contract import engines
from test_model_grant_activation import consent, revoke


def policy():
    return {'targets': [{'key': 'local', 'provider': 'ollama', 'model': 'qwen3:4b'},
                        {'key': 'second', 'provider': 'ollama', 'model': 'qwen3:8b'}],
            'default_target': 'local', 'limits': {'token_budget': 4096, 'output_tokens': 256, 'timeout_seconds': 45},
            'specialists': [], 'layers': []}


@pytest.fixture
async def ready(identity, monkeypatch):
    monkeypatch.setattr(settings(), 'business_planning_enabled', True)
    monkeypatch.setattr(settings(), 'studio_enabled', True)
    return identity


async def configured(client, identity, *, agent_payload=None):
    agent = await publish(client, identity, await make(client, identity, payload=agent_payload))
    skill = await publish(client, identity, await make(client, identity, 'skills', 's5-content', {
        'instruction': 'Return a factual JSON draft for human review.', 'agent_version_id': agent['version']['id'],
        'input_schema': SCHEMA, 'output_schema': SCHEMA}))
    value = policy(); value['specialists'] = [{'kind': 'analyst', 'skill_version_id': skill['version']['id']}]
    response = await client.put(base(identity) + '/routing', headers=identity['owner'], json={
        'expected_revision': 0, 'request_key': str(uuid4()), 'content': value})
    assert response.status_code == 200, response.text
    return response.json(), agent, skill


async def preflight(client, identity, path, **changes):
    return await client.post(path + '/routing-preview', headers=identity['owner'], json={
        'routing_revision': 1, 'plan_revision': 1, 'item_key': 'research', **changes})


@pytest.mark.parametrize('field,value', [('token_budget', True), ('output_tokens', 513), ('timeout_seconds', 0),
    ('token_budget', '4096'), ('cloud_allowed', 1), ('target', None), ('fallback_targets', ['second']),
    ('allowed_tools', ['business.ads.write']), ('secret', 'not-a-real-secret')])
def test_override_closed_strict(field, value):
    with pytest.raises(ValueError): Override.model_validate({field: value})


@pytest.mark.parametrize('cause', ['duplicate', 'duplicate_identity', 'missing_default', 'cloud_without_reference',
    'local_with_reference', 'cloud_default_private', 'escalate', 'unknown_target', 'duplicate_specialist', 'duplicate_layer'])
def test_invalid_policy(cause):
    value = policy()
    if cause == 'duplicate': value['targets'][1]['key'] = 'local'
    if cause == 'duplicate_identity': value['targets'][1]['model'] = 'qwen3:4b'
    if cause == 'missing_default': value['default_target'] = 'missing'
    if cause == 'cloud_without_reference': value['targets'][0]['provider'] = 'openai'
    if cause == 'local_with_reference': value['targets'][0]['reference_id'] = str(uuid4())
    if cause == 'cloud_default_private': value['targets'][0].update(provider='openai', reference_id=str(uuid4()))
    if cause in ('escalate', 'unknown_target', 'duplicate_layer'):
        value['layers'] = [{'kind': 'brand', 'scope_id': str(uuid4()), 'settings':
            {'token_budget': 8192} if cause == 'escalate' else {'target': 'missing'} if cause == 'unknown_target' else {}}]
        if cause == 'duplicate_layer': value['layers'] *= 2
    if cause == 'duplicate_specialist': value['specialists'] = [{'kind': 'content', 'skill_version_id': str(uuid4())}] * 2
    with pytest.raises(ValueError): RoutingContent.model_validate(value)


def test_full_inheritance_and_job_narrowing():
    brand, agent, workflow = [str(uuid4()) for _ in range(3)]
    value = policy(); value['layers'] = [
        {'kind': 'step', 'scope_id': workflow, 'step_id': 'draft', 'settings': {'output_tokens': 100}},
        {'kind': 'agent', 'scope_id': agent, 'settings': {'timeout_seconds': 20}},
        {'kind': 'brand', 'scope_id': brand, 'settings': {'target': 'second', 'token_budget': 2048}}]
    effective, target, trace = resolve(RoutingContent.model_validate(value), brand_id=brand, agent_id=agent,
        workflow_id=workflow, step_id='draft', job=Override(token_budget=1024))
    assert target.model == 'qwen3:8b' and effective['token_budget'] == 1024
    assert effective['output_tokens'] == 100 and effective['timeout_seconds'] == 20
    assert [v['scope'] for v in trace] == ['enterprise', 'brand', 'agent', 'step', 'job']
    assert trace[0]['settings']['token_budget'] == 4096


@pytest.mark.parametrize('job', [{'token_budget': 4096}, {'cloud_allowed': True}, {'target': 'local'},
    {'allowed_targets': ['local', 'second']}, {'timeout_seconds': 21}])
def test_child_cannot_expand_combined_policy(job):
    brand = str(uuid4()); value = policy(); value['layers'] = [{'kind': 'brand', 'scope_id': brand,
        'settings': {'target': 'second', 'allowed_targets': ['second'], 'token_budget': 1024, 'timeout_seconds': 20}}]
    with pytest.raises(ValueError): resolve(RoutingContent.model_validate(value), brand_id=brand, job=Override(**job))


async def test_config_cas_replay_history_immutable(client, ready):
    url = base(ready) + '/routing'; body = {'expected_revision': 0, 'request_key': str(uuid4()), 'content': policy()}
    first = await client.put(url, headers=ready['owner'], json=body); assert first.status_code == 200, first.text
    assert (await client.put(url, headers=ready['owner'], json=body)).json() == first.json()
    changed = deepcopy(body); changed['content']['default_target'] = 'second'
    assert (await client.put(url, headers=ready['owner'], json=changed)).status_code == 409
    changed.update(expected_revision=1, request_key=str(uuid4()))
    second = await client.put(url, headers=ready['owner'], json=changed)
    assert second.status_code == 200 and second.json()['revision'] == 2
    assert (await client.get(url + '/versions/1', headers=ready['owner'])).json() == first.json()
    assert (await client.put(url, headers=ready['owner'], json=body)).status_code == 409
    async with Session() as db:
        row = await db.get(BusinessRoutingVersion, first.json()['id']); row.content_hash = '0' * 64
        with pytest.raises(DBAPIError): await db.commit()
        await db.rollback()
        with pytest.raises(DBAPIError): await db.execute(text('DELETE FROM business_routing_versions'))
        await db.rollback()
        with pytest.raises(DBAPIError):
            await db.execute(text('INSERT INTO business_routing_versions SELECT gen_random_uuid(),created_at,workspace_id,9,actor_id,:key,content,content_hash FROM business_routing_versions LIMIT 1'), {'key': str(uuid4())})
        await db.rollback()


async def test_concurrent_cas_one_winner(client, ready):
    async def write():
        return await client.put(base(ready) + '/routing', headers=ready['owner'], json={
            'expected_revision': 0, 'request_key': str(uuid4()), 'content': policy()})
    results = await asyncio.gather(write(), write())
    assert sorted(r.status_code for r in results) == [200, 409]


async def test_sme_role_brand_isolation(client, ready):
    async with Session.begin() as db:
        other = Workspace(name='SME B'); db.add(other); await db.flush()
        db.add(Member(workspace_id=other.id, user_id=ready['user_id'], role='owner'))
        brand = Brand(workspace_id=other.id, name='Nhánh riêng'); db.add(brand); await db.flush()
    body = {'expected_revision': 0, 'request_key': str(uuid4()), 'content': policy()}
    assert (await client.put(base(ready) + '/routing', headers=ready['owner'], json=body)).status_code == 200
    second = f'/v1/workspaces/{other.id}/business-planning/routing'
    assert (await client.get(second, headers=ready['owner'])).json()['item'] is None
    for headers, code in ((ready['other'], 403), (ready['outsider'], 404), ({}, 401)):
        assert (await client.get(base(ready) + '/routing', headers=headers)).status_code == code
    body.update(expected_revision=1, request_key=str(uuid4()))
    body['content']['layers'] = [{'kind': 'brand', 'scope_id': brand.id, 'settings': {}}]
    assert (await client.put(base(ready) + '/routing', headers=ready['owner'], json=body)).status_code == 404


async def test_preview_two_models_no_calls_or_native_work(client, ready):
    _, agent, _ = await configured(client, ready); path, plan, _ = await draft(client, ready)
    first = await preflight(client, ready, path); assert first.status_code == 200, first.text
    assert first.json()['selection']['target']['model'] == 'qwen3:4b'
    second = await preflight(client, ready, path, job={'target': 'second'})
    assert second.status_code == 200 and second.json()['selection']['target']['model'] == 'qwen3:8b'
    assert first.json()['selection_hash'] != second.json()['selection_hash']
    assert first.json()['execution_enabled'] is False and first.json()['model_availability_verified'] is False
    assert first.json()['selection']['allowed_tools'] == first.json()['selection']['fallback_targets'] == []
    async with Session() as db:
        for table in ('tasks', 'runs', 'task_attempts', 'studio_executions'):
            assert await db.scalar(text('SELECT count(*) FROM ' + table)) == 0


@pytest.mark.parametrize('cause,code', [('revision', 409), ('item', 404), ('specialist', 422),
    ('override', 422), ('grant', 422), ('workflow', 422), ('source', 409), ('unpublished', 422)])
async def test_preview_denials(client, ready, cause, code):
    _, agent, _ = await configured(client, ready); path, row, body = await draft(client, ready); changes = {}
    if cause == 'revision': changes['routing_revision'] = 2
    if cause == 'item': changes['item_key'] = 'missing'
    if cause == 'specialist': changes['item_key'] = 'content'
    if cause == 'override': changes['job'] = {'token_budget': 8192}
    if cause == 'grant': changes['grant_id'] = str(uuid4())
    if cause == 'workflow': changes['step_id'] = 'draft'
    if cause == 'source':
        body.update(expected_revision=1, request_key=str(uuid4())); body['content']['title'] = 'Changed'
        assert (await client.put(path, headers=ready['owner'], json=body)).status_code == 200
    if cause == 'unpublished':
        from pao.models import StudioDefinition
        async with Session.begin() as db:
            definition = await db.get(StudioDefinition, agent['definition']['id']); definition.published_version_id = None
    response = await preflight(client, ready, path, **changes)
    assert response.status_code == code, response.text


async def test_agent_model_preference_not_silently_overridden(client, ready):
    await configured(client, ready, agent_payload={'instruction': 'Write a factual answer.',
        'model_preference': {'provider': 'ollama', 'model': 'qwen3:4b'}})
    path, _, _ = await draft(client, ready)
    assert (await preflight(client, ready, path, job={'target': 'second'})).status_code == 422


async def test_flag_and_studio_missing_fail_closed(client, identity, monkeypatch):
    assert (await client.get(base(identity) + '/routing', headers=identity['owner'])).status_code == 503
    monkeypatch.setattr(settings(), 'business_planning_enabled', True)
    body = {'expected_revision': 0, 'request_key': str(uuid4()), 'content': policy()}
    body['content']['specialists'] = [{'kind': 'content', 'skill_version_id': str(uuid4())}]
    assert (await client.put(base(identity) + '/routing', headers=identity['owner'], json=body)).status_code == 503


async def test_unowned_cloud_reference_denied_without_call(client, ready):
    value = policy(); value['targets'].append({'key': 'cloud', 'provider': 'openai', 'model': 'configured', 'reference_id': str(uuid4())})
    response = await client.put(base(ready) + '/routing', headers=ready['owner'], json={
        'expected_revision': 0, 'request_key': str(uuid4()), 'content': value})
    assert response.status_code == 404


async def test_stored_layers_roundtrip_and_workflow_step(client, ready):
    saved, agent, skill = await configured(client, ready)
    workflow = await publish(client, ready, await make(client, ready, 'workflows', 's5-flow', {
        'input_schema': SCHEMA, 'output_schema': SCHEMA, 'steps': [{'id': 'draft',
            'skill_version_id': skill['version']['id'], 'depends_on': [], 'inputs': {'text': {'source': 'workflow', 'field': 'text'}}}],
        'outputs': {'text': {'source': 'step', 'step': 'draft', 'field': 'text'}}}))
    content = saved['content']; content['layers'] = [
        {'kind': 'agent', 'scope_id': agent['version']['id'], 'settings': {'token_budget': 2048}},
        {'kind': 'step', 'scope_id': workflow['version']['id'], 'step_id': 'draft', 'settings': {'target': 'second', 'output_tokens': 100}}]
    response = await client.put(base(ready) + '/routing', headers=ready['owner'], json={
        'expected_revision': 1, 'request_key': str(uuid4()), 'content': content})
    assert response.status_code == 200, response.text
    path, _, _ = await draft(client, ready)
    checked = await preflight(client, ready, path, routing_revision=2, workflow_version_id=workflow['version']['id'], step_id='draft')
    assert checked.status_code == 200, checked.text
    assert checked.json()['selection']['target']['key'] == 'second'
    assert checked.json()['selection']['limits']['token_budget'] == 2048
    assert checked.json()['selection']['limits']['output_tokens'] == 100
    assert [v['scope'] for v in checked.json()['trace']] == ['enterprise', 'agent', 'step', 'job']


@pytest.mark.parametrize('change', ['revoke', 'model', 'rotate', 'wrong_actor', 'expired', 'private_brain'])
async def test_cloud_current_actor_grant_recheck_no_provider_call(client, fenced, monkeypatch, change):
    c, calls, _ = fenced
    monkeypatch.setattr(settings(), 'business_planning_enabled', True)
    monkeypatch.setattr(settings(), 'studio_enabled', True)
    agent_payload = None
    if change == 'private_brain':
        from pao.models import Brain
        monkeypatch.setattr(settings(), 'brain_manager_enabled', True)
        async with Session.begin() as db:
            brain = Brain(workspace_id=c['workspace'], owner_id=c['user_id'], name='Private test')
            db.add(brain); await db.flush()
        agent_payload = {'instruction': 'Write a factual draft.', 'brain_id': brain.id}
    await configured(client, c, agent_payload=agent_payload)
    grantee = c['operator_id'] if change == 'wrong_actor' else c['user_id']
    response, mapped, _, _ = await consent(client, c, stage_change={'brand_id': None, 'grantee_id': grantee})
    assert response.status_code == 201, response.text
    current = (await client.get(base(c) + '/routing', headers=c['owner'])).json()['item']
    content = current['content']; content['cloud_allowed'] = True
    content['targets'].append({'key': 'cloud', 'provider': 'openai', 'model': 'local-fixture', 'reference_id': mapped['reference']['id']})
    result = await client.put(base(c) + '/routing', headers=c['owner'], json={
        'expected_revision': 1, 'request_key': str(uuid4()), 'content': content})
    assert result.status_code == 200, result.text
    path, _, _ = await draft(client, c)
    args = {'routing_revision': 2, 'job': {'target': 'cloud'}, 'grant_id': mapped['grant']['id']}
    good = await preflight(client, c, path, **args)
    if change in ('wrong_actor', 'private_brain'):
        assert good.status_code == 403, good.text
        assert calls['factory'] == calls['stream'] == calls['plan'] == 0
        if change == 'private_brain':
            assert (await preflight(client, c, path, routing_revision=2)).status_code == 200
        return
    assert good.status_code == 200, good.text
    assert good.json()['selection']['connection_authority']['actor_id'] == c['user_id']
    if change == 'revoke': await revoke(client, c, mapped)
    elif change == 'expired':
        from datetime import timedelta
        from pao.modules.connections import grants
        current = grants.now()
        monkeypatch.setattr(grants, 'now', lambda: current + timedelta(days=2))
    else:
        from pao.models import ModelProviderConnection
        async with Session.begin() as db:
            connection = await db.get(ModelProviderConnection, c['connections']['a']['model'])
            if change == 'model': connection.model = 'changed'
            if change == 'rotate': connection.api_key_ciphertext = 'rotated-fixture'
    denied = await preflight(client, c, path, **args)
    assert denied.status_code == 403, denied.text
    assert calls['factory'] == calls['stream'] == calls['plan'] == 0
    assert 'ciphertext' not in good.text and 'local-fence-fixture' not in good.text


async def test_private_brain_and_brand_not_inferred_from_owner(client, ready, monkeypatch):
    from pao.models import Brain, BrainMember
    monkeypatch.setattr(settings(), 'brain_manager_enabled', True)
    async with Session.begin() as db:
        private = Brain(workspace_id=ready['workspace'], owner_id=ready['user_id'], name='Private')
        db.add(private); await db.flush()
    await configured(client, ready, agent_payload={'instruction': 'Write a factual answer.', 'brain_id': private.id})
    path, _, _ = await draft(client, ready)
    assert (await preflight(client, ready, path)).status_code == 200
    # An agent cannot silently acquire the other enterprise's Brain by ID.
    async with Session.begin() as db:
        other = Workspace(name='Other'); db.add(other); await db.flush()
        db.add(Member(workspace_id=other.id, user_id=ready['user_id'], role='owner'))
    response = await client.put(f'/v1/workspaces/{other.id}/business-planning/routing', headers=ready['owner'], json={
        'expected_revision': 0, 'request_key': str(uuid4()), 'content': (await client.get(base(ready) + '/routing', headers=ready['owner'])).json()['item']['content']})
    assert response.status_code == 404
