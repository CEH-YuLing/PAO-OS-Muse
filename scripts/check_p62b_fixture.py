"""Run ONLY after full regression: recreate fixture in pao_test then restore it."""
import os,subprocess,sys
from urllib.parse import urlsplit,urlunsplit
from pao.config import ROOT,settings
c=settings();assert c.database_url.endswith('/pao_acos_local')
url=c.database_url.rsplit('/',1)[0]+'/pao_test';redis=urlsplit(c.redis_url)
env={**os.environ,'DATABASE_URL':url,'PAO_TEST_DATABASE_URL':url,
    'REDIS_URL':urlunsplit((redis.scheme,redis.netloc,'/15','','')),'META_ENABLED':'false'}
subprocess.run([sys.executable,'-m','pytest','-q','apps/api/tests/test_durable_temporal.py'],cwd=ROOT,env=env,check=True)
subprocess.run([sys.executable,str(ROOT/'scripts/check_p62b_restore.py')],cwd=ROOT,check=True)
