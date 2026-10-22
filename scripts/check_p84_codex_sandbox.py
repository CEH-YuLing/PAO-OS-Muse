"""Synthetic Windows sandbox gate. No auth, model, provider or business data.

Runs the installed native sandbox in explicitly UNELEVATED mode. Never falls
back to elevated, installs an account, edits host requirements or grants access
to a real SME folder. This probe is not the final inference launch acceptance.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/cli-runtime'))
from pao_cli_runtime.containment import Containment
from pao_cli_runtime.transport import child_environment, _directory

CHILD = '''import json,pathlib,socket,sys
allowed,foreign,port=pathlib.Path(sys.argv[1]),pathlib.Path(sys.argv[2]),int(sys.argv[3])
out={"allowed_read":False,"foreign_read_denied":False,"write_denied":False,"network_denied":False}
try: out["allowed_read"]=allowed.read_text()=="synthetic allowed"
except OSError: pass
try: foreign.read_text()
except PermissionError: out["foreign_read_denied"]=True
except OSError: pass
try: (allowed.parent/"unexpected-write.txt").write_text("synthetic only")
except PermissionError: out["write_denied"]=True
except OSError: pass
try:
 s=socket.socket();s.settimeout(1);s.connect(("127.0.0.1",port));s.close()
except PermissionError: out["network_denied"]=True
except OSError as e: out["network_denied"]=getattr(e,"winerror",None)==10013
print(json.dumps(out))
'''


def main():
    if os.name != 'nt' or ROOT != Path('F:/PAO-ACOS'):
        raise SystemExit('p84_windows_local_probe_only')
    parser = argparse.ArgumentParser()
    parser.add_argument('--binary', type=Path, required=True)
    args = parser.parse_args()
    binary = args.binary
    _directory(binary.parent)
    if binary.name != 'codex.exe' or binary.is_symlink() or not binary.is_file():
        raise SystemExit('p84_native_binary_required')
    folder = ROOT / '.runtime' / ('p84-codex-sandbox-' + uuid4().hex)
    folder.mkdir()
    home, allowed, foreign, scratch = (folder / part for part in ('empty-home', 'allowed', 'foreign', 'scratch'))
    for directory in (home, allowed, foreign, scratch):
        directory.mkdir()
    (allowed / 'input.txt').write_text('synthetic allowed', encoding='utf-8')
    (foreign / 'sentinel.txt').write_text('synthetic foreign tenant sentinel', encoding='utf-8')
    fs = {':minimal': 'read', str(allowed): 'read', str(Path(sys.executable).parent): 'read',
          str(Path(sys.base_prefix)): 'read'}
    inline = '{' + ','.join(json.dumps(key) + '="read"' for key in fs) + '}'
    # This binary explicitly rejects --strict-config on the sandbox subcommand.
    # Do not silently reuse exec flags here. The probe's allow/deny assertions
    # remain mandatory and failure never enables inference.
    command = [str(binary), '-c', 'windows.sandbox="unelevated"',
               '-c', 'cli_auth_credentials_store="file"', '-c', 'permissions.pao_probe.filesystem=' + inline,
               '-c', 'permissions.pao_probe.network.enabled=false', 'sandbox', '--permission-profile', 'pao_probe',
               '--cd', str(allowed), sys.executable, '-I', '-B', '-X', 'utf8', '-c', CHILD,
               str(allowed / 'input.txt'), str(foreign / 'sentinel.txt')]
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    listener.listen(1)
    command.append(str(listener.getsockname()[1]))
    state = {'utc': datetime.now(timezone.utc).isoformat(), 'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
             'synthetic_only': True, 'inference_calls': 0, 'elevation_requested': False,
             'host_requirements_modified': False, 'pass': False, 'probe': 'unelevated_named_permission_profile',
             'live_accepted': False, 'launch_race_acceptance': False}
    process = None
    group = None
    try:
        env = child_environment(home)
        env.update(TMP=str(scratch), TEMP=str(scratch))
        process = subprocess.Popen(command, cwd=allowed, env=env,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW)
        group = Containment(process)
        stdout, stderr = process.communicate(timeout=25)
        state['returncode'] = process.returncode
        state['stderr_bytes'] = len(stderr)
        # No unbounded raw diagnostic or synthetic foreign data in the receipt.
        try:
            result = json.loads(stdout.decode('utf-8'))
        except (ValueError, UnicodeError):
            result = None
        state['checks'] = result if isinstance(result, dict) and all(type(v) is bool for v in result.values()) else None
        state['pass'] = process.returncode == 0 and state['checks'] == {
            'allowed_read': True, 'foreign_read_denied': True, 'write_denied': True, 'network_denied': True}
        if stderr:
            # Isolated empty-profile native diagnostics, not account/provider logs.
            with (folder / 'sandbox-diagnostic.txt').open('xb') as output:
                output.write(stderr[:8192])
    except subprocess.TimeoutExpired:
        state['error'] = 'sandbox_probe_timeout'
    finally:
        listener.close()
        if group:
            group.stop()
        elif process and process.poll() is None:
            process.kill()
        if process:
            process.communicate(timeout=3)
        with (folder / 'sandbox-gate.json').open('x', encoding='utf-8') as output:
            json.dump(state, output, indent=2)
    print(folder)
    print(json.dumps(state))
    raise SystemExit(0 if state['pass'] else 2)


if __name__ == '__main__':
    main()
