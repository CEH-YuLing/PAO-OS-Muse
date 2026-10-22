"""P6.2C result checkpoint regression; isolated pao_test and Redis15."""
import os
import subprocess
import sys
from urllib.parse import urlsplit, urlunsplit
from pao.config import ROOT, settings

config = settings()
url = config.database_url.rsplit('/', 1)[0] + '/pao_test'
redis = urlsplit(config.redis_url)
env = {**os.environ, 'DATABASE_URL': url, 'PAO_TEST_DATABASE_URL': url,
       'REDIS_URL': urlunsplit((redis.scheme, redis.netloc, '/15', '', '')),
       'META_ENABLED': 'false'}
subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], cwd=ROOT, env=env, check=True)
subprocess.run([sys.executable, '-m', 'alembic', 'check'], cwd=ROOT, env=env, check=True)
subprocess.run([sys.executable, '-m', 'pytest', '-q',
    'apps/api/tests/test_studio_arq_bridge.py', 'apps/api/tests/test_studio_step_jobs.py',
    'apps/api/tests/test_studio_results.py', 'apps/api/tests/test_studio.py',
    'apps/api/tests/test_workflow_planning.py', 'apps/api/tests/test_durable_admission.py',
    'apps/api/tests/test_durable_workflow.py', 'apps/api/tests/test_durable_temporal.py',
    'apps/api/tests/test_tasks.py', 'apps/api/tests/test_app_factory.py'], cwd=ROOT, env=env, check=True)
