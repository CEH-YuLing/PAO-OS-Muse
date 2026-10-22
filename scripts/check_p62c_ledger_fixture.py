"""Isolated two-step ledger fixture followed by restore; no concurrent test run."""
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
    'apps/api/tests/test_studio_step_jobs.py::test_reserve_claim_concurrent_finish_and_binding'],
    cwd=ROOT, env=env, check=True)
subprocess.run([sys.executable, str(ROOT / 'scripts/check_p62c_ledger_restore.py')],
    cwd=ROOT, env=os.environ, check=True)
