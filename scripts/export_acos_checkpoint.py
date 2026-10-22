"""Export a verified checkpoint without overwriting existing backups or copying CLI logins."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from uuid import uuid4

from gd00_baseline import ROOT, checkpoint, digest, owned_path, read_private, seal_private, write_new


def export(manifest):
    config = json.loads((ROOT/'infra/backup-storage.json').read_text(encoding='utf-8'))
    if (config['source_root'] != str(ROOT) or config['overwrite_existing_backups']
            or config['automatic_deletion'] or config['github_upload']):
        raise ValueError('backup_configuration_requires_review')
    saved, archive, dump = checkpoint(manifest)
    base = owned_path(config['backup_root'], Path(config['backup_root']))
    if not base.is_dir():
        raise ValueError('approved_backup_root_missing')
    container = owned_path(base/config['checkpoint_subdirectory'], base)
    container.mkdir(exist_ok=True)
    target = owned_path(container/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid4().hex), container)
    target.mkdir()  # Must be new; failed/partial exports are preserved for inspection.
    files = {}
    for name, source in (('source.zip', archive), ('database.dump', dump), ('checkpoint-original.json', Path(manifest).absolute())):
        dest = target/name
        with source.open('rb') as src, dest.open('xb') as output:
            shutil.copyfileobj(src, output)
        if digest(dest) != digest(source):
            raise ValueError('backup_copy_hash_mismatch')
        files[name] = digest(dest)
    sealed = seal_private(target)
    private = read_private(sealed)
    del private  # Verified in memory only. Never print decrypted content.
    for file in sealed.iterdir():
        files[file.relative_to(target).as_posix()] = digest(file)
    write_new(target/'recovery-index.json', {
        'format': 'pao-local-recovery-export-v1', 'files': files,
        'revision': saved['database']['revision_before'], 'binding': saved['binding'],
        'source': 'source.zip', 'database': 'database.dump', 'private_configuration': 'private-recovery',
        'original_manifest_preserved': True, 'original_paths_are_historical': True,
        'restore_primary': False, 'offsite': False, 'portable_keys': False,
        'native_cli_credentials_copied': False,
    })
    return {'backup': str(target), 'files_verified': len(files), 'private_roundtrip': True,
            'overwrite': False, 'offsite': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('manifest')
    print(json.dumps(export(parser.parse_args().manifest)))
