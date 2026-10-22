"""One durable read claim; effective authority comes from DB, never headers."""
import asyncio
from datetime import timedelta
from fastapi import HTTPException
from sqlalchemy import select,func
from ...auth import Principal
from ...config import settings
from ...db import Session
from ...models import ToolCall,Run,ChatSession,User,Member,StudioEvent,ConnectorConnection,now
from ...skills import execution_binding,require_execution_binding
from ..tools.audit import audit
from ..studio.contracts import digest
from ..studio.execution import check_pin
from ..engines.contract import EngineFailure
from . import service
from .transport import ConnectorFailure
from ..connections import read_authority,read_resources

async def lock_connection_read(db,workspace,cid):
    # Native rotate/disconnect/permission updates take connection FOR UPDATE.
    # SHARE keeps check -> token resolve atomic without holding it over network.
    await db.scalar(select(ConnectorConnection.id).where(ConnectorConnection.id==cid,
        ConnectorConnection.workspace_id==workspace).with_for_update(read=True))

async def guard(db,run,user_id,tool_id,pin=None,grant_id=None):
    service.enabled()
    if not settings().tools_enabled:raise HTTPException(403,'tool_permission_denied')
    if not run:raise HTTPException(404,'connector_run_not_found')
    chat=await db.get(ChatSession,run.session_id);user=await db.get(User,user_id)
    member=await db.get(Member,(run.workspace_id,user_id))
    selected=(pin or {}).get('connection_authority')
    if selected is not None:
        if not isinstance(selected,dict) or not isinstance(selected.get('grant_id'),str):
            raise HTTPException(403,read_authority.DENIED)
        grant_id=selected['grant_id']
    roles=('owner','admin','operator','analyst') if grant_id else ('owner','admin')
    if not chat or chat.workspace_id!=run.workspace_id or chat.user_id!=user_id or not user or not user.active or not member or member.role not in roles:
        raise HTTPException(403,'connector_permission_denied')
    if run.cancel_requested or run.status in ('failed','cancelled'):
        raise HTTPException(409,'connector_parent_stopped')
    from ..brains.context import check_run_brain
    brain=await check_run_brain(db,run,chat)
    brand=(run.brain_context or {}).get('brand_id') if run.brain_id else chat.brand_id
    if brain and (brain.workspace_id!=run.workspace_id or brain.brand_id!=brand):
        raise HTTPException(403,'connector_brain_scope_denied')
    if not run.studio_snapshot:raise HTTPException(403,'connector_published_skill_required')
    try:studio=await check_pin(db,run)
    except EngineFailure:raise HTTPException(403,'connector_studio_pin_invalid') from None
    if tool_id not in studio['skill']['payload']['allowed_tools']:
        raise HTTPException(403,'connector_skill_tool_denied')
    import re
    match=re.fullmatch(r'mcp\.([0-9a-f]{32})\.([a-zA-Z][a-zA-Z0-9_-]{0,19})',tool_id)
    if not match:raise HTTPException(422,'connector_tool_invalid')
    from uuid import UUID
    cid=str(UUID(match[1]));authority=None
    if grant_id:
        authority=await read_authority.pin(db,run.workspace_id,user_id,brand,grant_id)
        if authority['source_id']!=cid:raise HTTPException(403,read_authority.DENIED)
        row=await db.scalar(select(ConnectorConnection).where(ConnectorConnection.id==cid,
            ConnectorConnection.workspace_id==run.workspace_id).execution_options(populate_existing=True))
        if not row:raise HTTPException(403,read_authority.DENIED)
    else:
        await read_authority.unregistered(db,run.workspace_id,cid)
        row=await service.owned(db,cid,Principal(user_id,0))
    if row.workspace_id!=run.workspace_id or row.status!='connected':raise HTTPException(403,'connector_scope_denied')
    if row.brain_id and row.brain_id!=run.brain_id:raise HTTPException(403,'connector_brain_scope_denied')
    if row.circuit_until and row.circuit_until>now():raise HTTPException(409,'connector_circuit_open')
    grant=row.permissions.get(tool_id)
    if not grant:raise HTTPException(403,'connector_connection_tool_denied')
    tool=service.approved_tool(row,tool_id,grant['hash'])
    proof={'id':row.id,'kind':'connector','hash':row.manifest_hash,'version':row.version,'tool_id':tool_id,'schema_hash':tool['hash']}
    reviews=list(await db.scalars(select(StudioEvent).where(StudioEvent.version_id==studio['skill']['id'],StudioEvent.action=='review')))
    if not any(proof in event.data.get('links',[]) for event in reviews):raise HTTPException(403,'connector_review_scope_changed')
    value={'version':'p5-call-v1','connection_id':row.id,'connection_version':row.version,'manifest_hash':row.manifest_hash,
        'name':match[2],'hash':tool['hash'],'arguments':grant['arguments'],'skill_version_id':studio['skill']['id'],
        'skill_hash':studio['skill']['hash'],'binding':execution_binding()}
    if authority is not None:value['connection_authority']=authority
    value={**value,'sha256':digest(value)}
    if pin:
        try:require_execution_binding(pin.get('binding'))
        except ValueError:raise HTTPException(409,'connector_adapter_version_changed') from None
        if pin!=value:raise HTTPException(409,'connector_pin_changed')
    return row,value

