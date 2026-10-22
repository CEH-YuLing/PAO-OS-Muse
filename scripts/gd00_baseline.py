"""Local baseline evidence and sealed PAO recovery files. Never stages Git or restores primary."""
import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
import io
from contextlib import redirect_stdout
from pathlib import Path, PurePosixPath
import re
import subprocess
import shutil
import sys
from uuid import uuid4
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'apps/api'), str(ROOT/'scripts'), str(ROOT/'packages/cli-runtime'), str(ROOT/'packages/pao-mcp')]
from pao.modules.operations.checkpoint import digest, verify
from backup_acos_checkpoint import source_archive
PRIVATE_CONFIGURATION = {'.env', '.runtime/acos-python-runtime.json',
                         '.runtime/cli-device.json', '.runtime/antigravity-native.json'}


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8') as output:
        json.dump(value, output, ensure_ascii=False, indent=2)


def owned_path(raw, base):
    path, base = Path(os.path.abspath(raw)), Path(os.path.abspath(base))
    if not path.is_relative_to(base):
        raise ValueError('recovery_path_outside_scope')
    for item in (path, *path.parents):
        if item.is_symlink() or getattr(item, 'is_junction', lambda: False)():
            raise ValueError('recovery_link_denied')
    return path


def checkpoint(path, root=ROOT):
    path = owned_path(path, root/'.runtime/checkpoints')
    saved = json.loads(path.read_text(encoding='utf-8'))
    archive = owned_path(saved['source']['path'], path.parent)
    dump = owned_path(saved['database']['backup'], root/'.runtime')
    if digest(archive) != saved['source']['sha256'] or digest(dump) != saved['database']['sha256']:
        raise ValueError('checkpoint_hash_mismatch')
    verify(archive, saved['source']['files'])
    return saved, archive, dump


def extract_source(archive, manifest, target):
    if target.exists():
        raise ValueError('restore_source_target_exists')
    verify(archive, manifest)
    for name in manifest:
        p = PurePosixPath(name)
        if p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name:
            raise ValueError('unsafe_restore_source_path')
    target.mkdir()
    with ZipFile(archive) as saved:
        for name in manifest:
            output = owned_path(target/name, target)
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open('xb') as stream:
                stream.write(saved.read(name))
            if digest(output) != manifest[name]:
                raise ValueError('restored_source_hash_mismatch')


def configured_secrets(root):
    from dotenv import dotenv_values
    values = dotenv_values(root/'.env')
    return {name: value.encode() for name, value in values.items()
            if value and len(value) >= 12 and re.search(r'KEY|TOKEN|SECRET|PASSWORD', name)}


TOKEN_PATTERNS = {
    'private_key': re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'openai_key_shape': re.compile(rb'\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{40,}\b'),
    'github_key_shape': re.compile(rb'\b(?:ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b'),
}


def scan_bytes(raw, names, secrets):
    findings = []
    for name, value in secrets.items():
        if value in raw:
            findings.append({'rule': 'configured_value', 'field': name})
    for name, pattern in TOKEN_PATTERNS.items():
        for hit in pattern.finditer(raw):
            # Only a fingerprint/line identifier is recorded, never a matched value.
            findings.append({'rule': name, 'line': raw[:hit.start()].count(b'\n')+1,
                             'match_sha256': hashlib.sha256(hit.group()).hexdigest()})
    return [{'location': names, **finding} for finding in findings]


def git(*args, binary=False, root=ROOT):
    run = subprocess.run(['git', '-c', 'safe.directory='+root.as_posix(), '--no-optional-locks',
                          '-C', str(root), *args], check=True, capture_output=True, timeout=120)
    return run.stdout if binary else run.stdout.decode('utf-8', errors='strict')


