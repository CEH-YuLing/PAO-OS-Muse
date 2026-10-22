"""Compare project discovery without sending any prompt or reading credentials."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
BINARY = Path('C:/Users/o0o_v/AppData/Local/agy/bin/agy.exe')
SHA = 'b9ebbc8ae00dec96263979d2947124136cdae990811e27eafef1e7f021269192'


async def probe(folder, layout):
    allowed = ('SystemRoot', 'WINDIR', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH',
               'APPDATA', 'LOCALAPPDATA', 'TEMP', 'TMP', 'PATH', 'USERNAME', 'USERDOMAIN')
    env = {key: os.environ[key] for key in allowed if key in os.environ}
    env['NO_COLOR'] = '1'
    result = {'layout': layout, 'prompt_sent': False, 'inference_verified': False}
    process = None
    task = None
    with tempfile.TemporaryDirectory(prefix='cwd-', dir=folder) as temporary:
        cwd = Path(temporary)
        if layout == 'git-root':
            completed = subprocess.run(['git', 'init', '--quiet', str(cwd)],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
            if completed.returncode:
                raise RuntimeError('isolated_git_init_failed')
        if layout == 'project-marker':
            (cwd / '.antigravitycli').mkdir()
        agents = cwd / '.agents' / 'agents'
        agents.mkdir(parents=True)
        (agents / 'pao-text-probe.md').write_bytes((ROOT / 'apps/api/pao/modules/'
            'cli_connections/antigravity_text_agent.md').read_bytes())
        try:
            async with asyncio.timeout(20):
                assert hashlib.sha256(BINARY.read_bytes()).hexdigest() == SHA
                process = await asyncio.create_subprocess_exec(str(BINARY),
                    '--input-format', 'stream-json', '--output-format', 'stream-json',
                    '--model', 'gemini-3.8-flash-low', '--agent', 'pao-text-probe',
                    '--disable-slash-commands', cwd=cwd, env=env,
                    stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE, limit=65536,
                    creationflags=subprocess.CREATE_NO_WINDOW)

                async def drain():
                    size = 0
                    while chunk := await process.stderr.read(4096):
                        size += len(chunk)
                        if size > 262144:
                            raise ValueError('stderr_bound')
                    return size

                task = asyncio.create_task(drain())
                raw = await process.stdout.readline()
                if raw:
                    value = json.loads(raw)
                    init = value.get('init', {})
                    tools = init.get('tools')
                    result.update(init_observed=value.get('event') == 'init',
                        tool_count=len(tools) if isinstance(tools, list) else None,
                        zero_tools=tools == [], agent_matches=init.get('agent') == 'pao-text-probe',
                        model_matches=init.get('model') == 'gemini-3.8-flash-low',
                        permission_request_review=init.get('permission_mode') == 'request-review')
                else:
                    result['exit_code'] = await process.wait()
                    result['stderr_bytes'] = await task
        except TimeoutError:
            result['timed_out'] = True
        except (ValueError, UnicodeError):
            result['protocol_rejected'] = True
        finally:
            if process and process.returncode is None:
                process.kill()
                await asyncio.wait_for(process.wait(), 5)
            if task:
                if not task.done():
                    task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            result['process_stopped'] = process is not None and process.returncode is not None
            result['binary_unchanged'] = hashlib.sha256(BINARY.read_bytes()).hexdigest() == SHA
    return result


async def main():
    assert ROOT == Path('F:/PAO-ACOS')
    assert not any(p.is_symlink() or p.is_junction() for p in (BINARY, *BINARY.parents))
    runtime = ROOT / '.runtime'
    assert not any(p.is_symlink() or p.is_junction() for p in (runtime, *runtime.parents))
    assert hashlib.sha256(BINARY.read_bytes()).hexdigest() == SHA
    folder = runtime / ('antigravity-agent-discovery-' + uuid4().hex)
    folder.mkdir()
    result = {'binary_sha256': SHA, 'prompt_sent': False, 'probes': []}
    try:
        for layout in ('bare-directory', 'project-marker', 'git-root'):
            observed = await probe(folder, layout)
            result['probes'].append(observed)
            print(json.dumps(observed), flush=True)
    finally:
        with (folder / 'receipt.json').open('x', encoding='utf-8') as target:
            json.dump(result, target, indent=2)
        print(json.dumps({'receipt': str(folder / 'receipt.json')}))


if __name__ == '__main__':
    asyncio.run(main())
