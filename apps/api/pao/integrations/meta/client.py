"""Explicit read-only Marketing API surface. OAuth exchange is the only POST."""
import asyncio
import hashlib
import hmac
import json
import random
import re
from urllib.parse import urlsplit
import httpx
from cryptography.fernet import Fernet, InvalidToken
from ...config import settings

FIELDS = {
    'accounts':'id,account_id,name,currency,timezone_name,account_status,business',
    'campaigns':'id,account_id,name,status,effective_status,objective,updated_time',
    'adsets':'id,account_id,campaign_id,name,status,effective_status,updated_time',
    'ads':'id,account_id,campaign_id,adset_id,name,status,effective_status,updated_time,creative{id,name}',
    'insights':'account_id,campaign_id,adset_id,ad_id,date_start,date_stop,impressions,clicks,spend,actions,action_values',
}
RESOURCE_FIELDS={
    'campaign':'id,account_id,name,status,effective_status,daily_budget,lifetime_budget,updated_time',
    'adset':'id,account_id,campaign_id,name,status,effective_status,daily_budget,lifetime_budget,updated_time',
    'ad':'id,account_id,campaign_id,adset_id,name,status,effective_status,updated_time',
}


class MetaError(Exception):
    """Only a local reason code may escape the transport."""


def cipher():
    try:
        return Fernet(settings().integration_encryption_key.encode())
    except (ValueError, TypeError):
        raise MetaError('meta_encryption_not_configured') from None


def encrypt(token):
    return cipher().encrypt(token.encode()).decode()


def decrypt(token):
    try:
        return cipher().decrypt(token.encode()).decode()
    except (InvalidToken, AttributeError, UnicodeError):
        raise MetaError('meta_credential_unreadable') from None


def configured(config=None):
    c=config or settings()
    if not c.meta_enabled or not c.meta_app_id.isdecimal() or not c.meta_app_secret or not re.fullmatch(r'v\d+\.\d+',c.meta_graph_api_version):
        raise MetaError('meta_not_configured')
    cipher()
    uri=urlsplit(c.meta_redirect_uri)
    if uri.username or uri.password or uri.query or uri.fragment or uri.path!='/v1/integrations/meta/callback' or not uri.hostname or not (uri.scheme=='https' or uri.scheme=='http' and uri.hostname in ('localhost','127.0.0.1')):
        raise MetaError('meta_invalid_redirect_uri')


