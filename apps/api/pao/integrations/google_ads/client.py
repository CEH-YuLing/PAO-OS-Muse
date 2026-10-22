"""Bounded Google Ads v25 REST client. Search POSTs are read-only GAQL queries."""
import asyncio,json,random,re
from urllib.parse import urlsplit
import httpx
from cryptography.fernet import Fernet,InvalidToken
from ...config import settings

SCOPE='https://www.googleapis.com/auth/adwords'
class GoogleAdsError(Exception):pass

def cipher():
    try:return Fernet(settings().integration_encryption_key.encode())
    except (ValueError,TypeError):raise GoogleAdsError('google_ads_encryption_not_configured') from None
def encrypt(value):return cipher().encrypt(value.encode()).decode()
def decrypt(value):
    try:return cipher().decrypt(value.encode()).decode()
    except (InvalidToken,AttributeError,UnicodeError):raise GoogleAdsError('google_ads_credential_unreadable') from None
def configured(config=None):
    c=config or settings()
    if not c.google_ads_enabled or not c.google_ads_client_id or not c.google_ads_client_secret or not re.fullmatch(r'v\d+',c.google_ads_api_version):raise GoogleAdsError('google_ads_not_configured')
    cipher();uri=urlsplit(c.google_ads_redirect_uri)
    if uri.username or uri.password or uri.query or uri.fragment or uri.path!='/v1/integrations/google-ads/callback' or not uri.hostname or not (uri.scheme=='https' or uri.scheme=='http' and uri.hostname in ('localhost','127.0.0.1')):raise GoogleAdsError('google_ads_invalid_redirect_uri')
    if c.google_ads_login_customer_id and not re.fullmatch(r'\d{10}',c.google_ads_login_customer_id.replace('-','')):raise GoogleAdsError('google_ads_invalid_login_customer')

