"""Source archive manifest utilities; credentials/runtime/dependencies excluded."""
import hashlib
from pathlib import Path
import zipfile

ROOT_DIRS = {'apps','packages','scripts','docs','infra','evals','.github'}
ROOT_FILES = {'AGENTS.md','README.md','LICENSE','CREDITS.md','CLEANUP_REPORT.md','SANITIZATION_MANIFEST.md',
              '.env.example','.gitignore','.dockerignore','package.json','package-lock.json',
              'pyproject.toml','alembic.ini','requirements.lock','requirements-dev.lock'}
SUFFIXES = {'.py','.ts','.tsx','.js','.mjs','.cjs','.css','.json','.md','.yaml','.yml',
            '.ps1','.toml','.ini','.txt','.lock'}
BLOCKED = {'.git','.runtime','.venv','node_modules','__pycache__','.pytest_cache',
           '.next','out','build','uploads','exports','reports'}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def entries(root):
    root = Path(root).resolve()
    found = {}
    for base in ROOT_DIRS:
        directory = root / base
        if not directory.exists():
            continue
        # Do not follow symlinks/junctions into dependencies or outside root.
        import os
        for current, dirs, files in os.walk(directory, followlinks=False):
            dirs[:] = [d for d in dirs if d not in BLOCKED and not d.startswith('.pao-')
                       and not (Path(current)/d).is_symlink()
                       and not (getattr(Path(current)/d,'is_junction',lambda:False)())]
            for name in files:
                p = Path(current)/name
                if name.startswith('.env') or p.suffix not in SUFFIXES or p.is_symlink():
                    continue
                if not p.resolve().is_relative_to(root):
                    raise ValueError('Source path outside root')
                found[p.relative_to(root).as_posix()] = digest(p)
    for name in ROOT_FILES:
        p = root/name
        if p.is_file() and not p.is_symlink():
            found[name] = digest(p)
    return dict(sorted(found.items()))


def archive(root, target):
    root = Path(root).resolve()
    target = Path(target)
    if target.exists():
        raise FileExistsError('Refusing to overwrite source archive')
    manifest = entries(root)
    with zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED) as out:
        for name in manifest:
            out.write(root/name, name)
    verify(target, manifest)
    if entries(root) != manifest:
        raise RuntimeError('Source changed during checkpoint')
    return manifest


def verify(target, manifest):
    with zipfile.ZipFile(target) as source:
        if sorted(source.namelist()) != sorted(manifest):
            raise ValueError('Archive entry mismatch')
        for name, expected in manifest.items():
            path = Path(name)
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('Unsafe archive path')
            if hashlib.sha256(source.read(name)).hexdigest() != expected:
                raise ValueError('Archive hash mismatch')
