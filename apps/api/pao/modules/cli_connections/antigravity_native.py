"""Local personal native catalog only; not a model execution adapter.

Explicit POST may use the installed CLI's own machine session. No OAuth/token
reader, prompt, arbitrary args, global config edits or API fallback exists.
"""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
from uuid import uuid4
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, StrictBool
from sqlalchemy.ext.asyncio import AsyncSession
from ...auth import Principal, principal, check_session, rate_limit
from ...access import membership
from ...config import ROOT
from ...db import database
from .antigravity_smoke import native_smoke, SmokeFailure, MODEL

router = APIRouter(prefix='/v1/workspaces/{workspace_id}/antigravity-native', tags=['native-antigravity'])
CONFIG = ROOT / '.runtime/antigravity-native.json'
_state = {}
_busy = set()
_generation = {}


class Connect(BaseModel):
    model_config = ConfigDict(extra='forbid')
    acknowledge_local_session: StrictBool
    acknowledge_unsupported_consumer_wrapper: StrictBool


class SmokeRequest(Connect):
    acknowledge_fixed_model_test: StrictBool


def configuration(workspace, actor):
    try:
        if CONFIG.is_symlink() or CONFIG.is_junction() or CONFIG.stat().st_size > 8192: raise ValueError()
        raw = CONFIG.read_bytes(); value = json.loads(raw)
        if set(value) != {'version','workspace_id','actor_id','binary','binary_sha256','allow_catalog'}: raise ValueError()
        if value['version'] != 1 or value['allow_catalog'] is not True: raise ValueError()
        if (value['workspace_id'], value['actor_id']) != (workspace, actor): raise ValueError()
        path = Path(value['binary'])
        expected = Path(os.environ['LOCALAPPDATA']) / 'agy/bin/agy.exe'
        if os.name != 'nt' or path != expected or not re.fullmatch('[a-f0-9]{64}', value['binary_sha256']): raise ValueError()
        if any(p.is_symlink() or p.is_junction() for p in (path, *path.parents)): raise ValueError()
        return value, hashlib.sha256(raw).hexdigest()
    except (OSError,ValueError,TypeError,KeyError):
        raise HTTPException(503, 'antigravity_native_not_provisioned_for_actor') from None


async def authorize(db, workspace, who):
    await check_session(db, who)
    member = await membership(db, workspace, who)
    if member.role not in ('owner','admin'): raise HTTPException(403, 'antigravity_native_manager_required')
    return configuration(workspace, who.id)


def catalog_text(raw):
    if not isinstance(raw, bytes) or len(raw) > 262144: raise ValueError()
    text = raw.decode('utf-8', errors='strict')
    values = []
    for line in text.splitlines():
        # Native installed models format: stable slug, TAB/spaces, display name.
        columns = line.strip().split()
        if not columns: continue
        slug = columns[0]
        if re.fullmatch(r'[a-z][a-z0-9]*(?:-[a-z0-9][a-z0-9._-]*)+', slug) and len(slug) <= 120:
            if slug in values: raise ValueError()
            values.append(slug)
    if not 1 <= len(values) <= 100: raise ValueError()
    return values


