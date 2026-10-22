"""Checkpoint/verify the offline CLI foundation; never migrate or run a provider.

Baseline is captured after adding the separate package, BEFORE documentation/CI
updates. It is not represented as a pre-implementation full database backup.
Only primary schema metadata is read, in a server-enforced read-only connection.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
from urllib.request import build_opener, ProxyHandler
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps/api'))
from pao.modules.operations.checkpoint import archive, digest, entries, verify


def protected():
    paths = []
    for current, directories, files in os.walk(ROOT / 'apps', followlinks=False):
        directories[:] = [name for name in directories if name not in {
            '.next', 'node_modules', '__pycache__', '.pytest_cache'} and not (Path(current) / name).is_symlink()
            and not getattr(Path(current) / name, 'is_junction', lambda: False)()]
        paths.extend(Path(current) / name for name in files if not (Path(current) / name).is_symlink())
    paths += [ROOT / name for name in ('.env', '.env.example', 'requirements.lock', 'requirements-dev.lock',
        'pyproject.toml', 'package.json', 'package-lock.json', 'scripts/start_acos_local.ps1',
        'scripts/get_acos_python.ps1', '.runtime/acos-python-runtime.json', '.runtime/current-local-release.json')]
    return {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(set(paths)) if p.is_file()}


def binding():
    root = ROOT / 'apps/api/pao'
    value = hashlib.sha256()
    value.update(f'python:{sys.version_info[:3]}'.encode())
    for path in sorted(root.rglob('*.py')):
        value.update(path.relative_to(root).as_posix().encode() + b'\0')
        value.update(path.read_bytes().replace(b'\r\n', b'\n') + b'\0')
    return value.hexdigest()


async def primary_schema():
    from sqlalchemy import text
    from sqlalchemy.engine import make_url
    from sqlalchemy.ext.asyncio import create_async_engine
    from pao.config import settings
    url = make_url(settings().database_url)
    if (url.drivername, url.host, url.port, url.database) != ('postgresql+asyncpg', '127.0.0.1', 15432, 'pao_acos_local'):
        raise RuntimeError('p84_primary_scope_denied')
    engine = create_async_engine(url, connect_args={'server_settings': {
        'default_transaction_read_only': 'on', 'statement_timeout': '5000', 'application_name': 'p84_schema_readonly'}})
    try:
        async with engine.connect() as db:
            readonly = await db.scalar(text('SHOW transaction_read_only'))
            if readonly != 'on':
                raise RuntimeError('p84_readonly_required')
            revision = await db.scalar(text('SELECT version_num FROM alembic_version'))
            tables = list(await db.scalars(text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")))
            return {'revision': revision, 'physical_tables': len(tables),
                    'table_names_sha256': hashlib.sha256(json.dumps(tables).encode()).hexdigest(), 'read_only': True}
    finally:
        await engine.dispose()


def health():
    result = {}
    opener = build_opener(ProxyHandler({}))
    for name, url in (('api', 'http://127.0.0.1:8100/health'), ('ready', 'http://127.0.0.1:8100/ready'),
                      ('web', 'http://127.0.0.1:3200/')):
        try:
            with opener.open(url, timeout=10) as response:
                result[name] = response.status
        except Exception:
            result[name] = 'unavailable'
    return result


def inventory():
    result = {}
    for binary in ('codex', 'claude', 'agy'):
        path = shutil.which(binary)
        result[binary] = {'found': path is not None, 'version': 'not_executed_in_AB',
                          'authenticated': 'not_probed', 'inference': 'not_probed'}
        if path:
            result[binary].update(path=path, sha256=digest(path))
    return result


def write_new(path, value):
    with path.open('x', encoding='utf-8') as output:
        json.dump(value, output, ensure_ascii=False, indent=2)


def main():
    if ROOT != Path('F:/PAO-ACOS'):
        raise SystemExit('p84_primary_checkout_required')
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('baseline', 'verify'))
    parser.add_argument('--folder', type=Path)
    parser.add_argument('--linux-image')
    args = parser.parse_args()
    if args.action == 'baseline':
        folder = ROOT / '.runtime' / ('p84-foundation-' + uuid4().hex)
        folder.mkdir()
        manifest = archive(ROOT, folder / 'source-baseline.zip')
        state = {'stage': 'foundation_pre_acceptance_not_pre_implementation', 'utc': datetime.now(timezone.utc).isoformat(),
                 'python': platform.python_version(), 'binding': binding(), 'protected': protected(),
                 'schema': asyncio.run(primary_schema()), 'health': health(), 'inventory': inventory(),
                 'source_manifest': manifest, 'primary_content_hashes_measured': False,
                 'migrations': 0, 'provider_calls': 0}
        write_new(folder / 'baseline.json', state)
        print(folder)
        print(json.dumps({k: state[k] for k in ('stage', 'binding', 'schema', 'health')}))
        return
    folder = args.folder
    if (folder is None or folder.is_symlink() or not folder.is_absolute()
            or folder.parent != ROOT / '.runtime' or not re.fullmatch(r'p84-foundation-[0-9a-f]{32}', folder.name)):
        raise SystemExit('p84_receipt_scope_denied')
    before = json.loads((folder / 'baseline.json').read_text(encoding='utf-8'))
    verify(folder / 'source-baseline.zip', before['source_manifest'])
    source = entries(ROOT)
    repetitions = []
    for repeat in range(3):
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/test_p84_cli_foundation.py')],
                                cwd=ROOT, capture_output=True, timeout=90)
        log = result.stdout + result.stderr
        name = f'unit-{uuid4().hex}.log'
        with (folder / name).open('xb') as output:
            output.write(log)
        match = re.search(rb'Ran (\d+) tests', log)
        repetitions.append({'pass': result.returncode == 0 and b'\nOK' in log,
                            'tests': int(match[1]) if match else 0, 'log': name})
    linux = {'executed': False, 'pass': False}
    if args.linux_image:
        if not re.fullmatch(r'[0-9a-f]{12,64}', args.linux_image):
            raise SystemExit('p84_local_image_id_required')
        command = ['docker', 'run', '--rm', '--pull=never', '--network=none', '--read-only',
                   '--tmpfs', '/tmp:rw,noexec,nosuid,size=64m', '--cap-drop=ALL',
                   '--security-opt=no-new-privileges', '--pids-limit=64', '--memory=512m', '--cpus=1',
                   '--user=65534:65534', '--mount',
                   f'type=bind,source={ROOT / "packages/cli-runtime"},target=/workspace/packages/cli-runtime,readonly',
                   '--mount', f'type=bind,source={ROOT / "scripts/test_p84_cli_foundation.py"},target=/workspace/scripts/test_p84_cli_foundation.py,readonly',
                   '--entrypoint=python', args.linux_image, '-B', '/workspace/scripts/test_p84_cli_foundation.py']
        result = subprocess.run(command, capture_output=True, timeout=120)
        log = result.stdout + result.stderr
        name = f'linux-unit-{uuid4().hex}.log'
        with (folder / name).open('xb') as output:
            output.write(log)
        match = re.search(rb'Ran (\d+) tests', log)
        linux = {'executed': True, 'pass': result.returncode == 0 and b'\nOK' in log,
                 'tests': int(match[1]) if match else 0, 'image_id': args.linux_image,
                 'network': 'none', 'host_secrets_mounted': False, 'log': name}
    schema = asyncio.run(primary_schema())
    endpoints = health()
    result = {'stage': 'P8.4-A-B-offline-foundation', 'utc': datetime.now(timezone.utc).isoformat(),
              'python': platform.python_version(), 'windows_execution': sys.platform == 'win32',
              'repetitions': repetitions, 'protected_unchanged': before['protected'] == protected(),
              'linux_offline': linux,
              'binding_unchanged': before['binding'] == binding(), 'schema_unchanged': before['schema'] == schema,
              'schema': schema, 'health': endpoints, 'baseline_health': before['health'],
              'tested_source_manifest': source, 'source_unchanged_during_tests': source == entries(ROOT),
              'primary_content_hashes_measured': False, 'live_provider_calls': 0,
              'serving_engine_registered': False, 'full_backend_regression': False,
              'live_cli_accepted': False, 'production_accepted': False}
    result['pass'] = (all(x['pass'] and x['tests'] >= 26 for x in repetitions)
                      and all(result[key] for key in ('protected_unchanged', 'binding_unchanged', 'schema_unchanged', 'source_unchanged_during_tests'))
                      and (not args.linux_image or linux['pass'] and linux.get('tests', 0) >= 26)
                      and all(status == 200 for status in endpoints.values()))
    receipt = folder / ('receipt-' + uuid4().hex + '.json')
    write_new(receipt, result)
    print(receipt)
    print(json.dumps({k: v for k, v in result.items() if k != 'tested_source_manifest'}))
    raise SystemExit(0 if result['pass'] else 1)


if __name__ == '__main__':
    main()
