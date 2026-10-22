"""Run focused Meta settings tests in pao_test; .env writes mocked to temp files."""
import os,subprocess,sys
from urllib.parse import urlsplit,urlunsplit
from pao.config import settings,ROOT
c=settings();url=c.database_url.rsplit('/',1)[0]+'/pao_test';redis=urlsplit(c.redis_url)
env={**os.environ,'DATABASE_URL':url,'PAO_TEST_DATABASE_URL':url,
     'REDIS_URL':urlunsplit((redis.scheme,redis.netloc,'/15','',''))}
subprocess.run([sys.executable,'-m','alembic','upgrade','head'],env=env,cwd=ROOT,check=True)
subprocess.run([sys.executable,'-m','pytest','-q','apps/api/tests/test_meta_app_settings.py',
                'apps/api/tests/test_meta.py','apps/api/tests/test_app_factory.py'],env=env,cwd=ROOT,check=True)
