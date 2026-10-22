"""Pinned Muse Code text adapter; no API keys, implicit fallback or raw tracing logs.

Muse1.4.10 JSONL lacks token events. Its documented transport trace is consumed
in memory only for actual response.completed usage, never printed/persisted.
Unknown/missing counters remain unknown. This codec is version/SHA-specific.
"""
import asyncio
import json
from pathlib import Path
from uuid import uuid4
from ...db import Session
from ...gateway import Chunk
from ...models import ChatSession,Run,LlmAttempt
from ..engines.contract import EngineFailure
from ..chat.ledger import CURRENT_ATTEMPT
from . import muse_client as client,muse_profile as profile
from .muse_process import Child

MAX_WIRE=8*1024*1024
LIMIT=16*1024*1024
VERSION='muse-exec-text-v1'


def run_environment(folder):
    env=profile.environment()
    # Only this approved login configuration is shared. No previous run data,
    # personal memory, workspace or skill home is reused between SMEs/attempts.
    for key,relative in [('HOME','home'),('USERPROFILE','home'),('APPDATA','appdata'),
            ('LOCALAPPDATA','localappdata'),('XDG_DATA_HOME','data'),('MUSE_HOME','data/muse'),('TEMP','tmp'),('TMP','tmp')]:
        target=client.safe_path(folder/relative);target.mkdir(parents=True,exist_ok=True);env[key]=str(target)
    config=client.safe_path(profile.PROFILE/'.config/muse/settings.json')
    if config.exists():
        if config.stat().st_size>65536:raise EngineFailure('muse_profile_configuration_changed')
        data=json.loads(config.read_bytes())
        # No config rewriting or stripping managed controls. Refuse changed
        # policy and have the operator review the dedicated profile instead.
        if not isinstance(data,dict) or any(k not in ('model','provider','reasoning_effort','contributor_mode_enabled','tui','permissions') for k in data):
            raise EngineFailure('muse_profile_configuration_changed')
    for relative in ('AGENTS.md','CLAUDE.md','.agents','.claude','skills','plugins','mcp.json'):
        if (profile.PROFILE/'.config/muse'/relative).exists():raise EngineFailure('muse_profile_configuration_changed')
    env['MUSE_TRANSPORT_TRACE']='1'
    return env


def parse(stdout,stderr,model,effort):
    from pao_cli_runtime.codex_protocol import json_object
    final=None;configured=0;run=None
    for raw in stdout.splitlines():
        row=json_object(raw);payload=row.get('payload')
        if row.get('schema_version')!=1 or not isinstance(payload,dict):raise EngineFailure('muse_protocol_invalid')
        kind=row.get('payload_type','')
        if kind=='run.model.configured':
            configured+=1
            if payload.get('model_id')!=model or payload.get('provider_id')!='meta':raise EngineFailure('muse_model_mismatch')
        if kind=='session.run.linked':run=payload.get('run_stream')
        if kind.startswith('task.lifecycle'):
            event=payload.get('event') or {}
            task=event.get('task_kind','')
            if task and not task.startswith('model.'):raise EngineFailure('muse_unexpected_tool')
        if kind.startswith('run.terminal.'):
            if final is not None or payload.get('terminal')!='completed':raise EngineFailure('muse_native_failed')
            final=payload
    if configured!=1 or not run or not final or final.get('run_stream')!=run or not isinstance(final.get('text'),str):
        raise EngineFailure('muse_protocol_invalid')
    requests=0;usage={};completions=0
    for raw in stderr.decode(errors='replace').splitlines():
        start=raw.find('{')
        if start<0:continue
        try:value=json_object(raw[start:])
        except Exception:continue  # Malformed/non-JSON diagnostic lines are never reflected.
        if 'model' in value and 'instructions' in value and 'input' in value:
            requests+=1
            if value.get('model')!=model or value.get('tools') or (value.get('reasoning') or {}).get('effort')!=effort:
                raise EngineFailure('muse_request_mismatch')
        if value.get('type')=='response.completed':
            response=value.get('response') or {}
            if response.get('model')!=model:raise EngineFailure('muse_model_mismatch')
            completions+=1
            reported=response.get('usage') or {}
            for key in ('input_tokens','output_tokens'):
                n=reported.get(key)
                if type(n) is int and 0<=n<=1_000_000:usage[key]=n
    if requests!=1 or completions!=1:raise EngineFailure('muse_unexpected_request_count')
    return final['text'],usage


