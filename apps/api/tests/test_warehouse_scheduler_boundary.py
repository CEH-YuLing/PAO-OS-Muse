"""P0.3A.1 boundary characterization; scheduling behavior is in test_warehouse."""
import ast
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from pao.modules.business import warehouse_scheduler as service


def test_legacy_and_worker_import_the_same_scheduler_function():
    from pao import runtime, warehouse_api
    assert runtime.schedule_warehouse is service.schedule_warehouse
    assert warehouse_api.schedule_warehouse is service.schedule_warehouse
    tree = ast.parse(Path(runtime.__file__).read_text(encoding='utf-8'))
    assert not any(isinstance(n, ast.ImportFrom) and n.module == 'warehouse_api'
                   for n in ast.walk(tree))


async def test_disabled_scheduler_does_not_open_a_database_session(monkeypatch):
    monkeypatch.setattr(service, 'settings', lambda: SimpleNamespace(meta_enabled=False))
    def forbidden(*args, **kwargs):
        raise AssertionError('Disabled scheduler must not touch database')
    monkeypatch.setattr(service, 'Session', forbidden)
    assert await service.schedule_warehouse({}) is None


def test_fresh_scheduler_import_has_no_http_adapters_or_network():
    code = """
import socket, sys
def forbidden(*args, **kwargs):
    raise AssertionError('Scheduler import must not open network connections')
socket.socket.connect = forbidden
socket.create_connection = forbidden
from pao.modules.business.warehouse_scheduler import schedule_warehouse
assert callable(schedule_warehouse)
for name in ('pao.main', 'pao.core_api', 'pao.app', 'pao.warehouse_api',
             'pao.report_api', 'pao.integrations.meta.api'):
    assert name not in sys.modules, name
print('PASS independent scheduler import')
"""
    result = subprocess.run(
        [sys.executable, '-c', code],
        env={**os.environ, 'PYTHONUTF8': '1', 'PYTHONDONTWRITEBYTECODE': '1'},
        check=True, capture_output=True, text=True, timeout=20,
    )
    assert 'PASS independent scheduler import' in result.stdout
