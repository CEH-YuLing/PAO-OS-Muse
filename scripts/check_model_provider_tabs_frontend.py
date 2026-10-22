"""Build current UI in a disposable source-only copy; never mutate serving output."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'apps/api'), str(ROOT / 'scripts')]
from pao.modules.operations.checkpoint import entries, digest
from backup_acos_checkpoint import frontend_supplements


def main():
    assert ROOT == Path('F:/PAO-ACOS')
    origin = ROOT / '.runtime/codex-login-candidate-20261019' if '--codex-login-candidate' in sys.argv else ROOT
    files = {**entries(origin), **frontend_supplements(origin)}
    folder = ROOT / '.runtime' / ('model-provider-tabs-frontend-' + uuid4().hex)
    source = folder / 'source'
    source.mkdir(parents=True)
    for name, sha in files.items():
        incoming, target = origin / name, source / name
        assert target.resolve().is_relative_to(source) and not target.exists()
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(incoming, target)
        assert digest(target) == sha
    env = {**os.environ, 'NEXT_TELEMETRY_DISABLED': '1', 'PAO_BUILD_CHECK': '1',
           'PAO_API_URL': 'http://127.0.0.1:8100'}
    modules = ROOT / 'node_modules'
    commands = {
        **({'contracts':[str(modules/'openapi-typescript/bin/cli.js'),'packages/contracts/openapi.json','-o','packages/contracts/schema.d.ts']} if origin!=ROOT else {}),
        'node': ['--test', *[str(p.relative_to(source)) for p in sorted((source / 'apps/web/lib').glob('*.test.mjs'))]],
        'typegen': [str(modules / 'next/dist/bin/next'), 'typegen', 'apps/web'],
        'typecheck': [str(modules / 'typescript/bin/tsc'), '--noEmit', '-p', 'apps/web/tsconfig.json'],
        'build': [str(modules / 'next/dist/bin/next'), 'build', 'apps/web'],
    }
    result = {'pass': False, 'source': str(source), 'stages': [], 'provider_calls': 0,
              'database_tests': False, 'production_accepted': False}
    print(folder, flush=True)
    try:
        for name, command in commands.items():
            print(name, flush=True)
            with (folder / (name + '.log')).open('xb') as output:
                subprocess.run([shutil.which('node'), *command], cwd=source, env=env,
                    stdout=output, stderr=subprocess.STDOUT, timeout=900, check=True,
                    **({'creationflags': 0x08000000 | 0x00004000} if os.name == 'nt' else {}))
            result['stages'].append(name)
        current = {**entries(origin), **frontend_supplements(origin)}
        result['frontend_unchanged_during_build'] = {k:v for k,v in files.items() if k.startswith('apps/web/')} == {k:v for k,v in current.items() if k.startswith('apps/web/')}
        result['pass'] = result['frontend_unchanged_during_build']
    finally:
        (folder / 'receipt.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps(result), flush=True)
    raise SystemExit(0 if result['pass'] else 1)


if __name__ == '__main__':
    main()
