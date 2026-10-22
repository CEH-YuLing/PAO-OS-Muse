"""Human-requested direct local Codex smoke, not a serving PAO adapter.

Uses the installed binary's official login cache in place; never reads/copies
auth files or emits raw login diagnostics. Sends only the fixed synthetic prompt
below, no business content. No retry, API-key fallback, resume, or shell bypass.
"""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/cli-runtime'))
from pao_cli_runtime.codex_protocol import CodexExecParser
from pao_cli_runtime.contracts import CliFailure, Limits

BINARY = Path('C:/Users/o0o_v/AppData/Roaming/npm/node_modules/@openai/codex/node_modules/'
              '@openai/codex-win32-x64/vendor/x86_64-pc-windows-msvc/bin/codex.exe')
PIN = '8cb0e69e99ff2a158c54815db82d0f2e524d8f301bc30184722cfd1ae5973574'
PROMPT = 'Connectivity test only. Do not use any tools or inspect any files. Reply with exactly: PAO_CODEX_OK'


def main():
    if ROOT != Path('F:/PAO-ACOS') or hashlib.sha256(BINARY.read_bytes()).hexdigest() != PIN:
        raise SystemExit('p84_installed_binary_pin_mismatch')
    folder = ROOT / '.runtime' / ('p84-codex-direct-' + uuid4().hex)
    folder.mkdir()
    work, scratch = folder / 'empty-work', folder / 'scratch'
    work.mkdir()
    scratch.mkdir()
    # Only OS/auth-location variables, not API keys, proxy, project config or
    # provider secrets. Codex itself owns access to its existing login cache.
    env = {key: os.environ[key] for key in ('SystemRoot', 'SYSTEMROOT', 'USERPROFILE',
            'APPDATA', 'LOCALAPPDATA', 'HOME', 'CODEX_HOME') if key in os.environ}
    env.update(TMP=str(scratch), TEMP=str(scratch))
    state = {'utc': datetime.now(timezone.utc).isoformat(), 'stage': 'direct_operator_smoke_not_PAO_dispatch',
             'binary_sha256': PIN, 'version': '0.157.1', 'pass': False, 'inference_attempts': 0,
             'auth_cache_copied': False, 'raw_auth_output_stored': False, 'business_content_sent': False,
             'PAO_connected': False, 'production_accepted': False, 'timeout_seconds': 60,
             'sandbox_mode': 'read-only', 'tool_configuration': 'disabled', 'api_key_env_forwarded': False}
    try:
        status = subprocess.run([str(BINARY), 'login', 'status'], capture_output=True,
            env=env, cwd=work, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
        # Classification only; never print a potentially identifying status body.
        auth = status.stdout + status.stderr
        state['auth_mode'] = 'chatgpt' if status.returncode == 0 and b'Logged in using ChatGPT' in auth else 'not_verified_chatgpt'
        if state['auth_mode'] != 'chatgpt':
            raise CliFailure('cli_access_denied')
        command = [str(BINARY), '--strict-config', '--sandbox', 'read-only', '--ask-for-approval', 'never']
        for config in ('model_provider="openai"', 'features.shell_tool=false', 'features.apps=false',
                       'web_search="disabled"', 'project_doc_max_bytes=0', 'allow_login_shell=false'):
            command += ['-c', config]
        command += ['exec', '--ignore-user-config', '--ignore-rules', '--ephemeral', '--json',
                    '--skip-git-repo-check', '--color', 'never', '--cd', str(work), '-']
        state['inference_attempts'] = 1
        result = subprocess.run(command, input=PROMPT.encode(), capture_output=True, env=env, cwd=work,
                                timeout=60, creationflags=subprocess.CREATE_NO_WINDOW)
        state.update(returncode=result.returncode, stderr_bytes=len(result.stderr), stdout_bytes=len(result.stdout))
        parser = CodexExecParser(Limits(timeout_seconds=60))
        parser.feed(result.stdout)
        answer = parser.finish(result.returncode)
        # Store the expected synthetic result only, not arbitrary provider text.
        state['expected_response_matched'] = answer.text.strip() == 'PAO_CODEX_OK'
        state.update(input_tokens=answer.input_tokens, output_tokens=answer.output_tokens)
        state['pass'] = state['expected_response_matched']
        if state['pass']:
            state['response'] = 'PAO_CODEX_OK'
    except subprocess.TimeoutExpired:
        state['failure_code'] = 'cli_timeout'
    except CliFailure as failure:
        state['failure_code'] = failure.code
    finally:
        with (folder / 'direct-smoke.json').open('x', encoding='utf-8') as output:
            json.dump(state, output, indent=2)
    print(folder)
    print(json.dumps(state))
    raise SystemExit(0 if state['pass'] else 2)


if __name__ == '__main__':
    main()
