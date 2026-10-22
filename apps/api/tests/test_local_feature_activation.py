"""The local feature combination preserves auth, scope and truthful status."""
import pytest
from pao.config import settings
from local_feature_activation import ENABLE, non_feature_hash

PATHS = ('/v1/results/status', '/v1/results', '/v1/business-events/approvals',
         '/v1/schedules/workflows/status', '/v1/goal-executions/status', '/v1/goal-runners/status')


@pytest.fixture
def local_features(monkeypatch):
    for key in ENABLE:
        monkeypatch.setattr(settings(), key, True)


async def test_combined_status_keeps_execution_and_external_delivery_honest(client, identity, local_features):
    params = {'workspace_id': identity['workspace']}
    async def get(path):
        response = await client.get(path, params=params, headers=identity['owner'])
        assert response.status_code == 200, response.text
        return response.json()
    result = await get('/v1/results/status')
    assert result['enabled'] and result['destinations'] == ['in_app']
    assert result['external_delivery_enabled'] is False
    approvals = await get('/v1/business-events/status')
    assert approvals['enabled'] and approvals['producer_enabled'] and approvals['delivery_enabled']
    assert approvals['consumer'] == 'internal.audit.v1'
    schedule = await get('/v1/schedules/workflows/status')
    assert schedule['manager_enabled'] and not schedule['dispatch_enabled'] and not schedule['model_calls']
    goal = await get('/v1/goal-executions/status')
    assert goal['admission_enabled'] and not goal['execution_enabled'] and goal['dry_run_only']
    runner = await get('/v1/goal-runners/status')
    assert not runner['execution_enabled'] and not runner['model_calls']
    assert await get('/v1/results') == []
    assert await get('/v1/business-events/approvals') == []


@pytest.mark.parametrize('path', PATHS)
async def test_local_features_do_not_bypass_sign_in(client, identity, local_features, path):
    response = await client.get(path, params={'workspace_id': identity['workspace']})
    assert response.status_code == 401


@pytest.mark.parametrize('path', PATHS)
async def test_local_features_do_not_bypass_enterprise_scope(client, identity, local_features, path):
    response = await client.get(path, params={'workspace_id': identity['workspace']}, headers=identity['outsider'])
    assert response.status_code == 404


def test_config_comparison_only_excludes_reviewed_switches():
    before = b'JWT_SECRET=synthetic-private\nMEMORY_ENABLED=true\n'
    after = before + b'RESULT_INBOX_ENABLED=true\n'
    assert non_feature_hash(before) == non_feature_hash(after)
    assert non_feature_hash(after) != non_feature_hash(after.replace(b'synthetic-private', b'changed'))
    assert non_feature_hash(after) != non_feature_hash(after + b'META_WRITE_ENABLED=true\n')
    with pytest.raises(ValueError, match='duplicate_local_feature_flag'):
        non_feature_hash(after + b'RESULT_INBOX_ENABLED=false\n')