def git_inventory(files, secrets):
    status = git('status', '--porcelain=v1', '-z', '--untracked-files=all').split('\0')
    rows, index = [], 0
    while index < len(status):
        item = status[index]; index += 1
        if not item: continue
        state, name = item[:2], item[3:]
        if 'R' in state or 'C' in state: index += 1
        rows.append({'status': state, 'path': name, 'source_allowlisted': name in files})
    objects = git('rev-list', '--objects', '--all').splitlines()
    if len(objects) > 20_000: raise ValueError('history_review_size_limit')
    candidates = {line.split(' ', 1)[0]: line.split(' ', 1)[1] for line in objects if ' ' in line}
    # Bound object sizes before reading any historical blob.
    meta = subprocess.run(['git', '-c', 'safe.directory='+ROOT.as_posix(), '-C', str(ROOT),
                           'cat-file', '--batch-check=%(objectname) %(objecttype) %(objectsize)'],
                          input=('\n'.join(candidates)+'\n').encode(), capture_output=True,
                          check=True, timeout=60).stdout.decode().splitlines()
    blobs = [line.split() for line in meta if len(line.split()) == 3 and line.split()[1] == 'blob']
    if sum(int(row[2]) for row in blobs) > 128*1024*1024:
        raise ValueError('history_review_bytes_limit')
    findings = []
    batch = subprocess.run(['git', '-c', 'safe.directory='+ROOT.as_posix(), '-C', str(ROOT), 'cat-file', '--batch'],
        input=('\n'.join(row[0] for row in blobs)+'\n').encode(), capture_output=True, check=True, timeout=120).stdout
    cursor = 0
    for oid, _, size in blobs:
        end = batch.index(b'\n', cursor)
        if batch[cursor:end].split() != [oid.encode(), b'blob', size.encode()]:
            raise ValueError('history_blob_protocol_mismatch')
        cursor = end+1; raw = batch[cursor:cursor+int(size)]; cursor += int(size)+1
        findings.extend(scan_bytes(raw, {'object': oid, 'path': candidates[oid]}, secrets))
    return {'head': git('rev-parse', 'HEAD').strip(),
            'branch': git('branch', '--show-current').strip(),
            'commit_count': int(git('rev-list', '--count', '--all')),
            'changes': rows, 'historical_blobs_scanned': len(blobs), 'history_findings': findings,
            'index_changed_by_tool': False, 'commit_created': False, 'push_performed': False}


def private_files(root=ROOT):
    files = [root/name for name in sorted(PRIVATE_CONFIGURATION)]
    profiles = root/'.runtime/pao-mcp/profiles'
    if profiles.exists():
        owned_path(profiles, root)
        files += list(profiles.glob('*.dpapi'))
    selected = []
    for path in files:
        owned_path(path, root)
        if path.exists():
            if not path.is_file() or not 0 < path.stat().st_size <= 65536:
                raise ValueError('private_recovery_file_requires_review')
            selected.append(path)
    return selected


def seal_private(folder, root=ROOT):
    sys.path.insert(0, str(ROOT/'packages/pao-mcp'))
    from pao_mcp.profile import crypt
    protected = folder/'private-recovery'; protected.mkdir()
    records = []
    for index, source in enumerate(private_files(root)):
        raw = source.read_bytes()
        cipher = crypt(raw)
        path = protected/(str(index)+'.dpapi')
        with path.open('xb') as output: output.write(cipher)
        if crypt(path.read_bytes(), True) != raw:
            raise ValueError('private_recovery_roundtrip_failed')
        records.append({'source': source.relative_to(root).as_posix(),
                        'sealed': path.name, 'sha256': digest(path),
                        'original_sha256': hashlib.sha256(raw).hexdigest()})
    write_new(protected/'manifest.json', {'format': 'windows-dpapi-current-user-v1', 'files': records,
              'portable_disaster_recovery': False, 'offsite': False,
              'native_cli_credentials_copied': False})
    return protected


def read_private(folder):
    sys.path.insert(0, str(ROOT/'packages/pao-mcp'))
    from pao_mcp.profile import crypt
    manifest = json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('format') != 'windows-dpapi-current-user-v1':
        raise ValueError('private_recovery_format_denied')
    result = {}
    for item in manifest['files']:
        name = item['source']
        if (name in result or not (name in PRIVATE_CONFIGURATION
                or re.fullmatch(r'\.runtime/pao-mcp/profiles/[A-Za-z0-9_-]+\.dpapi', name))):
            raise ValueError('private_recovery_source_denied')
        path = owned_path(folder/item['sealed'], folder)
        if digest(path) != item['sha256']:
            raise ValueError('private_recovery_hash_mismatch')
        raw = crypt(path.read_bytes(), True)
        if hashlib.sha256(raw).hexdigest() != item['original_sha256']:
            raise ValueError('private_recovery_content_mismatch')
        result[item['source']] = raw
    if '.env' not in result: raise ValueError('private_recovery_env_missing')
    return result


