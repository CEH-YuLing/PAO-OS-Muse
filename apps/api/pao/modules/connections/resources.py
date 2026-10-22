"""Atomic model admission by SME; authority stays in the existing gates.

Workspace KEY SHARE -> scoped advisory -> Run/Attempt/Lease. No network inside
the admission transaction. Daily UTC estimates are not provider billing.
"""
import hashlib
import asyncio
import inspect
from functools import wraps
from datetime import timedelta
from sqlalchemy import select, text, func
from ...models import Workspace, TenantResourcePolicy, TenantModelLease, LlmAttempt, now
from ..engines.contract import EngineFailure

DEFAULTS={'daily_model_calls':500,'daily_model_tokens':1000000,'concurrent_models':2}
CEILINGS={'daily_model_calls':10000,'daily_model_tokens':10000000,'concurrent_models':8}
CALL_TIMEOUT=180
CLOSE_TIMEOUT=10
LEASE_SECONDS=240  # Hard invocation + close deadline + safety margin.
ACCOUNTING_REQUIRED='tenant_resource_accounting_required'


def bounded(method):
    if inspect.isasyncgenfunction(method):
        @wraps(method)
        async def stream(*args,**kwargs):
            async with asyncio.timeout(CALL_TIMEOUT):
                source=method(*args,**kwargs)
                try:
                    async for value in source:yield value
                finally:
                    async with asyncio.timeout(CLOSE_TIMEOUT):await source.aclose()
        return stream
    @wraps(method)
    async def call(*args,**kwargs):
        async with asyncio.timeout(CALL_TIMEOUT):return await method(*args,**kwargs)
    return call


async def lock(db,wid):
    workspace=await db.scalar(select(Workspace.id).where(Workspace.id==wid)
        .with_for_update(read=True,key_share=True))
    if workspace is None:raise EngineFailure('tenant_resource_scope_missing')
    key=int.from_bytes(hashlib.sha256(('pao-resource-v1:'+wid).encode()).digest()[:8],'big',signed=True)
    await db.execute(text('SELECT pg_advisory_xact_lock(:key)'),{'key':key})


async def policy(db,wid):
    row=await db.get(TenantResourcePolicy,wid,populate_existing=True)
    return {'version':row.version if row else 0,**{key:getattr(row,key) if row else value for key,value in DEFAULTS.items()}}


async def require_accounted(db,wid):
    # Defaults are real caps too. Neither absence of a policy row nor disabling
    # chat features authorizes legacy inference without a ledger/deadline.
    # This guard is only for the unaccounted path, not model management probes.
    raise EngineFailure(ACCOUNTING_REQUIRED)


def require_run_accounting(snapshot):
    # Never invent policy/pins for previously queued unknown work at execution.
    if not isinstance(snapshot,dict) or not isinstance(snapshot.get('chat_policy'),dict):
        raise EngineFailure(ACCOUNTING_REQUIRED)


async def reap(db,wid):
    """Expired bounded invocations are unknown/failed, never retried/refunded."""
    current=now()
    rows=list(await db.scalars(select(TenantModelLease).where(TenantModelLease.workspace_id==wid,
        TenantModelLease.status=='active',TenantModelLease.expires_at<=current).with_for_update()))
    for row in rows:
        if row.attempt_id:
            attempt=await db.scalar(select(LlmAttempt).where(LlmAttempt.id==row.attempt_id,
                LlmAttempt.workspace_id==wid).with_for_update())
            if attempt.status=='started':
                attempt.status='failed';attempt.finished_at=current
                # Nullable actual usage and reservations stay intact.
        row.status='expired';row.released_at=current
    await db.flush()


async def usage(db,wid):
    day=now().replace(hour=0,minute=0,second=0,microsecond=0)
    charge=func.greatest(LlmAttempt.estimated_input_tokens,func.coalesce(LlmAttempt.input_tokens,0))+func.greatest(
        LlmAttempt.reserved_output_tokens,func.coalesce(LlmAttempt.output_tokens,0),func.coalesce(LlmAttempt.estimated_output_tokens,0))
    calls,tokens,unknown=(await db.execute(select(func.count(),func.coalesce(func.sum(charge),0),
        func.count().filter(LlmAttempt.usage_state!='reported')).where(LlmAttempt.workspace_id==wid,
            LlmAttempt.created_at>=day))).one()
    probes,probe_tokens=(await db.execute(select(func.count(),func.coalesce(func.sum(TenantModelLease.reserved_tokens),0)).where(
        TenantModelLease.workspace_id==wid,TenantModelLease.kind.in_(('management_probe','embedding')),TenantModelLease.created_at>=day))).one()
    active=await db.scalar(select(func.count()).select_from(TenantModelLease).where(
        TenantModelLease.workspace_id==wid,TenantModelLease.status=='active'))
    # Pre-migration started attempts remain conservative. No blind recovery of
    # invocations that lack a hard deadline/pin from this checkpoint.
    legacy=await db.scalar(select(func.count()).select_from(LlmAttempt).where(LlmAttempt.workspace_id==wid,
        LlmAttempt.status=='started',~select(TenantModelLease.id).where(TenantModelLease.attempt_id==LlmAttempt.id).exists()))
    return {'period_start':day.isoformat(),'calls':calls+probes,'reserved_or_reported_tokens':tokens+probe_tokens,
        'unknown_usage_calls':unknown+probes,'active_models':active+legacy,
        'billing_amount':None,'provider_subscription_remaining':None}


async def admit(db,wid,actor,kind,key,tokens,attempt=None,embedding_pin=None,provider_managed=False):
    # Caller holds lock before subordinate rows. Retries cannot resend even an
    # expired lease; key is a durable single-invocation identity, not a job id.
    if await db.scalar(select(TenantModelLease.id).where(TenantModelLease.workspace_id==wid,
        TenantModelLease.kind==kind,TenantModelLease.request_key==key)):
        raise EngineFailure('tenant_resource_replay_denied')
    await reap(db,wid)
    limits=await policy(db,wid);current=await usage(db,wid)
    if current['calls']>=limits['daily_model_calls']:raise EngineFailure('tenant_model_daily_calls_exhausted')
    explicit=await db.get(TenantResourcePolicy,wid) if provider_managed else None
    if (not provider_managed or explicit is not None) and current['reserved_or_reported_tokens']+tokens>limits['daily_model_tokens']:
        raise EngineFailure('tenant_model_daily_tokens_exhausted')
    if current['active_models']>=limits['concurrent_models']:raise EngineFailure('tenant_model_concurrency_exhausted')
    stamp=now()
    row=TenantModelLease(workspace_id=wid,actor_id=actor,kind=kind,request_key=key,attempt_id=attempt,
        policy_version=limits['version'],reserved_tokens=tokens if kind=='embedding' else 96 if kind=='management_probe' else 0,
        embedding_pin=embedding_pin,created_at=stamp,expires_at=stamp+timedelta(seconds=15 if kind=='embedding' else LEASE_SECONDS))
    db.add(row);return row


async def release(db,wid,*,attempt=None,lease=None):
    query=select(TenantModelLease).where(TenantModelLease.workspace_id==wid,TenantModelLease.status=='active')
    query=query.where(TenantModelLease.attempt_id==attempt) if attempt else query.where(TenantModelLease.id==lease)
    row=await db.scalar(query.with_for_update())
    if row:row.status='released';row.released_at=now()
