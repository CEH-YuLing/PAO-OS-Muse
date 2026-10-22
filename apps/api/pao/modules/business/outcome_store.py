"""Immutable read-only evidence snapshots; timestamps never fast-forward a window."""
import json
from datetime import datetime,timedelta,timezone
from uuid import UUID,uuid5
from fastapi import Depends,HTTPException,Request
from pydantic import Field
from sqlalchemy import select,func
from ...auth import Principal,principal,rate_limit
from ...access import membership
from ...config import settings
from ...db import database
from ...integrations.meta.api import connection
from ...models import AdAction,AdActionAudit,AdMetric,MetaSyncJob,OutcomeObservation,now
from ..studio.contracts import Closed,digest

def enabled():
    if not settings().outcome_observations_enabled:raise HTTPException(409,'outcome_observations_disabled')

async def action_row(db,who,ident,write=False,lock=False):
    query=select(AdAction).where(AdAction.id==str(ident))
    if lock:query=query.with_for_update().execution_options(populate_existing=True)
    action=await db.scalar(query)
    if not action:raise HTTPException(404,'action_not_found')
    await membership(db,action.workspace_id,who,write)
    if action.user_id!=who.id:raise HTTPException(404,'action_not_found')
    return action

def scalar(value):
    if value is None or isinstance(value,(str,int,bool)):return value
    return value.isoformat() if hasattr(value,'isoformat') else str(value)

async def evidence(db,who,action,stamp):
    from .outcomes import compare
    conn=await connection(db,who,action.workspace_id)
    if not conn or action.connection_id!=conn.id or action.connection_version!=conn.version:raise HTTPException(409,'action_source_stale')
    audits=list(await db.scalars(select(AdActionAudit).where(AdActionAudit.action_id==action.id,AdActionAudit.workspace_id==action.workspace_id,
        AdActionAudit.event=='action.succeeded',AdActionAudit.action_version<=action.version).order_by(AdActionAudit.id)))
    verified=any(a.actor_id==action.user_id and a.data.get('after_state')==action.after_state and not a.data.get('error_code') for a in audits)
    rows=[];others=[];jobs={}
    if action.executed_at and verified and not action.dry_run and action.execution_status=='succeeded':
        start=action.executed_at-timedelta(days=8);end=action.executed_at+timedelta(days=8)
        rows=list(await db.scalars(select(AdMetric).where(AdMetric.connection_id==conn.id,AdMetric.connection_version==conn.version,
            AdMetric.platform=='meta',AdMetric.account_id==action.account_id,AdMetric.level==action.resource_type,AdMetric.entity_id==action.resource_id,
            AdMetric.granularity=='hourly',AdMetric.day>=start.date(),AdMetric.day<=end.date()).order_by(AdMetric.id).limit(5001)))
        if len(rows)>5000:raise HTTPException(409,'outcome_evidence_limit_exceeded')
        job_ids={r.source_job_id for r in rows}
        if job_ids:
            jobs={j.id:j for j in await db.scalars(select(MetaSyncJob).where(MetaSyncJob.id.in_(job_ids)))}
        others=list(await db.scalars(select(AdAction).where(AdAction.connection_id==conn.id,AdAction.connection_version==conn.version,
            AdAction.account_id==action.account_id,AdAction.resource_type==action.resource_type,AdAction.resource_id==action.resource_id,
            AdAction.execution_status=='succeeded',AdAction.dry_run.is_(False),AdAction.executed_at>=start,AdAction.executed_at<=end).order_by(AdAction.id).limit(1001)))
        if len(others)>1000:raise HTTPException(409,'outcome_confounder_limit_exceeded')
    valid=[r for r in rows if (j:=jobs.get(r.source_job_id)) and j.status=='completed' and j.connection_id==conn.id and j.connection_version==conn.version and j.granularity=='hourly' and j.account_id==action.account_id]
    snapshot={'format':'p67-observation-v1','observed_at':stamp.astimezone(timezone.utc).isoformat(),
        'action':{k:scalar(getattr(action,k)) for k in ('id','workspace_id','user_id','version','connection_id','connection_version','account_id','resource_type','resource_id','action_type','executed_at','execution_status','dry_run','payload_hash')},
        'execution_proofs':[{'id':a.id,'version':a.action_version,'actor_id':a.actor_id,'data_hash':digest(a.data)} for a in audits],
        'metrics':[{k:scalar(getattr(r,k)) for k in ('id','source_job_id','day','hour','granularity','timezone','currency','attribution','spend','clicks','purchase','revenue')} for r in rows],
        'jobs':[{'id':j.id,'status':j.status,'connection_id':j.connection_id,'version':j.connection_version,'account_id':j.account_id,'granularity':j.granularity} for j in sorted(jobs.values(),key=lambda j:j.id)],
        'confounder_sources':[{k:scalar(getattr(a,k)) for k in ('id','version','executed_at','action_type','payload_hash')} for a in others],
        'outcomes':compare(action,valid,others,stamp,execution_verified=verified),
        'causal_effect_proven':False,'external_send':False,'model_calls':False}
    if len(json.dumps(snapshot).encode())>2097152:raise HTTPException(409,'outcome_snapshot_limit_exceeded')
    return snapshot

