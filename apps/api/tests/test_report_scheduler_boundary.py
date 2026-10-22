"""Report scheduler extraction boundaries; behavior is covered by test_reporting."""
import ast
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock

from pao.modules.business import report_scheduler as service


def test_legacy_and_worker_share_report_scheduler():
    from pao import report_api, runtime
    assert report_api.schedule_reports is service.schedule_reports
    assert runtime.schedule_reports is service.schedule_reports
    tree = ast.parse(Path(runtime.__file__).read_text(encoding='utf-8'))
    assert not any(isinstance(n, ast.ImportFrom) and n.module in
                   ('report_api', 'warehouse_api') for n in ast.walk(tree))


async def test_no_due_reports_has_no_delivery_side_effects(monkeypatch):
    class EmptySession:
        scalars = AsyncMock(return_value=[])
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return False
    monkeypatch.setattr(service, 'Session', EmptySession)
    build = AsyncMock()
    deliver = AsyncMock()
    monkeypatch.setattr(service, 'build_report', build)
    monkeypatch.setattr(service, 'queue_report', deliver)
    assert await service.schedule_reports({}) is None
    build.assert_not_awaited()
    deliver.assert_not_awaited()


def test_fresh_import_avoids_api_adapters_and_telegram_router():
    code = """
import socket, sys
def forbidden(*args, **kwargs):
    raise AssertionError('Import must not open network connections')
socket.socket.connect = forbidden
socket.create_connection = forbidden
from pao.modules.business import report_scheduler as service
from pao.modules.channels import telegram_helpers
assert service.queue is telegram_helpers.queue
assert service.telegram_permitted is telegram_helpers.permitted
assert callable(service.schedule_reports)
for name in ('pao.main', 'pao.core_api', 'pao.app', 'pao.report_api',
             'pao.warehouse_api', 'pao.integrations.meta.api', 'pao.telegram'):
    assert name not in sys.modules, name
assert 'pao.modules.channels.telegram_helpers' in sys.modules
print('PASS report service import')
"""
    result = subprocess.run(
        [sys.executable, '-c', code],
        env={**os.environ, 'PYTHONUTF8': '1', 'PYTHONDONTWRITEBYTECODE': '1'},
        check=True, capture_output=True, text=True, timeout=20,
    )
    assert 'PASS report service import' in result.stdout
