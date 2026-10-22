"""Focused integration acceptance on this fork's disposable DB/Redis only."""
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit,urlunsplit
from uuid import uuid4

from muse_sandbox import guard,ROOT,RUNTIME,PYTHON
from local_cycle_test_lock import isolated_test_slot

if __name__=='__main__':
    cfg=guard()
    pg=urlsplit(cfg.database_url);redis=urlsplit(cfg.redis_url)
    assert pg.port==25432 and pg.path=='/pao_muse_local' and redis.port==26379
    env={**os.environ,'DATABASE_URL':urlunsplit(pg._replace(path='/pao_test')),
         'PAO_TEST_DATABASE_URL':urlunsplit(pg._replace(path='/pao_test')),
         'REDIS_URL':urlunsplit(redis._replace(path='/15'))}
    folder=RUNTIME/('sandbox-test-'+uuid4().hex);folder.mkdir()
    with isolated_test_slot():
        with (folder/'migration.log').open('wb') as log:
            subprocess.run([str(PYTHON),'-B','-m','alembic','upgrade','0077'],cwd=ROOT,env=env,
                stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
        with (folder/'pytest.log').open('wb') as log:
            result=subprocess.run([str(PYTHON),'-B','-m','pytest','-q','--maxfail=1',
                '-p','local_cycle_network_guard','apps/api/tests/test_provider_managed_tokens.py',
                'apps/api/tests/test_muse_business.py','--junitxml='+str(folder/'junit.xml')],
                cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=300)
    report={'pass':result.returncode==0,'test_db_port':25432,'test_db':'pao_test','redis_port':26379,
        'redis_db':15,'provider_calls':0,'test_folder':str(folder)}
    (folder/'receipt.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report));raise SystemExit(result.returncode)
