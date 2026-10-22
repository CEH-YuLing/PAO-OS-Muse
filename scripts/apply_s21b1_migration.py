"""Guarded additive rollout: no native rows, mapping, credentials or flags change."""
import asyncio
import json
from pathlib import Path
import subprocess
import sys

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from pao.config import ROOT, settings
from pao.skills import execution_binding
from pao.modules.operations.checkpoint import digest, verify
from check_p11_migration import snapshot
from check_m2_restore import inspect


async def main(manifest_path):
    url = make_url(settings().database_url)
    if ROOT.resolve() != Path('F:/PAO-ACOS') or url.database != 'pao_acos_local' or url.host != '127.0.0.1' or url.port != 15432:
        raise SystemExit('Only ACOS-local rollout allowed')
    manifest = Path(manifest_path).resolve()
    assert manifest.is_relative_to((ROOT/'.runtime/checkpoints').resolve()) and manifest.is_file()
    saved = json.loads(manifest.read_text(encoding='utf-8'))
    assert saved['database']['revision_before'] == '0048'
    backup = Path(saved['database']['backup']).resolve()
    assert backup.is_relative_to((ROOT/'.runtime').resolve()) and digest(backup) == saved['database']['sha256']
    archive = Path(saved['source']['path']).resolve()
    assert archive.is_relative_to(manifest.parent) and digest(archive) == saved['source']['sha256']
    assert saved['binding'] == execution_binding()
    verify(archive, saved['source']['files'])
    subprocess.run([sys.executable, 'scripts/check_acos_idle.py', '--safe-repair'], cwd=ROOT, check=True)
    before = await snapshot(url)
    archives = await inspect(url)
    assert archives['revision'] == '0048' and len(archives['counts']) == saved['database']['table_count']
    subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', '0049'], cwd=ROOT, check=True)
    assert (await snapshot(url, before[0]))[1] == before[1], 'Legacy data changed; retain backup and stop'
    after = await inspect(url)
    assert after['revision'] == '0049' and after['artifact_hashes'] == archives['artifact_hashes']
    added = {'tenant_connection_references', 'tenant_connection_grants', 'tenant_connection_audits'}
    assert set(after['counts'])-set(archives['counts']) == added and all(after['counts'][name] == 0 for name in added)
    subprocess.run([sys.executable, '-m', 'alembic', 'check'], cwd=ROOT, check=True)
    print(json.dumps({'pass': True, 'revision': '0049', 'legacy_tables_preserved': len(before[0]),
        'legacy_row_hashes_exact': True, 'archive_hashes_preserved': True, 'new_tables': 3,
        'automatic_mapping': False, 'external_calls': False, 'pre_checkpoint': str(manifest)}))


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Pass verified pre-deployment manifest')
    asyncio.run(main(sys.argv[1]))