async def execute(messages,model,effort,authorize,*,lifecycle=None):
    if not isinstance(messages,list) or not messages or any(
            not isinstance(m,dict) or set(m)!={'role','content'} or m['role'] not in ('system','user','assistant')
            or not isinstance(m['content'],str) for m in messages):raise EngineFailure('muse_input_invalid')
    prompt=json.dumps({'messages':messages},ensure_ascii=False,separators=(',',':'))
    if len(prompt.encode())>MAX_WIRE:raise EngineFailure('muse_input_limit')
    native=await client.discover()
    if native['account_state']!='accountLogin':raise EngineFailure('engine_provider_authentication')
    from ..installation_ai.catalog import selection
    selection(native['models'],model,effort)
    default=next(v['default_effort'] for v in native['models'] if v['model']==model)
    effort=effort or default
    folder=client.safe_path(profile.PROFILE/'runs'/uuid4().hex);folder.mkdir(parents=True)
    work=folder/'workspace';work.mkdir();input_file=folder/'prompt.txt'
    child=None;out=err=None
    try:
        env=run_environment(folder)
        input_file.write_text(prompt,encoding='utf-8')
        command=[str(await asyncio.to_thread(client.binary)),'exec','--provider','meta','--preset','empty','--json',
            '--no-session-log','--disable-shell','--disable-write','--disable-web-tools','--disable-reminders',
            '--disable-request-user-input','--no-foreign-personal-context','--approval-mode','untrusted',
            '--approval-judge','off','--max-model-steps','1','--model',model,'--reasoning-effort',effort,
            '--prompt-file',str(input_file)]
        await authorize()
        child=Child(command,cwd=work,env=env)  # Suspended, already attached to Job.
        await authorize()  # Recheck exact attempt/source before first instruction.
        child.resume()
        if lifecycle is not None:lifecycle['resumed']=True
        def bounded(stream):
            parts=[];total=0
            while part:=stream.read(8192):
                total+=len(part)
                if total>LIMIT:raise EngineFailure('muse_output_limit')
                parts.append(part)
            return b''.join(parts)
        out=asyncio.create_task(asyncio.to_thread(bounded,child.process.stdout))
        err=asyncio.create_task(asyncio.to_thread(bounded,child.process.stderr))
        async with asyncio.timeout(120):
            stdout,stderr=await asyncio.gather(out,err)
            code=await asyncio.to_thread(child.process.wait,5)
        if code:raise EngineFailure('muse_native_failed')
        result=parse(stdout,stderr,model,effort)
        await authorize()
        return result
    except TimeoutError:raise EngineFailure('engine_timeout') from None
    finally:
        try:
            if child:
                await asyncio.shield(asyncio.to_thread(child.close))
                if lifecycle is not None:lifecycle['cleanup_verified']=child.cleanup_verified
        finally:
            if out or err:await asyncio.gather(*(t for t in (out,err) if t),return_exceptions=True)
            if input_file.exists():input_file.unlink()  # Only this generated temporary input.


class MuseGateway:
    provider_name='muse'
    def __init__(self,run_id,snapshot):
        self.run_id=run_id;self.snapshot=dict(snapshot);self.model_name=snapshot['model'];self.last_usage={}

    async def authorize(self,attempt,claim=False):
        from sqlalchemy import select
        from ..connections.model_fence import check_run
        from ..connections.resources import lock
        async with Session.begin() as db:
            wid=await db.scalar(select(Run.workspace_id).where(Run.id==self.run_id))
            await lock(db,wid)
            run=await db.scalar(select(Run).where(Run.id==self.run_id).with_for_update())
            row=await db.scalar(select(LlmAttempt).where(LlmAttempt.id==attempt).with_for_update())
            if not run or not row or row.run_id!=run.id or row.provider!='muse' or row.model!=self.model_name or row.status!='started' or run.status!='running' or run.cancel_requested:
                raise EngineFailure('engine_run_not_active')
            if run.engine_snapshot!=self.snapshot:raise EngineFailure('installation_ai_selection_changed')
            await check_run(db,run)
            if claim:
                if (row.trace or {}).get('muse_dispatch'):raise EngineFailure('engine_attempt_replay_denied')
                row.trace={**(row.trace or {}),'muse_dispatch':{'version':VERSION,'status':'dispatched'}}

    async def invoke(self,messages):
        attempt=CURRENT_ATTEMPT.get()
        if attempt is None:raise EngineFailure('tenant_resource_accounting_required')
        await self.authorize(attempt,claim=True)
        async def authorize():await self.authorize(attempt)
        lifecycle={'resumed':False,'cleanup_verified':False};status='failed'
        try:
            value=await execute(messages,self.model_name,self.snapshot.get('reasoning_effort'),authorize,lifecycle=lifecycle)
            status='native_completed';return value
        except asyncio.CancelledError:status='cancelled';raise
        finally:
            async def finish():
                from sqlalchemy import select
                from ...models import now
                async with Session.begin() as db:
                    row=await db.scalar(select(LlmAttempt).where(LlmAttempt.id==attempt).with_for_update())
                    if row:
                        row.trace={**(row.trace or {}),'muse_dispatch':{'version':VERSION,
                            'status':status if lifecycle['cleanup_verified'] or not lifecycle['resumed'] else 'unknown',
                            **lifecycle,'finished_at':now().isoformat()}}
            await asyncio.shield(finish())

    async def stream(self,messages,max_tokens=None):
        text,self.last_usage=await self.invoke(messages)
        yield Chunk(text=text,usage=self.last_usage)

    async def plan(self,messages):
        # Share the existing structured planner codec, not a second orchestrator.
        from .gateway import CliGateway
        class Planner(CliGateway):
            async def invoke(inner,wire):
                from types import SimpleNamespace
                text,usage=await self.invoke(wire);self.last_usage=usage
                return SimpleNamespace(text=text)
        return await Planner(self.run_id,self.snapshot).plan(messages)