class MetaClient:
    def __init__(self, token='', transport=None, sleep=asyncio.sleep, *, config=None, guard=None):
        self.config=config or settings().model_copy(deep=True);self.guard=guard
        configured(self.config)
        self.token=token;self.transport=transport;self.sleep=sleep

    async def _request(self, path, params=None, oauth=None, write_data=None):
        if self.guard:
            async with self.guard():return await self._perform(path,params,oauth,write_data)
        return await self._perform(path,params,oauth,write_data)

    async def _perform(self, path, params=None, oauth=None, write_data=None):
        params=dict(params or {})
        is_write=write_data is not None
        if oauth is not None and (path!='oauth/access_token' or is_write):
            raise MetaError('meta_write_forbidden')
        read_allowed=path in ('me','me/permissions','me/adaccounts') or re.fullmatch(r'act_\d+/(campaigns|adsets|ads|insights)',path) or re.fullmatch(r'(act_)?\d{1,64}',path)
        if oauth is None and not read_allowed:
            raise MetaError('meta_endpoint_forbidden')
        if is_write:
            if not settings().meta_write_enabled or not re.fullmatch(r'\d{1,64}',path):raise MetaError('meta_write_forbidden')
            if not isinstance(write_data,dict) or set(write_data) not in ({'status'},{'daily_budget'}):raise MetaError('meta_write_payload_invalid')
            if 'status' in write_data and write_data['status'] not in ('ACTIVE','PAUSED'):raise MetaError('meta_write_payload_invalid')
            if 'daily_budget' in write_data and (isinstance(write_data['daily_budget'],bool) or not isinstance(write_data['daily_budget'],int) or not 1<=write_data['daily_budget']<=10**12):raise MetaError('meta_write_payload_invalid')
        c=self.config
        headers={}
        if oauth is None:
            headers['Authorization']='Bearer '+self.token
            params['appsecret_proof']=hmac.new(c.meta_app_secret.encode(),self.token.encode(),hashlib.sha256).hexdigest()
        url=f'https://graph.facebook.com/{c.meta_graph_api_version}/{path}'
        attempts=1 if is_write else 3
        for attempt in range(attempts):
            try:
                async with httpx.AsyncClient(transport=self.transport,timeout=20,trust_env=False,follow_redirects=False) as client:
                    method='POST' if oauth is not None or is_write else 'GET'
                    async with client.stream(method,url,params=params,data=oauth if oauth is not None else write_data,headers=headers) as response:
                        raw=bytearray()
                        async for chunk in response.aiter_bytes():
                            raw.extend(chunk)
                            if len(raw)>2_000_000:raise MetaError('meta_response_too_large')
                        try:payload=json.loads(raw)
                        except (ValueError,TypeError):raise MetaError('meta_write_unknown' if is_write else 'meta_invalid_response') from None
                        if not isinstance(payload,dict):raise MetaError('meta_invalid_response')
                        error=payload.get('error') or {}
                        code=error.get('code') if isinstance(error,dict) else None
                        if code==190:raise MetaError('meta_reauthorization_required')
                        if code in (10,200):raise MetaError('meta_permission_denied')
                        transient=response.status_code==429 or response.status_code>=500 or code in (4,17,32,613,80004) or (isinstance(error,dict) and error.get('is_transient'))
                        if transient:
                            retry_after=response.headers.get('retry-after','0')
                            delay=float(retry_after) if retry_after.isdecimal() else 0
                            if is_write:raise MetaError('meta_write_unknown')
                            if attempt==2 or delay>10:raise MetaError('meta_rate_limited' if response.status_code==429 or code in (4,17,32,613,80004) else 'meta_provider_unavailable')
                            await self.sleep(max(delay,2**attempt)+random.random()/4)
                            continue
                        if response.status_code!=200 or error:raise MetaError('meta_request_rejected')
                        return payload
            except MetaError:
                raise
            except (httpx.HTTPError, ValueError, TypeError):
                if is_write:raise MetaError('meta_write_unknown') from None
                if attempt==2:raise MetaError('meta_provider_unavailable') from None
                await self.sleep(2**attempt)
        raise MetaError('meta_provider_unavailable')

    async def resource(self,resource_type,resource_id,account_id):
        if resource_type not in RESOURCE_FIELDS or not re.fullmatch(r'\d{1,64}',resource_id) or not re.fullmatch(r'act_\d+',account_id):raise MetaError('meta_invalid_resource')
        payload=await self._request(resource_id,{'fields':RESOURCE_FIELDS[resource_type]})
        if str(payload.get('id',''))!=resource_id or 'act_'+str(payload.get('account_id','')).removeprefix('act_')!=account_id:raise MetaError('meta_resource_scope_mismatch')
        allowed=set(RESOURCE_FIELDS[resource_type].split(','))
        return {key:payload[key] for key in allowed if key in payload}

    async def write_resource(self,resource_id,payload):
        result=await self._request(resource_id,write_data=payload)
        if result.get('success') is not True:raise MetaError('meta_write_rejected')
        return {'success':True}

    async def exchange(self, code):
        c=self.config
        result=await self._request('oauth/access_token',oauth={'client_id':c.meta_app_id,'client_secret':c.meta_app_secret,
            'redirect_uri':c.meta_redirect_uri,'code':code})
        token=result.get('access_token')
        if not isinstance(token,str) or not token:raise MetaError('meta_invalid_token_response')
        return token,result.get('expires_in')

    async def identity(self):
        person=await self._request('me',{'fields':'id'})
        permissions=await self._request('me/permissions')
        granted=permissions.get('data')
        if not isinstance(granted,list):raise MetaError('meta_invalid_response')
        scopes=[p['permission'] for p in granted if isinstance(p,dict) and p.get('status')=='granted' and isinstance(p.get('permission'),str)]
        if 'ads_read' not in scopes:raise MetaError('meta_ads_read_required')
        if settings().meta_write_enabled and 'ads_management' not in scopes:raise MetaError('meta_ads_management_required')
        if not str(person.get('id','')).isdecimal():raise MetaError('meta_invalid_identity')
        return str(person['id']),scopes

    async def account(self, account_id):
        if not isinstance(account_id,str) or not re.fullmatch(r'act_\d{1,32}',account_id):
            raise MetaError('meta_invalid_account')
        row=await self._request(account_id,{'fields':FIELDS['accounts']})
        if not isinstance(row,dict) or row.get('id')!=account_id:
            raise MetaError('warehouse_account_mismatch')
        clean={key:row[key] for key in FIELDS['accounts'].split(',') if key in row}
        if 'business' in clean:
            value=clean['business'];clean['business']={k:value[k] for k in ('id','name') if k in value} if isinstance(value,dict) else None
        return clean

    async def rows(self, kind, account_id=None, since=None, until=None, *, level='ad', granularity='daily', warehouse=False):
        if kind not in FIELDS:raise MetaError('meta_endpoint_forbidden')
        if kind!='accounts' and not re.fullmatch(r'act_\d+',account_id or ''):raise MetaError('meta_invalid_account')
        path='me/adaccounts' if kind=='accounts' else f'{account_id}/{kind}'
        params={'fields':FIELDS[kind],'limit':100}
        fields=FIELDS[kind].replace('creative{id,name}','creative').split(',')
        if kind=='insights':
            if level not in ('campaign','adset','ad') or granularity not in ('daily','hourly'):raise MetaError('meta_invalid_grain')
            params.update(level=level,time_increment=1,time_range=json.dumps({'since':since,'until':until}))
            if warehouse:
                extra='account_currency,inline_link_clicks'+(',reach,frequency' if granularity=='daily' else '')
                params['fields']+=','+extra;fields+=extra.split(',')
                params.update(action_report_time='impression',action_attribution_windows=json.dumps(['7d_click','1d_view']))
                if granularity=='hourly':
                    params['breakdowns']='hourly_stats_aggregated_by_advertiser_time_zone'
                    fields.append(params['breakdowns'])
        seen=set()
        for page in range(20):
            result=await self._request(path,params)
            rows=result.get('data')
            if not isinstance(rows,list) or any(not isinstance(row,dict) for row in rows):raise MetaError('meta_invalid_response')
            for row in rows:
                clean={key:row[key] for key in fields if key in row}
                if 'creative' in clean:
                    creative=clean['creative'];clean['creative']={k:creative[k] for k in ('id','name') if k in creative} if isinstance(creative,dict) else None
                if 'business' in clean:
                    business=clean['business'];clean['business']={k:business[k] for k in ('id','name') if k in business} if isinstance(business,dict) else None
                for field in ('actions','action_values'):
                    if field in clean:
                        if not isinstance(clean[field],list):raise MetaError('meta_invalid_response')
                        clean[field]=[{k:r[k] for k in ('action_type','value') if k in r} for r in clean[field] if isinstance(r,dict)]
                yield clean
            paging=result.get('paging') or {}
            if not isinstance(paging,dict):raise MetaError('meta_invalid_cursor')
            if not paging.get('next'):return
            # Never follow provider's URL, which can contain tokens or a hostile host.
            cursors=paging.get('cursors') or {}
            after=cursors.get('after') if isinstance(cursors,dict) else None
            if not isinstance(after,str) or not after or len(after)>4096 or after in seen:raise MetaError('meta_invalid_cursor')
            seen.add(after);params['after']=after
        raise MetaError('meta_page_limit_reduce_range')
