"""Build a source-identical disposable copy; never generate egg-info in candidate."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from uuid import uuid4
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps/api'))
from pao.modules.operations.checkpoint import entries


def main():
    candidate = ROOT / '.runtime/p84-native-candidate-20261018'
    build_deps = ROOT / '.runtime/p84-build-deps'
    assert ROOT == Path('F:/PAO-ACOS') and candidate.is_dir()
    assert (build_deps / 'setuptools/build_meta.py').is_file()
    before = entries(candidate)
    folder = ROOT / '.runtime' / ('p84-package-' + uuid4().hex)
    source = folder / 'source'
    dist = folder / 'dist'
    dist.mkdir(parents=True)
    for name in before:
        target = source / name
        assert target.resolve().is_relative_to(source) and not target.exists()
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(candidate / name, target)
    assert entries(source) == before
    env = {**os.environ, 'PYTHONPATH': str(build_deps), 'PYTHONDONTWRITEBYTECODE': '1',
           'PAO_ROOT': str(source), 'JWT_SECRET': 'synthetic-package-import-only-not-a-real-secret',
           'DATABASE_URL': 'postgresql+asyncpg://synthetic@127.0.0.1:1/pao_test',
           'REDIS_URL': 'redis://127.0.0.1:1/15'}
    with (folder / 'build.log').open('xb') as log:
        subprocess.run([sys.executable, '-B', '-c',
            'from setuptools.build_meta import build_wheel; build_wheel(' + repr(str(dist)) + ')'],
            cwd=source, env=env, stdout=log, stderr=subprocess.STDOUT, check=True, timeout=120)
    wheels = list(dist.glob('*.whl'))
    assert len(wheels) == 1
    wheel = wheels[0]
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        assert {'pao_cli_runtime/docker_transport.py', 'pao_cli_runtime/profile_transport.py', 'pao_cli_runtime/source_pin.py',
                'pao/modules/cli_connections/gateway.py'} <= set(names)
        assert not any('/.runtime/' in '/' + name or '/.env' in '/' + name or 'auth.json' in name
                       or name.endswith(('.db', '.dump', '.log')) for name in names)
        installed = folder / 'wheel-only'
        for name in names:
            target = installed / name
            assert target.resolve().is_relative_to(installed) and '\\' not in name
        archive.extractall(installed)
    expected = hashlib.sha256()
    for module in sorted((source / 'packages/cli-runtime/pao_cli_runtime').glob('*.py')):
        expected.update(module.name.encode('utf-8') + b'\0')
        expected.update(module.read_bytes() + b'\0')
    host_runtime_sha256 = expected.hexdigest()
    # Import only from the wheel, not an editable checkout or source PYTHONPATH.
    probe = ('import sys; sys.path.insert(0,' + repr(str(installed)) + '); '
             'import pao_cli_runtime.docker_transport as d; '
             'import pao_cli_runtime.source_pin as s; '
             'import pao.modules.cli_connections.gateway as g; '
             'assert d.__file__.startswith(sys.path[0]); '
             'assert g.__file__.startswith(sys.path[0]); '
             'assert s.library_digest() == ' + repr(host_runtime_sha256) + '; print("wheel_import_and_source_pin_ok")')
    with (folder / 'import.log').open('xb') as log:
        subprocess.run([sys.executable, '-I', '-B', '-c', probe], cwd=folder, env=env,
                       stdout=log, stderr=subprocess.STDOUT, check=True, timeout=30)
    result = {'pass': entries(candidate) == before, 'candidate_unchanged': entries(candidate) == before,
              'wheel_sha256': hashlib.sha256(wheel.read_bytes()).hexdigest(),
              'host_runtime_sha256': host_runtime_sha256,
              'wheel_files': len(names), 'source_manifest': before, 'provider_calls': 0,
              'installed_into_serving_runtime': False, 'production_accepted': False}
    (folder / 'receipt.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'source_manifest'}))
    print(folder)
    raise SystemExit(0 if result['pass'] else 1)


if __name__ == '__main__':
    main()
