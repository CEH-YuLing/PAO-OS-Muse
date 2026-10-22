"""Durable tool boundary: permissions, frozen input, approval, audit and single claim."""
import asyncio
import hashlib
import json
from datetime import timedelta
from urllib.parse import urlsplit
import httpx
from fastapi import HTTPException
from sqlalchemy import select, func, text
from .config import settings
from .db import Session
from .models import ToolCall, ToolAudit, Run, ChatSession, User, Member, now
from .tool_registry import TOOLS, ToolRequest, validate_request
from .auth import Principal
from .business_tools import read_kpi, read_tasks, read_intelligence, read_creative, read_attribution
from .skills import execution_binding, require_execution_binding, require_snapshot_execution


from .modules.tools.audit import audit
from .modules.events.producer import requested as record_approval_requested
from .modules.events.guards import execution_hash, tool_fingerprint
from .modules.events.approvals import require_snapshot


async def guard(db, run, user_id, name, call_id=None):
    if not run:
        raise HTTPException(404,'Không tìm thấy run')
    if (run.channel_context or {}).get('kind')=='customer':
        raise HTTPException(403,'customer_tools_denied')
    chat=await db.get(ChatSession,run.session_id)
    user=await db.get(User,user_id)
    member=await db.get(Member,(run.workspace_id,user_id))
    if chat.user_id != user_id or not member:
        raise HTTPException(404,'Không tìm thấy run')
    if not settings().tools_enabled or not user.active or member.role=='viewer':
        raise HTTPException(403,'tool_permission_denied')
    if TOOLS[name]['approval'] and member.role not in ('owner','admin','operator'):
        raise HTTPException(403,'tool_write_permission_denied')
    if run.status in ('failed','cancelled') or run.cancel_requested:
        raise HTTPException(409,'parent_run_stopped')
    if name.startswith('business.'):
        plan = run.execution_plan or {}
        try:
            if plan.get('skill_route') or plan.get('skill_snapshot'):
                require_snapshot_execution(plan.get('skill_snapshot'))
            if call_id is not None:
                require_execution_binding(plan.get('business_tool_bindings', {}).get(call_id))
        except ValueError:
            raise HTTPException(409, 'skill_version_incompatible') from None


async def propose(run_id, user_id, request_key, request):
    request=ToolRequest.model_validate(request)
    async with Session() as db:
        run=await db.scalar(select(Run).where(Run.id==run_id).with_for_update())
        try:
            await guard(db,run,user_id,request.name)
            try:
                request=validate_request(request)
            except PermissionError:
                raise HTTPException(403,'agent_tool_denied')
            except ValueError:
                raise HTTPException(422,'tool_arguments_invalid')
        except HTTPException as error:
            if run and error.status_code != 404:
                audit(db,run,user_id,'permission.denied',tool=request.name,reason=error.detail)
                await db.commit()
            raise
        payload=request.model_dump(mode='json')
        fingerprint=hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        existing=await db.scalar(select(ToolCall).where(ToolCall.run_id==run_id,ToolCall.request_key==request_key))
        if existing:
            if existing.fingerprint != fingerprint:
                raise HTTPException(409,'Khóa yêu cầu đã dùng với nội dung khác')
            return existing
        count=await db.scalar(select(func.count()).select_from(ToolCall).where(ToolCall.run_id==run_id))
        if count >= 4:
            raise HTTPException(409,'Mỗi run tối đa 4 tool calls')
        call=ToolCall(workspace_id=run.workspace_id,run_id=run_id,user_id=user_id,request_key=request_key,
            fingerprint=fingerprint,name=request.name,agent_key=request.agent,arguments=request.arguments,
            status='pending' if TOOLS[request.name]['approval'] else 'queued')
        db.add(call);await db.flush()
        if call.name.startswith('business.'):
            plan = run.execution_plan or {}
            run.execution_plan = {**plan, 'business_tool_bindings': {
                **plan.get('business_tool_bindings', {}), call.id: execution_binding()}}
        audit(db,run,user_id,'tool.proposed',call,tool=call.name,requires_approval=TOOLS[call.name]['approval'])
        if call.status == 'pending':
            await record_approval_requested(db,call,Principal(user_id,0),'tool')
        await db.commit()
        return call


