"""Container entrypoint. One text request, fixed command/config, own CLI auth only."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4
from .codex_probe import CodexBinary
from .codex_protocol import REQUIRED_FLAGS, json_object, prepare
from .codex_catalog import text_catalog
from .contracts import CliFailure, CliProvider, CliRequest, CliScope

BINARY_SHA256 = '3e2584f3f3829a43a0495011a1cecb2facbe64a2403e2b682351fd9c2983f970'
VERSION = '0.157.1'


def main():
    raw = sys.stdin.buffer.read(65537)
    if len(raw) > 65536:
        raise CliFailure('cli_input_limit')
    data = json_object(raw)
    if not {'model','prompt'}<=set(data) or set(data)-{'model','prompt','reasoning_effort'}:
        raise CliFailure('cli_contract_invalid')
    profile, work = Path('/profile/codex'), Path('/tmp/job')
    profile.mkdir(mode=0o700, exist_ok=True)
    work.mkdir(mode=0o700)
    env = {'HOME': '/profile', 'CODEX_HOME': str(profile), 'TMPDIR': '/tmp', 'LC_ALL': 'C.UTF-8',
           'PATH': '/usr/local/bin:/usr/bin:/bin'}
    pin = CodexBinary('/usr/local/bin/codex', BINARY_SHA256, VERSION, REQUIRED_FLAGS)
    pin.check()
    # Codex reads its own cache; never transfer it to PAO or permit cached API
    # key mode to become an unrequested paid fallback.
    status = subprocess.run([pin.path, 'login', 'status'], env=env, cwd=work,
        capture_output=True, timeout=10)
    if status.returncode or b'Logged in using ChatGPT' not in status.stdout + status.stderr:
        raise CliFailure('cli_access_denied')
    request = CliRequest(CliProvider.CODEX, CliScope(*(str(uuid4()) for _ in range(5))),
                         str(uuid4()), data['prompt'], data['model'],reasoning_effort=data.get('reasoning_effort'))
    draft = prepare(request, pin, work)
    catalog = work / 'models.json'
    catalog.write_text(json.dumps(text_catalog(request.model,request.reasoning_effort)), encoding='utf-8')
    command = list(draft.argv)
    command[1:1] = ['-c', 'model_catalog_json=' + json.dumps(str(catalog))]
    if request.reasoning_effort is not None:
        command[1:1]=['-c','model_reasoning_effort='+json.dumps(request.reasoning_effort)]
    # Reopen stdin with the bounded prompt only. No shell, argv payload, image,
    # host path, resume id, API key or configuration accepted from the caller.
    import tempfile
    with tempfile.TemporaryFile() as incoming:
        incoming.write(draft.stdin)
        incoming.seek(0)
        os.dup2(incoming.fileno(), 0)
    os.execve(pin.path, command, env)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # No auth/provider body or prompt in diagnostics; parser rejects this.
        print(json.dumps({'type': 'error', 'message': 'cli_worker_denied'}), flush=True)
        raise SystemExit(2)
