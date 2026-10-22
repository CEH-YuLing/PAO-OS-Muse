"""One fixed text-only smoke. Init must deny ALL tools before stdin is written.

Not a general chat adapter, shell sandbox, OAuth reader or retry mechanism.
"""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from uuid import UUID

from ...config import ROOT

MODEL = 'gemini-3.8-flash-low'
AGENT = 'pao-text-probe'
ANSWER = 'PAO_ANTIGRAVITY_OK'
PROMPT = 'Reply with exactly PAO_ANTIGRAVITY_OK. Do not use tools, files, browsing or delegation.'
AGENT_SOURCE = Path(__file__).with_name('antigravity_text_agent.md')


class SmokeFailure(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def decode(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result: raise SmokeFailure('protocol_invalid')
            result[key] = value
        return result
    try:
        if not 0 < len(raw) <= 65536: raise ValueError()
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=unique,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if not isinstance(value, dict): raise ValueError()
        return value
    except (ValueError, UnicodeError, RecursionError):
        raise SmokeFailure('protocol_invalid') from None


def init_gate(value):
    init = value.get('init')
    if value.get('event') != 'init' or not isinstance(init, dict):
        raise SmokeFailure('protocol_invalid')
    # Most important: BEFORE sending any prompt, not post-hoc tool detection.
    if init.get('tools') != []: raise SmokeFailure('tools_not_disabled')
    if (init.get('model') != MODEL or init.get('agent') != AGENT
            or init.get('permission_mode') != 'request-review'):
        raise SmokeFailure('configuration_mismatch')
    try:
        sid = value['conversation_id']
        if str(UUID(sid)) != sid: raise ValueError()
        return sid
    except (KeyError, ValueError, TypeError, AttributeError):
        raise SmokeFailure('protocol_invalid') from None


async def native_smoke(cfg, recheck):
    """recheck verifies current PAO authority/config immediately before dispatch."""
    binary = Path(cfg['binary'])
    async def pin():
        if await asyncio.to_thread(lambda: hashlib.sha256(binary.read_bytes()).hexdigest()) != cfg['binary_sha256']:
            raise SmokeFailure('binary_changed')
    await pin()
    parent = ROOT / '.runtime/antigravity-smoke'
    parent.mkdir(exist_ok=True)
    if any(p.is_symlink() or p.is_junction() for p in (parent, *parent.parents)):
        raise SmokeFailure('configuration_mismatch')
    allowed = ('SystemRoot','WINDIR','USERPROFILE','HOMEDRIVE','HOMEPATH','APPDATA',
               'LOCALAPPDATA','TEMP','TMP','PATH','USERNAME','USERDOMAIN')
    env = {key: os.environ[key] for key in allowed if key in os.environ}
    env['NO_COLOR'] = '1'
    with tempfile.TemporaryDirectory(prefix='attempt-', dir=parent) as cwd:
        agent = Path(cwd)/'.agents/agents'/f'{AGENT}.md'
        agent.parent.mkdir(parents=True)
        shutil.copyfile(AGENT_SOURCE, agent)
        (Path(cwd)/'.antigravitycli').mkdir()
        process = None
        stderr_task = None
        try:
            async with asyncio.timeout(35):
                process = await asyncio.create_subprocess_exec(str(binary), '--input-format','stream-json',
                    '--output-format','stream-json','--model',MODEL,'--agent',AGENT,
                    '--disable-slash-commands',cwd=cwd,env=env,stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,limit=65536,
                    creationflags=subprocess.CREATE_NO_WINDOW)
                async def drain():
                    size = 0
                    while chunk := await process.stderr.read(4096):
                        size += len(chunk)
                        if size > 262144: raise SmokeFailure('output_limit')
                stderr_task = asyncio.create_task(drain())
                size = 0
                async def event():
                    nonlocal size
                    raw = await process.stdout.readline()
                    size += len(raw)
                    if size > 262144: raise SmokeFailure('output_limit')
                    return decode(raw)
                sid = init_gate(await event())
                await pin()
                await recheck()
                process.stdin.write((json.dumps({'event':'user','message':{'content':PROMPT}})+'\n').encode())
                await process.stdin.drain()
                process.stdin.close()  # Exactly one turn, no retries/continuation/fallback.
                text = ''
                terminal = None
                for _ in range(2048):
                    value = await event()
                    if value.get('event') == 'result':
                        terminal = value.get('result'); break
                    step = value.get('step_update')
                    if (value.get('event') != 'step_update' or not isinstance(step,dict)
                            or step.get('conversation_id') != sid
                            or step.get('step_type') not in ('user_input','agent_response','checkpoint')
                            or step.get('tool_info') or step.get('tool_name') or step.get('subagent_info')):
                        raise SmokeFailure('unexpected_tool_or_event')
                    delta = step.get('text_delta','')
                    if not isinstance(delta,str) or len(delta)>4096: raise SmokeFailure('protocol_invalid')
                    if step['step_type']=='agent_response': text += delta
                    elif delta: raise SmokeFailure('protocol_invalid')
                if (not isinstance(terminal,dict) or terminal.get('conversation_id') != sid
                        or terminal.get('status') != 'SUCCESS' or terminal.get('error')
                        or type(terminal.get('num_turns')) is not int or terminal['num_turns'] != 1
                        or not isinstance(terminal.get('response'),str)
                        or terminal['response'].strip() != ANSWER or text.strip() not in ('',ANSWER)):
                    raise SmokeFailure('result_not_verified')
                if await process.stdout.read(1): raise SmokeFailure('protocol_invalid')
                if await process.wait() != 0: raise SmokeFailure('process_failed')
                await stderr_task
                await pin()
                await recheck()
                usage = terminal.get('usage')
                usage = {key: usage.get(key) for key in ('input_tokens','output_tokens','total_tokens')} if isinstance(usage,dict) else {}
                if any(type(n) is not int or not 0 <= n <= 10**9 for n in usage.values()):
                    raise SmokeFailure('protocol_invalid')
                return {'status':'passed','response':ANSWER,'model':MODEL,'usage':usage or None,
                        'inference_verified':True,'prompt_sent':True,'tools_enabled':False}
        finally:
            if process and process.returncode is None:
                process.kill(); await asyncio.wait_for(process.wait(),5)
            if stderr_task:
                if not stderr_task.done(): stderr_task.cancel()
                await asyncio.gather(stderr_task,return_exceptions=True)
