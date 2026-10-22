"""Report scheduling service; HTTP compatibility lives in report_api."""
from datetime import timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from ...config import settings
from ...db import Session
from ...models import AdEntity, AdReport, AdReportSchedule, MetaConnection, TelegramPeer, now
from ...integrations.meta.sync import permitted as meta_permitted
from ...reporting import build_report, queue_report, next_delivery
from ..channels.telegram_helpers import queue, permitted as telegram_permitted


async def schedule_reports(ctx):
    async with Session() as db:
        ids=list(await db.scalars(select(AdReportSchedule.id).where(AdReportSchedule.enabled.is_(True),AdReportSchedule.next_at<=now()).order_by(AdReportSchedule.next_at).limit(20)))
    for ident in ids:
        async with Session.begin() as db:
            schedule=await db.get(AdReportSchedule,ident,with_for_update=True)
            if not schedule or not schedule.enabled or schedule.next_at>now():continue
            conn=await db.get(MetaConnection,schedule.connection_id)
            account=await db.scalar(select(AdEntity).where(AdEntity.connection_id==schedule.connection_id,
                AdEntity.connection_version==schedule.connection_version,AdEntity.account_id==schedule.account_id,AdEntity.kind=='account'))
            if not await meta_permitted(db,conn,schedule.connection_version) or not account:
                schedule.enabled=False;continue
            scoped_binding=None
            if schedule.telegram and schedule.telegram_binding_id:
                from ..channels.telegram_reports import destination
                from fastapi import HTTPException
                from ..channels.telegram_runtime import TelegramRuntimeError
                try:scoped_binding=await destination(db,conn.workspace_id,conn.user_id,schedule.telegram_binding_id,schedule.telegram_binding_version)
                except (HTTPException,TelegramRuntimeError):schedule.enabled=False;continue
            elif schedule.telegram and (not settings().telegram_enabled or not settings().telegram_bot_token):
                schedule.enabled=False;continue
            peers=[]
            if schedule.telegram and not scoped_binding:
                candidates=list(await db.scalars(select(TelegramPeer).where(TelegramPeer.user_id==conn.user_id,
                    TelegramPeer.connection_id.is_(None),TelegramPeer.workspace_id==conn.workspace_id,TelegramPeer.enabled.is_(True))))
                peers=[peer for peer in candidates if await telegram_permitted(db,peer)]
                if not peers:schedule.enabled=False;continue
            local=now().astimezone(ZoneInfo(account.timezone));end=local.date()-timedelta(days=1)
            key=f'report-schedule:{schedule.id}:{end}'
            report=await db.scalar(select(AdReport).where(AdReport.connection_id==conn.id,AdReport.request_key==key))
            if not report:
                try:report=await build_report(db,conn,conn.user_id,schedule.account_id,schedule.kind,end,key)
                except ValueError:
                    schedule.next_at=next_delivery(account.timezone,schedule.kind,schedule.delivery_hour,schedule.weekday,now()+timedelta(minutes=1));continue
            if scoped_binding:
                from ..channels.telegram_reports import queue_report as scoped_queue
                await scoped_queue(db,report,scoped_binding)
            elif schedule.telegram:
                for peer in peers:
                    await queue_report(db,report,peer,queue)
            schedule.next_at=next_delivery(account.timezone,schedule.kind,schedule.delivery_hour,schedule.weekday,now()+timedelta(minutes=1))
