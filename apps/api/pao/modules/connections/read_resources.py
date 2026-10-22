"""SME read-job resource admission. Not provider HTTP quota or authority."""
from sqlalchemy import select,text,func,true,and_,or_
from fastapi import HTTPException
from ...models import Workspace,TenantReadPolicy,ToolCall,AdSyncSchedule,MetaConnection,now

DEFAULTS={'daily_read_jobs':500,'queued_read_jobs':20,'concurrent_reads':2}
CEILINGS={'daily_read_jobs':10000,'queued_read_jobs':100,'concurrent_reads':8}


async def lock(db,wid):
    if await db.scalar(select(Workspace.id).where(Workspace.id==wid).with_for_update(read=True,key_share=True)) is None:
        raise HTTPException(404,'tenant_read_resource_scope_missing')
    await db.execute(text('SELECT pg_advisory_xact_lock(hashtextextended(:identity,0))'),
        {'identity':'pao-read-resource-v1:'+wid})


async def policy(db,wid):
    row=await db.get(TenantReadPolicy,wid,populate_existing=True)
    return {'version':row.version if row else 0,**{key:getattr(row,key) if row else value for key,value in DEFAULTS.items()}}


async def usage(db,wid):
    row=(await db.execute(text('SELECT * FROM pao_read_resource_usage(:wid)'),{'wid':wid})).mappings().one()
    return dict(row)


async def admit(db,wid):
    limits=await policy(db,wid);used=await usage(db,wid)
    if used['daily_jobs']>=limits['daily_read_jobs']:raise HTTPException(429,'tenant_read_daily_jobs_exhausted')
    if used['queued_jobs']>=limits['queued_read_jobs']:raise HTTPException(429,'tenant_read_queue_exhausted')


async def available(db,wid):
    return (await usage(db,wid))['running_jobs']<(await policy(db,wid))['concurrent_reads']


async def fair_queued(db,model,source=None,limit=20):
    """One tenant's old backlog cannot hide other SMEs behind global LIMIT."""
    wid=source.workspace_id if source is not None else model.workspace_id
    query=select(model.id.label('id'),model.created_at.label('created'),
        func.row_number().over(partition_by=wid,order_by=(model.created_at,model.id)).label('rank')).select_from(model).where(model.status=='queued')
    if source is not None:query=query.join(source,source.id==model.connection_id)
    used=func.pao_read_resource_usage(wid).table_valued('daily_jobs','queued_jobs','running_jobs').lateral('used')
    ceiling=select(TenantReadPolicy.concurrent_reads).where(TenantReadPolicy.workspace_id==wid).correlate(
        source if source is not None else model).scalar_subquery()
    # Offer only one oldest item per SME and do not prefill Redis behind a busy
    # SME. Caps still allow explicitly parallel claims; dispatch is conservative.
    eligible=and_(used.c.running_jobs==0,used.c.running_jobs<func.coalesce(ceiling,DEFAULTS['concurrent_reads']))
    if model is ToolCall:
        eligible=or_(and_(or_(ToolCall.connector_snapshot.is_(None),func.json_typeof(ToolCall.connector_snapshot)=='null'),
            ~ToolCall.name.like('mcp.%')),eligible)
    query=query.join(used,true()).where(eligible)
    ranked=query.subquery()
    return list(await db.scalars(select(ranked.c.id).where(ranked.c.rank==1)
        .order_by(ranked.c.created,ranked.c.id).limit(limit)))


async def fair_schedules(db,limit=20):
    """Quota-blocked due schedules cannot monopolize the first global page."""
    wid=MetaConnection.workspace_id
    used=func.pao_read_resource_usage(wid).table_valued('daily_jobs','queued_jobs','running_jobs').lateral('used')
    def cap(field):
        return func.coalesce(select(getattr(TenantReadPolicy,field)).where(TenantReadPolicy.workspace_id==wid)
            .correlate(MetaConnection).scalar_subquery(),DEFAULTS[field])
    ranked=select(AdSyncSchedule.id.label('id'),AdSyncSchedule.next_at.label('due'),
        func.row_number().over(partition_by=wid,order_by=(AdSyncSchedule.next_at,AdSyncSchedule.id)).label('rank'))
    ranked=ranked.select_from(AdSyncSchedule).join(MetaConnection,MetaConnection.id==AdSyncSchedule.connection_id)
    ranked=ranked.join(used,true()).where(AdSyncSchedule.enabled.is_(True),AdSyncSchedule.next_at<=now(),
        used.c.daily_jobs<cap('daily_read_jobs'),used.c.queued_jobs<cap('queued_read_jobs')).subquery()
    return list(await db.scalars(select(ranked.c.id).where(ranked.c.rank==1).order_by(ranked.c.due,ranked.c.id).limit(limit)))