class GoogleAdsClient:
    def __init__(self,transport=None,sleep=asyncio.sleep,*,config=None,guard=None):
        self.config=config or settings().model_copy(deep=True);self.guard=guard
        configured(self.config);self.transport=transport;self.sleep=sleep
    async def request(self,method,url,*,headers=None,data=None,json_body=None,oauth=False):
        if self.guard:
            async with self.guard():return await self._perform(method,url,headers=headers,data=data,json_body=json_body,oauth=oauth)
        return await self._perform(method,url,headers=headers,data=data,json_body=json_body,oauth=oauth)
    async def _perform(self,method,url,*,headers=None,data=None,json_body=None,oauth=False):
        allowed=url in ('https://oauth2.googleapis.com/token',f'https://googleads.googleapis.com/{self.config.google_ads_api_version}/customers:listAccessibleCustomers') or bool(re.fullmatch(rf'https://googleads\.googleapis\.com/{self.config.google_ads_api_version}/customers/\d{{10}}/googleAds:search',url))
        if not allowed or method not in ('GET','POST') or method=='POST' and not (oauth or url.endswith('/googleAds:search')):raise GoogleAdsError('google_ads_endpoint_forbidden')
        if oauth and (url!='https://oauth2.googleapis.com/token' or not isinstance(data,dict) or data.get('grant_type') not in ('authorization_code','refresh_token')):raise GoogleAdsError('google_ads_endpoint_forbidden')
        if url.endswith('/googleAds:search') and (not isinstance(json_body,dict) or not set(json_body)<= {'query','pageSize','pageToken'} or not re.fullmatch(r'\s*SELECT\s+[\s\S]{1,5990}',str(json_body.get('query','')),re.I) or ';' in json_body['query']):raise GoogleAdsError('google_ads_invalid_query')
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(transport=self.transport,timeout=25,trust_env=False,follow_redirects=False) as client:
                    async with client.stream(method,url,headers=headers,data=data,json=json_body) as response:
                        raw=bytearray()
                        async for chunk in response.aiter_bytes():
                            raw.extend(chunk)
                            if len(raw)>4_000_000:raise GoogleAdsError('google_ads_response_too_large')
                        try:payload=json.loads(raw)
                        except Exception:raise GoogleAdsError('google_ads_invalid_response') from None
                        if response.status_code in (401,403):raise GoogleAdsError('google_ads_reauthorization_required' if response.status_code==401 else 'google_ads_permission_denied')
                        if response.status_code==429 or response.status_code>=500:
                            if attempt==2:raise GoogleAdsError('google_ads_rate_limited' if response.status_code==429 else 'google_ads_provider_unavailable')
                            await self.sleep(2**attempt+random.random()/4);continue
                        if response.status_code!=200 or not isinstance(payload,dict):raise GoogleAdsError('google_ads_request_rejected')
                        return payload
            except GoogleAdsError:raise
            except httpx.HTTPError:
                if attempt==2:raise GoogleAdsError('google_ads_provider_unavailable') from None
                await self.sleep(2**attempt)
        raise GoogleAdsError('google_ads_provider_unavailable')
    async def exchange(self,code):
        c=self.config;payload=await self.request('POST','https://oauth2.googleapis.com/token',oauth=True,data={'code':code,'client_id':c.google_ads_client_id,'client_secret':c.google_ads_client_secret,'redirect_uri':c.google_ads_redirect_uri,'grant_type':'authorization_code'})
        token=payload.get('refresh_token');scope=str(payload.get('scope','')).split()
        if not isinstance(token,str) or not token or SCOPE not in scope:raise GoogleAdsError('google_ads_invalid_token_response')
        return token,scope
    async def access(self,refresh_token):
        c=self.config;payload=await self.request('POST','https://oauth2.googleapis.com/token',oauth=True,data={'refresh_token':refresh_token,'client_id':c.google_ads_client_id,'client_secret':c.google_ads_client_secret,'grant_type':'refresh_token'})
        token=payload.get('access_token')
        if not isinstance(token,str) or not token:raise GoogleAdsError('google_ads_invalid_token_response')
        return token
    def headers(self,token):
        c=self.config;headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'}
        if c.google_ads_developer_token:headers['developer-token']=c.google_ads_developer_token
        if c.google_ads_login_customer_id:headers['login-customer-id']=c.google_ads_login_customer_id.replace('-','')
        return headers
    async def accessible(self,refresh_token):
        token=await self.access(refresh_token);url=f'https://googleads.googleapis.com/{self.config.google_ads_api_version}/customers:listAccessibleCustomers'
        payload=await self.request('GET',url,headers=self.headers(token));names=payload.get('resourceNames')
        if not isinstance(names,list):raise GoogleAdsError('google_ads_invalid_response')
        ids=[]
        for name in names:
            match=re.fullmatch(r'customers/(\d{10})',str(name))
            if not match:raise GoogleAdsError('google_ads_invalid_response')
            ids.append(match[1])
        return token,ids
    async def search(self,token,customer_id,query):
        if not re.fullmatch(r'\d{10}',customer_id) or not isinstance(query,str) or len(query)>6000 or ';' in query or not re.match(r'^SELECT\s',query,re.I):raise GoogleAdsError('google_ads_invalid_query')
        url=f'https://googleads.googleapis.com/{self.config.google_ads_api_version}/customers/{customer_id}/googleAds:search';page=None;count=0
        while True:
            body={'query':query,'pageSize':1000}
            if page:body['pageToken']=page
            payload=await self.request('POST',url,headers=self.headers(token),json_body=body);rows=payload.get('results',[])
            if not isinstance(rows,list):raise GoogleAdsError('google_ads_invalid_response')
            for row in rows:
                count+=1
                if count>10000 or not isinstance(row,dict):raise GoogleAdsError('google_ads_row_limit_reduce_range')
                yield row
            page=payload.get('nextPageToken')
            if not page:break
