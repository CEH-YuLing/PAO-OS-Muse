"""Installation-wide Muse metadata connection, not yet an inference adapter.

No credentials are imported, no session or model turn is created. The pending
execution boundary is explicit: catalog discovery never admits Chat or Jobs.
"""
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession
from ...access import membership
from ...auth import Principal, principal, check_session
from ...config import ROOT
from ...db import database
from ..installation_ai.catalog import normalize
from ..installation_ai.service import manager

router = APIRouter(prefix='/v1/muse-client', tags=['muse-client'])
STATE = ROOT / '.runtime/muse-client.json'
VERSION = '1.4.10-R6427.1'
SHA = '893a04138b81d844cc53e25216fafe0cbf7c786423534b93aacf1419a840f6b7'
SCHEMA = 'sha256:5d3b43e5ccdb7dc4f5a32c380f5f2cde0f10e3059b93610afb2e73f73b1d914c'
_lock = asyncio.Lock()


class Command(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_key: UUID
    expected_revision: int = Field(ge=0, strict=True)


class MuseFailure(RuntimeError):
    pass


def safe_path(path):
    if any(p.is_symlink() or p.is_junction() for p in (path, *path.parents)):
        raise MuseFailure('muse_linked_path')
    return path


def binary():
    if os.name != 'nt' or not os.environ.get('LOCALAPPDATA'):
        raise MuseFailure('muse_platform_unavailable')
    path = safe_path(Path(os.environ['LOCALAPPDATA']) / f'Programs/muse/muse-bin-{VERSION}.exe')
    if not path.is_file(): raise MuseFailure('muse_not_installed')
    if hashlib.sha256(path.read_bytes()).hexdigest() != SHA:
        raise MuseFailure('muse_binary_changed')
    return path


def catalog_rows(result):
    if (not isinstance(result, dict) or result.get('providerId') != 'meta'
            or result.get('source') != 'providerCatalog'):
        raise MuseFailure('muse_catalog_invalid')
    rows = result.get('models')
    if not isinstance(rows, list) or not 1 <= len(rows) <= 100:
        raise MuseFailure('muse_catalog_invalid')
    try:
        # `variants` is the complete selectable set; the similarly named
        # reasoningEffortVariants contains descriptions for only some tiers.
        return normalize([{'model': row['modelId'], 'display_name': row['displayLabel'],
            'reasoning_efforts': row['variants'], 'default_effort': row.get('defaultReasoningEffort'),
            'provider_output_modalities': ['text']} for row in rows])
    except (KeyError, TypeError, ValueError):
        raise MuseFailure('muse_catalog_invalid') from None


async def discover():
    from .muse_profile import Host, ProfileFailure
    path = await asyncio.to_thread(binary)
    host = Host(path,SCHEMA)
    try:
        async with asyncio.timeout(30):
            await host.open()
            account = await host.query('account/read')
            if account.get('state') not in ('accountLogin','loggedOut'):
                raise MuseFailure('muse_profile_account_not_subscription_login')
            models = catalog_rows(await host.query('model/list')) if account['state']=='accountLogin' else []
            if await asyncio.to_thread(lambda: hashlib.sha256(path.read_bytes()).hexdigest()) != SHA:
                raise MuseFailure('muse_binary_changed')
            return {'account_state':account['state'],'models':models,
                'observed_at':datetime.now(timezone.utc).isoformat(),'binary_version':VERSION,
                'binary_sha256':SHA,'schema_fingerprint':SCHEMA,'profile':'pao_isolated'}
    except MuseFailure:
        raise
    except (ProfileFailure,OSError,ValueError,TimeoutError):
        raise MuseFailure('muse_profile_connection_unavailable') from None
    finally:
        await host.close()


def read_state():
    safe_path(STATE)
    if not STATE.exists(): return {'revision':0,'connected':False,'models':[]}
    if not STATE.is_file() or STATE.stat().st_size > 65536:
        raise MuseFailure('muse_saved_state_invalid')
    try:
        value = json.loads(STATE.read_bytes())
        if not isinstance(value,dict) or type(value.get('revision')) is not int or value['revision'] < 1 or type(value.get('connected')) is not bool:
            raise ValueError()
        if not isinstance(value.get('models'),list): raise ValueError()
        if value['models']: value['models'] = normalize(value['models'])
        return value
    except (ValueError, TypeError, KeyError):
        raise MuseFailure('muse_saved_state_invalid') from None


def write_state(value):
    safe_path(STATE)
    fd, name = tempfile.mkstemp(prefix='muse-state-', suffix='.tmp', dir=STATE.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as stream:
            json.dump(value,stream,ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, STATE)
    finally:
        # Only the exact file just created by mkstemp, never a recursive delete.
        if os.path.exists(name): os.unlink(name)


def public(value, can_manage, inference=False):
    fields = ('revision','connected','models','observed_at','account_state','binary_version')
    safe = {k:value[k] for k in fields if k in value}
    if safe.get('models'): safe['models'] = normalize(safe['models'])
    return {**safe, 'can_manage':can_manage,
        'scope':'installation', 'connection_mode':'text_adapter' if inference else 'catalog_only', 'inference_enabled':inference,
        'inference_verified':False, 'quota_verified':False, 'provider_inference_calls':0,
        'execution_blocker':None if inference else 'muse_not_published', 'credentials_stored_in_PAO':False}


async def view(db,value,can_manage):
    from .muse_resource import available
    return public(value,can_manage,await available(db,value))


async def access(db, workspace, who):
    await check_session(db,who)
    await membership(db,str(workspace),who)
    return await manager(db,who.id)


@router.get('')
async def status(workspace_id:UUID,response:Response,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    response.headers['Cache-Control']='no-store'
    can_manage = await access(db,workspace_id,who)
    try: return await view(db,read_state(),can_manage)
    except MuseFailure as exc: raise HTTPException(409,str(exc)) from None


async def change(workspace_id, body, response, who, db, disconnect):
    response.headers['Cache-Control']='no-store'
    if not await access(db,workspace_id,who): raise HTTPException(403,'muse_installation_manager_required')
    if _lock.locked(): raise HTTPException(409,'muse_connection_busy')
    async with _lock:
        try:
            old = read_state()
            key = str(body.request_key)
            if old.get('request_key') == key:
                if old.get('request_actor') != who.id or old.get('request_disconnect') != disconnect or old.get('request_revision') != body.expected_revision:
                    raise HTTPException(409,'muse_request_conflict')
                # Reconcile an acknowledged metadata write whose DB publication
                # previously failed; never repeat native discovery or inference.
                if old.get('execution_adapter'):
                    from .muse_resource import publish
                    await publish(db,who.id,str(workspace_id),key,disconnect)
                    await db.commit()
                return await view(db,old,True)
            if old['revision'] != body.expected_revision: raise HTTPException(409,'muse_revision_conflict')
            data = {} if disconnect else await discover()
            # Recheck current PAO authority after native I/O and before publish.
            db.expire_all()
            if not await access(db,workspace_id,who): raise HTTPException(403,'muse_installation_manager_required')
            value = {**data,'revision':old['revision']+1,'connected':not disconnect,
                'models':data.get('models',[]),'request_key':key,'request_actor':who.id,
                'request_disconnect':disconnect,'request_revision':body.expected_revision}
            from .muse_resource import ADAPTER,publish
            if not disconnect and data.get('account_state')=='accountLogin' and data.get('binary_sha256')==SHA and data.get('schema_fingerprint')==SCHEMA and data.get('profile')=='pao_isolated':
                value['execution_adapter']=ADAPTER
            elif disconnect and old.get('execution_adapter'):value['execution_adapter']=ADAPTER
            write_state(value)
            if value.get('execution_adapter'):
                await publish(db,who.id,str(workspace_id),key,disconnect)
                await db.commit()
            return await view(db,value,True)
        except MuseFailure as exc: raise HTTPException(409,str(exc)) from None
        except Exception as exc:
            from ..engines.contract import EngineFailure
            if isinstance(exc,EngineFailure):raise HTTPException(409,exc.code) from None
            raise


@router.post('')
async def connect(workspace_id:UUID,body:Command,response:Response,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    return await change(workspace_id,body,response,who,db,False)


@router.delete('')
async def disconnect(workspace_id:UUID,body:Command,response:Response,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    return await change(workspace_id,body,response,who,db,True)


@router.post('/login')
async def login_start(workspace_id:UUID,response:Response,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    response.headers['Cache-Control']='no-store'
    if not await access(db,workspace_id,who): raise HTTPException(403,'muse_installation_manager_required')
    from .muse_profile import start_login, ProfileFailure
    try:
        result = await start_login(who.id,await asyncio.to_thread(binary),SCHEMA)
        db.expire_all()
        if not await access(db,workspace_id,who):
            from .muse_profile import cancel_login
            await cancel_login(who.id)
            raise HTTPException(403,'muse_installation_manager_required')
        return result
    except (ProfileFailure,OSError,ValueError,TimeoutError):
        raise HTTPException(409,'muse_login_unavailable') from None


@router.get('/login')
async def login_status(workspace_id:UUID,response:Response,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    response.headers['Cache-Control']='no-store'
    if not await access(db,workspace_id,who): raise HTTPException(403,'muse_installation_manager_required')
    from .muse_profile import status
    return status(who.id)


@router.delete('/login')
async def login_cancel(workspace_id:UUID,response:Response,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    response.headers['Cache-Control']='no-store'
    if not await access(db,workspace_id,who): raise HTTPException(403,'muse_installation_manager_required')
    from .muse_profile import cancel_login, status
    await cancel_login(who.id)
    return status(who.id)