async def snapshot():
    from pao.config import settings
    from check_acos_startup_schema import local_url
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text
    engine = create_async_engine(local_url(settings().database_url), connect_args={'server_settings': {
        'default_transaction_read_only': 'on', 'statement_timeout': '20000'}})
    try:
        async with engine.connect() as db:
            names = list(await db.scalars(text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")))
            result = {}
            for name in names:
                rows = sorted(await db.scalars(text('SELECT row_to_json(t)::text FROM "'+name.replace('"','""')+'" t')))
                result[name] = {'count': len(rows), 'sha256': hashlib.sha256(json.dumps(rows).encode()).hexdigest()}
            return result
    finally: await engine.dispose()


def operating_inventory():
    """Version/status metadata only; never Docker Env or native credential files."""
    import platform
    from urllib.request import build_opener, ProxyHandler
    from pao.app import create_app
    from pao.config import settings
    def output(args):
        return subprocess.run(args,capture_output=True,check=True,timeout=30).stdout.decode('utf-8').strip()
    live=json.loads(build_opener(ProxyHandler({})).open('http://127.0.0.1:8100/openapi.json',timeout=15).read())
    source=create_app().openapi()
    stored=json.loads((ROOT/'packages/contracts/openapi.json').read_text(encoding='utf-8'))
    if source!=live or stored!=live:raise ValueError('gd00_live_source_contract_mismatch')
    containers=[json.loads(line) for line in output(['docker','inspect','pao-acos-local-postgres-1','pao-acos-local-redis-1',
        '--format','[{{json .Name}},{{json .Config.Image}},{{json .State.Status}},{{json .State.Health.Status}}]']).splitlines()]
    return {'windows':platform.platform(),'node':output(['node','--version']),
        'docker':json.loads(output(['docker','version','--format','{{json .}}'])),
        'containers':containers,'processes':runtime_identities(),
        'contract':{'operations':sum(m in {'get','post','patch','put','delete','head','options'}
            for path in live['paths'].values() for m in path),'source_live_stored_equal':True,
            'stored_sha256':digest(ROOT/'packages/contracts/openapi.json')},
        'native_cli_profile_volume_names':output(['docker','volume','ls','--format','{{.Name}}','--filter','name=pao-cli-profile-']).splitlines(),
        'runtime_pin_sha256':digest(ROOT/'.runtime/acos-python-runtime.json'),
        'historical_release_receipt_sha256':digest(ROOT/'.runtime/current-local-release.json'),
        'historical_receipt_is_current_acceptance':False,
        'activation_flags':{k:v for k,v in settings().model_dump().items() if k.endswith('_enabled')},
        'schema_candidate_0076_installed':False,
        'backup_scope':'source+PostgreSQL+PAO private configuration; native CLI auth requires re-login',
        'build_evidence':'docs/LOCAL-THEME-AUTO-2026-10-21.vi.md (unchanged frontend; not rerun in GD00)'}


def prepare():
    from check_p84_foundation import binding, health
    from check_acos_startup_schema import check
    from pao.config import settings
    from importlib.metadata import version
    if ROOT != Path('F:/PAO-ACOS'): raise ValueError('acos_checkout_required')
    folder = ROOT/'.runtime'/('gd00-'+uuid4().hex); folder.mkdir()
    before = asyncio.run(snapshot()); write_new(folder/'primary-before.json', before)
    inventory=operating_inventory();write_new(folder/'operating-inventory.json',inventory)
    source = source_archive(ROOT, folder/'source.zip')
    secrets = configured_secrets(ROOT)
    findings = []
    for name in source:
        findings.extend(scan_bytes((ROOT/name).read_bytes(), name, secrets))
    repository = git_inventory(source, secrets)
    write_new(folder/'git-baseline-plan.json', repository)
    private = seal_private(folder)
    from pao_mcp.profile import crypt
    tamper_rejected = False
    cipher = crypt(b'synthetic-gd00-only')
    try: crypt(cipher[:-1]+bytes([cipher[-1]^1]), True)
    except Exception: tamper_rejected = True
    if not tamper_rejected: raise ValueError('dpapi_tamper_not_rejected')
    result = {'scope': 'GD00_local_preparation', 'created_at': datetime.now(timezone.utc).isoformat(),
        'binding': binding(), 'schema': asyncio.run(check(settings().database_url)), 'health': health(),
        'python': sys.version, 'python_executable': sys.executable,
        'dependencies': {name: version(name) for name in ('fastapi','SQLAlchemy','asyncpg','alembic','PyJWT','cryptography','arq')},
        'lock_hashes': {name: digest(ROOT/name) for name in ('requirements.lock','requirements-dev.lock','package-lock.json','pyproject.toml')},
        'source_files': source, 'source_zip_sha256': digest(folder/'source.zip'),
        'source_findings': findings, 'history_findings': repository['history_findings'],
        'private_recovery': str(private), 'private_tamper_rejected': tamper_rejected,
        'private_key_portable_backup': False, 'offsite': False, 'git_committed': False,
        'primary_before': str(folder/'primary-before.json'), 'env_sha256': digest(ROOT/'.env'),
        'native_cli_profiles': 'metadata/re-login only; native credential volumes/keyrings not copied',
        'database_file_bytes': 'Brain file/note contents reside in database; covered by DB checkpoint',
        'whole_phase_complete': False, 'production_accepted': False}
    write_new(folder/'baseline.json', result)
    print(json.dumps({'folder': str(folder), 'source_files': len(source), 'git_changes': len(repository['changes']),
        'source_findings': len(findings), 'history_findings': len(repository['history_findings']),
        'dpapi_roundtrip': True, 'tamper_rejected': tamper_rejected}))


def runtime_identities():
    from read_owned_pao_processes import metadata
    rows = json.loads((ROOT/'.runtime/acos-processes.json').read_text(encoding='utf-8-sig'))
    result = {}
    for name, expected in rows.items():
        value = metadata(expected['id'])
        if value['started'] != int(expected['started']):
            raise ValueError('gd00_process_identity_changed')
        result[name] = {'id':value['id'],'started':str(value['started']),
                        'exe':value['exe'],'command_sha256':hashlib.sha256(value['command'].encode()).hexdigest()}
    if not {'api','worker','web'} <= result.keys():
        raise ValueError('gd00_runtime_incomplete')
    return result


def verify_phase(folder, manifest):
    from check_s03_restore import main as restore
    from check_p84_foundation import binding, health
    from check_acos_startup_schema import check
    from pao.config import settings
    folder = owned_path(folder, ROOT/'.runtime')
    if not re.fullmatch(r'gd00-[0-9a-f]{32}',folder.name):raise ValueError('gd00_baseline_folder_denied')
    baseline = json.loads((folder/'baseline.json').read_text(encoding='utf-8'))
    # This is a retained evidence-bound baseline, never an instruction to restore primary.
    if baseline['binding'] != binding() or baseline['env_sha256'] != digest(ROOT/'.env'):
        raise ValueError('gd00_baseline_inputs_changed')
    for name, raw in read_private(folder/'private-recovery').items():
        if hashlib.sha256(raw).hexdigest()!=digest(ROOT/name):
            raise ValueError('gd00_private_configuration_changed')
    saved, _, _ = checkpoint(manifest)
    before = json.loads((folder/'primary-before.json').read_text())
    if asyncio.run(snapshot()) != before:raise ValueError('gd00_primary_changed_since_baseline')
    processes = runtime_identities()
    write_new(folder/'runtime-before.json',processes)
    shell=shutil.which('pwsh.exe') or shutil.which('powershell.exe')
    if not shell:raise ValueError('gd00_powershell_unavailable')
    shell_env=os.environ.copy()
    # A Python child does not perform PowerShell's PS5/PS7 module-path transition.
    # Let the selected shell build its own default module path; no global edit.
    shell_env.pop('PSModulePath',None)
    checks_to_run = [
        ('offline-unit', [sys.executable,'-B','-m','unittest','scripts.test_acos_startup_schema',
            'scripts.test_gd00_baseline','scripts.test_s03_restore','-v']),
        ('source-archive', [str(ROOT/'.venv/Scripts/python.exe'),'-B','-m','pytest',
            'scripts/test_acos_checkpoint.py','-q','-p','no:cacheprovider']),
        ('runtime-pin', [shell,'-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'scripts/test_acos_python_pin.ps1')]),
    ]
    tests={}
    for name, command in checks_to_run:
        run_env={**shell_env,'PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1'}
        ran=subprocess.run(command,cwd=ROOT,env=run_env,capture_output=True,timeout=120)
        with (folder/(name+'.log')).open('xb') as log:log.write(ran.stdout+b'\n'+ran.stderr)
        if ran.returncode:raise ValueError('gd00_offline_test_failed')
        combined=(ran.stdout+ran.stderr).decode('utf-8',errors='replace')
        if name=='offline-unit':
            counts=re.findall(r'Ran (\d+) tests? in ',combined)
            if not counts or int(counts[-1])<28 or 'skipped=' in combined:raise ValueError('gd00_unit_receipt_invalid')
            tests[name]={'passed':int(counts[-1]),'interpreter':sys.executable}
        elif name=='source-archive':
            if '5 passed' not in combined:raise ValueError('gd00_archive_receipt_invalid')
            tests[name]={'passed':5,'interpreter':command[0],'serving_runtime_modified':False}
        else:
            pin=json.loads(ran.stdout.decode('utf-8-sig'))
            if not pin.get('pass') or pin.get('tests')!=6:raise ValueError('gd00_pin_receipt_invalid')
            tests[name]={'passed':6,'synthetic_only':True}
    for index in range(2):
        started = subprocess.run([shell,'-NoProfile','-ExecutionPolicy','Bypass',
            '-File',str(ROOT/'scripts/start_acos_local.ps1')],cwd=ROOT,env=shell_env,capture_output=True,timeout=120)
        # Launcher contains no credential-printing commands; keep output private.
        with (folder/f'startup-{index+1}.log').open('xb') as log:
            log.write(started.stdout+b'\n'+started.stderr)
        if started.returncode:raise ValueError('gd00_startup_failed')
        if runtime_identities()!=processes:raise ValueError('gd00_startup_not_idempotent')
        if asyncio.run(snapshot())!=before:raise ValueError('gd00_startup_changed_primary')
    output = io.StringIO()
    try:
        with redirect_stdout(output): asyncio.run(restore(manifest, str(folder)))
    finally:
        with (folder/'restore.log').open('x',encoding='utf-8') as log:log.write(output.getvalue())
    restored = [json.loads(line) for line in output.getvalue().splitlines() if line.startswith('{')]
    if not restored or not restored[-1].get('pass'):raise ValueError('gd00_restore_receipt_missing')
    after = asyncio.run(snapshot()); write_new(folder/'primary-after.json',after)
    if after!=before:raise ValueError('gd00_primary_changed')
    if runtime_identities()!=processes or digest(ROOT/'.env')!=baseline['env_sha256']:
        raise ValueError('gd00_runtime_or_env_changed')
    # Final source is the exact source in this checkpoint, not merely a binding match.
    current = source_archive(ROOT,folder/'final-source.zip')
    if current!=saved['source']['files'] or current!=baseline['source_files']:
        raise ValueError('gd00_checkpoint_source_stale')
    checks=health()
    if set(checks.values())!={200}:raise ValueError('gd00_health_failed')
    findings=baseline['source_findings']+baseline['history_findings']
    reviewed={'location':'apps/api/tests/test_artifact_learning.py','rule':'private_key','line':51,
              'match_sha256':'8bcac7908eb950419537b91e19adc83ce2c9cbfdacf4f81157fdadfec11f7017'}
    if (any(item!=reviewed for item in findings) or digest(ROOT/reviewed['location']) !=
            'df716b4e584fd8b7495d02364bb0d157e7e0d90ecfc86e58bf44ea8eca6054c0'):
        raise ValueError('gd00_secret_review_required')
    result={'phase':'GD00','local_accepted':True,'created_at':datetime.now(timezone.utc).isoformat(),
        'baseline':str(folder/'baseline.json'),'checkpoint':str(manifest),
        'source_files':len(current),'source_zip_sha256':saved['source']['sha256'],
        'schema':asyncio.run(check(settings().database_url)),'backend_binding':binding(),
        'restore':restored[-1], 'health':checks,'two_starts_same_processes':True,
        'tests':tests,
        'primary_exact_row_hashes_unchanged':True,'env_unchanged':True,
        'reviewed_synthetic_scan_findings':len(findings),'unreviewed_scan_findings':0,
        'git_commit_performed':False,'git_publication':'pending_separate_authorization',
        'offsite_backup':'external_pending','portable_recovery_key':'external_pending',
        'native_cli_auth_backup':'not_copied_relogin_required_on_new_host',
        'production_accepted':False,'whole_disaster_recovery_accepted':False,
        'next':'GD01_not_started_by_this_phase'}
    write_new(folder/'completion.json',result)
    # Stable pointer is the only replaceable file; immutable run receipts remain intact.
    pointer=ROOT/'.runtime/gd00-current-status.json'
    temporary=folder/'current-status.tmp';write_new(temporary,result);os.replace(temporary,pointer)
    print(json.dumps({'local_accepted':True,'receipt':str(folder/'completion.json'),
        'source_files':len(current),'tables':len(after),'archive_replays':restored[-1]['artifacts'],
        'health':checks,'offsite_backup':'external_pending','portable_recovery_key':'external_pending'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('action', choices=('prepare','verify'))
    parser.add_argument('--folder', type=Path);parser.add_argument('--manifest', type=Path)
    args=parser.parse_args()
    if args.action=='prepare':prepare()
    elif args.folder and args.manifest:verify_phase(args.folder,args.manifest)
    else:parser.error('verify requires --folder and --manifest')
