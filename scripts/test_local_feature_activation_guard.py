"""Operator-only manifest regression; no PAO services, DB or credentials."""
import pytest
from local_feature_activation import source_manifest, non_feature_hash


def test_declared_next_outputs_are_not_application_source():
    base = {'apps/web/next.config.mjs': 'config', 'apps/web/components/Chat.tsx': 'source',
        'apps/api/pao/auth.py': 'auth', 'apps/api/tests/test_access.py': 'tests',
        '.runtime/acos-python-runtime.json': 'pin', 'requirements.lock': 'deps'}
    generated = {**base, '.env': 'private-hash', 'apps/web/.pao-next/trace': 'trace',
        'apps/web/.pao-next/cache/webpack/client-development/0.pack.gz': 'cache',
        'apps/web/.pao-build-check/server/app/page.js': 'generated'}
    assert source_manifest(generated) == base


@pytest.mark.parametrize('path', ('apps/web/next.config.mjs', 'apps/web/components/Chat.tsx',
    'apps/api/pao/auth.py', 'apps/api/tests/test_access.py', '.runtime/acos-python-runtime.json',
    'requirements.lock', 'apps/web/.pao-next.tsx'))
def test_source_and_security_pin_changes_remain_visible(path):
    assert source_manifest({path: 'before'}) != source_manifest({path: 'after'})


def test_only_reviewed_environment_switches_are_ignored():
    baseline = b'JWT_SECRET=synthetic\nMETA_WRITE_ENABLED=false\n'
    assert non_feature_hash(baseline) == non_feature_hash(baseline + b'RESULT_INBOX_ENABLED=true\n')
    assert non_feature_hash(baseline) != non_feature_hash(baseline.replace(b'false', b'true'))
    assert non_feature_hash(baseline) != non_feature_hash(baseline.replace(b'synthetic', b'changed'))
