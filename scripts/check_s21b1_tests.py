"""Staged grant corpus + S21A/native regressions; pao_test/Redis15 only."""
import os
import subprocess
import sys
from urllib.parse import urlsplit, urlunsplit

from pao.config import ROOT, settings

c = settings()
url = c.database_url.rsplit('/', 1)[0] + '/pao_test'
r = urlsplit(c.redis_url)
env = {**os.environ, 'DATABASE_URL': url, 'PAO_TEST_DATABASE_URL': url,
       'REDIS_URL': urlunsplit((r.scheme, r.netloc, '/15', '', ''))}


def call(*args):
    subprocess.run(list(args), cwd=ROOT, env=env, check=True)


if __name__ == '__main__':
    call(sys.executable, '-m', 'alembic', 'upgrade', 'head')
    call(sys.executable, '-m', 'alembic', 'check')
    call(sys.executable, '-m', 'pytest', '-q', '--tb=short', '--show-capture=no',
         'apps/api/tests/test_connection_grants.py', 'apps/api/tests/test_connection_inventory.py',
         'apps/api/tests/test_app_factory.py', 'apps/api/tests/test_tenant_context.py',
         'apps/api/tests/test_model_router.py', 'apps/api/tests/test_meta_app_settings.py',
         'apps/api/tests/test_meta.py', 'apps/api/tests/test_google_ads.py',
         'apps/api/tests/test_connectors.py', 'apps/api/tests/test_engine_contract.py')
    call('node', '--test', 'apps/web/lib/tenant-transport.test.mjs', 'apps/web/lib/tenant-context.test.mjs',
         'apps/web/lib/runtime-state.test.mjs', 'apps/web/lib/sse.test.mjs')
    call('node', 'node_modules/typescript/bin/tsc', '--noEmit', '-p', 'apps/web/tsconfig.json')
