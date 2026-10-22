"""Retain unverified candidate source without calling it a DB/release checkpoint."""
import hashlib
import json
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'apps/api'), str(ROOT / 'scripts')]
from backup_acos_checkpoint import source_archive
from pao.modules.operations.checkpoint import verify


def main():
    candidate = ROOT / '.runtime/p84-native-candidate-20261018'
    assert ROOT == Path('F:/PAO-ACOS') and candidate.is_dir()
    folder = ROOT / '.runtime' / ('p84-candidate-source-' + uuid4().hex)
    folder.mkdir()
    archive = folder / 'source.zip'
    manifest = source_archive(candidate, archive)
    verify(archive, manifest)
    receipt = {'archive_integrity_verified': True, 'source_manifest': manifest,
        'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
        'candidate_qualification_passed': False, 'pending_changes_tested': False,
        'primary_migrated': False, 'database_checkpoint': False, 'provider_calls': 0,
        'whole_P84_C_accepted': False, 'production_accepted': False}
    (folder / 'receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(folder)
    print(json.dumps({k: v for k, v in receipt.items() if k != 'source_manifest'}))


if __name__ == '__main__':
    main()
