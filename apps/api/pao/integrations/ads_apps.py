"""Tenant app selection. No ambient configuration mutation or secret responses.

An absent selection is explicitly legacy managed mode. A persisted BYO selection
never falls back to host credentials. Rotation fences every connection in SME.
"""
import hashlib
import hmac
import json
import re
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator
from sqlalchemy import select, text

from ..access import membership
from ..config import settings
from ..db import Session
from ..models import Workspace, Member, User
from ..modules.connections.read_authority import lock_scope

PROVIDERS=('meta','google')
DENIED='ads_app_binding_changed'


class AppSave(BaseModel):
    model_config=ConfigDict(extra='forbid')
    mode: Literal['managed','byo']
    expected_revision: int=Field(ge=0)
    consent: Literal[True]
    client_id: str=Field(default='',max_length=256)
    client_secret: SecretStr | None=None
    api_version: str=Field(default='',max_length=16)
    developer_token: SecretStr | None=None
    login_customer_id: str=Field(default='',pattern=r'^(|[0-9]{10})$')

    @model_validator(mode='after')
    def fields(self):
        if self.mode=='managed' and (self.client_id or self.client_secret is not None or self.api_version or self.developer_token is not None or self.login_customer_id):
            raise ValueError('managed credentials are server-owned')
        for secret in (self.client_secret,self.developer_token):
            if secret is not None and not re.fullmatch(r'[A-Za-z0-9._~+/-]{8,512}',secret.get_secret_value()):
                raise ValueError('invalid credential')
        return self


class AppStatus(BaseModel):
    workspace_id: str
    provider: Literal['meta','google']
    mode: Literal['managed','byo']
    revision: int
    explicit_selection: bool
    client_id: str
    api_version: str
    redirect_uri: str
    secret_present: bool
    developer_token_present: bool
    login_customer_id: str
    platform_enabled: bool
    configured: bool
    external_verified: bool=False
    reconnect_required: bool


@dataclass(frozen=True)
class Context:
    config: object=field(repr=False)
    binding: str
    explicit: bool
    mode: str
    revision: int


def error(provider,reason):
    from .meta.client import MetaError
    from .google_ads.client import GoogleAdsError
    return (MetaError if provider=='meta' else GoogleAdsError)(reason)


async def resolve(db,wid,provider):
    assert provider in PROVIDERS
    row=(await db.execute(text('SELECT * FROM ads_app_configs WHERE workspace_id=:wid AND provider=:p'),{'wid':wid,'p':provider})).mappings().one_or_none()
    c=settings().model_copy(deep=True)
    mode=row['mode'] if row else 'managed';revision=row['revision'] if row else 0
    payload={}
    if mode=='byo':
        try:
            from .meta.client import decrypt
            payload=json.loads(decrypt(row['credential_ciphertext']))
            if not isinstance(payload,dict):raise ValueError()
            prefix='meta' if provider=='meta' else 'google_ads'
            fields={'app_id':'client_id','app_secret':'client_secret','graph_api_version':'api_version'} if provider=='meta' else {'client_id':'client_id','client_secret':'client_secret','api_version':'api_version','developer_token':'developer_token','login_customer_id':'login_customer_id'}
            for target,source in fields.items():setattr(c,prefix+'_'+target,payload.get(source,''))
        except Exception:raise error(provider,'ads_app_credential_unreadable') from None
    keys=('meta_app_id','meta_app_secret','meta_graph_api_version','meta_redirect_uri') if provider=='meta' else ('google_ads_client_id','google_ads_client_secret','google_ads_api_version','google_ads_redirect_uri','google_ads_developer_token','google_ads_login_customer_id')
    value={'workspace_id':wid,'provider':provider,'mode':mode,'revision':revision,**{key:getattr(c,key) for key in keys}}
    # HMAC prevents a returned/internal pin from becoming a credential oracle.
    binding=hmac.new(c.integration_encryption_key.encode(),json.dumps(value,sort_keys=True).encode(),hashlib.sha256).hexdigest()
    return Context(c,binding,bool(row),mode,revision)


def validate(context,provider):
    from .meta.client import configured as meta_ready
    from .google_ads.client import configured as google_ready
    if provider=='meta' and context.mode=='managed':
        from .meta.app_config import runtime_ready
        if not runtime_ready():raise error(provider,'meta_app_restart_required')
    (meta_ready if provider=='meta' else google_ready)(context.config)


async def bound(db,conn,provider):
    context=await resolve(db,conn.workspace_id,provider)
    validate(context,provider)
    if conn.app_binding!=context.binding:
        raise error(provider,DENIED)
    return context


async def valid(db,conn,provider):
    try:await bound(db,conn,provider);return True
    except Exception:return False


async def matches(db,conn,provider):
    """Stored-data authority also fences a changed managed app, without probing it."""
    if not conn:return True
    try:
        context=await resolve(db,conn.workspace_id,provider)
        return conn.app_binding==context.binding
    except Exception:return False


