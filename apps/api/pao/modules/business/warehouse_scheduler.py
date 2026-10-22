"""Warehouse sync scheduling, independent of HTTP route adapters."""
from datetime import timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from ...config import settings
from ...db import Session
from ...models import AdEntity, AdSyncSchedule, MetaConnection, MetaSyncJob, now
from ...integrations.meta.sync import permitted
from ..connections import read_resources
from fastapi import HTTPException
from ...integrations import ads_apps


async def schedule_warehouse(ctx):
    if not settings().meta_enabled:return
    async with Session() as db:
        ids=await read_resources.fair_schedules(db,20)
    for ident in ids:
        async with Session.begin() as db:
            item=await db.get(AdSyncSchedule,ident)
            if not item:continue
            scope=await db.get(MetaConnection,item.connection_id)
            if not scope:continue
            await read_resources.lock(db,scope.workspace_id)
            conn=await db.get(MetaConnection,item.connection_id,with_for_update=True)
            await db.refresh(item,with_for_update=True)
            if not item.enabled or item.next_at>now():continue
            if not await permitted(db,conn,item.connection_version):item.enabled=False;continue
            active=await db.scalar(select(MetaSyncJob.id).where(MetaSyncJob.connection_id==conn.id,MetaSyncJob.status.in_(['queued','running'])))
            if active:continue
            account=await db.scalar(select(AdEntity).where(AdEntity.connection_id==conn.id,AdEntity.connection_version==conn.version,AdEntity.account_id==item.account_id,AdEntity.kind=='account'))
            if not account:item.enabled=False;continue
            end=now().astimezone(ZoneInfo(account.timezone)).date()
            key=f'schedule:{item.id}:{int(item.next_at.timestamp())}'
            exists=await db.scalar(select(MetaSyncJob.id).where(MetaSyncJob.connection_id==conn.id,MetaSyncJob.request_key==key))
            if not exists:
                try:await read_resources.admit(db,conn.workspace_id)
                except HTTPException as exc:
                    if exc.status_code!=429:raise
                    continue  # Keep next_at; bounded next tick retries admission, no job/provider call.
                app_context=await ads_apps.bound(db,conn,'meta')
                db.add(MetaSyncJob(connection_id=conn.id,connection_version=conn.version,api_version=app_context.config.meta_graph_api_version,
                request_key=key,kind='historical',account_id=item.account_id,since=(end-timedelta(days=item.lookback_days-1)).isoformat(),until=end.isoformat(),
                warehouse=True,granularity=item.granularity))
            item.next_at=now()+timedelta(minutes=item.interval_minutes)
