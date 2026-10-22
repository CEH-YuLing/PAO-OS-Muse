"""Durable, bounded per-SME/model cooling-off using the existing attempt ledger.

No extra runner, queue, credential store, automatic retry or provider fallback.
Three consecutive transient failures in 60 seconds stop new requests briefly.
Success or a new resource revision breaks the streak; DB state survives restart.
"""
from datetime import timedelta
from sqlalchemy import select
from ...models import LlmAttempt, now
from ..engines.contract import EngineFailure

TRANSIENT=frozenset(('engine_timeout','engine_provider_rate_limited','engine_provider_temporary'))
FAILURE_CODES=TRANSIENT|{'engine_provider_authentication'}


def selection(snapshot,provider,model):
    result={'provider':provider,'model':model}
    if (snapshot.get('provider'),snapshot.get('model'))==(provider,model):
        result['reasoning_effort']=snapshot.get('reasoning_effort')
        authority=snapshot.get('connection_authority') or {}
        if authority.get('mode')=='installation_resource':
            result.update(resource_id=authority.get('resource_id'),resource_revision=authority.get('resource_revision'))
    return result


async def require_ready(db,run,provider,model):
    selected=selection(run.engine_snapshot or {},provider,model)
    route=lambda value:{k:v for k,v in value.items() if k!='reasoning_effort'}
    rows=list(await db.scalars(select(LlmAttempt).where(LlmAttempt.workspace_id==run.workspace_id,
        LlmAttempt.provider==provider,LlmAttempt.model==model,LlmAttempt.finished_at>=now()-timedelta(seconds=60)
    ).order_by(LlmAttempt.finished_at.desc(),LlmAttempt.id).limit(3)))
    if len(rows)==3 and all(row.status=='failed' and (row.trace or {}).get('failure_code') in TRANSIENT
            and route((row.trace or {}).get('engine_selection') or {})==route(selected) for row in rows):
        raise EngineFailure('engine_resource_cooling_down')