def invocation(conn,provider,job=None,*,binding):
    """Hold current tenant/source authority THROUGH each HTTP request.

    Config mutation takes an exclusive Workspace lock. No changed credentials
    can be substituted into a queued client; paging/retries/refresh recheck.
    """
    wid,cid,version,pin=conn.workspace_id,conn.id,conn.version,conn.app_binding
    @asynccontextmanager
    async def guard():
        from ..models import MetaConnection,GoogleAdsConnection
        from ..modules.connections import ads_authority
        async with Session.begin() as db:
            await lock_scope(db,wid)
            model=MetaConnection if provider=='meta' else GoogleAdsConnection
            source=await db.get(model,cid,with_for_update={'read':True})
            if not source or source.workspace_id!=wid or source.version!=version or source.app_binding!=pin:
                raise error(provider,DENIED)
            if (await resolve(db,wid,provider)).binding!=binding:
                raise error(provider,DENIED)
            from .meta.sync import permitted as meta_permitted
            from .google_ads.sync import permitted as google_permitted
            if not await (meta_permitted if provider=='meta' else google_permitted)(db,source,version,job):
                raise error(provider,DENIED)
            yield
    return guard


async def status(db,who,wid,provider):
    await membership(db,wid,who)
    from ..models import MetaConnection,GoogleAdsConnection
    context=await resolve(db,wid,provider);c=context.config
    prefix='meta' if provider=='meta' else 'google_ads'
    enabled=getattr(c,prefix+'_enabled')
    try:validate(context,provider);ready=True
    except Exception:ready=False
    model=MetaConnection if provider=='meta' else GoogleAdsConnection
    connection=await db.scalar(select(model).where(model.workspace_id==wid,model.user_id==who.id))
    return AppStatus(workspace_id=wid,provider=provider,mode=context.mode,revision=context.revision,
        explicit_selection=context.explicit,client_id=c.meta_app_id if provider=='meta' else c.google_ads_client_id,
        api_version=c.meta_graph_api_version if provider=='meta' else c.google_ads_api_version,
        redirect_uri=getattr(c,prefix+'_redirect_uri'),secret_present=bool(c.meta_app_secret if provider=='meta' else c.google_ads_client_secret),
        developer_token_present=bool(c.google_ads_developer_token) if provider=='google' else False,
        login_customer_id=c.google_ads_login_customer_id if provider=='google' else '',platform_enabled=enabled,configured=ready,
        reconnect_required=not connection or connection.status!='connected' or connection.app_binding!=context.binding)


async def save(db,who,wid,provider,body):
    member=await membership(db,wid,who)
    if member.role not in ('owner','admin'):raise HTTPException(403,'ads_app_manager_required')
    await db.scalar(select(Workspace.id).where(Workspace.id==wid).with_for_update())
    member=await db.get(Member,(wid,who.id),with_for_update={'read':True},populate_existing=True)
    user=await db.get(User,who.id,with_for_update={'read':True},populate_existing=True)
    if not member or member.role not in ('owner','admin') or not user or not user.active:raise HTTPException(403,'ads_app_manager_required')
    old=(await db.execute(text('SELECT * FROM ads_app_configs WHERE workspace_id=:wid AND provider=:p FOR UPDATE'),{'wid':wid,'p':provider})).mappings().one_or_none()
    revision=old['revision'] if old else 0
    if body.expected_revision!=revision:raise HTTPException(409,'ads_app_revision_conflict')
    encrypted=None
    if body.mode=='byo':
        if not body.client_secret:raise HTTPException(422,'ads_app_secret_required')
        if provider=='meta' and (not re.fullmatch(r'[0-9]{1,64}',body.client_id) or not re.fullmatch(r'v[0-9]+\.[0-9]+',body.api_version) or body.developer_token or body.login_customer_id):raise HTTPException(422,'ads_app_invalid_input')
        if provider=='google' and (not re.fullmatch(r'[A-Za-z0-9_-]+\.apps\.googleusercontent\.com',body.client_id) or not re.fullmatch(r'v[0-9]+',body.api_version)):raise HTTPException(422,'ads_app_invalid_input')
        from .meta.client import encrypt
        try:encrypted=encrypt(json.dumps({'client_id':body.client_id,'client_secret':body.client_secret.get_secret_value(),'api_version':body.api_version,
            'developer_token':body.developer_token.get_secret_value() if body.developer_token else '', 'login_customer_id':body.login_customer_id}))
        except Exception:raise HTTPException(503,'ads_app_encryption_unavailable') from None
    await db.execute(text('''INSERT INTO ads_app_configs(workspace_id,provider,mode,revision,credential_ciphertext)
        VALUES(:wid,:p,:mode,1,:secret) ON CONFLICT(workspace_id,provider) DO UPDATE
        SET mode=EXCLUDED.mode,revision=ads_app_configs.revision+1,credential_ciphertext=EXCLUDED.credential_ciphertext,updated_at=now()'''),
        {'wid':wid,'p':provider,'mode':body.mode,'secret':encrypted})
    # Database trigger invalidates tokens/states/jobs, including first selection.
    await db.execute(text('INSERT INTO ads_app_audits(id,created_at,workspace_id,provider,actor_id,revision,mode) VALUES(:id,now(),:wid,:p,:actor,:rev,:mode)'),
        {'id':str(__import__('uuid').uuid4()),'wid':wid,'p':provider,'actor':who.id,'rev':revision+1,'mode':body.mode})
    await db.commit()
    return await status(db,who,wid,provider)
