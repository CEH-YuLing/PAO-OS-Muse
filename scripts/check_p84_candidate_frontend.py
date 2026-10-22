"""Check additive CLI contract against unchanged UI in a complete disposable copy."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'apps/api'), str(ROOT / 'scripts')]
from pao.modules.operations.checkpoint import entries
from backup_acos_checkpoint import frontend_supplements


def main():
    candidate = ROOT / '.runtime/p84-native-candidate-20261018'
    assert ROOT == Path('F:/PAO-ACOS') and candidate.is_dir()
    before = entries(candidate)
    primary_frontend = {k: v for k, v in entries(ROOT).items() if k.startswith('apps/web/')}
    supplements = frontend_supplements(ROOT)
    # The initial C checkpoint used the base source allowlist, not its existing
    # JSX/d.mts supplement. Retain that archive, explicitly hash the originals
    # here, and never silently treat an incomplete archive as a frontend build.
    assert not any(name in before and before[name] != sha for name, sha in supplements.items())
    folder = ROOT / '.runtime' / ('p84-frontend-' + uuid4().hex)
    source = folder / 'source'
    source.mkdir(parents=True)
    for name, sha in {**before, **supplements}.items():
        origin = candidate / name if name in before else ROOT / name
        target = source / name
        assert target.resolve().is_relative_to(source) and not target.exists()
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origin, target)
    env = {**os.environ, 'NEXT_TELEMETRY_DISABLED': '1', 'PAO_BUILD_CHECK': '1',
           'PAO_API_URL': 'http://127.0.0.1:8100'}
    # The copy is inside this checkout's .runtime and resolves its existing,
    # locked node_modules by normal parent resolution. No npm install/link.
    node = shutil.which('node')
    assert node
    modules = ROOT / 'node_modules'
    commands = {
        'contracts': [str(modules / 'openapi-typescript/bin/cli.js'),
                      'packages/contracts/openapi.json', '-o', 'packages/contracts/schema.d.ts'],
        'node': ['--test', *[str(p.relative_to(source)) for p in sorted((source / 'apps/web/lib').glob('*.test.mjs'))]],
        'typegen': [str(modules / 'next/dist/bin/next'), 'typegen', 'apps/web'],
        'typecheck': [str(modules / 'typescript/bin/tsc'), '--noEmit', '-p', 'apps/web/tsconfig.json'],
        'build': [str(modules / 'next/dist/bin/next'), 'build', 'apps/web'],
    }
    result = {'pass': False, 'stages': [], 'provider_calls': 0, 'primary_frontend_changed': False,
              'candidate_source_changed': False, 'frontend_supplements': supplements,
              'production_accepted': False}
    try:
        for name, command in commands.items():
            print(name, flush=True)
            with (folder / (name + '.log')).open('xb') as output:
                subprocess.run([node, *command], cwd=source, env=env, stdout=output,
                    stderr=subprocess.STDOUT, timeout=900, check=True,
                    **({'creationflags': 0x08000000 | 0x00004000} if os.name == 'nt' else {}))
            result['stages'].append(name)
        result['candidate_source_changed'] = entries(candidate) != before
        result['primary_frontend_changed'] = (frontend_supplements(ROOT) != supplements or
            {k: v for k, v in entries(ROOT).items() if k.startswith('apps/web/')} != primary_frontend)
        result['pass'] = not result['candidate_source_changed'] and not result['primary_frontend_changed']
    finally:
        (folder / 'receipt.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(folder)
        print(json.dumps({k: v for k, v in result.items() if k != 'frontend_supplements'}))
    raise SystemExit(0 if result['pass'] else 1)


if __name__ == '__main__':
    main()
