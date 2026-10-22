"""Owner-scoped connection state, encrypted references and explicit grants."""
from fastapi import HTTPException
import asyncio
import hashlib
from sqlalchemy import select
from ...config import settings
from ...models import ConnectorConnection,ConnectorSecret,ConnectorEvent,ToolCall,now
from ...access import membership
from ..studio.contracts import digest,validate_value
from .transport import Client,ConnectorFailure,clean

PROBE_TIMEOUT=32 # Native transport30s including close, bounded fixture adapters.

def enabled():
    if not settings().connectors_enabled:raise HTTPException(503,'connectors_disabled')

def event(db,row,actor,action,**data):
    db.add(ConnectorEvent(workspace_id=row.workspace_id,connection_id=row.id,actor_id=actor,action=action,data=data))

def namespace(connection_id,name):return 'mcp.'+connection_id.replace('-','')+'.'+name

async def owned(db,cid,who,lock=False):
    enabled()
    query=select(ConnectorConnection).where(ConnectorConnection.id==str(cid))
    if lock:query=query.with_for_update().execution_options(populate_existing=True)
    row=await db.scalar(query)
    if not row or row.owner_id!=who.id:raise HTTPException(404,'connector_not_found')
    member=await membership(db,row.workspace_id,who,True)
    if member.role not in ('owner','admin'):raise HTTPException(403,'connector_owner_required')
    if row.brain_id:
        from ..brains.access import require_brain
        await require_brain(db,who,row.brain_id)
    return row

def revision(row,expected):
    if row.version!=expected:raise HTTPException(409,'connector_revision_conflict')
    if row.status=='revoked':raise HTTPException(409,'connector_revoked')

def seal(value):
    from ...model_router import encrypt_key,ModelRouterError
    try:return encrypt_key(value)
    except ModelRouterError:raise HTTPException(503,'connector_encryption_not_configured') from None

async def token(db,row):
    secret=await db.scalar(select(ConnectorSecret).where(ConnectorSecret.connection_id==row.id,ConnectorSecret.workspace_id==row.workspace_id))
    if not secret or not secret.ciphertext:return None
    from ...model_router import decrypt_key,ModelRouterError
    try:return decrypt_key(secret.ciphertext)
    except ModelRouterError:raise ConnectorFailure('connector_credential_unreadable') from None

def public(row,secret=False):
    return {'id':row.id,'workspace_id':row.workspace_id,'brain_id':row.brain_id,'endpoint':row.endpoint,
        'status':row.status,'version':row.version,'protocol':'2025-11-25','secret_present':secret,
        'manifest_hash':row.manifest_hash,'permissions':list(row.permissions),
        'tools':[{'id':namespace(row.id,name),'name':name,**tool} for name,tool in row.manifest.get('tools',{}).items()],
        'circuit_open':bool(row.circuit_until and row.circuit_until>now())}

async def view(db,row):
    present=bool(await db.scalar(select(ConnectorSecret.id).where(
        ConnectorSecret.connection_id==row.id,ConnectorSecret.workspace_id==row.workspace_id,
        ConnectorSecret.ciphertext.is_not(None))))
    return public(row,present)

async def cancel_calls(db,row):
    calls=list(await db.scalars(select(ToolCall).where(ToolCall.status.in_(('queued','running')),
        ToolCall.connector_snapshot['connection_id'].as_string()==row.id).with_for_update()))
    for call in calls:
        call.status='cancelled';call.error_code='connector_revoked';call.version+=1;call.updated_at=now()

async def probe_source(db,cid,who):
    # Fresh owner/manager, private Brain and secret pins before key resolution
    # and again before publication. Enterprise ownership never bypasses Brain.
    from ..connections.model_metadata import manager
    from ...models import BrainMember
    try:
        preliminary=await owned(db,cid,who)
        await manager(db,preliminary.workspace_id,who)
    except HTTPException:raise HTTPException(403,'connector_probe_authority_changed') from None
    row=await owned(db,cid,who,True)
    if row.brain_id:
        from ..brains.access import require_brain
        brain=await require_brain(db,who,row.brain_id,lock=True)
        grant=await db.scalar(select(BrainMember).where(BrainMember.brain_id==row.brain_id,
            BrainMember.user_id==who.id).with_for_update(read=True).execution_options(populate_existing=True))
        if brain.workspace_id!=row.workspace_id or (brain.owner_id!=who.id and not grant):
            raise HTTPException(403,'connector_probe_brain_changed')
    secret=await db.scalar(select(ConnectorSecret).where(ConnectorSecret.connection_id==row.id,
        ConnectorSecret.workspace_id==row.workspace_id).with_for_update(read=True).execution_options(populate_existing=True))
    pinned=(row.id,row.workspace_id,row.owner_id,row.brain_id,row.endpoint,row.status,row.version,
        row.manifest_hash,row.failures,row.circuit_until,
        secret.id if secret else None,hashlib.sha256((secret.ciphertext or '').encode()).hexdigest() if secret else None)
    return row,pinned


async def probe(db,cid,who,expected_version,request_key=None):
    from ..connections import metadata_resources
    preliminary=await owned(db,cid,who);wid=preliminary.workspace_id
    await db.rollback() # Do not carry a stale ACL identity map into the claim.
    await metadata_resources.lock(db,wid)
    row,pinned=await probe_source(db,cid,who)
    if row.workspace_id!=wid:raise HTTPException(403,'connector_probe_scope_changed')
    revision(row,expected_version)
    if row.circuit_until and row.circuit_until>now():raise HTTPException(409,'connector_circuit_open')
    lease=await metadata_resources.admit(db,wid,who.id,'mcp_discovery',request_key,repr(pinned))
    lid=lease.id;failure=None;client=None
    try:secret=await token(db,row);client=Client(row.endpoint,secret)
    except ConnectorFailure as exc:failure=exc
    await db.commit() # No source/Brain/actor locks or transaction over network.
    try:
        await metadata_resources.require_current(wid,lid)
        if failure is None:
            try:
                async with asyncio.timeout(PROBE_TIMEOUT):
                    manifest=await client.exchange()
                    clean(manifest,secret) # Replacement adapter cannot publish a tainted manifest.
            except TimeoutError:failure=ConnectorFailure('connector_timeout')
            except ConnectorFailure as exc:failure=exc
        row,current=await probe_source(db,cid,who)
        if current!=pinned:raise HTTPException(409,'connector_probe_source_changed')
        revision(row,expected_version)
        if failure:
            from datetime import timedelta
            row.failures+=1
            if row.failures>=3:row.circuit_until=now()+timedelta(seconds=60)
            event(db,row,who.id,'discovery_failed',reason=str(failure));await db.commit()
            raise HTTPException(502,str(failure)) from None
        checksum=digest(manifest)
        if checksum!=row.manifest_hash:
            row.permissions={};row.version+=1;await cancel_calls(db,row)
        row.manifest,row.manifest_hash,row.status=manifest,checksum,'connected'
        row.failures=0;row.circuit_until=None
        event(db,row,who.id,'discovery_passed',hash=checksum,tools=len(manifest['tools']),permission_granted=False)
        await db.commit();return row
    finally:
        # Rollback before cleanup: admission holds metadata->source, so cleanup
        # must never hold a publication source lock while waiting on that pool.
        await db.rollback()
        await metadata_resources.finish(wid,lid)

def approved_tool(row,tool_id,expected_hash):
    for name,tool in row.manifest.get('tools',{}).items():
        if namespace(row.id,name)==tool_id and tool['hash']==expected_hash:return tool
    raise HTTPException(409,'connector_schema_drift')