class Capture(Closed):
    observed_at:datetime=Field(strict=False)
    confirmation_hash:str=Field(pattern='^[a-f0-9]{64}$')
    request_key:UUID=Field(strict=False)

def summary(row):
    return {'id':row.id,'action_id':row.action_id,'observed_at':row.observed_at,'source_hash':row.source_hash,
        'statuses':{k:v['status'] for k,v in row.snapshot['outcomes'].items()},'causal_effect_proven':False}

def verify(row):
    if digest(row.snapshot)!=row.source_hash or row.snapshot.get('action',{}).get('id')!=row.action_id:
        raise HTTPException(409,'outcome_snapshot_invalid')

def register(router):
    @router.get('/outcome-observations/status')
    async def observation_status(workspace_id:UUID,who:Principal=Depends(principal),db=Depends(database)):
        await membership(db,str(workspace_id),who)
        return {'enabled':settings().outcome_observations_enabled,'external_writes':False,'causal_effect_proven':False}

    @router.post('/actions/{action_id}/outcome-preview')
    async def preview_observation(action_id:UUID,request:Request,who:Principal=Depends(principal),db=Depends(database)):
        enabled();action=await action_row(db,who,action_id);stamp=now()
        await rate_limit(request.app.state.redis,'outcome-preview',who.id,20,60)
        snapshot=await evidence(db,who,action,stamp);fingerprint=digest(snapshot)
        return {'observed_at':stamp,'confirmation_hash':fingerprint,'source_hash':fingerprint,'outcomes':snapshot['outcomes'],
            'pins':{'action_version':action.version,'connection_version':action.connection_version,'metric_count':len(snapshot['metrics']),'proof_count':len(snapshot['execution_proofs'])},
            'read_only_external':True,'creates_observation':False,'causal_effect_proven':False}

    @router.post('/actions/{action_id}/outcome-observations',status_code=201)
    async def capture_observation(action_id:UUID,body:Capture,who:Principal=Depends(principal),db=Depends(database)):
        enabled();action=await action_row(db,who,action_id,True,True)
        if not body.observed_at.tzinfo:raise HTTPException(422,'outcome_timestamp_requires_timezone')
        stamp=body.observed_at.astimezone(timezone.utc)
        request_hash=digest({'observed_at':stamp.isoformat(),'confirmation_hash':body.confirmation_hash,'request_key':str(body.request_key)})
        ident=str(uuid5(UUID(action.id),who.id+':'+str(body.request_key)))
        saved=await db.get(OutcomeObservation,ident)
        if saved:
            verify(saved)
            if saved.request_hash!=request_hash:raise HTTPException(409,'outcome_request_key_conflict')
            return summary(saved)
        if not now()-timedelta(minutes=5)<=stamp<=now():raise HTTPException(409,'outcome_preview_expired')
        day=now().replace(hour=0,minute=0,second=0,microsecond=0)
        count=await db.scalar(select(func.count(OutcomeObservation.id)).where(OutcomeObservation.action_id==action.id,OutcomeObservation.actor_id==who.id,OutcomeObservation.created_at>=day))
        if count>=50:raise HTTPException(429,'outcome_daily_budget_exhausted')
        snapshot=await evidence(db,who,action,stamp)
        if digest(snapshot)!=body.confirmation_hash:raise HTTPException(409,'outcome_source_changed')
        saved=OutcomeObservation(id=ident,workspace_id=action.workspace_id,action_id=action.id,actor_id=who.id,request_key=str(body.request_key),request_hash=request_hash,source_hash=body.confirmation_hash,observed_at=stamp,snapshot=snapshot)
        db.add(saved);await db.commit();return summary(saved)

    @router.get('/actions/{action_id}/outcome-observations')
    async def list_observations(action_id:UUID,who:Principal=Depends(principal),db=Depends(database)):
        enabled();action=await action_row(db,who,action_id)
        rows=list(await db.scalars(select(OutcomeObservation).where(OutcomeObservation.action_id==action.id,OutcomeObservation.actor_id==who.id).order_by(OutcomeObservation.created_at.desc()).limit(50)))
        for row in rows:verify(row)
        return [summary(row) for row in rows]

    @router.get('/outcome-observations/{observation_id}')
    async def read_observation(observation_id:UUID,who:Principal=Depends(principal),db=Depends(database)):
        enabled();row=await db.get(OutcomeObservation,str(observation_id))
        if not row or row.actor_id!=who.id:raise HTTPException(404,'outcome_observation_not_found')
        action=await action_row(db,who,row.action_id);verify(row)
        try:current=digest(await evidence(db,who,action,row.observed_at))==row.source_hash
        except HTTPException:current=False
        return {**summary(row),'snapshot':row.snapshot,'current_source_matches':current,'historical_snapshot':True}
