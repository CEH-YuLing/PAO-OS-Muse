import asyncio
from datetime import timedelta
from sqlalchemy import select
from ...config import settings
from ...db import Session
from ...models import GoogleAdsConnection,GoogleAdsSyncJob,Member,User,now
from .client import GoogleAdsClient,GoogleAdsError,decrypt
from .warehouse import fetch_accounts,fetch_historical,publish_accounts,publish_historical
from ...modules.connections import ads_authority,read_authority,read_resources
from .. import ads_apps
TIMEOUT=300
async def permitted(db,conn,version,job=None):
    if not settings().google_ads_enabled or not conn or conn.version!=version or conn.status!='connected' or not conn.refresh_token_ciphertext:return False
    if not await ads_apps.valid(db,conn,'google'):return False
    member=await db.get(Member,(conn.workspace_id,conn.user_id));user=await db.get(User,conn.user_id)
    native=bool(member and member.role in ('owner','admin') and user and user.active)
    return native and (await ads_authority.job_allowed(db,conn,'google_ads',job) if job else not await ads_authority.registered(db,conn,'google_ads'))
async def sync_google_ads(ctx,job_id):
    async with Session.begin() as db:
        first=await db.get(GoogleAdsSyncJob,job_id)
        if not first:return
        source=await db.get(GoogleAdsConnection,first.connection_id)
        if not source:return
        await read_resources.lock(db,source.workspace_id)
        await db.refresh(source,with_for_update={'read':True})
        job=await db.get(GoogleAdsSyncJob,job_id,with_for_update=True)
        if not job or job.status!='queued':return
        conn=await db.get(GoogleAdsConnection,job.connection_id)
        if not await permitted(db,conn,job.connection_version,job):job.status='cancelled';job.error_code='google_ads_access_revoked';return
        if not await read_resources.available(db,source.workspace_id):job.error_code='tenant_read_concurrency_wait';return
        job.status='running';job.error_code=None;job.attempts+=1;job.updated_at=now();generation=job.attempts
        try:
            credential=decrypt(conn.refresh_token_ciphertext)
            app_context=await ads_apps.bound(db,conn,'google')
        except GoogleAdsError as exc:job.status='failed';job.error_code=str(exc);return
    error=None;result=None
    try:
        if job.api_version!=app_context.config.google_ads_api_version:raise GoogleAdsError('google_ads_api_version_changed')
        client=GoogleAdsClient(config=app_context.config,guard=ads_apps.invocation(conn,'google',job,binding=app_context.binding))
        async with asyncio.timeout(TIMEOUT):result=await (fetch_accounts(client,credential,job) if job.kind=='accounts' else fetch_historical(client,credential,job))
    except GoogleAdsError as exc:error=str(exc)
    except TimeoutError:error='google_ads_sync_timeout_reduce_range'
    except Exception:error='google_ads_sync_failed'
    async with Session.begin() as db:
        await read_authority.lock_scope(db,conn.workspace_id)
        conn=await db.get(GoogleAdsConnection,job.connection_id,with_for_update=True);current=await db.get(GoogleAdsSyncJob,job_id,with_for_update=True)
        if current.status!='running' or current.attempts!=generation:return
        if not await permitted(db,conn,current.connection_version,current):current.status='cancelled';current.error_code='google_ads_access_revoked'
        elif error:
            current.status='failed';current.error_code=error
            if error=='google_ads_reauthorization_required':conn.status='expired';conn.refresh_token_ciphertext=None
        else:
            try:
                async with db.begin_nested():
                    if current.kind=='accounts':await publish_accounts(db,current,result);count=len(result)
                    else:await publish_historical(db,current,*result);count=sum(map(len,result))
                    await db.flush()
                current.status='completed';current.row_count=count;current.error_code=None
            except Exception:current.status='failed';current.error_code='google_ads_publish_failed'
        current.updated_at=now()
async def dispatch_google_ads(ctx):
    if not settings().google_ads_enabled:return
    async with Session.begin() as db:
        stale=list(await db.scalars(select(GoogleAdsSyncJob).where(GoogleAdsSyncJob.status=='running',GoogleAdsSyncJob.updated_at<now()-timedelta(seconds=TIMEOUT+60)).with_for_update(skip_locked=True)))
        for job in stale:job.status='failed';job.error_code='google_ads_worker_lost_unknown';job.updated_at=now()
        queued=await read_resources.fair_queued(db,GoogleAdsSyncJob,GoogleAdsConnection,20)
    for job_id in queued:await ctx['redis'].enqueue_job('sync_google_ads',job_id,_job_id=f'google-ads:{job_id}',_expires=3600)
