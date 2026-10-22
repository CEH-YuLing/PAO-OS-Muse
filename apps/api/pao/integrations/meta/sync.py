"""Bounded read-only sync on the existing worker; publish snapshots atomically."""
import asyncio
import hashlib
import json
from datetime import date, timedelta
from sqlalchemy import select, delete
from ...config import settings
from ...db import Session
from ...models import MetaConnection, MetaSyncJob, MetaSnapshot, Member, User, now
from .client import MetaClient, MetaError, decrypt
from ...warehouse import fetch_warehouse, publish_warehouse
from ...modules.connections import ads_authority, read_authority,read_resources
from .. import ads_apps

TIMEOUT=300


async def permitted(db,connection,version,job=None):
    if not settings().meta_enabled or not connection or connection.version!=version or connection.status!='connected' or not connection.expires_at or connection.expires_at<=now():return False
    if not await ads_apps.valid(db,connection,'meta'):return False
    member=await db.get(Member,(connection.workspace_id,connection.user_id))
    user=await db.get(User,connection.user_id)
    native=bool(member and member.role in ('owner','admin') and user and user.active)
    return native and (await ads_authority.job_allowed(db,connection,'meta_ads',job) if job else not await ads_authority.registered(db,connection,'meta_ads'))


async def sync_meta(ctx,job_id):
    async with Session.begin() as db:
        first=await db.get(MetaSyncJob,job_id)
        if not first:return
        source=await db.get(MetaConnection,first.connection_id)
        if not source:return
        await read_resources.lock(db,source.workspace_id)
        await db.refresh(source,with_for_update={'read':True})
        job=await db.get(MetaSyncJob,job_id,with_for_update=True)
        if not job or job.status!='queued':return
        conn=await db.get(MetaConnection,job.connection_id)
        if not await permitted(db,conn,job.connection_version,job):
            job.status='cancelled';job.error_code='meta_access_revoked';return
        if not await read_resources.available(db,source.workspace_id):
            job.error_code='tenant_read_concurrency_wait';return
        job.status='running';job.error_code=None;job.attempts+=1;job.updated_at=now()
        generation=job.attempts
        try:
            credential=decrypt(conn.token_ciphertext)
            app_context=await ads_apps.bound(db,conn,'meta')
        except MetaError as exc:
            job.status='failed';job.error_code=str(exc);return
    error=None;rows={};payload_bytes=0;normalized=None
    try:
        if job.api_version!=app_context.config.meta_graph_api_version:raise MetaError('meta_api_version_changed')
        client=MetaClient(credential,config=app_context.config,guard=ads_apps.invocation(conn,'meta',job,binding=app_context.binding))
        async with asyncio.timeout(TIMEOUT):
            if job.warehouse:normalized=await fetch_warehouse(client,job)
            kinds=[] if job.warehouse else ['accounts'] if job.kind=='accounts' else ['campaigns','adsets','ads','insights']
            for kind in kinds:
                windows=[(None,None)]
                if kind=='insights':
                    start=date.fromisoformat(job.since);end=date.fromisoformat(job.until);windows=[]
                    while start<=end:
                        last=min(start+timedelta(days=6),end);windows.append((start.isoformat(),last.isoformat()));start=last+timedelta(days=1)
                for since,until in windows:
                    async for payload in client.rows(kind,job.account_id,since,until):
                        payload_bytes+=len(json.dumps(payload).encode())
                        if payload_bytes>16_000_000:raise MetaError('meta_data_limit_reduce_range')
                        if kind=='insights':
                            required=('ad_id','date_start','date_stop')
                            if any(not payload.get(k) for k in required):raise MetaError('meta_invalid_response')
                            key=hashlib.sha256(json.dumps([payload[k] for k in required]).encode()).hexdigest()
                        else:
                            key=payload.get('id')
                            if not isinstance(key,str) or not key or len(key)>180:raise MetaError('meta_invalid_response')
                        rows[(kind,key)]=payload
                        if len(rows)>10000:raise MetaError('meta_row_limit_reduce_range')
    except MetaError as exc:error=str(exc)
    except TimeoutError:error='meta_sync_timeout_reduce_range'
    except Exception:error='meta_sync_failed'
    async with Session.begin() as db:
        await read_authority.lock_scope(db,conn.workspace_id)
        # Match API lock order: connection then job. Generation fences lost workers.
        conn=await db.get(MetaConnection,job.connection_id,with_for_update=True)
        current=await db.get(MetaSyncJob,job_id,with_for_update=True)
        if current.status!='running' or current.attempts!=generation:return
        if not await permitted(db,conn,current.connection_version,current):
            current.status='cancelled';current.error_code='meta_access_revoked'
        elif error:
            current.status='failed';current.error_code=error
            if error=='meta_reauthorization_required':conn.status='expired';conn.token_ciphertext=None
        else:
            try:
                async with db.begin_nested():
                    if normalized is not None:
                        await publish_warehouse(db,current,*normalized)
                    else:
                        await db.execute(delete(MetaSnapshot).where(MetaSnapshot.job_id==job_id))
                        db.add_all([MetaSnapshot(job_id=job_id,kind=kind,remote_key=key,payload=payload) for (kind,key),payload in rows.items()])
                    await db.flush()
                current.status='completed';current.row_count=sum(map(len,normalized)) if normalized is not None else len(rows);current.error_code=None
            except Exception:
                current.status='failed';current.error_code='warehouse_publish_failed' if normalized is not None else 'meta_publish_failed'
        current.updated_at=now()


async def dispatch_meta(ctx):
    if not settings().meta_enabled:return
    async with Session.begin() as db:
        stale=list(await db.scalars(select(MetaSyncJob).where(MetaSyncJob.status=='running',MetaSyncJob.updated_at<now()-timedelta(seconds=TIMEOUT+60)).with_for_update(skip_locked=True)))
        for job in stale:
            job.status='failed';job.error_code='meta_worker_lost_unknown';job.updated_at=now()
        queued=await read_resources.fair_queued(db,MetaSyncJob,MetaConnection,20)
    for job_id in queued:await ctx['redis'].enqueue_job('sync_meta',job_id,_job_id=f'meta:{job_id}',_expires=3600)
