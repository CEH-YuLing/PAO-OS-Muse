"""Migrate and test ONLY a pre-created pao_test DB and isolated Redis DB 15."""
import os
import subprocess
import sys
from urllib.parse import urlsplit, urlunsplit

from pao.config import ROOT,settings

config = settings()
test_url = config.database_url.rsplit('/', 1)[0] + '/pao_test'
redis = urlsplit(config.redis_url)
env = {**os.environ, 'DATABASE_URL': test_url, 'PAO_TEST_DATABASE_URL': test_url,
       'PAO_ARQ_WALL_CLOCK_TESTS': os.environ.get('PAO_ARQ_WALL_CLOCK_TESTS', '1'),
       'REDIS_URL': urlunsplit((redis.scheme, redis.netloc, '/15', '', ''))}
if '--roundtrip' in sys.argv:
    subprocess.run([sys.executable, '-m', 'alembic', 'downgrade', 'base'], env=env, check=True)
subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], env=env, check=True)
subprocess.run([sys.executable, '-m', 'alembic', 'check'], env=env, check=True)
targets=['apps/api/tests']
(ROOT/'.runtime').mkdir(exist_ok=True)
subprocess.run([sys.executable, '-m', 'pytest', '-q', *targets,
                '--junitxml='+str(ROOT/'.runtime/backend-full.xml')], env=env, check=True)
if '--browser' in sys.argv:
    # Browser is an explicit acceptance gate, not a hidden prerequisite for
    # backend-only CI. No skip and no fabricated API response when requested.
    # A second invocation is intentional: directory + nonstandard test filename
    # together can be deduplicated away by pytest collection.
    subprocess.run([sys.executable,'-m','pytest','-q',
                    'apps/api/tests/p62_browser_acceptance.py',
                    'apps/api/tests/p63_browser_acceptance.py',
                    'apps/api/tests/p64_browser_acceptance.py',
                    'apps/api/tests/p64_goal_browser_acceptance.py',
                    'apps/api/tests/p65_browser_acceptance.py',
                    'apps/api/tests/p66_browser_acceptance.py',
                    'apps/api/tests/p67_browser_acceptance.py',
                    'apps/api/tests/p7_browser_acceptance.py'],env=env,check=True)
