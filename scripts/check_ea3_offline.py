"""EA3 evidence generator: pure parser tests, credential-free file inventory.

Never launches a provider CLI, reads its auth store, touches DB or imports a
candidate into the serving transport. New receipts are exclusive and retained.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
assert ROOT == Path('F:/PAO-ACOS')
PROTECTED = ('.env', '.runtime/cli-device.json', '.runtime/acos-python-runtime.json',
             'pyproject.toml', 'apps/api/pao/modules/cli_connections/service.py',
             'apps/web/components/workspace/ClientModelSettings.tsx')


def digest(path):
    sha=hashlib.sha256()
    with path.open('rb') as file:
        for block in iter(lambda:file.read(1048576),b''):
            sha.update(block)
    return sha.hexdigest()


def protected():
    paths=[ROOT/name for name in PROTECTED]
    paths+=sorted((ROOT/'packages/cli-runtime/pao_cli_runtime').glob('*.py'))
    return {p.relative_to(ROOT).as_posix():digest(p) for p in paths}


def inventory():
    # Exact paths observed from Get-Command and the public npm wrapper, not an
    # arbitrary UI path or recursive scan. No credential files are inspected.
    found=[]
    for provider,name in (
        ('claude_code_cli','C:/Users/o0o_v/AppData/Roaming/npm/node_modules/@anthropic-ai/claude-code/bin/claude.exe'),
        ('antigravity_cli','C:/Users/o0o_v/AppData/Local/agy/bin/agy.exe')):
        path=Path(name)
        row={'provider':provider,'path':str(path),'binary_executed':False,
             'authentication':'not_checked','inference_verified':False,'version':'not_probed'}
        if path.is_file():
            assert not any(p.is_symlink() or getattr(p,'is_junction',lambda:False)() for p in (path,*path.parents))
            row.update(installed_file_found=True,bytes=path.stat().st_size,sha256=digest(path))
        else:
            row['installed_file_found']=False
        found.append(row)
    return found


def main():
    folder=ROOT/'.runtime'/('ea3-offline-'+uuid4().hex)
    folder.mkdir()
    before=protected()
    source={p.relative_to(ROOT).as_posix():digest(p) for p in sorted((ROOT/'packages/client-adapters').rglob('*')) if p.is_file()}
    result={'pass':False,'scope':'EA3_offline_protocol_subset','provider_calls':0,
            'provider_cli_executions':0,'database_access':False,'serving_adapter_registered':False,
            'EA22':'deferred_by_user','EA3_live_accepted':False,'production_accepted':False}
    bootstrap="""import json,sys,unittest
def guard(event,args):
 if event in ('socket.__new__','socket.connect','socket.getaddrinfo','subprocess.Popen','os.system','os.exec','os.posix_spawn'):
  raise RuntimeError('EA3 offline test network/process denied')
sys.addaudithook(guard)
suite=unittest.defaultTestLoader.discover('packages/client-adapters/tests')
result=unittest.TextTestRunner(verbosity=2).run(suite)
print('EA3_COUNTS='+json.dumps({'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped)}))
sys.exit(0 if result.wasSuccessful() and not result.skipped else 1)
"""
    try:
        env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONUTF8':'1'}
        run=subprocess.run([sys.executable,'-I','-B','-c',bootstrap],cwd=ROOT,env=env,
                           stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30)
        with (folder/'unit.log').open('xb') as log:log.write(run.stdout)
        lines=run.stdout.decode('utf-8').splitlines()
        counts=[json.loads(line.split('=',1)[1]) for line in lines if line.startswith('EA3_COUNTS=')]
        assert run.returncode==0 and len(counts)==1 and counts[0]['tests']>=61
        assert not any(counts[0][k] for k in ('failures','errors','skipped'))
        result.update(counts=counts[0],inventory=inventory())
        assert protected()==before
        assert source=={p.relative_to(ROOT).as_posix():digest(p) for p in sorted((ROOT/'packages/client-adapters').rglob('*')) if p.is_file()}
        result.update({'pass':True,'source_unchanged_during_tests':True,'protected_files_unchanged':True})
    finally:
        result.update(protected_before=before,protected_after=protected(),source=source)
        with (folder/'receipt.json').open('x',encoding='utf-8') as out:json.dump(result,out,indent=2)
        print(json.dumps({'folder':str(folder),**{k:v for k,v in result.items() if k not in ('source','protected_before','protected_after','inventory')}}))


if __name__=='__main__':
    main()
