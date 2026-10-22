"""Explicit scoped destination; never select the first bot/peer of an SME."""
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select
from pao.auth import Principal
from pao.models import ChannelBinding,AdReport,MetaConnection
from . import service,telegram_scoped as scoped


async def destination(db,workspace_id,user_id,binding_id,version=None):
    binding=await db.get(ChannelBinding,str(binding_id),populate_existing=True)
    if (not binding or binding.connection_id is None or binding.workspace_id!=workspace_id or binding.actor_id!=user_id or
        not binding.reports_enabled or not binding.enabled or not binding.outbound_confirmed or
        version is not None and binding.version!=version):raise HTTPException(409,'telegram_report_destination_unavailable')
    await scoped.context(db,binding)
    return binding


def report_id(key):
    try:return str(UUID(key.removeprefix('ads-report:').partition(':p:')[0]))
    except ValueError:raise HTTPException(409,'telegram_report_reference_invalid') from None


async def visible(db,binding,row):
    from pao.integrations.meta.sync import permitted
    from pao.reporting import report_text
    report=await db.get(AdReport,report_id(row.request_key),populate_existing=True)
    if (not binding.reports_enabled or not report or report.workspace_id!=binding.workspace_id or report.user_id!=binding.actor_id):return False
    connection=await db.get(MetaConnection,report.connection_id,populate_existing=True)
    if not await permitted(db,connection,report.connection_version):return False
    if connection.workspace_id!=binding.workspace_id or connection.user_id!=binding.actor_id:return False
    # Use the same UTF-16 partition boundary as Channels.queue.
    body=report_text(report);parts=[];current='';units=0
    for char in body:
        width=len(char.encode('utf-16-le'))//2
        if units+width>3500:parts.append(current);current='';units=0
        current+=char;units+=width
    if current:parts.append(current)
    _,sep,part=row.request_key.partition(':p:')
    if sep and (not part.isdigit() or str(int(part))!=part):return False
    index=int(part) if sep else 0
    return index<len(parts) and (sep or len(parts)==1) and row.body==parts[index]


async def queue_report(db,report,binding):
    from pao.reporting import report_text
    binding=await destination(db,report.workspace_id,report.user_id,binding.id)
    return await service.queue(db,binding,'ads-report:'+report.id,report_text(report),'manual')
