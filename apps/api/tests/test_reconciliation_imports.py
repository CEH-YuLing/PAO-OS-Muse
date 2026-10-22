"""Characterization of the legacy import boundary after P0.2A extraction."""
import json
import os
import subprocess
import sys

from pao import reconciliation as legacy
from pao.modules.business import reconciliation as service


PUBLIC_SYMBOLS = {
    'BaseModel', 'ConfigDict', 'Decimal', 'ExportTotals', 'Field', 'Literal',
    'MetricDifference', 'ReconciliationOut', 'ZoneInfo', 'ZoneInfoNotFoundError',
    'compare_report', 'date', 'datetime', 'field_validator', 'model_validator',
}


def test_legacy_exports_preserve_public_symbol_identity():
    assert {name for name in vars(legacy) if not name.startswith('_')} == PUBLIC_SYMBOLS
    assert set(legacy.__all__) == PUBLIC_SYMBOLS
    for name in PUBLIC_SYMBOLS:
        assert getattr(legacy, name) is getattr(service, name)


def test_http_router_keeps_the_same_model_and_service_objects():
    from pao import report_api
    assert report_api.ExportTotals is service.ExportTotals
    assert report_api.ReconciliationOut is service.ReconciliationOut
    assert report_api.compare_report is service.compare_report


def test_fresh_import_is_independent_of_config_db_runtime_and_network():
    code = """
import json, socket, sys
def forbidden(*args, **kwargs):
    raise AssertionError('Reconciliation import must not open network connections')
socket.socket.connect = forbidden
socket.create_connection = forbidden
from pao import reconciliation as legacy
from pao.modules.business import reconciliation as service
assert legacy.ExportTotals is service.ExportTotals
for name in ('pao.config', 'pao.db', 'pao.main', 'pao.runtime',
             'pao.skills', 'pao.model_router'):
    assert name not in sys.modules, name
print(json.dumps({'pure_import': True}))
"""
    result = subprocess.run(
        [sys.executable, '-c', code],
        env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
        check=True, capture_output=True, text=True, timeout=20,
    )
    assert json.loads(result.stdout) == {'pure_import': True}
