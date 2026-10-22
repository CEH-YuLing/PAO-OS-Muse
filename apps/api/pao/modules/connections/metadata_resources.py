"""SME metadata pool, not inference, provider RPC count, token quota or billing."""
import hashlib
import time
from datetime import timedelta
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import select,text,func
from ...models import Workspace,TenantMetadataPolicy,TenantMetadataLease,now
from ...db import Session

DEFAULTS={'daily_metadata_requests':100,'concurrent_metadata':2}
CEILINGS={'daily_metadata_requests':1000,'concurrent_metadata':8}
LEASE_SECONDS=90


async def lock(db,wid):
    if await db.scalar(select(Workspace.id).where(Workspace.id==wid).with_for_update(read=True,key_share=True)) is None:
        raise HTTPException(403,'tenant_metadata_scope_changed')
    await db.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:identity,0))'),
        {'identity':'pao-metadata-resource-v1:'+wid})


async def policy(db,wid):
    row=await db.get(TenantMetadataPolicy,wid,populate_existing=True)
    return {'version':row.version if row else 0,**{key:getattr(row,key) if row else value for key,value in DEFAULTS.items()}}


async def usage(db,wid):
    stamp=func.clock_timestamp()
    day=func.timezone('UTC',func.date_trunc('day',func.timezone('UTC',stamp)))
    query=select(func.count().filter(TenantMetadataLease.created_at>=day),
        func.count().filter((TenantMetadataLease.status=='active')&(TenantMetadataLease.expires_at>stamp)),
        func.count().filter((TenantMetadataLease.status=='expired')|((TenantMetadataLease.status=='active')&(TenantMetadataLease.expires_at<=stamp))))
    daily,active,unknown=(await db.execute(query.where(TenantMetadataLease.workspace_id==wid))).one()
    return {'daily_requests':daily,'active_requests':active,'expired_unknown_requests':unknown,
        'provider_remaining_quota':None,'billing_amount':None}


async def admit(db,wid,actor,kind,request_key,target):
    key=str(request_key or uuid4())
    if await db.scalar(select(TenantMetadataLease.id).where(TenantMetadataLease.workspace_id==wid,TenantMetadataLease.request_key==key)):
        raise HTTPException(409,'tenant_metadata_replay_denied')
    limits=await policy(db,wid);used=await usage(db,wid)
    if used['daily_requests']>=limits['daily_metadata_requests']:raise HTTPException(429,'tenant_metadata_daily_exhausted')
    if used['active_requests']>=limits['concurrent_metadata']:raise HTTPException(429,'tenant_metadata_concurrency_exhausted')
    stamp=now();lease=TenantMetadataLease(workspace_id=wid,actor_id=actor,kind=kind,request_key=key,
        target_hash=hashlib.sha256(target.encode()).hexdigest(),policy_version=limits['version'],
        created_at=stamp,expires_at=stamp+timedelta(seconds=LEASE_SECONDS))
    db.add(lease);await db.flush();return lease


async def finish(wid,lid):
    # No source locks: completion frees an in-flight slot, never daily quota or
    # request identity. Cleanup cannot revive an already expired invocation.
    async with Session.begin() as db:
        await db.execute(text("""UPDATE tenant_metadata_leases SET status=
          CASE WHEN expires_at<=clock_timestamp() THEN 'expired' ELSE 'released' END,
          released_at=clock_timestamp() WHERE workspace_id=:wid AND id=:lid AND status='active'"""),{'wid':wid,'lid':lid})


async def require_current(wid,lid):
    # A stalled commit/response must not start I/O after its lease was recovered.
    # Measure RTT from before the DB read: this underestimates remaining time,
    # never grants a fresh lease from a delayed server response.
    started=time.monotonic()
    async with Session() as db:
        remaining=await db.scalar(select(TenantMetadataLease.expires_at-func.clock_timestamp()).where(
            TenantMetadataLease.workspace_id==wid,TenantMetadataLease.id==lid,TenantMetadataLease.status=='active'))
    if remaining is None or started+remaining.total_seconds()<=time.monotonic()+40:
        raise HTTPException(409,'tenant_metadata_lease_expired')
