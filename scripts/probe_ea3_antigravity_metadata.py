"""Fixed installed agy version/help only; no auth, model query or inference.

Outputs whitelisted metadata, never raw CLI output. An empty home does not
isolate the Windows keyring: this helper must not gain an auth/status command.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
BINARY = Path('C:/Users/o0o_v/AppData/Local/agy/bin/agy.exe')
EXPECTED_SHA = 'e137ee4f362b5b2f2c37141d4d1d1c12298f6b42873ca6867c618a5b945421df'


def main():
    if ROOT != Path('F:/PAO-ACOS'):
        raise RuntimeError('Unexpected checkout')
    for path in (BINARY, *BINARY.parents):
        if path.is_symlink() or path.is_junction():
            raise RuntimeError('Reparse path denied')
    digest = hashlib.sha256(BINARY.read_bytes()).hexdigest()
    if digest != EXPECTED_SHA:
        raise RuntimeError('Binary changed; review required')
    out = ROOT / '.runtime' / ('ea3-antigravity-metadata-' + uuid4().hex)
    out.mkdir()
    receipt = {'binary_sha256': digest, 'commands': {}, 'auth_probed': False,
               'inference_requested': False, 'raw_output_saved': False,
               'keyring_isolation_claimed': False, 'live_accepted': False}
    with tempfile.TemporaryDirectory(prefix='empty-home-', dir=out) as folder:
        env = {'SystemRoot': os.environ['SystemRoot'], 'WINDIR': os.environ['SystemRoot'],
               'HOME': folder, 'USERPROFILE': folder, 'APPDATA': folder,
               'LOCALAPPDATA': folder, 'TMP': folder, 'TEMP': folder,
               'NO_COLOR': '1', 'CI': 'true'}
        for name, arg in (('version', '--version'), ('help', '--help')):
            try:
                run = subprocess.run([str(BINARY), arg], cwd=folder, env=env,
                                     stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, timeout=15,
                                     creationflags=subprocess.CREATE_NO_WINDOW)
                value = {'exit_code': run.returncode, 'stdout_bytes': len(run.stdout),
                         'stderr_bytes': len(run.stderr)}
                if len(run.stdout) + len(run.stderr) > 262144:
                    value['output_rejected'] = True
                else:
                    # agy 1.2.12 emits --help on stderr even when exit=0.
                    body = (run.stdout if name == 'version' else
                            run.stdout + b'\n' + run.stderr).decode('utf-8', errors='strict')
                    if name == 'version':
                        match = re.fullmatch(r'(?:agy |Antigravity CLI )?(\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?)\s*', body)
                        value['version'] = match[1] if match else 'unknown'
                    else:
                        value['flags'] = sorted(set(re.findall(r'(?<![\w-])--[a-z][a-zA-Z-]*', body)))
                receipt['commands'][name] = value
            except subprocess.TimeoutExpired:
                receipt['commands'][name] = {'timed_out': True}
            except UnicodeError:
                receipt['commands'][name] = {'output_rejected': True}
    receipt['binary_unchanged'] = hashlib.sha256(BINARY.read_bytes()).hexdigest() == digest
    with (out / 'receipt.json').open('x', encoding='utf-8') as target:
        json.dump(receipt, target, indent=2)
    print(json.dumps({'receipt': str(out / 'receipt.json'), **receipt}))


if __name__ == '__main__':
    main()
