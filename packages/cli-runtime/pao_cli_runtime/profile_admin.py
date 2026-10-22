"""Container-local profile initialization/status. No token extraction or inference."""
import json
import os
from pathlib import Path
import subprocess
import sys
from .codex_probe import CodexBinary
from .codex_protocol import REQUIRED_FLAGS
from .codex_worker import BINARY_SHA256, VERSION


def main():
    if sys.argv[1:] == ['initialize']:
        # Only the named volume mount itself, never recursive chown or host paths.
        if os.getuid() != 0 or Path('/profile').is_symlink():
            raise RuntimeError()
        info = Path('/profile').stat()
        if info.st_uid == 0:
            os.chmod('/profile', 0o700)
        elif info.st_uid != 65534 or info.st_mode & 0o777 != 0o700:
            raise RuntimeError()
        os.chown('/profile', 65534, 65534)
        print(json.dumps({'initialized': True}))
        return
    if sys.argv[1:] != ['status'] or os.getuid() != 65534:
        raise RuntimeError()
    binary = CodexBinary('/usr/local/bin/codex', BINARY_SHA256, VERSION, REQUIRED_FLAGS)
    binary.check()
    result = subprocess.run([binary.path, 'login', 'status'], capture_output=True, timeout=10,
        env={'HOME':'/profile','CODEX_HOME':'/profile/codex','TMPDIR':'/tmp',
             'PATH':'/usr/local/bin:/usr/bin:/bin'}, cwd='/tmp')
    output = result.stdout + result.stderr
    mode = 'chatgpt' if result.returncode == 0 and b'Logged in using ChatGPT' in output else 'not_authenticated'
    print(json.dumps({'auth_mode': mode, 'binary_sha256': BINARY_SHA256, 'binary_version': VERSION,
                      'provider_inference_verified': False}))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print(json.dumps({'error':'cli_profile_operation_failed'}))
        raise SystemExit(2)