async def decide(call_id, user_id, decision, version, expected_hash=None):
    async with Session.begin() as db:
        call=await db.scalar(select(ToolCall).where(ToolCall.id==call_id).with_for_update())
        if not call or call.user_id != user_id:
            raise HTTPException(404,'Không tìm thấy tool call')
        run=await db.get(Run,call.run_id)
        await guard(db,run,user_id,call.name)
        await require_snapshot(db,'tool',call,expected_hash)
        if tool_fingerprint(call) != call.fingerprint:
            raise HTTPException(409,'approval_input_changed')
        if decision=='approve' and call.approved_by==user_id:
            return call
        if decision=='reject' and call.status=='rejected':
            return call
        if call.status!='pending' or call.version!=version:
            raise HTTPException(409,'Trạng thái đã thay đổi; tải lại trước khi duyệt')
        if call.created_at < now()-timedelta(hours=24):
            raise HTTPException(409,'Approval đã hết hạn')
        call.status='queued' if decision=='approve' else 'rejected'
        call.approved_by=user_id if decision=='approve' else None
        call.approval_input_hash=execution_hash('tool',call) if decision=='approve' else None
        call.version+=1;call.updated_at=now()
        audit(db,run,user_id,'approval.'+decision,call,version=version)
        return call


async def invoke(name, arguments, call_id):
    if name=='email.mock_send':
        return {'simulated':True,'delivered':False,'message_id':call_id,'summary':'Mô phỏng email; không gửi email thật.'}
    if name=='calendar.mock_create':
        return {'simulated':True,'external_event_created':False,'event_id':call_id,'summary':'Mô phỏng lịch; không tạo sự kiện bên ngoài.'}
    async with httpx.AsyncClient(timeout=15,trust_env=False,follow_redirects=False) as client:
        async with client.stream('GET',settings().searxng_url.rstrip('/')+'/search',params={
            'q':arguments['query'],'format':'json','categories':'general'}) as response:
            response.raise_for_status()
            raw=bytearray()
            async for chunk in response.aiter_bytes():
                raw.extend(chunk)
                if len(raw)>1_000_000:
                    raise ValueError('search_response_too_large')
        payload=json.loads(raw)
    results=[]
    for row in payload.get('results',[])[:20]:
        url=row.get('url','')
        parsed=urlsplit(url)
        if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or len(url)>1200:
            continue
        results.append({'title':str(row.get('title',''))[:160],'url':url,'snippet':str(row.get('content',''))[:400]})
        if len(results)==5:
            break
    return {'simulated':False,'results':results,'unresponsive_engines':len(payload.get('unresponsive_engines',[]))}


async def invoke_business(name, arguments, call_id):
    # Context comes exclusively from the durable call and owned parent run,
    # never model arguments. Recheck permission inside the read transaction.
    async with Session.begin() as db:
        await db.execute(text('SET TRANSACTION READ ONLY'))
        await db.execute(text("SET LOCAL statement_timeout = '8000'"))
        call = await db.get(ToolCall, call_id)
        run = await db.get(Run, call.run_id)
        await guard(db, run, call.user_id, name, call_id)
        validate_request({'name': name, 'agent': call.agent_key, 'arguments': arguments})
        handler = {'business.attribution.read': read_attribution, 'business.kpi.read': read_kpi, 'business.tasks.read': read_tasks,
                   'business.ads.intelligence.read': read_intelligence, 'business.creative.read': read_creative}[name]
        return await handler(db, Principal(call.user_id, 0), call.workspace_id, arguments)


