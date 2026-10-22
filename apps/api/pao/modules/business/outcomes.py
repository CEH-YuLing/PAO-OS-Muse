"""Read-only action outcome evidence; never infers a causal effect.

Use full hourly buckets only. Daily aggregates cannot prove an exact 24h window.
Warehouse hours have no DST fold identity: ambiguous hours fail coverage.
"""
from datetime import timedelta,timezone
from decimal import Decimal
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
from uuid import UUID
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from ...auth import Principal,principal
from ...db import database
from ...integrations.meta.api import connection
from ...models import AdAction,AdActionAudit,AdMetric,now

router=APIRouter(prefix='/v1/ads',tags=['action-outcomes'])
WINDOWS={'24h':24,'72h':72,'7d':168}


def aggregate(metrics,start,end):
    slots={};dimensions=set();source_ids=[];ambiguous=False
    for metric in metrics:
        try:zone=ZoneInfo(metric.timezone)
        except (ZoneInfoNotFoundError,ValueError):ambiguous=True;continue
        wall=metric.day.isoformat()+f'T{metric.hour:02d}:00:00'
        from datetime import datetime
        local=datetime.fromisoformat(wall).replace(tzinfo=zone)
        stamp=local.astimezone(timezone.utc)
        if not start<=stamp<end:continue
        if local.replace(fold=0).utcoffset()!=local.replace(fold=1).utcoffset():
            ambiguous=True;continue
        if stamp.astimezone(zone).replace(tzinfo=None)!=local.replace(tzinfo=None):
            ambiguous=True;continue
        dimensions.add((metric.currency,metric.timezone,metric.attribution))
        slots.setdefault(stamp,[]).append(metric);source_ids.append(metric.id)
    expected=int((end-start).total_seconds()//3600)
    valid=len(dimensions)==1 and len(slots)==expected and all(len(rows)==1 for rows in slots.values()) and not ambiguous
    rows=[rows[0] for rows in slots.values() if len(rows)==1]
    complete=all(all(getattr(r,k) is not None for k in ('spend','clicks','purchase','revenue')) for r in rows)
    valid=valid and complete
    sums={key:sum((Decimal(str(getattr(r,key))) for r in rows if getattr(r,key) is not None),Decimal(0))
        for key in ('spend','clicks','purchase','revenue')}
    return {'complete':valid,'expected_hours':expected,'covered_hours':len(slots),
        'ambiguous_dst':ambiguous,'dimensions':[list(d) for d in sorted(dimensions)],
        'metric_ids':sorted(source_ids),'totals':{key:str(value) for key,value in sums.items()} if valid else {}}


def compare(action,metrics,other_actions,observed_at,*,execution_verified):
    results={}
    for name,hours in WINDOWS.items():
        base={'action_id':action.id,'window':name,'causal_effect_proven':False,
            'model_executed':False,'confounders':[], 'status':'insufficient'}
        if not execution_verified or action.dry_run or action.execution_status!='succeeded' or not action.executed_at:
            results[name]={**base,'reason':'real_execution_not_verified'};continue
        executed=action.executed_at.astimezone(timezone.utc)
        # Hourly warehouse cannot accurately split an action's partial hour.
        if executed.minute or executed.second or executed.microsecond:
            results[name]={**base,'reason':'hourly_resolution_insufficient'};continue
        end=executed+timedelta(hours=hours)
        if observed_at<end:
            results[name]={**base,'status':'pending','reason':'window_not_elapsed','due_at':end.isoformat()};continue
        baseline=aggregate(metrics,executed-timedelta(hours=hours),executed)
        outcome=aggregate(metrics,executed,end)
        confounders=[{'kind':'other_resource_action','action_id':a.id} for a in other_actions
            if a.id!=action.id and a.executed_at and executed-timedelta(hours=hours)<=a.executed_at<end]
        base={**base,'baseline':baseline,'outcome':outcome,'confounders':confounders,
            'baseline_start':(executed-timedelta(hours=hours)).isoformat(),'action_at':executed.isoformat(),'outcome_end':end.isoformat()}
        if not baseline['complete'] or not outcome['complete'] or baseline['dimensions']!=outcome['dimensions']:
            results[name]={**base,'reason':'coverage_or_dimensions_insufficient'};continue
        delta={k:str(Decimal(outcome['totals'][k])-Decimal(baseline['totals'][k])) for k in baseline['totals']}
        results[name]={**base,'status':'observed','reason':'association_only','delta':delta}
    return results


@router.get('/actions/{action_id}/outcomes')
async def read_outcomes(action_id:UUID,who:Principal=Depends(principal),db=Depends(database)):
    action=await db.get(AdAction,str(action_id))
    if not action:raise HTTPException(404,'action_not_found')
    conn=await connection(db,who,action.workspace_id)
    if conn is None or action.connection_id!=conn.id or action.connection_version!=conn.version:
        raise HTTPException(409,'action_source_stale')
    proof=await db.scalar(select(AdActionAudit.id).where(AdActionAudit.action_id==action.id,
        AdActionAudit.workspace_id==action.workspace_id,AdActionAudit.event=='action.succeeded',
        AdActionAudit.action_version<=action.version))
    metrics=[];others=[]
    if action.executed_at and proof and not action.dry_run and action.execution_status=='succeeded':
        start=action.executed_at-timedelta(days=8);end=action.executed_at+timedelta(days=8)
        rows=list(await db.scalars(select(AdMetric).where(AdMetric.connection_id==conn.id,
            AdMetric.connection_version==conn.version,AdMetric.platform=='meta',
            AdMetric.account_id==action.account_id,AdMetric.level==action.resource_type,
            AdMetric.entity_id==action.resource_id,AdMetric.granularity=='hourly',
            AdMetric.day>=start.date(),AdMetric.day<=end.date()).limit(5001)))
        if len(rows)>5000:raise HTTPException(409,'outcome_evidence_limit_exceeded')
        metrics=rows
        others=list(await db.scalars(select(AdAction).where(AdAction.connection_id==conn.id,
            AdAction.connection_version==conn.version,AdAction.account_id==action.account_id,
            AdAction.resource_type==action.resource_type,AdAction.resource_id==action.resource_id,
            AdAction.execution_status=='succeeded',AdAction.dry_run.is_(False),
            AdAction.executed_at>=start,AdAction.executed_at<=end).limit(1001)))
        if len(others)>1000:raise HTTPException(409,'outcome_confounder_limit_exceeded')
    return {'action_id':action.id,'read_only':True,'outcomes':compare(action,metrics,others,now(),execution_verified=bool(proof))}


from .outcome_store import register
register(router)
