"""Only an owned disposable browser DB; all provider I/O is synthetic."""
import os,re,json,hmac
from urllib.parse import parse_qs
from sqlalchemy.engine import make_url
from pao.config import settings
url=make_url(settings().database_url)
if os.environ.get('PAO_S4_BROWSER_TEST')!='1' or not re.fullmatch('pao_s4_browser_[0-9a-f]{32}',url.database or '') or url.host!='127.0.0.1' or url.port!=15432:
    raise SystemExit('Owned S4 browser database and opt-in required')
import httpx
from pao.main import app
from fastapi import Request,HTTPException


def provider(request):
    print(json.dumps({'fixture_http':request.url.path,'method':request.method}),flush=True)
    if request.url.host=='graph.facebook.com':
        if request.url.path.endswith('/oauth/access_token'):
            body=parse_qs(request.content.decode());assert body['client_id']==['456'] and body['client_secret']==['tenant-secret-456']
            return httpx.Response(200,json={'access_token':'synthetic-user-token','expires_in':3600})
        if request.url.path.endswith('/me/permissions'):return httpx.Response(200,json={'data':[{'permission':'ads_read','status':'granted'}]})
        if request.url.path.endswith('/me'):return httpx.Response(200,json={'id':'42'})
    if request.url.host=='oauth2.googleapis.com' and request.url.path=='/token':
        body=parse_qs(request.content.decode());assert body['client_id']==['999.apps.googleusercontent.com'] and body['client_secret']==['google-secret-new']
        if body['grant_type']==['authorization_code']:
            return httpx.Response(200,json={'refresh_token':'synthetic-google-refresh','scope':'https://www.googleapis.com/auth/adwords'})
        assert body['grant_type']==['refresh_token'] and body['refresh_token']==['synthetic-google-refresh']
        return httpx.Response(200,json={'access_token':'synthetic-google-access'})
    if request.url.host=='googleads.googleapis.com' and request.url.path.endswith('/customers:listAccessibleCustomers'):
        assert request.headers['authorization']=='Bearer synthetic-google-access'
        assert 'developer-token' not in request.headers and 'login-customer-id' not in request.headers,'BYO must not borrow host context'
        return httpx.Response(200,json={'resourceNames':[]})
    raise AssertionError('S4 browser must never reach a real provider or Ads write')


# After app import: do not replace a base transport before subclass imports.
httpx.AsyncHTTPTransport=lambda **kwargs:httpx.MockTransport(provider)
from httpx import _client as transport_module
transport_module.AsyncHTTPTransport=lambda **kwargs:httpx.MockTransport(provider)


@app.post('/fixture/google-platform',include_in_schema=False)
async def test_google_platform(request:Request):
    if not hmac.compare_digest(request.headers.get('x-fixture-key',''),os.environ['PAO_S4_FIXTURE_KEY']):raise HTTPException(403)
    settings().google_ads_enabled=True  # Only this opt-in synthetic process/owned DB.
    return {'enabled':True,'fixture_only':True}

# Diagnostic reason codes only; never log code/token/request body.
from pao.integrations.meta.client import MetaClient,MetaError
for name in ('exchange','identity'):
    original=getattr(MetaClient,name)
    def wrap(operation,method):
        async def call(self,*args,**kwargs):
            try:return await operation(self,*args,**kwargs)
            except MetaError as exc:
                reason=str(exc);print(json.dumps({'fixture_oauth':method,'reason':reason if re.fullmatch('[a-z_]{1,64}',reason) else 'redacted'}),flush=True);raise
        return call
    setattr(MetaClient,name,wrap(original,name))

if __name__=='__main__':
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=18101,access_log=False,log_level='error')
