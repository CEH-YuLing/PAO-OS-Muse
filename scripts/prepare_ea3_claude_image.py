"""Download a version-pinned official platform package; build offline candidate.

Only public npm registry metadata/archive, verified SHA512 integrity. Does not
execute npm lifecycle scripts, modify host Claude/Codex, or enable a provider.
"""
import argparse,base64,hashlib,json,shutil,subprocess,sys,tarfile
from pathlib import Path,PurePosixPath
from urllib.request import build_opener,ProxyHandler
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
VERSION='2.1.220'
NAME='@anthropic-ai/claude-code-linux-x64'
METADATA='https://registry.npmjs.org/@anthropic-ai%2fclaude-code-linux-x64/'+VERSION
BASE='python:3.12-slim-trixie@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1'

def hashfile(path):
    sha=hashlib.sha256()
    with path.open('rb') as file:
        for block in iter(lambda:file.read(1048576),b''):sha.update(block)
    return sha.hexdigest()

def protected():
    paths=[ROOT/name for name in ('.env','.runtime/cli-device.json','.runtime/acos-python-runtime.json','pyproject.toml')]
    paths+=sorted((ROOT/'packages/cli-runtime/pao_cli_runtime').glob('*.py'))
    return {str(p.relative_to(ROOT)):hashfile(p) for p in paths}

def main():
    assert ROOT==Path('F:/PAO-ACOS')
    parser=argparse.ArgumentParser()
    parser.add_argument('--cached-archive',type=Path)
    args=parser.parse_args()
    before=protected()
    folder=ROOT/'.runtime'/('ea3-claude-image-'+uuid4().hex)
    context=folder/'context';context.mkdir(parents=True)
    state={'pass':False,'version':VERSION,'provider_calls':0,'auth_copied':False,'serving_registry_changed':False}
    try:
        opener=build_opener(ProxyHandler({}))
        if args.cached_archive:
            cached=args.cached_archive
            assert cached.is_absolute() and cached.name=='claude-linux.tgz' and cached.parent.parent==ROOT/'.runtime'
            assert cached.parent.name.startswith('ea3-claude-image-')
            assert not any(p.is_symlink() or getattr(p,'is_junction',lambda:False)() for p in (cached,*cached.parents))
            raw=(cached.parent/'public-package-metadata.json').read_bytes();assert len(raw)<=262144
        else:
            with opener.open(METADATA,timeout=30) as response:
                assert response.url==METADATA
                raw=response.read(262145);assert len(raw)<=262144
        meta=json.loads(raw)
        assert (meta['name'],meta['version'])==(NAME,VERSION)
        dist=meta['dist'];url=dist['tarball']
        assert url=='https://registry.npmjs.org/@anthropic-ai/claude-code-linux-x64/-/claude-code-linux-x64-'+VERSION+'.tgz'
        assert dist['integrity'].startswith('sha512-')
        expected=base64.b64decode(dist['integrity'][7:],validate=True);assert len(expected)==64
        with (folder/'public-package-metadata.json').open('xb') as out:out.write(raw)
        archive=folder/'claude-linux.tgz';sha=hashlib.sha512();size=0
        print('Verifying cached package' if args.cached_archive else 'Downloading official pinned Claude Linux package',flush=True)
        source=cached.open('rb') if args.cached_archive else opener.open(url,timeout=45)
        with source as response,archive.open('xb') as out:
            if not args.cached_archive:assert response.url==url
            while block:=response.read(1048576):
                size+=len(block);assert size<=256*1024*1024
                sha.update(block);out.write(block)
        assert sha.digest()==expected
        print('Archive SHA512 verified; extracting explicit allowlist',flush=True)
        with tarfile.open(archive,'r:gz') as package:
            members=package.getmembers();assert len(members)<100
            for member in members:
                name=PurePosixPath(member.name)
                assert not name.is_absolute() and '..' not in name.parts
                assert member.isfile() or member.isdir()
            for source,target,cap in (('package/claude','claude',384*1024*1024),
                                      ('package/package.json','package.json',262144),
                                      ('package/README.md','README.md',1048576),
                                      ('package/LICENSE.md','LICENSE.md',1048576)):
                selected=[m for m in members if m.name==source and m.isfile()]
                assert len(selected)==1 and 0<selected[0].size<=cap
                with package.extractfile(selected[0]) as inp,(context/target).open('xb') as out:shutil.copyfileobj(inp,out)
        package_meta=json.loads((context/'package.json').read_text())
        assert (package_meta['name'],package_meta['version'])==(NAME,VERSION)
        for src,dst in (('infra/claude-local/Dockerfile','Dockerfile'),('scripts/ea3_claude_fixture.py','fixture.py'),
                        ('infra/claude-local/managed-settings.json','managed-settings.json')):
            shutil.copyfile(ROOT/src,context/dst)
        binary=hashfile(context/'claude')
        tag='pao-claude-candidate:'+folder.name.removeprefix('ea3-claude-image-')
        print('Building isolated candidate image without network',flush=True)
        with (folder/'build.log').open('xb') as log:
            subprocess.run(['docker','build','--network=none','--pull=false','--build-arg','CLAUDE_SHA256='+binary,
                            '--tag',tag,str(context)],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
        image=subprocess.check_output(['docker','image','inspect',tag,'--format','{{.Id}}'],timeout=15).decode().strip()
        assert image.startswith('sha256:') and len(image)==71
        assert protected()==before
        state.update({'pass':True,'image':image,'tag':tag,'binary_sha256':binary,'base':BASE,
                      'source_url':url,'npm_integrity':dist['integrity'],'download_bytes':size,
                      'package_license':package_meta.get('license'),'provenance_certified':False,
                      'protected_files_unchanged':True,
                      'context':{p.name:hashfile(p) for p in sorted(context.iterdir())}})
    finally:
        state.update(protected_before=before,protected_after=protected())
        with (folder/'image.json').open('x',encoding='utf-8') as out:json.dump(state,out,indent=2)
        print(json.dumps({'folder':str(folder),**{k:v for k,v in state.items() if not k.startswith('protected_') and k!='context'}}),flush=True)

if __name__=='__main__':main()
