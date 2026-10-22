"""Local catalogue admissions share the SME metadata pool, not inference quota.

Read members stay read members; model selection still requires the owned session.
No locks/transaction across Ollama I/O; publication and cleanup have separate
short transactions. Never grant tools, pull models or send remote requests.
"""
import asyncio
import time
from contextlib import asynccontextmanager
from fastapi import HTTPException
from sqlalchemy import select
from ...models import User,Member
from ...config import settings
from ..connections import metadata_resources as resources
from .service import local_url,model_name
from .contract import EngineFailure

TIMEOUT=5


def endpoint_pin():
    try:return local_url()
    except EngineFailure:raise HTTPException(503,'engine_local_endpoint_invalid') from None


async def actor(db,wid,who,write=False):
    from ...auth import check_session
    user=await db.scalar(select(User).where(User.id==who.id).with_for_update(read=True)
        .execution_options(populate_existing=True))
    member=await db.scalar(select(Member).where(Member.workspace_id==wid,Member.user_id==who.id)
        .with_for_update(read=True).execution_options(populate_existing=True))
    if not user or not user.active or not member or who.expires<=time.time() or (write and member.role=='viewer'):
        raise HTTPException(403,'engine_metadata_authority_changed')
    # Keep domain authority failures stable; independently reject a session
    # revoked while discovery released its database transaction for I/O.
    await check_session(db, who)
    if not settings().engine_contract_enabled:raise HTTPException(503,'engine_contract_disabled')


@asynccontextmanager
async def discovery(db,wid,who,loader,kind,request_key,check=None):
    # Pool before member/session; no legacy session lock before this admission.
    await resources.lock(db,wid)
    await actor(db,wid,who,write=check is not None)
    initial=await check() if check else None
    expected=initial[1] if initial else None
    url=endpoint_pin()
    lease=await resources.admit(db,wid,who.id,kind,request_key,'ollama:'+url+':'+str(expected))
    lid=lease.id
    await db.commit()
    try:
        await resources.require_current(wid,lid)
        if not settings().engine_contract_enabled:raise HTTPException(503,'engine_contract_disabled')
        if endpoint_pin()!=url:raise HTTPException(409,'engine_metadata_source_changed')
        result=[];error=None
        try:
            async with asyncio.timeout(TIMEOUT):
                result=await loader()
                if not isinstance(result,list) or len(result)>500:
                    raise EngineFailure('engine_local_catalogue_invalid')
                result=sorted({model_name(value) for value in result})
        except Exception:
            # Includes native/adapted timeouts and malformed response. Never raw
            # exception text, local paths, model metadata or credential fields.
            result=[];error='engine_local_offline'
        await actor(db,wid,who,write=check is not None)
        if endpoint_pin()!=url:raise HTTPException(409,'engine_metadata_source_changed')
        current=await check() if check else None
        if current and current[1]!=expected:raise HTTPException(409,'engine_metadata_session_changed')
        yield result,error,current[0] if current else None
    finally:
        # Never wait for the metadata pool while holding a publication lock.
        await db.rollback()
        await resources.finish(wid,lid)