async def native_catalog(cfg):
    binary = Path(cfg['binary'])
    digest = await asyncio.to_thread(lambda: hashlib.sha256(binary.read_bytes()).hexdigest())
    if digest != cfg['binary_sha256']: raise SmokeFailure('binary_changed')
    allowed = ('SystemRoot','WINDIR','USERPROFILE','HOMEDRIVE','HOMEPATH','APPDATA',
               'LOCALAPPDATA','TEMP','TMP','PATH','USERNAME','USERDOMAIN')
    env = {key: os.environ[key] for key in allowed if key in os.environ}
    env['NO_COLOR'] = '1'
    root = ROOT / '.runtime/antigravity-catalog-cwd'
    root.mkdir(exist_ok=True)
    if root.is_symlink() or root.is_junction(): raise ValueError('linked_cwd')
    # Only metadata command: no -p/model test/hook/tool permissions.
    with tempfile.TemporaryDirectory(prefix='request-', dir=root) as folder:
        process = None
        try:
            async with asyncio.timeout(25):
                process = await asyncio.create_subprocess_exec(str(binary), 'models', cwd=folder, env=env,
                    stdin=asyncio.subprocess.DEVNULL, stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
                async def bounded(stream):
                    chunks=[]; size=0
                    while chunk := await stream.read(8192):
                        size += len(chunk)
                        if size > 262144: raise ValueError('output_bound')
                        chunks.append(chunk)
                    return b''.join(chunks)
                stdout, _ = await asyncio.gather(bounded(process.stdout), bounded(process.stderr))
                if await process.wait() != 0: raise ValueError('catalog_failed')
                models = catalog_text(stdout)
                if await asyncio.to_thread(lambda: hashlib.sha256(binary.read_bytes()).hexdigest()) != digest:
                    raise ValueError('binary_changed')
                return models
        finally:
            if process and process.returncode is None:
                process.kill()
                await asyncio.wait_for(process.wait(), 5)


def view(workspace, actor, pin):
    saved = _state.get((workspace, actor))
    if saved and saved['pin'] != pin: saved = None
    return {'workspace_id': workspace, 'actor_id': actor, 'provider': 'antigravity_native',
            'status': 'catalog_available' if saved else 'not_checked',
            'models': saved['models'] if saved else [], 'observed_at': saved['at'] if saved else None,
            'scope': 'local_personal_machine_session', 'provider_support_confirmed': False,
            'inference_enabled': False, 'inference_called': False, 'credentials_stored_in_PAO': False,
            'busy': (workspace, actor) in _busy}


def headers(response):
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Pragma'] = 'no-cache'


@router.get('')
async def status(workspace_id: UUID, response: Response, who: Principal=Depends(principal), db: AsyncSession=Depends(database)):
    headers(response)
    _, pin = await authorize(db, str(workspace_id), who)
    return view(str(workspace_id), who.id, pin)


@router.post('/connect')
async def connect(workspace_id: UUID, body: Connect, request: Request, response: Response,
                  who: Principal=Depends(principal), db: AsyncSession=Depends(database)):
    headers(response); workspace = str(workspace_id)
    cfg, pin = await authorize(db, workspace, who)
    if not body.acknowledge_local_session or not body.acknowledge_unsupported_consumer_wrapper:
        raise HTTPException(422, 'antigravity_native_ack_required')
    await rate_limit(request.app.state.redis, 'antigravity-native-catalog', workspace+':'+who.id, 5, 60)
    key = (workspace, who.id)
    if key in _busy: raise HTTPException(409, 'antigravity_native_busy')
    stamp = _generation.get(key, 0)
    _busy.add(key); _state.pop(key, None)
    try:
        try: models = await native_catalog(cfg)
        except SmokeFailure as exc:
            raise HTTPException(409, 'antigravity_native_'+exc.code) from None
        except (OSError, ValueError, TimeoutError, UnicodeError):
            raise HTTPException(503, 'antigravity_native_catalog_unavailable') from None
        _, current = await authorize(db, workspace, who)
        if pin != current or stamp != _generation.get(key, 0): raise HTTPException(409, 'antigravity_native_scope_changed')
        _state[key] = {'pin': pin, 'models': models, 'at': int(time.time())}
        return view(workspace, who.id, pin)
    finally: _busy.discard(key)


@router.post('/test')
async def test_model(workspace_id: UUID, body: SmokeRequest, request: Request, response: Response,
                     who: Principal=Depends(principal), db: AsyncSession=Depends(database)):
    headers(response); workspace = str(workspace_id)
    cfg, pin = await authorize(db, workspace, who)
    if not body.acknowledge_local_session or not body.acknowledge_unsupported_consumer_wrapper or not body.acknowledge_fixed_model_test:
        raise HTTPException(422,'antigravity_native_ack_required')
    await rate_limit(request.app.state.redis,'antigravity-native-smoke',workspace+':'+who.id,2,60)
    key = (workspace,who.id)
    if key in _busy: raise HTTPException(409,'antigravity_native_busy')
    saved = _state.get(key)
    if not saved or saved['pin'] != pin or MODEL not in saved['models']:
        raise HTTPException(409,'antigravity_native_connect_first')
    generation = _generation.get(key,0)
    async def recheck():
        _, current = await authorize(db,workspace,who)
        if current != pin or generation != _generation.get(key,0):
            raise HTTPException(409,'antigravity_native_scope_changed')
    _busy.add(key)
    try:
        try:
            result = await native_smoke(cfg,recheck)
        except SmokeFailure as exc:
            raise HTTPException(409,'antigravity_native_'+exc.code) from None
        except (OSError,ValueError,TimeoutError,UnicodeError):
            raise HTTPException(503,'antigravity_native_test_unverified') from None
        await recheck()
        return {**result,'workspace_id':workspace,'actor_id':who.id,
                'attempt_id':str(uuid4()),'general_chat_enabled':False,'provider_support_confirmed':False}
    finally:
        _busy.discard(key)


@router.post('/disconnect')
async def disconnect(workspace_id: UUID, response: Response, who: Principal=Depends(principal), db: AsyncSession=Depends(database)):
    headers(response); workspace = str(workspace_id)
    _, pin = await authorize(db, workspace, who)
    key = (workspace, who.id)
    _generation[key] = _generation.get(key, 0) + 1
    _state.pop(key, None)
    return {**view(workspace, who.id, pin), 'provider_logout_performed': False}
