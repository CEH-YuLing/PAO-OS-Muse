"""No-prompt native init compatibility gate. Never sends a user turn."""
import asyncio, hashlib, json, os, subprocess
from pathlib import Path
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
BINARY=Path('C:/Users/o0o_v/AppData/Local/agy/bin/agy.exe')
SHA='b9ebbc8ae00dec96263979d2947124136cdae990811e27eafef1e7f021269192'

async def main():
    assert ROOT==Path('F:/PAO-ACOS')
    assert not any(p.is_symlink() or p.is_junction() for p in (BINARY,*BINARY.parents))
    assert hashlib.sha256(BINARY.read_bytes()).hexdigest()==SHA
    cwd=ROOT/'.runtime/antigravity-smoke-cwd'
    assert not any(p.is_symlink() or p.is_junction() for p in (cwd,*cwd.parents))
    folder=ROOT/'.runtime'/('antigravity-text-gate-'+uuid4().hex);folder.mkdir()
    result={'binary_sha256':SHA,'prompt_sent':False,'tools_executed_by_probe':False,
            'inference_verified':False,'os_isolation_verified':False,'init_observed':False}
    allowed=('SystemRoot','WINDIR','USERPROFILE','HOMEDRIVE','HOMEPATH','APPDATA',
             'LOCALAPPDATA','TEMP','TMP','PATH','USERNAME','USERDOMAIN')
    env={k:os.environ[k] for k in allowed if k in os.environ};env['NO_COLOR']='1'
    process=None
    try:
        async with asyncio.timeout(20):
            process=await asyncio.create_subprocess_exec(str(BINARY),'--input-format','stream-json',
                '--output-format','stream-json','--model','gemini-3.8-flash-low',
                '--agent','pao-text-probe','--disable-slash-commands',cwd=cwd,env=env,
                stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,limit=65536,creationflags=subprocess.CREATE_NO_WINDOW)
            async def drain():
                size=0
                while chunk:=await process.stderr.read(4096):
                    size+=len(chunk)
                    if size>262144:raise ValueError('stderr_bound')
                return size
            stderr_task=asyncio.create_task(drain())
            raw=await process.stdout.readline()
            if raw:
                value=json.loads(raw)
                if isinstance(value,dict) and value.get('event')=='init':
                    init=value.get('init',{})
                    tools=init.get('tools')
                    result.update(init_observed=True,zero_tools=tools==[],
                        tool_count=len(tools) if isinstance(tools,list) else None,
                        known_tools=[v for v in tools if v in ('ask_permission','run_command','write_to_file','view_file','read_file','write_file','invoke_subagent')] if isinstance(tools,list) else [],
                        selected_agent_matches=init.get('agent')=='pao-text-probe',
                        model_matches=init.get('model')=='gemini-3.8-flash-low',
                        permission_request_review=init.get('permission_mode')=='request-review')
                else:result['unexpected_event']=True
            else:
                result['exit_code']=await process.wait()
                result['stderr_bytes']=await stderr_task
    except TimeoutError:result['timed_out_before_prompt']=True
    except (ValueError,UnicodeError):result['protocol_rejected']=True
    finally:
        if process and process.returncode is None:
            process.kill();await asyncio.wait_for(process.wait(),5)
        if process:result['process_stopped']=process.returncode is not None
        result['binary_unchanged']=hashlib.sha256(BINARY.read_bytes()).hexdigest()==SHA
        with (folder/'receipt.json').open('x',encoding='utf-8') as out:json.dump(result,out,indent=2)
        print(json.dumps({'folder':str(folder),**result}))

if __name__=='__main__':asyncio.run(main())
