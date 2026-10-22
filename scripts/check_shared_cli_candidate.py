"""Disposable PostgreSQL + staged backend/CLI. Never migrate/restart primary.

There is no auth mount, provider call, copied .env or production enable switch.
All SQL guard changes live only in the stage and a labeled ephemeral container.
"""
import asyncio
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
from uuid import uuid4
from xml.etree import ElementTree

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'scripts'),str(ROOT/'apps/api')]
from stage_installation_cli_candidate import stage
from check_pao_mcp_local import digests
from check_p84_foundation import primary_schema,health
from check_installation_ai_migration import signatures
from check_m2_restore import inspect as archive_inventory
from pao.modules.operations.checkpoint import digest
from local_cycle_test_lock import isolated_test_slot
from pao.config import settings
from sqlalchemy.engine import make_url


def docker(*args,timeout=60):
    result=subprocess.run(['docker',*args],capture_output=True,timeout=timeout)
    if result.returncode:
        raise RuntimeError('candidate_docker_command_failed:' + args[0])
    return result.stdout.decode('utf-8').strip()


def main():
    assert ROOT==Path('F:/PAO-ACOS')
    primary=make_url(settings().database_url)
    assert (primary.host,primary.port,primary.database)==('127.0.0.1',15432,'pao_acos_local')
    before=digests();schema=asyncio.run(primary_schema());rows=asyncio.run(signatures(primary))
    folder=ROOT/'.runtime'/('shared-cli-candidate-'+uuid4().hex);folder.mkdir()
    staged=folder/'stage';hashes=stage(staged)
    label=uuid4().hex;container=None
    state={'pass':False,'installed':False,'provider_calls':0,'identity_admission':'synthetic_only',
        'auth_mounted':False,'primary_migrated':False,'candidate_hashes':hashes}
    try:
        image=json.loads(docker('inspect','pao-acos-local-postgres-1'))[0]['Image']
        container=docker('run','-d','--pull=never','--label','pao.shared-cli.test='+label,
            '--name','pao-shared-cli-'+label,'-p','127.0.0.1::5432',
            '-e','POSTGRES_USER=pao','-e','POSTGRES_PASSWORD=synthetic-candidate-only',
            '-e','POSTGRES_DB=pao_test','--tmpfs','/var/lib/postgresql/data:rw,nosuid,size=1g',image)
        assert len(container)==64 and all(v in '0123456789abcdef' for v in container)
        port=int(json.loads(docker('inspect',container))[0]['NetworkSettings']['Ports']['5432/tcp'][0]['HostPort'])
        deadline=time.monotonic()+40
        while True:
            check=subprocess.run(['docker','exec',container,'pg_isready','-U','pao','-d','pao_test'],capture_output=True,timeout=5)
            if check.returncode==0:break
            if time.monotonic()>deadline:raise RuntimeError('candidate_postgres_not_ready')
            time.sleep(0.25)
        target=f'postgresql+asyncpg://pao:synthetic-candidate-only@127.0.0.1:{port}/pao_test'
        from cryptography.fernet import Fernet
        env={**os.environ,'DATABASE_URL':target,'PAO_TEST_DATABASE_URL':target,
            'REDIS_URL':make_url(settings().redis_url).set(database='15').render_as_string(hide_password=False),
            'PAO_ROOT':str(staged),'JWT_SECRET':'synthetic-'+secrets.token_hex(24),
            'INTEGRATION_ENCRYPTION_KEY':Fernet.generate_key().decode(),
            'PYTHONUTF8':'1','PYTHONDONTWRITEBYTECODE':'1',
            'PYTHONPATH':os.pathsep.join(str(p) for p in (
                ROOT/'.runtime/p84-native-test-deps',staged/'apps/api',staged/'packages/cli-runtime',ROOT/'scripts'))}
        for index,args in enumerate((('upgrade','0076'),('downgrade','0075'),('upgrade','0076'))):
            with (folder/f'migration-{index}.log').open('wb') as log:
                result=subprocess.run([sys.executable,'-B','-m','alembic',*args],cwd=staged,env=env,
                    stdout=log,stderr=subprocess.STDOUT,timeout=180)
            assert result.returncode==0,'Candidate migration failed; retained migration log'
        state['empty_roundtrip']=True
        # Restore only a verified existing checkpoint into a second DB in the
        # freshly-created container. No primary restore, credential mount or
        # execution of historical business runs/archives is performed.
        checkpoint=ROOT/'.runtime/checkpoints/p0-20261020T132233-b4755cb9/manifest.json'
        manifest=json.loads(checkpoint.read_text())
        backup=Path(manifest['database']['backup']).resolve()
        assert backup.parent==ROOT/'.runtime' and backup.name.startswith('m2-') and backup.suffix=='.dump' and not backup.is_symlink()
        assert digest(backup)==manifest['database']['sha256']
        clone='pao_candidate_restore'
        docker('exec',container,'createdb','-U','pao',clone)
        with backup.open('rb') as source,(folder/'restore.log').open('wb') as log:
            restored=subprocess.run(['docker','exec','-i',container,'pg_restore','-U','pao','-d',clone,'--no-owner','--exit-on-error'],
                stdin=source,stdout=log,stderr=subprocess.STDOUT,timeout=120)
        assert restored.returncode==0,'Owned clone restore failed; retained restore.log'
        clone_url=make_url(target).set(database=clone)
        old=asyncio.run(signatures(clone_url));archives=asyncio.run(archive_inventory(clone_url))
        clone_env={**env,'DATABASE_URL':clone_url.render_as_string(hide_password=False)}
        for index,args in enumerate((('upgrade','0075'),('upgrade','0076'),('downgrade','0075'),('upgrade','0076'))):
            with (folder/f'populated-{index}.log').open('wb') as log:
                migrated=subprocess.run([sys.executable,'-B','-m','alembic',*args],cwd=staged,env=clone_env,
                    stdout=log,stderr=subprocess.STDOUT,timeout=120)
            assert migrated.returncode==0,'Populated candidate migration failed; retained migration log'
            current=asyncio.run(signatures(clone_url))
            assert all(current.get(k)==v for k,v in old.items() if k!='alembic_version')
            assert asyncio.run(archive_inventory(clone_url))['artifact_hashes']==archives['artifact_hashes']
        state['populated_clone_roundtrip']={'pass':True,'old_rows_unchanged':True,'archives':len(archives['artifact_hashes']),
            'checkpoint':str(checkpoint),'primary_restore':False}
        files=['test_shared_cli_candidate.py','test_cli_connections.py','test_personal_cli.py',
            'test_cli_models.py','test_installation_ai.py','test_engine_contract.py','test_business_routing.py']
        with (folder/'pytest.log').open('wb') as log:
            result=subprocess.run([sys.executable,'-B','-m','pytest','-q','--maxfail=1','-p','local_cycle_network_guard',
                *['apps/api/tests/'+v for v in files],'--junitxml='+str(folder/'junit.xml')],
                cwd=staged,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=600)
        counts={k:0 for k in ('tests','failures','errors','skipped')}
        assert (folder/'junit.xml').is_file(),'Test bootstrap failed; retained pytest.log'
        for suite in ElementTree.parse(folder/'junit.xml').getroot().iter('testsuite'):
            for key in counts:counts[key]+=int(suite.attrib.get(key,0))
        state['counts']=counts
        assert result.returncode==0 and counts['tests']>=100 and not any(counts[k] for k in ('failures','errors','skipped')),'Candidate tests failed; see retained pytest.log'
        state['pass']=True
    finally:
        state['cleanup_verified']=container is None
        if container:
            metadata=json.loads(docker('inspect',container))[0]
            assert metadata['Id']==container and metadata['Config']['Labels']['pao.shared-cli.test']==label
            docker('rm','--force',container)
            state['cleanup_verified']=True
        state.update(serving_source_env_runtime_unchanged=before==digests(),
            primary_schema_unchanged=schema==asyncio.run(primary_schema()),
            primary_rows_unchanged=rows==asyncio.run(signatures(primary)),health=health())
        state['pass']=state['pass'] and all(state[k] for k in (
            'cleanup_verified','serving_source_env_runtime_unchanged','primary_schema_unchanged','primary_rows_unchanged'))
        state['pass']=state['pass'] and all(v==200 for v in state['health'].values())
        (folder/'receipt.json').write_text(json.dumps(state,indent=2),encoding='utf-8')
        print(json.dumps({'folder':str(folder),**{k:v for k,v in state.items() if k!='candidate_hashes'}}))
    raise SystemExit(0 if state['pass'] else 1)


if __name__=='__main__':
    with isolated_test_slot():main()
