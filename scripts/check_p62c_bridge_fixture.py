"""Real local Temporal/ARQ echo fixture, then isolated DB restore, serially."""
import os
import subprocess
import sys
from urllib.parse import urlsplit, urlunsplit
from pao.config import ROOT, settings

config = settings()
assert config.database_url.endswith('/pao_acos_local')
url = config.database_url.rsplit('/', 1)[0] + '/pao_test'
redis = urlsplit(config.redis_url)
env = {**os.environ, 'DATABASE_URL': url, 'PAO_TEST_DATABASE_URL': url,
       'REDIS_URL': urlunsplit((redis.scheme, redis.netloc, '/15', '', '')),
       'META_ENABLED': 'false'}
subprocess.run([sys.executable, '-m', 'pytest', '-q',
    'apps/api/tests/test_studio_arq_bridge.py::test_real_temporal_arq_two_steps_and_receipt_replay'],
    cwd=ROOT, env=env, check=True)
subprocess.run([sys.executable, str(ROOT / 'scripts/check_p62c_ledger_restore.py'), '--bridge'],
    cwd=ROOT, env=os.environ, check=True)
