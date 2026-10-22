"""Focused P6.1 regression; pao_test/Redis15 only, all provider flags off."""
import os,subprocess,sys
from urllib.parse import urlsplit,urlunsplit
from pao.config import ROOT,settings
c=settings();url=c.database_url.rsplit('/',1)[0]+'/pao_test';redis=urlsplit(c.redis_url)
env={**os.environ,'DATABASE_URL':url,'PAO_TEST_DATABASE_URL':url,
     'REDIS_URL':urlunsplit((redis.scheme,redis.netloc,'/15','','')),'META_ENABLED':'false'}
subprocess.run([sys.executable,'-m','alembic','upgrade','head'],cwd=ROOT,env=env,check=True)
subprocess.run([sys.executable,'-m','pytest','-q','apps/api/tests/test_workflow_planning.py',
               'apps/api/tests/test_studio.py','apps/api/tests/test_tasks.py','apps/api/tests/test_app_factory.py'],cwd=ROOT,env=env,check=True)
