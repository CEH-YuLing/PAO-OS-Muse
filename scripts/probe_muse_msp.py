"""Metadata-only Muse discovery. No session, prompt, login or credential reads.

The official binary owns its credentials. Experimental opt-in is limited to
account projection/schema metadata in this owned child; it changes no settings.
"""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
BINARY = Path(os.environ['LOCALAPPDATA']) / 'Programs/muse/muse-bin-1.4.10-R6427.1.exe'
SHA = '893a04138b81d844cc53e25216fafe0cbf7c786423534b93aacf1419a840f6b7'


async def main():
    assert ROOT == Path('F:/PAO-ACOS') and hashlib.sha256(BINARY.read_bytes()).hexdigest() == SHA
    assert not any(p.is_symlink() or p.is_junction() for p in (BINARY, *BINARY.parents))
    folder = ROOT / '.runtime' / ('muse-discovery-' + uuid4().hex)
    folder.mkdir()
    cwd = folder / 'empty-workspace'
    cwd.mkdir()
    env = {k: os.environ[k] for k in ('SystemRoot','WINDIR','USERPROFILE','HOMEDRIVE','HOMEPATH',
        'APPDATA','LOCALAPPDATA','TEMP','TMP','PATH','USERNAME','USERDOMAIN') if k in os.environ}
    state = {'pass': False, 'prompt_sent': False, 'session_started': False,
             'inference_verified': False, 'binary_sha256': SHA}
    process = None
    try:
        async with asyncio.timeout(25):
            process = await asyncio.create_subprocess_exec(str(BINARY), 'serve',
                '--provider','meta','--no-session-log','--disable-write','--disable-shell',
                '--disable-request-user-input', cwd=cwd, env=env, stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                limit=1048576, creationflags=subprocess.CREATE_NO_WINDOW)
            async def drain():
                size = 0
                while data := await process.stderr.read(4096):
                    size += len(data)
                    if size > 262144: raise ValueError('stderr_limit')
            drain_task = asyncio.create_task(drain())
            async def send(value):
                process.stdin.write(json.dumps(value,separators=(',',':')).encode() + b'\n')
                await process.stdin.drain()
            async def query(i, method):
                params = {'clientInfo':{'name':'pao_metadata_probe','version':'0.1.0'},
                          'capabilities':{'experimentalApi':True,'userInputDialogs':False}} if i == 1 else {}
                await send({'jsonrpc':'2.0','id':i,'method':method,'params':params})
                for _ in range(32):
                    raw = await process.stdout.readline()
                    if not raw: raise ValueError('host_eof')
                    value = json.loads(raw)
                    if value.get('id') == i:
                        if 'error' in value: return {'error_code':value['error'].get('code')}
                        return value.get('result',{})
                raise ValueError('frame_limit')
            initialized = await query(1,'initialize')
            state['server_info'] = initialized.get('serverInfo')
            state['schema'] = initialized.get('schema')
            await send({'jsonrpc':'2.0','method':'initialized','params':{}})
            account = await query(2,'account/read')
            state['account'] = {k:v for k,v in account.items() if k in ('state','credentialRequired','error_code')}
            catalog = await query(3,'model/list')
            state['catalog_source'] = catalog.get('source')
            state['models'] = [{k:v for k,v in row.items() if k in
                ('modelId','displayLabel','defaultReasoningEffort','variants','reasoningEffortVariants')}
                for row in catalog.get('models',[])]
            schema = await query(4,'settings/readSchema')
            # Schema contains configuration definitions, not effective secrets.
            with (folder/'settings-schema.json').open('x',encoding='utf-8') as out:
                json.dump(schema,out,ensure_ascii=False,indent=2)
            state['settings_schema_fields'] = list(schema)
            state['pass'] = bool(state.get('server_info') and state['models'])
    except (TimeoutError,OSError,ValueError,UnicodeError) as exc:
        state['error_type'] = type(exc).__name__
    finally:
        if process and process.returncode is None:
            process.kill()
            await asyncio.wait_for(process.wait(),5)
        state['own_child_stopped'] = process is not None and process.returncode is not None
        if 'drain_task' in locals():
            drain_task.cancel()
            await asyncio.gather(drain_task,return_exceptions=True)
        state['binary_unchanged'] = hashlib.sha256(BINARY.read_bytes()).hexdigest() == SHA
        with (folder/'receipt.json').open('x',encoding='utf-8') as out:
            json.dump(state,out,ensure_ascii=False,indent=2)
        print(json.dumps({'folder':str(folder),**state},ensure_ascii=False))


if __name__ == '__main__':
    asyncio.run(main())
