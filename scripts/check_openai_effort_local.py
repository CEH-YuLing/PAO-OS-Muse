"""Staged OpenAI effort acceptance; pao_test/Redis15 serial, zero provider calls."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
from urllib.parse import urlsplit,urlunsplit
from uuid import uuid4
from xml.etree import ElementTree

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'apps/api')]
from stage_openai_effort_candidate import stage
from check_pao_mcp_local import digests
from check_p84_foundation import primary_schema,health
from check_installation_ai_migration import signatures
from pao.config import settings
from sqlalchemy.engine import make_url
from local_cycle_test_lock import isolated_test_slot
from cryptography.fernet import Fernet


def main():
    assert ROOT==Path('F:/PAO-ACOS')
    cfg=settings();pg=urlsplit(cfg.database_url)
    assert (pg.hostname,pg.port,pg.path)==('127.0.0.1',15432,'/pao_acos_local')
    before=digests();schema=asyncio.run(primary_schema());rows=asyncio.run(signatures(make_url(cfg.database_url)))
    folder=ROOT/'.runtime'/('openai-effort-tests-'+uuid4().hex);folder.mkdir()
    staged=stage(folder/'source')
    focused=sys.argv[1:]==['--focused']
    assert sys.argv[1:] in ([],['--focused'])
    state={'pass':False,'installed':False,'focused_adapter_only':focused,'provider_calls':0,'primary_migrated':False,'schema':schema['revision'],
        'primary_rows_before':rows}
    env={**os.environ,'PAO_ROOT':str(staged),'DATABASE_URL':urlunsplit(pg._replace(path='/pao_test')),
        'PAO_TEST_DATABASE_URL':urlunsplit(pg._replace(path='/pao_test')),
        'REDIS_URL':urlunsplit(urlsplit(cfg.redis_url)._replace(path='/15')),
        'JWT_SECRET':'synthetic-effort-'+secrets.token_hex(24),'INTEGRATION_ENCRYPTION_KEY':Fernet.generate_key().decode(),
        'PYTHONDONTWRITEBYTECODE':'1','PYTHONUTF8':'1',
        'PYTHONPATH':os.pathsep.join(str(p) for p in (ROOT/'.runtime/p84-native-test-deps',staged/'apps/api',staged/'packages/cli-runtime',ROOT/'scripts'))}
    try:
        with (folder/'migration.log').open('wb') as log:
            result=subprocess.run([sys.executable,'-B','-m','alembic','upgrade','0075'],cwd=staged,env=env,
                stdout=log,stderr=subprocess.STDOUT,timeout=90)
        assert result.returncode==0,'Test database migration failed'
        files=['test_openai_effort.py','test_gateway.py','test_installation_ai.py','test_installation_ai_catalog.py',
            'test_model_router.py','test_engine_contract.py','test_business_routing.py','test_enterprise_ai.py',
            'test_studio.py','test_business_operations.py','test_model_connection_fence.py','test_personal_cli.py','test_cli_models.py']
        if focused:files=['test_openai_effort.py']
        with (folder/'pytest.log').open('wb') as log:
            result=subprocess.run([sys.executable,'-B','-m','pytest','-q','--maxfail=1','-p','local_cycle_network_guard',
                *['apps/api/tests/'+v for v in files],'--junitxml='+str(folder/'junit.xml')],cwd=staged,env=env,
                stdout=log,stderr=subprocess.STDOUT,timeout=600)
        assert (folder/'junit.xml').is_file(),'Test bootstrap failed; retained log'
        counts={k:0 for k in ('tests','failures','errors','skipped')}
        for suite in ElementTree.parse(folder/'junit.xml').getroot().iter('testsuite'):
            for key in counts:counts[key]+=int(suite.attrib.get(key,0))
        state['counts']=counts
        state['candidate_files']={str(p.relative_to(staged)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (staged/'apps/api/pao/gateway.py',staged/'apps/api/pao/model_router.py',
                staged/'apps/api/pao/modules/installation_ai/service.py',staged/'apps/api/pao/modules/installation_ai/openai_effort.py')}
        state['functional_tests_passed']=result.returncode==0 and counts['tests']>=(30 if focused else 300) and not any(counts[k] for k in ('failures','errors','skipped'))
        state['pass']=state['functional_tests_passed']
    finally:
        after=asyncio.run(signatures(make_url(cfg.database_url)))
        state.update(serving_source_env_pins_unchanged=before==digests(),primary_schema_unchanged=schema==asyncio.run(primary_schema()),
            primary_rows_unchanged=rows==after,primary_rows_after=after,
            changed_primary_tables=[k for k in sorted(set(rows)|set(after)) if rows.get(k)!=after.get(k)],health=health())
        state['pass']=state['pass'] and all(state[k] for k in ('serving_source_env_pins_unchanged','primary_schema_unchanged','primary_rows_unchanged')) and all(v==200 for v in state['health'].values())
        (folder/'receipt.json').write_text(json.dumps(state,indent=2),encoding='utf-8')
        print(json.dumps({'folder':str(folder),**{k:v for k,v in state.items() if k not in ('candidate_files','primary_rows_before','primary_rows_after')}}))
    raise SystemExit(0 if state['pass'] else 1)


if __name__=='__main__':
    with isolated_test_slot():main()
