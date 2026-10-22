"""Checkpoint before schema work; create an allowlisted candidate, never migrate primary."""
import asyncio
import json
from pathlib import Path
import shutil
import subprocess
import sys
from uuid import uuid4
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps/api'))
sys.path.insert(0, str(ROOT / 'scripts'))
from check_p84_foundation import binding, primary_schema, protected, health
from pao.modules.operations.checkpoint import archive, digest, verify
from backup_acos_checkpoint import source_archive


def main():
    if ROOT != Path('F:/PAO-ACOS'):
        raise SystemExit('p84_checkout_required')
    candidate = ROOT / '.runtime/p84-native-candidate-20261018'
    if candidate.exists():
        raise SystemExit('p84_candidate_exists_preserve_changes')
    folder = ROOT / '.runtime' / ('p84-native-checkpoint-' + uuid4().hex)
    folder.mkdir()
    state = {'binding': binding(), 'protected': protected(), 'schema': asyncio.run(primary_schema()),
             'health': health(), 'primary_migrated': False}
    if state['schema']['revision'] != '0071' or any(code != 200 for code in state['health'].values()):
        raise SystemExit('p84_baseline_not_ready')
    state['source_manifest'] = source_archive(ROOT, folder / 'source.zip')
    with (folder / 'primary.dump').open('xb') as output:
        result = subprocess.run(['docker', 'exec', 'pao-acos-local-postgres-1', 'pg_dump', '-U', 'pao',
            '-d', 'pao_acos_local', '-Fc'], stdout=output, stderr=subprocess.PIPE, timeout=60)
    if result.returncode or (folder / 'primary.dump').stat().st_size < 1024:
        raise SystemExit('p84_database_checkpoint_failed_schema_work_blocked')
    state['database_checkpoint_sha256'] = digest(folder / 'primary.dump')
    verify(folder / 'source.zip', state['source_manifest'])
    if state['protected'] != protected() or state['binding'] != binding():
        raise SystemExit('p84_source_drift_during_checkpoint')
    candidate.mkdir()
    with zipfile.ZipFile(folder / 'source.zip') as source:
        # Archive was verified against exact source manifest; no runtime/env/git.
        for name in state['source_manifest']:
            path = candidate / name
            if not path.resolve().is_relative_to(candidate) or path.exists():
                raise RuntimeError('p84_candidate_path_denied')
            path.parent.mkdir(parents=True, exist_ok=True)
            with source.open(name) as incoming, path.open('xb') as output:
                shutil.copyfileobj(incoming, output)
    state['candidate'] = str(candidate)
    state['candidate_created'] = True
    (folder / 'checkpoint.json').write_text(json.dumps(state, indent=2), encoding='utf-8')
    print(json.dumps({'checkpoint': str(folder), 'candidate': str(candidate), 'primary_migrated': False}))


if __name__ == '__main__':
    main()
