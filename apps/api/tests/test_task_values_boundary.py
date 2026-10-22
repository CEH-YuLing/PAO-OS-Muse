"""Pure Task service boundary; behavior covered by task characterization tests."""
import os
import subprocess
import sys
from pao.modules.tasks import values


def test_legacy_task_helpers_keep_identity():
    from pao import task_api
    for name in ('bounded_json', 'clean_criteria', 'attempt_fingerprint'):
        assert getattr(task_api, name) is getattr(values, name)


def test_task_values_import_has_no_framework_database_or_network():
    code = """
import sys, socket
def forbidden(*args, **kwargs):
    raise AssertionError('Pure helper import must not connect')
socket.socket.connect = forbidden
socket.create_connection = forbidden
from pao.modules.tasks.values import bounded_json, clean_criteria, attempt_fingerprint
assert clean_criteria([' x ']) == ['x']
assert len(attempt_fingerprint({}, None)) == 64
assert bounded_json({}) == {}
for name in ('pao.task_api','pao.main','pao.runtime','pao.db','pao.config',
             'pao.models','fastapi','sqlalchemy'):
    assert name not in sys.modules, name
print('PASS pure task helper import')
"""
    result = subprocess.run([sys.executable, '-c', code],
        env={**os.environ, 'PYTHONUTF8': '1', 'PYTHONDONTWRITEBYTECODE': '1'},
        capture_output=True, text=True, check=True, timeout=20)
    assert 'PASS pure task helper import' in result.stdout
