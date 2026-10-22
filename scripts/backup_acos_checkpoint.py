"""Create a private, non-overwriting DB+source+file manifest ACOS checkpoint."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
from uuid import uuid4
from zipfile import ZipFile, ZIP_DEFLATED
from pao.config import ROOT, settings
from pao.modules.operations.checkpoint import archive, digest, verify, entries, BLOCKED
from pao.skills import execution_binding

def _supplements(root, relative, suffixes):
    """Bounded source only; never dependencies, builds or linked trees."""
    root=Path(root).resolve();directory=root/relative;found={}
    if directory.is_symlink() or getattr(directory,'is_junction',lambda:False)():
        raise ValueError('Source directory must not be linked')
    for current,dirs,names in os.walk(directory,followlinks=False):
        dirs[:]=[name for name in dirs if name not in BLOCKED and not name.startswith('.pao-')
            and not (Path(current)/name).is_symlink()
            and not getattr(Path(current)/name,'is_junction',lambda:False)()]
        for name in names:
            if name.startswith('.env') or not name.endswith(suffixes):continue
            path=Path(current)/name
            if path.is_symlink() or not path.is_file():continue
            if not path.resolve().is_relative_to(root):raise ValueError('Frontend source outside root')
            found[path.relative_to(root).as_posix()]=digest(path)
    return dict(sorted(found.items()))


def frontend_supplements(root):
    return _supplements(root, 'apps/web', ('.d.mts','.jsx'))


def source_supplements(root):
    found={**frontend_supplements(root),**_supplements(root, 'infra', ('.Dockerfile','.sh'))}
    # Exact reviewed source files only, not arbitrary SQL dumps/config/secret files.
    for name in ('infra/production/roles.sql','infra/production/grants.sql',
                 'infra/production/Caddyfile','infra/production/Caddyfile.public.example',
                 'infra/codex-local/Dockerfile'):
        path=Path(root)/name
        if not path.exists():continue
        if any(p.is_symlink() or getattr(p,'is_junction',lambda:False)() for p in (path,*path.parents) if p!=Path(root).parent) or not path.resolve().is_relative_to(Path(root).resolve()):raise ValueError('Linked deployment source forbidden')
        found[name]=digest(path)
    return dict(sorted(found.items()))


def source_archive(root, target):
    """Supplement frontend/infra source without changing backend binding."""
    root=Path(root).resolve()
    production=root/'infra/production'
    reviewed={'roles.sql','grants.sql','Caddyfile','Caddyfile.public.example','runtime.example.json',
              'entrypoint.py','api.Dockerfile','web.Dockerfile','proxy.Dockerfile','compose.private.yaml'}
    if production.exists():
        if production.is_symlink() or getattr(production,'is_junction',lambda:False)():raise ValueError('Linked deployment source forbidden')
        for path in production.iterdir():
            if path.name in BLOCKED:continue
            if path.name not in reviewed or not path.is_file() or path.is_symlink():
                raise ValueError('Review unrecognized production source before archiving; keep real secrets outside source')
    files=archive(root,target)
    initial=dict(files)
    supplements=source_supplements(root)
    extra={name:value for name,value in supplements.items() if name not in files}
    if extra:
        with ZipFile(target,'a',compression=ZIP_DEFLATED) as out:
            for name in extra:out.write(root/name,name)
        files.update(extra)
    files=dict(sorted(files.items()))
    verify(target,files)
    if entries(root)!=initial or source_supplements(root)!=supplements:
        raise RuntimeError('Source changed during frontend backup')
    return files

def main():
    if ROOT.resolve() != Path('F:/PAO-ACOS') or not settings().database_url.endswith('/pao_acos_local'):
        raise SystemExit('ACOS-local backup only')
    run=subprocess.run([sys.executable,str(ROOT/'scripts/check_m2_restore.py')],
                       cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
    if run.returncode:
        raise SystemExit('Database backup/restore failed; inspect the retained local backup')
    db=json.loads(run.stdout.splitlines()[-1])
    checkpoint=ROOT/'.runtime'/'checkpoints'/(
        datetime.now(timezone.utc).strftime('p0-%Y%m%dT%H%M%S')+'-'+uuid4().hex[:8])
    checkpoint.mkdir(parents=True,exist_ok=False)
    source=checkpoint/'source.zip'
    files=source_archive(ROOT,source)
    db_path=Path(db['backup']).resolve()
    if not db_path.is_relative_to((ROOT/'.runtime').resolve()):
        raise SystemExit('Unexpected backup path')
    manifest={'version':'p0-checkpoint-v1','created_at':datetime.now(timezone.utc).isoformat(),
              'binding':execution_binding(),'database':{**db,'sha256':digest(db_path)},
              'source':{'path':str(source),'sha256':digest(source),'files':files},
              'credentials':'excluded; preserve encryption/JWT keys in a separate private recovery procedure'}
    target=checkpoint/'manifest.json'
    target.write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    loaded=json.loads(target.read_text(encoding='utf-8'))
    verify(source,loaded['source']['files'])
    assert digest(source)==loaded['source']['sha256']
    assert digest(db_path)==loaded['database']['sha256']
    print(json.dumps({'manifest':str(target),'source_files':len(files),'tables':db['table_count'],
                      'artifacts':db['artifact_count'],'revision':db['revision_before'],'verified':True}))
if __name__=='__main__':
    main()
