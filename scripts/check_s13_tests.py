"""S1.3 reproducible local gates; pao_test + Redis15 only, never .env writes."""
import os
import subprocess
import sys
from urllib.parse import urlsplit, urlunsplit

from pao.config import ROOT, settings

modes = set(sys.argv[1:]) & {'--full', '--corpus-only', '--browser-only'}
if len(modes) > 1:
    raise SystemExit('Choose only one of --full / --corpus-only / --browser-only')

config = settings()
url = config.database_url.rsplit('/', 1)[0] + '/pao_test'
redis = urlsplit(config.redis_url)
env = {**os.environ, 'DATABASE_URL': url, 'PAO_TEST_DATABASE_URL': url,
       'PAO_ARQ_WALL_CLOCK_TESTS': '1',
       'REDIS_URL': urlunsplit((redis.scheme, redis.netloc, '/15', '', ''))}


def call(*args):
    subprocess.run(list(args), cwd=ROOT, env=env, check=True)


if '--browser-only' in sys.argv:
    call(sys.executable, 'scripts/check_s12_tests.py', '--browser-only')
else:
    call(sys.executable, '-m', 'alembic', 'upgrade', 'head')
    call(sys.executable, '-m', 'alembic', 'check')
    targets = ['apps/api/tests'] if '--full' in sys.argv else [
        'apps/api/tests/test_s13_tenant_isolation.py', 'apps/api/tests/test_s13_stream_cleanup.py',
        'apps/api/tests/test_tenant_context.py', 'apps/api/tests/test_brain_scopes.py',
        'apps/api/tests/test_brain_manager.py', 'apps/api/tests/test_brain_files.py',
        'apps/api/tests/test_brain_notes.py', 'apps/api/tests/test_brain_portable.py',
        'apps/api/tests/test_knowledge_sources.py', 'apps/api/tests/test_knowledge_workspace.py',
        'apps/api/tests/test_chat_management.py', 'apps/api/tests/test_memory.py',
        'apps/api/tests/test_channels.py', 'apps/api/tests/test_result_inbox.py',
        'apps/api/tests/test_result_outbox.py', 'apps/api/tests/test_business_delivery.py',
        'apps/api/tests/test_business_events.py', 'apps/api/tests/test_voice_turns.py']
    if '--corpus-only' in sys.argv:
        targets = ['apps/api/tests/test_s13_tenant_isolation.py',
                   'apps/api/tests/test_s13_stream_cleanup.py', 'apps/api/tests/test_app_factory.py']
    call(sys.executable, '-m', 'pytest', '-q', '--tb=short', '--show-capture=no', *targets)
    call('node', '--test', 'apps/web/lib/tenant-transport.test.mjs', 'apps/web/lib/tenant-context.test.mjs',
         'apps/web/lib/runtime-state.test.mjs', 'apps/web/lib/sse.test.mjs')
    call('node', 'node_modules/typescript/bin/tsc', '--noEmit', '-p', 'apps/web/tsconfig.json')