async def execute_tool(ctx, call_id):
    async with Session() as connector_db:
        connector_call=await connector_db.get(ToolCall,call_id)
        is_connector=bool(connector_call and connector_call.name.startswith('mcp.'))
    if is_connector:
        from .modules.connectors.gateway import execute
        return await execute(ctx,call_id)
    async with Session.begin() as db:
        call=await db.scalar(select(ToolCall).where(ToolCall.id==call_id).with_for_update())
        if not call or call.status!='queued':
            return
        run=await db.get(Run,call.run_id)
        try:
            await guard(db,run,call.user_id,call.name,call.id)
            validate_request({'name':call.name,'agent':call.agent_key,'arguments':call.arguments})
            if TOOLS[call.name]['approval'] and call.approved_by!=call.user_id:
                raise HTTPException(403,'approval_required')
            if TOOLS[call.name]['approval'] and call.created_at < now()-timedelta(hours=24):
                raise HTTPException(409,'approval_expired')
            if tool_fingerprint(call)!=call.fingerprint or (call.approval_input_hash and call.approval_input_hash!=execution_hash('tool',call)):
                raise HTTPException(409,'approval_input_changed')
        except (HTTPException,ValueError,PermissionError) as denied:
            reason = 'skill_version_incompatible' if isinstance(denied, HTTPException) and denied.detail == 'skill_version_incompatible' else 'permission_or_parent_changed'
            call.status,call.error_code,call.updated_at='cancelled',reason,now()
            call.version+=1
            audit(db,run,call.user_id,'tool.cancelled',call,reason=call.error_code)
            return
        call.status='running';call.version+=1;call.updated_at=now()
        claimed_version=call.version
        name,arguments,user_id,run_id=call.name,call.arguments,call.user_id,call.run_id
        audit(db,run,user_id,'tool.started',call)
    error=None;result={};cancelled=False
    try:
        async with asyncio.timeout(20):
            if name.startswith('business.'):
                result = await invoke_business(name, arguments, call_id)
            else:
                result=await (ctx.get('tool_invoke') or invoke)(name,arguments,call_id)
    except asyncio.CancelledError:
        error='execution_interrupted';cancelled=True
    except Exception:
        error='tool_provider_unavailable'
    async with Session.begin() as db:
        call=await db.scalar(select(ToolCall).where(ToolCall.id==call_id).with_for_update())
        if call.status!='running' or call.version!=claimed_version:
            return
        run=await db.get(Run,run_id)
        try:
            await guard(db,run,user_id,name,call_id)
        except HTTPException as denied:
            error='skill_version_incompatible' if denied.detail == 'skill_version_incompatible' else 'permission_or_parent_changed';result={}
        call.status='unknown' if cancelled else 'failed' if error else 'completed'
        call.error_code=error;call.result=result if not error else {};call.version+=1;call.updated_at=now()
        audit(db,run,user_id,'tool.'+call.status,call,reason=error)
    if cancelled:
        raise asyncio.CancelledError


async def dispatch_tools(ctx):
    async with Session.begin() as db:
        stopped=list(await db.scalars(select(ToolCall).join(Run,Run.id==ToolCall.run_id).where(
            ToolCall.status.in_(('pending','queued')),
            (Run.status.in_(('failed','cancelled'))) | (Run.cancel_requested.is_(True)))
            .with_for_update(of=ToolCall,skip_locked=True).limit(100)))
        for call in stopped:
            call.status='cancelled';call.error_code='parent_run_stopped'
            call.version+=1;call.updated_at=now()
            run=await db.get(Run,call.run_id)
            audit(db,run,call.user_id,'tool.cancelled',call,reason=call.error_code)
        stale=list(await db.scalars(select(ToolCall).where(
            ((ToolCall.status=='running') & (ToolCall.updated_at < now()-timedelta(seconds=90))) |
            ((ToolCall.status=='pending') & (ToolCall.created_at < now()-timedelta(hours=24))))
            .with_for_update(skip_locked=True).limit(100)))
        for call in stale:
            call.status='unknown' if call.status=='running' else 'expired'
            call.error_code='worker_lost' if call.status=='unknown' else 'approval_expired'
            call.version+=1;call.updated_at=now()
            run=await db.get(Run,call.run_id)
            audit(db,run,call.user_id,'tool.'+call.status,call,reason=call.error_code)
        from .modules.connections import read_resources
        queued=await read_resources.fair_queued(db,ToolCall,limit=50)
    for call_id in queued:
        await ctx['redis'].enqueue_job('execute_tool',call_id,_job_id=f'tool:{call_id}',_expires=3600)
