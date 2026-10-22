"""Verify the exact frozen candidate and local receipts before a dependency cutover."""
import hashlib,json,sys
from pathlib import Path
from zipfile import ZipFile
from pao.config import ROOT
from check_phase3_readiness import runtime_source_names,is_runtime_source

CHANGED=('pyproject.toml','requirements.lock','apps/api/tests/temporal_fixture.py',
         'apps/api/tests/test_studio_connection_recovery.py','scripts/ci_entry.py')
NEW=('scripts/test_temporal_namespace.py','scripts/check_python_dependencies.py','scripts/test_python_dependencies.py')
OPS=('scripts/start_acos_local.ps1','scripts/stop_acos_local.ps1','scripts/restart_acos_backend.ps1','scripts/supervise_acos_local.ps1','scripts/start_local.ps1')

def main():
    assert ROOT.resolve()==Path('F:/PAO-ACOS')
    candidate=Path('F:/Apex/phase3-candidate')
    paths=[Path(arg).resolve() for arg in sys.argv[1:]];assert len(paths)==4
    for p in paths:assert p.is_relative_to((ROOT/'.runtime').resolve()) and p.is_file()
    ci,windows,private,cold=[json.loads(p.read_text(encoding='utf-8-sig')) for p in paths]
    assert ci.get('pass') and ci.get('linux_execution') and ci.get('node_and_typecheck_and_build')
    assert ci.get('backend',{}).get('tests',0)>=2258
    assert all(ci['backend'].get(k)==0 for k in ('failures','errors','skipped'))
    assert all(ci.get(k) is True for k in ('primary_unchanged','env_unchanged','owned_containers_removed'))
    assert windows.get('pass') and windows.get('crypto_compatibility') and windows.get('network_guard')
    assert windows.get('primary_unchanged') and windows.get('owned_resources_removed')
    assert private.get('pass') and all(private.get(k) is True for k in ('primary_unchanged','env_unchanged','backend_unchanged','owned_resources_removed'))
    assert cold.get('pass') and cold.get('primary_unchanged') and cold.get('source_archive_hashes_match')
    assert cold.get('source_image')=='pao-s6-linux:'+ci['run_id']
    assert cold.get('archive_reader',{}).get('incompatible_execution_denied')==3
    digest=lambda b:hashlib.sha256(b).hexdigest()
    with ZipFile(paths[0].parent/'source.zip') as frozen,ZipFile(paths[2].parent/'source.zip') as profile:
        expected={n for n in frozen.namelist() if is_runtime_source(n)}
        assert runtime_source_names(candidate)==runtime_source_names(ROOT)==expected,'Runtime source file set changed after CI'
        for name in frozen.namelist():
            if is_runtime_source(name) or name in ('pyproject.toml','requirements.lock','requirements-dev.lock','package.json','package-lock.json'):
                assert digest(frozen.read(name))==digest((candidate/name).read_bytes()),'Candidate changed after CI: '+name
                assert digest(profile.read(name))==digest(frozen.read(name)),'Private profile source differs: '+name
                if name not in CHANGED:assert digest((ROOT/name).read_bytes())==digest(frozen.read(name)),'Unrelated primary source drift: '+name
        security=json.loads((paths[0].parent/'python-security.json').read_text())
        assert security.get('audit_completed') and security.get('runtime_clean') and security.get('affected_packages')==[]
        assert security.get('runtime_requirements_sha256')==digest(frozen.read('requirements.lock'))
        baseline=json.loads((ROOT/'.runtime/checkpoints/p0-20261017T074318-95950754/manifest.json').read_text())['source']['files']
        for name in CHANGED:
            assert digest((ROOT/name).read_bytes())==baseline[name],'Primary edited since rollback baseline: '+name
            assert digest(frozen.read(name))==digest((candidate/name).read_bytes())
        for name in OPS:assert digest((ROOT/name).read_bytes())==baseline[name],'Primary launcher changed: '+name
        for name in NEW:
            assert digest(frozen.read(name))==digest((candidate/name).read_bytes())
            if (ROOT/name).exists():assert digest((ROOT/name).read_bytes())==digest(frozen.read(name))
        assert windows.get('requirements_sha256')==digest(frozen.read('requirements.lock'))
        assert windows.get('crypto_compat_source_sha256')==digest((candidate/'scripts/test_phase3_crypto_compat.py').read_bytes())
    wheels=candidate/'.runtime/backend-wheel-metadata'
    pin_test=json.loads((ROOT/'.runtime/phase3-pin-tests.json').read_text(encoding='utf-8-sig'))
    assert pin_test.get('pass') and pin_test.get('tests')==6
    assert set(pin_test['source_hashes'])=={'get_acos_python.ps1',*[Path(n).name for n in OPS]}
    for name,expected in pin_test['source_hashes'].items():assert digest((candidate/'scripts'/name).read_bytes())==expected
    rollback=json.loads((ROOT/'.runtime/phase3-crypto-rollback.json').read_text())
    assert rollback.get('pass') and rollback.get('new_jwt_readable_by_old') and rollback.get('new_fernet_readable_by_old') and rollback.get('synthetic_only')
    old=list((wheels/'old').glob('*.whl'));new=list((wheels/'new').glob('*.whl'))
    assert len(old)==len(new)==3
    for kind in ('old','new'):
        with ZipFile(wheels/kind/'pao_backend-0.1.0-py3-none-any.whl') as wheel:
            metadata=wheel.read('pao_backend-0.1.0.dist-info/METADATA').decode()
            assert ('cryptography<50,>=49' if kind=='old' else 'cryptography<51,>=50.0.2') in metadata.replace(' ','')
            for name in wheel.namelist():
                if name.startswith('pao/') and name.endswith('.py'):
                    assert digest(wheel.read(name).replace(b'\r\n',b'\n'))==digest((ROOT/'apps/api'/name).read_bytes().replace(b'\r\n',b'\n'))
    result={'pass':True,'production_accepted':False,'ci_manifest':str(paths[0]),'new_files':list(NEW),
        'changed_files':list(CHANGED),'operator_changed_files':list(OPS),'wheel_hashes':{kind:{p.name:digest(p.read_bytes()) for p in (wheels/kind).glob('*.whl')} for kind in ('old','new')}}
    (ROOT/'.runtime/phase3-candidate-release.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result))

if __name__=='__main__':main()
