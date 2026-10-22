"""Explicit S1.2 gates, isolated database/Redis; no runtime configuration writes."""
import os
import subprocess
import sys
from urllib.parse import urlsplit, urlunsplit
from pao.config import ROOT, settings

config = settings()
url = config.database_url.rsplit('/', 1)[0] + '/pao_test'
redis = urlsplit(config.redis_url)
env = {**os.environ, 'DATABASE_URL': url, 'PAO_TEST_DATABASE_URL': url,
       'REDIS_URL': urlunsplit((redis.scheme, redis.netloc, '/15', '', ''))}
def call(*args):
    subprocess.run(list(args), cwd=ROOT, env=env, check=True)
if '--browser-only' not in sys.argv and '--s12-only' not in sys.argv:
    call(sys.executable, '-m', 'alembic', 'upgrade', 'head')
    call(sys.executable, '-m', 'alembic', 'check')
    call('node', '--test', 'apps/web/lib/tenant-transport.test.mjs',
         'apps/web/lib/tenant-context.test.mjs', 'apps/web/lib/runtime-state.test.mjs', 'apps/web/lib/sse.test.mjs')
    call('node', 'node_modules/typescript/bin/tsc', '--noEmit', '-p', 'apps/web/tsconfig.json')
    call(sys.executable, '-m', 'pytest', '-q', '--tb=short', '--show-capture=no', 'apps/api/tests/test_tenant_context.py',
         'apps/api/tests/test_chat_management.py', 'apps/api/tests/test_voice_turns.py')
call(sys.executable, '-m', 'pytest', '-q', '--tb=short', '--show-capture=no', 'apps/api/tests/s12_browser_acceptance.py')
if '--s12-only' not in sys.argv:
    call(sys.executable, '-m', 'pytest', '-q', '--tb=short', '--show-capture=no', 'apps/api/tests/s11_browser_acceptance.py')
    call(sys.executable, '-m', 'pytest', '-q', '--tb=short', '--show-capture=no', 'apps/api/tests/p7_browser_acceptance.py')
