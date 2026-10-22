"""Build one pinned, secret-free OFFLINE image; never login or run inference.

Only official public npm bytes are downloaded. The build context is an explicit
allowlist in a new runtime folder, not the PAO checkout or the Windows home.
Registry integrity is pinned here; npm provenance/signatures are not certified.
"""
import base64
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile
from urllib.request import build_opener, ProxyHandler
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/cli-runtime'))
from pao_cli_runtime.source_pin import library_digest
VERSION = '0.157.1'
URL = 'https://registry.npmjs.org/@openai/codex/-/codex-0.157.1-linux-x64.tgz'
INTEGRITY = 'Eac8XlC0nCXSeUjDU9l8yLJ6P9evv1mO+AnvILoNwlegBC7B3AVXqJ05QcMhQX7RcJ3Lk2618ykCb2X2ui8VAQ=='
BASE = 'python:3.12-slim-trixie@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1'


def main():
    if ROOT != Path('F:/PAO-ACOS'):
        raise SystemExit('p84_checkout_required')
    parser = argparse.ArgumentParser()
    parser.add_argument('--cached-archive', type=Path)
    parser.add_argument('--runtime-candidate',action='store_true')
    args = parser.parse_args()
    runtime_source=ROOT/'packages/cli-runtime/pao_cli_runtime'
    if runtime_source.is_symlink() or not runtime_source.is_dir():raise RuntimeError('runtime_source_invalid')
    def runtime_files():
        files={path.name:path for path in runtime_source.glob('*.py')}
        if args.runtime_candidate:
            overlay=ROOT/'packages/cli-runtime/candidates/installation-ai/pao_cli_runtime'
            expected={'contracts.py','docker_transport.py','codex_worker.py','codex_catalog.py'}
            if overlay.is_symlink() or {path.name for path in overlay.iterdir()}!=expected:raise RuntimeError('candidate_overlay_invalid')
            for name in expected:
                path=overlay/name
                if path.is_symlink() or not path.is_file() or path.stat().st_size>131072 or name not in files:raise RuntimeError('candidate_overlay_invalid')
                files[name]=path
        return files
    folder = ROOT / '.runtime' / ('p84-codex-image-' + uuid4().hex)
    context = folder / 'context'
    context.mkdir(parents=True)
    archive = folder / 'codex-linux.tgz'
    digest = hashlib.sha512()
    size = 0
    if args.cached_archive:
        cache = args.cached_archive
        if (not cache.is_absolute() or cache.is_symlink() or not cache.is_file()
                or cache.name != 'codex-linux.tgz' or cache.parent.parent != ROOT / '.runtime'
                or not cache.parent.name.startswith('p84-codex-image-')):
            raise RuntimeError('p84_cache_scope_denied')
        shutil.copyfile(cache, archive)
        with archive.open('rb') as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b''):
                size += len(chunk)
                if size > 256 * 1024 * 1024:
                    raise RuntimeError('p84_download_limit')
                digest.update(chunk)
    else:
      with build_opener(ProxyHandler({})).open(URL, timeout=60) as response, archive.open('xb') as output:
        # No redirects to a different authority or unbounded archive downloads.
        if response.url != URL:
            raise RuntimeError('p84_download_redirect_denied')
        while chunk := response.read(1024 * 1024):
            size += len(chunk)
            if size > 256 * 1024 * 1024:
                raise RuntimeError('p84_download_limit')
            digest.update(chunk)
            output.write(chunk)
    if digest.digest() != base64.b64decode(INTEGRITY, validate=True):
        raise RuntimeError('p84_download_integrity_failed')
    with tarfile.open(archive, 'r:gz') as package:
        members = package.getmembers()
        for member in members:
            name = PurePosixPath(member.name)
            if name.is_absolute() or '..' in name.parts or member.issym() or member.islnk() or member.isdev():
                raise RuntimeError('p84_archive_path_denied')
        binary = [m for m in members if m.name.endswith('/x86_64-unknown-linux-musl/bin/codex') and m.isfile()]
        metadata = [m for m in members if m.name == 'package/package.json' and m.isfile()]
        readmes = [m for m in members if m.name == 'package/README.md' and m.isfile()]
        if (len(binary) != 1 or len(metadata) != 1 or len(readmes) != 1
                or binary[0].size > 384 * 1024 * 1024):
            raise RuntimeError('p84_archive_contract_invalid')
        # This published platform archive has no standalone LICENSE file. Keep
        # upstream metadata/README intact; do not invent a license certificate.
        with package.extractfile(metadata[0]) as source:
            upstream = json.load(source)
        if (upstream.get('name'), upstream.get('version'), upstream.get('license')) != (
                '@openai/codex', VERSION + '-linux-x64', 'Apache-2.0'):
            raise RuntimeError('p84_package_metadata_invalid')
        for member, name in ((binary[0], 'codex'), (metadata[0], 'package.json'), (readmes[0], 'README.md')):
            with package.extractfile(member) as source, (context / name).open('xb') as output:
                shutil.copyfileobj(source, output)
    shutil.copyfile(ROOT / 'infra/codex-local/Dockerfile', context / 'Dockerfile')
    shutil.copyfile(ROOT / 'scripts/p84_codex_docker_fixture.py', context / 'fixture.py')
    package_dir = context / 'pao_cli_runtime'
    package_dir.mkdir()
    # Copy only this independent transport library, never apps/api or .env.
    for source in runtime_files().values():
        if source.is_symlink():
            raise RuntimeError('p84_source_link_denied')
        shutil.copyfile(source, package_dir / source.name)
    context_runtime = hashlib.sha256()
    for source in sorted(package_dir.glob('*.py')):
        context_runtime.update(source.name.encode('utf-8') + b'\0')
        context_runtime.update(source.read_bytes() + b'\0')
    runtime_sha256 = context_runtime.hexdigest()
    def current_digest():
        value=hashlib.sha256()
        for name,path in sorted(runtime_files().items()):
            value.update(path.name.encode()+b'\0');value.update(path.read_bytes()+b'\0')
        return value.hexdigest()
    if current_digest() != runtime_sha256:
        raise RuntimeError('p84_host_context_runtime_mismatch')
    tag = 'pao-codex-offline:' + folder.name.removeprefix('p84-codex-image-')
    result = subprocess.run(['docker', 'build', '--network=none', '--pull=false', '--tag', tag, str(context)],
                            capture_output=True, timeout=180)
    (folder / 'build.log').write_bytes(result.stdout + result.stderr)
    if result.returncode:
        print(folder)
        raise SystemExit('p84_image_build_failed')
    image = subprocess.check_output(['docker', 'image', 'inspect', tag, '--format', '{{.Id}}'], timeout=15).decode().strip()
    if current_digest() != runtime_sha256:
        raise RuntimeError('p84_host_runtime_changed_during_build')
    receipt = {'stage': 'p84_codex_offline_image', 'version': VERSION, 'source_url': URL,
               'sha512': digest.hexdigest(), 'binary_sha256': hashlib.sha256((context / 'codex').read_bytes()).hexdigest(),
               'base': BASE, 'image': image, 'tag': tag, 'host_mounts': [], 'auth_copied': False,
               'upstream_license_declaration': 'Apache-2.0', 'standalone_license_in_archive': False,
               'provider_inference_verified': False,
               'host_runtime_sha256': runtime_sha256,
               'runtime_candidate':args.runtime_candidate,
               'context_sha256': {p.relative_to(context).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in sorted(context.rglob('*')) if p.is_file()}}
    (folder / 'image.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(folder)
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
