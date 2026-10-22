"""Bounded local embedding admission; shared model pool, no raw text ledger."""
import asyncio,hashlib,math
from uuid import uuid4
from sqlalchemy import select
from ...auth import Principal
from ...config import settings
from ...db import Session
from ...gateway import OllamaGateway
from ...models import User,Member,Brand,TenantModelLease,now
from ..engines.contract import EngineFailure
from ..engines.service import local_url,model_name
from . import resources


async def authorize(db,wid,actor,brand,brain,write,check,lock=False):
    user=await db.get(User,actor,populate_existing=True)
    member=await db.get(Member,(wid,actor),populate_existing=True)
    if lock:
        member=await db.scalar(select(Member).where(Member.workspace_id==wid,Member.user_id==actor)
            .with_for_update(read=True).execution_options(populate_existing=True))
    if not user or not user.active or not member or (write and member.role=='viewer'):
        raise EngineFailure('embedding_access_revoked')
    if brand:
        row=await db.get(Brand,brand,populate_existing=True)
        if not row or row.workspace_id!=wid:raise EngineFailure('embedding_scope_denied')
    if brain:
        from ..brains.access import require_brain
        row=await require_brain(db,Principal(actor,0),brain,write)
        if row.workspace_id!=wid or row.brand_id!=brand:raise EngineFailure('embedding_scope_denied')
    if check:await check(db)


def vector(value):
    if not isinstance(value,(list,tuple)) or len(value)!=768:raise EngineFailure('embedding_invalid_vector')
    if any(type(item) not in (int,float) for item in value):raise EngineFailure('embedding_invalid_vector')
    result=[float(item) for item in value]
    if not all(math.isfinite(item) and abs(item)<=100000 for item in result) or not any(result):
        raise EngineFailure('embedding_invalid_vector')
    return result


async def embed(value,*,workspace_id,actor_id,brand_id=None,brain_id=None,write=False,
                purpose,request_key=None,gateway=None,check=None,engine_pin=None):
    # All host settings are captured before awaiting. No cloud router/model pull.
    url=local_url(engine_pin['url'] if engine_pin else None)
    model=model_name(engine_pin['model'] if engine_pin else settings().embedding_model)
    if not isinstance(value,str) or not value or len(value.encode('utf-8'))>8192:
        raise EngineFailure('embedding_input_limit')
    # Byte reservation is deliberately conservative; vector API here reports
    # no trustworthy token usage through the adapter. Never bill unknown as 0.
    tokens=len(value.encode('utf-8'))
    key=hashlib.sha256((request_key or str(uuid4())).encode()).hexdigest()
    pin={'version':1,'provider':'ollama','model':model,'endpoint_hash':hashlib.sha256(url.encode()).hexdigest(),
         'brain_id':brain_id,'brand_id':brand_id,'purpose':purpose,
         'input_hash':hashlib.sha256(value.encode()).hexdigest(),'write':write}
    async with Session.begin() as db:
        await resources.lock(db,workspace_id)
        await authorize(db,workspace_id,actor_id,brand_id,brain_id,write,check)
        lease=await resources.admit(db,workspace_id,actor_id,'embedding',key,tokens,embedding_pin=pin)
        await db.flush();lid=lease.id
    try:
        async with Session() as db:
            row=await db.get(TenantModelLease,lid)
            if not row or row.status!='active' or row.expires_at<=now():raise EngineFailure('embedding_lease_expired')
            await authorize(db,workspace_id,actor_id,brand_id,brain_id,write,check)
        async with asyncio.timeout(min(2,settings().memory_timeout_seconds)):
            # Test injection is internal only; it still requires real admission.
            result=vector(await (gateway or OllamaGateway(url=url,embedding_model=model)).embed(value))
        async with Session() as db:
            row=await db.get(TenantModelLease,lid)
            if not row or row.status!='active' or row.expires_at<=now():raise EngineFailure('embedding_lease_expired')
            await authorize(db,workspace_id,actor_id,brand_id,brain_id,write,check)
        return result,model
    finally:
        # Timeout/cancel/invalid/unknown results retain the daily debit; release
        # the slot only. Lost worker is reaped, never resent under the same key.
        async with Session.begin() as db:
            await resources.lock(db,workspace_id)
            await resources.release(db,workspace_id,lease=lid)
