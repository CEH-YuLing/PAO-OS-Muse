"""Contract and lifecycle gates for the incremental P0.2B app factory."""
import json
import os
import subprocess
import sys
from importlib import import_module

import pytest
from fastapi.routing import APIRoute

from pao.app import ROUTER_SPECS, create_app
from pao.config import ROOT
from pao.main import app


def test_factory_matches_saved_utf8_full_contract_and_legacy_entrypoint():
    saved = json.loads((ROOT / 'packages/contracts/openapi.json').read_text(encoding='utf-8'))
    assert app.openapi() == saved
    assert create_app().openapi() == saved
    assert 'RunEvent' in saved['components']['schemas']


def test_factory_has_stable_unique_route_registration_and_handler_identity():
    from pao import core_api, main
    assert len(ROUTER_SPECS) == 50  # Adds the disabled-by-default local CLI router.
    first, second = create_app(), create_app()
    def keys(value):
        return [(method.upper(), path) for path, operations in value.openapi()['paths'].items()
                for method in operations if method in ('get', 'post', 'put', 'patch', 'delete', 'head', 'options')]
    assert keys(first) == keys(second) == keys(app)
    assert len(keys(first)) == len(set(keys(first))) == 416  # Adds four scoped browser-login operations.
    assert {('GET','/v1/workspaces/{workspace_id}/cli-connections/login-capabilities'),
            ('POST','/v1/workspaces/{workspace_id}/cli-connections/{connection_id}/login'),
            ('GET','/v1/workspaces/{workspace_id}/cli-connections/{connection_id}/login'),
            ('POST','/v1/workspaces/{workspace_id}/cli-connections/{connection_id}/login/cancel')} <= set(keys(first))
    assert ('DELETE', '/v1/tasks/{task_id}') in set(keys(first))
    assert ('GET', '/v1/workspaces/{workspace_id}/context') in set(keys(first))
    assert ('GET', '/v1/workspaces/{workspace_id}/connection-inventory') in set(keys(first))
    assert ('POST', '/v1/workspaces/{workspace_id}/connection-inventory/mapping-preview') in set(keys(first))
    # OpenAPI alone can hide duplicate declarations. Check the source routers,
    # independently of FastAPI's version-specific included-router wrappers.
    declared = [(method, route.path) for module, attribute in ROUTER_SPECS
                for route in getattr(import_module(module, package='pao'), attribute).routes
                if isinstance(route, APIRoute) for method in sorted(route.methods)]
    assert len(declared) == len(set(declared)) == 416
    assert ('POST', '/v1/workspaces/{workspace_id}/cli-connections/{connection_id}/prepare') in set(declared)
    assert set(declared) == set(keys(first))
    for name in ('health', 'ready', 'login', 'me', 'create_session',
                 'list_sessions', 'delete_session', 'get_session',
                 'create_run', 'get_run', 'cancel', 'events'):
        assert getattr(main, name) is getattr(core_api, name)


def test_factory_keeps_state_overrides_and_openapi_cache_independent():
    first, second = create_app(), create_app()
    first.state.factory_marker = True
    assert not hasattr(second.state, 'factory_marker')
    first.dependency_overrides[lambda: None] = lambda: True
    assert second.dependency_overrides == {}
    first.openapi()['info']['title'] = 'isolated-test-only'
    assert second.openapi()['info']['title'] == 'PAO Local API'
    assert app.openapi()['info']['title'] == 'PAO Local API'


@pytest.mark.parametrize('raise_inside', [False, True])
async def test_lifespan_opens_one_pool_per_app_and_always_closes(monkeypatch, raise_inside):
    import arq
    created = []
    class Pool:
        def __init__(self):
            self.closes = 0
        async def aclose(self):
            self.closes += 1
    async def fake_create_pool(*args, **kwargs):
        pool = Pool()
        created.append(pool)
        return pool
    monkeypatch.setattr(arq, 'create_pool', fake_create_pool)
    first, second = create_app(), create_app()
    assert not created
    async def run():
        async with first.router.lifespan_context(first):
            async with second.router.lifespan_context(second):
                assert first.state.redis is not second.state.redis
                if raise_inside:
                    raise RuntimeError('lifespan-test-only')
    if raise_inside:
        with pytest.raises(RuntimeError, match='lifespan-test-only'):
            await run()
    else:
        await run()
    assert len(created) == 2 and all(pool.closes == 1 for pool in created)


def test_fresh_factory_import_and_composition_open_no_network_connections():
    code = """
import socket, sys
def forbidden(*args, **kwargs):
    raise AssertionError('Factory must not open network connections')
socket.socket.connect = forbidden
socket.create_connection = forbidden
from pao.app import create_app
for name in ('pao.main', 'pao.config', 'pao.db', 'pao.runtime'):
    assert name not in sys.modules, name
first, second = create_app(), create_app()
assert 'pao.main' not in sys.modules
assert not hasattr(first.state, 'redis')
assert first is not second
print('PASS factory import/composition without network or pool startup')
"""
    result = subprocess.run(
        [sys.executable, '-c', code],
        env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUTF8': '1'},
        check=True, capture_output=True, text=True, timeout=30,
    )
    assert 'PASS factory' in result.stdout