async def propose(cid,run_id,who,tool_id,request_key,grant_id=None):
    async with Session.begin() as db:
        scope=await db.get(Run,run_id)
        if scope:await read_resources.lock(db,scope.workspace_id)
        run=await db.scalar(select(Run).where(Run.id==run_id).with_for_update())
        if run:await lock_connection_read(db,run.workspace_id,cid)
        row,pin=await guard(db,run,who.id,tool_id,grant_id=grant_id)
        if row.id!=cid:raise HTTPException(404,'connector_tool_not_found')
        fingerprint=digest({'tool':tool_id,'pin':pin})
        old=await db.scalar(select(ToolCall).where(ToolCall.run_id==run.id,ToolCall.request_key==request_key))
        if old:
            if old.fingerprint!=fingerprint:raise HTTPException(409,'connector_request_key_conflict')
            return old
        if await db.scalar(select(func.count()).select_from(ToolCall).where(ToolCall.run_id==run.id))>=4:
            raise HTTPException(409,'connector_run_call_limit')
        await read_resources.admit(db,run.workspace_id)
        call=ToolCall(workspace_id=run.workspace_id,run_id=run.id,user_id=who.id,request_key=request_key,
            fingerprint=fingerprint,name=tool_id,agent_key='chief_of_staff',arguments=pin['arguments'],
            connector_snapshot=pin,result={},status='queued',version=1)
        db.add(call);await db.flush()
        audit(db,run,who.id,'connector.proposed',call,tool=tool_id,hash=pin['hash'])
        return call

async def execute(ctx,call_id):
    async with Session.begin() as db:
        scope=await db.get(ToolCall,call_id)
        if scope:
            await read_resources.lock(db,scope.workspace_id)
            if scope.connector_snapshot:
                await lock_connection_read(db,scope.workspace_id,scope.connector_snapshot['connection_id'])
        call=await db.scalar(select(ToolCall).where(ToolCall.id==call_id).with_for_update())
        if not call or call.status!='queued':return
        run=await db.get(Run,call.run_id)
        try:
            if not run or call.workspace_id!=run.workspace_id:raise HTTPException(403,read_authority.DENIED)
            row,pin=await guard(db,run,call.user_id,call.name,call.connector_snapshot)
            if not await read_resources.available(db,run.workspace_id):
                call.error_code='tenant_read_concurrency_wait';return
            credential=await service.token(db,row)
        except Exception:
            call.status='cancelled';call.error_code='connector_permission_changed';call.version+=1;call.updated_at=now()
            audit(db,run,call.user_id,'connector.denied',call)
            return
        call.status='running';call.error_code=None;call.version+=1;call.updated_at=now();claim=call.version
        endpoint=row.endpoint;user=call.user_id;rid=run.id;name=call.name;workspace=run.workspace_id
        audit(db,run,user,'connector.started',call,hash=pin['hash'])
    task=asyncio.create_task(service.Client(endpoint,credential).exchange(pin));result={};error=None;interrupted=False
    try:
        async with asyncio.timeout(32):
            while not task.done():
                await asyncio.wait({task},timeout=.2)
                async with Session() as db:
                    current=await db.get(ToolCall,call_id)
                    if current.status!='running' or current.version!=claim:raise ConnectorFailure('connector_revoked')
                    await guard(db,await db.get(Run,rid),user,name,pin)
            result=await task
            service.clean(result,credential) # Replacement adapter still cannot persist credentials.
    except ConnectorFailure as exc:error=str(exc)
    except HTTPException:error='connector_permission_changed'
    except TimeoutError:error='connector_timeout'
    except asyncio.CancelledError:
        interrupted=True;error='connector_interrupted'
    except Exception:error='connector_provider_unavailable'
    finally:
        if not task.done():task.cancel()
        await asyncio.gather(task,return_exceptions=True)
    async with Session.begin() as db:
        await read_authority.lock_scope(db,workspace)
        # Match mutation lock order (connection -> call), including circuit updates.
        await db.scalar(select(ConnectorConnection).where(ConnectorConnection.id==pin['connection_id']).with_for_update())
        call=await db.scalar(select(ToolCall).where(ToolCall.id==call_id).with_for_update())
        if call.status=='running' and call.version==claim:
            run=await db.get(Run,rid)
            row=None
            try:row,_=await guard(db,run,user,name,pin)
            except Exception:error='connector_permission_changed'
            if row and not interrupted:
                if error:
                    row.failures+=1
                    if row.failures>=3:row.circuit_until=now()+timedelta(seconds=60)
                else:row.failures=0;row.circuit_until=None
            call.status='unknown' if interrupted else 'failed' if error else 'completed'
            call.error_code=error;call.result={} if error else result;call.updated_at=now();call.version+=1
            audit(db,run,user,'connector.'+call.status,call,reason=error,result_hash=digest(result) if not error else None)
    if interrupted:raise asyncio.CancelledError
