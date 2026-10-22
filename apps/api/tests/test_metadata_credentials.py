"""Reflected fake credentials only; no network or real provider credentials."""
import base64
import json
import logging
from urllib.parse import quote
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import select
from pao.credential_guard import require_clean_payload, CredentialPayloadError
from pao.model_router import fetch_models, ModelRouterError
from pao.db import Session
from pao.models import ModelProviderConnection, ConnectorConnection, ConnectorEvent, TenantMetadataLease
from pao.modules.connectors import service
from pao.modules.connectors.transport import Client, ConnectorFailure
from test_connectors import Server, connectors, connected, granted, pinned_run, propose
from test_model_metadata import configured, request_metadata, KEY
from test_tenant_metadata_resources import usage
from pao.tool_gateway import execute_tool


def representations(key):
    return [key, json.dumps(key)[1:-1], quote(key, safe=''),
            base64.b64encode(key.encode()).decode(), base64.urlsafe_b64encode(key.encode()).decode()]


@pytest.mark.parametrize('form', representations('fixture-quote"slash\\unicode-ñ-secret'))
@pytest.mark.parametrize('position', ['value', 'key'])
def test_decoded_strings_keys_and_common_representations(form, position):
    key='fixture-quote"slash\\unicode-ñ-secret'
    value={'nested': [{'text': 'prefix '+form+' suffix'} if position=='value' else {form: 'discarded'}]}
    with pytest.raises(CredentialPayloadError, match='^payload_credential_reflected$') as exc:
        require_clean_payload(value,key)
    assert key not in str(exc.value)


def test_clean_payload_no_key_and_bounded_depth_nodes(monkeypatch):
    require_clean_payload({'ok':['non-secret',None,1,True]},KEY)
    require_clean_payload({'text':KEY}) # Legacy token-optional mode, not grant widening.
    deep='text'
    for _ in range(34):deep=[deep]
    with pytest.raises(CredentialPayloadError,match='^payload_complexity_limit$'):require_clean_payload(deep,KEY)
    monkeypatch.setattr('pao.credential_guard.MAX_NODES',5)
    with pytest.raises(CredentialPayloadError,match='^payload_complexity_limit$'):require_clean_payload([0]*6,KEY)


@pytest.mark.parametrize('provider',['openai','anthropic','gemini','openrouter'])
@pytest.mark.parametrize('position',['id','ignored','dict_key','cursor','escaped'])
async def test_cloud_payload_reflection_all_providers_before_publication(provider,position,caplog):
    calls=[]
    def reply(request):
        calls.append(request)
        row={'name':'models/fixture','supportedGenerationMethods':['generateContent']} if provider=='gemini' else {'id':'fixture'}
        payload={'models' if provider=='gemini' else 'data':[row]}
        if position=='id':row['name' if provider=='gemini' else 'id']=KEY
        elif position=='ignored':payload['unused']={'nested':[{'description':KEY}]}
        elif position=='dict_key':payload['unused']={KEY:'not displayed'}
        elif position=='cursor':
            payload['nextPageToken' if provider=='gemini' else 'last_id']=KEY
            payload['has_more']=True
        else:
            # Wire JSON Unicode escapes must be decoded before matching.
            payload['unused']=KEY
            raw=json.dumps(payload).replace(KEY,''.join('\\u%04x'%ord(c) for c in KEY))
            return httpx.Response(200,headers={'content-type':'application/json'},content=raw.encode())
        return httpx.Response(200,json=payload)
    with caplog.at_level(logging.INFO,logger='httpx'),pytest.raises(ModelRouterError,match='^provider_models_sensitive$') as exc:
        await fetch_models(provider,KEY,httpx.MockTransport(reply))
    assert len(calls)==1 and KEY not in str(exc.value) and KEY not in caplog.text
    assert KEY not in str(calls[0].url) and exc.value.__cause__ is None


async def test_gemini_header_all_pages_and_info_log_has_no_key(caplog):
    calls=[]
    def reply(request):
        calls.append(request)
        assert request.headers['x-goog-api-key']==KEY and 'key' not in request.url.params
        payload={'models':[{'name':'models/fixture','supportedGenerationMethods':['generateContent']}]}
        if len(calls)==1:payload['nextPageToken']='opaque-next'
        else:assert request.url.params['pageToken']=='opaque-next'
        return httpx.Response(200,json=payload)
    with caplog.at_level(logging.INFO,logger='httpx'):
        assert await fetch_models('gemini',KEY,httpx.MockTransport(reply))==['fixture']
    assert len(calls)==2 and len(caplog.records)>=2 and KEY not in caplog.text


@pytest.mark.parametrize('operation',['stream','plan','extract'])
async def test_gemini_gateway_header_no_key_url_log_or_model_change(monkeypatch,caplog,operation):
    from pao.gateway import GeminiGateway
    original=httpx.AsyncClient;calls=[]
    def reply(request):
        calls.append(request)
        assert request.headers['x-goog-api-key']==KEY and 'key' not in request.url.params and KEY not in str(request.url)
        assert request.url.host=='generativelanguage.googleapis.com'
        body=json.loads(request.content)
        assert body['contents'][0]['parts'][0]['text']=='Fixture request'
        assert body['generationConfig']['maxOutputTokens']==(16 if operation=='stream' else 512)
        value='Fixture answer' if operation=='stream' else json.dumps({'goal':'Fixture goal','steps':[]} if operation=='plan' else {'facts':[]})
        payload={'candidates':[{'content':{'parts':[{'text':value}]},'finishReason':'STOP'}],
                 'usageMetadata':{'promptTokenCount':3,'candidatesTokenCount':4,'totalTokenCount':7}}
        if operation=='stream':
            assert request.url.path.endswith('/gemini-fixture:streamGenerateContent') and request.url.params['alt']=='sse'
            return httpx.Response(200,headers={'content-type':'text/event-stream'},content=('data: '+json.dumps(payload)+'\n\n').encode())
        assert request.url.path.endswith('/gemini-fixture:generateContent')
        assert body['generationConfig']['responseMimeType']=='application/json' and 'responseJsonSchema' in body['generationConfig']
        return httpx.Response(200,json=payload)
    monkeypatch.setattr('pao.gateway.httpx.AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(reply),**kwargs))
    gateway=GeminiGateway(KEY,'models/gemini-fixture')
    with caplog.at_level(logging.INFO,logger='httpx'):
        if operation=='stream':
            chunks=[chunk async for chunk in gateway.stream([{'role':'user','content':'Fixture request'}],max_tokens=16)]
            assert chunks[0].text=='Fixture answer' and chunks[1].usage['totalTokenCount']==7
        elif operation=='plan':assert (await gateway.plan([{'role':'system','content':'placeholder'},{'role':'user','content':'Fixture request'}])).goal=='Fixture goal'
        else:assert (await gateway.extract('Fixture request')).facts==[]
    assert len(calls)==1 and caplog.records and KEY not in caplog.text and gateway.model_name=='gemini-fixture'


@pytest.mark.parametrize('route',['connect','models','model'])
async def test_adapter_taint_no_source_update_charge_release_and_replay(client,identity,monkeypatch,route):
    cid=await configured(identity,monkeypatch)
    async def bad(provider,key):return ['fixture-new',key]
    monkeypatch.setattr('pao.model_api.fetch_models',bad)
    result=await request_metadata(client,identity,route)
    assert result.status_code==503 and KEY not in result.text and result.headers['cache-control']=='no-store'
    counts=await usage(identity)
    assert counts['daily_requests']==1 and counts['active_requests']==0
    async with Session() as db:
        row=await db.get(ModelProviderConnection,cid)
        assert row.model=='fixture-old' and row.model_count==0 and row.last_checked_at is None
        lease=await db.scalar(select(TenantMetadataLease))
        assert lease.status=='released'
        request_key=lease.request_key
    replay=await client.get('/v1/model-providers/openai/models',headers={**identity['owner'],'Idempotency-Key':str(request_key)},params={'workspace_id':identity['workspace']})
    assert replay.status_code==409 and replay.json()['detail']=='tenant_metadata_replay_denied'
    assert (await usage(identity))['daily_requests']==1


@pytest.mark.parametrize('position',['initialize','schema','ignored','dict_key','cursor','session','call','discarded_call'])
@pytest.mark.parametrize('sse',[False,True])
async def test_mcp_full_decoded_response_and_session_guard(position,sse):
    key='fixture-mcp-quote"slash\\secret'
    server=Server();server.sse=sse
    async def reply(request):
        response=await server.respond(request)
        method=json.loads(request.content)['method']
        if method=='notifications/initialized':return response
        value=json.loads(response.content.decode().removeprefix('data: ').strip())
        result=value['result']
        if position=='initialize' and method=='initialize':result['serverInfo']['name']=key
        elif method=='tools/list':
            if position=='schema':result['tools'][0]['inputSchema']={**result['tools'][0]['inputSchema'],'description':key}
            elif position=='ignored':result['unused']={'data':[key]}
            elif position=='dict_key':result['unused']={key:'ignored'}
            elif position=='cursor':result['nextCursor']=key
        elif method=='tools/call':
            if position=='call':result['structuredContent']={'text':key}
            elif position=='discarded_call':result['content']=[{'type':'text','text':key}]
        headers={'mcp-session-id':key} if position=='session' and method=='initialize' else {}
        if sse:return httpx.Response(200,headers={**headers,'content-type':'text/event-stream'},content=('data: '+json.dumps(value)+'\n\n').encode())
        return httpx.Response(200,json=value,headers=headers)
    transport=httpx.MockTransport(reply)
    approved=None
    if position in ('call','discarded_call'):
        manifest=await Client('https://fixture.example/mcp',key,transport).exchange()
        from pao.modules.studio.contracts import digest
        approved={'manifest_hash':digest(manifest),'name':'read_report','hash':manifest['tools']['read_report']['hash'],'arguments':{'text':'Synthetic request'}}
    with pytest.raises(ConnectorFailure,match='^connector_sensitive_result$') as exc:
        await Client('https://fixture.example/mcp',key,transport).exchange(approved)
    assert key not in str(exc.value) and exc.value.__cause__ is None
    assert server.calls==(1 if position in ('call','discarded_call') else 0)


@pytest.mark.parametrize('adapter',[False,True])
async def test_mcp_taint_never_published_or_audited_quota_released(client,identity,connectors,monkeypatch,adapter):
    row=await connected(client,identity)
    key='synthetic-secret-marker-1234'
    original=connectors.respond
    async def reply(request):
        response=await original(request)
        if json.loads(request.content)['method']=='tools/list':
            value=response.json();value['result']['tools'][0]['outputSchema']['description']=key
            return httpx.Response(200,json=value)
        return response
    if adapter:
        class Replacement:
            async def exchange(self):return {'tools':{key:{}}}
        monkeypatch.setattr(service,'Client',lambda *args:Replacement())
    else:monkeypatch.setattr(service,'Client',lambda url,token=None:Client(url,token,httpx.MockTransport(reply)))
    nonce=str(uuid4())
    result=await client.post(f"/v1/connectors/connections/{row['id']}/test",headers={**identity['owner'],'Idempotency-Key':nonce},json={'version':row['version']})
    assert result.status_code==502 and result.json()['detail']=='connector_sensitive_result' and key not in result.text
    counts=await usage(identity)
    assert counts['daily_requests']==2 and counts['active_requests']==0
    async with Session() as db:
        source=await db.get(ConnectorConnection,row['id'])
        assert source.manifest_hash==row['manifest_hash'] and source.version==row['version'] and source.status=='connected' and source.permissions=={}
        assert key not in json.dumps(source.manifest)
        events=list(await db.scalars(select(ConnectorEvent).where(ConnectorEvent.connection_id==row['id'])))
        assert key not in json.dumps([event.data for event in events])
        assert events[-1].data=={'reason':'connector_sensitive_result'}
    replay=await client.post(f"/v1/connectors/connections/{row['id']}/test",headers={**identity['owner'],'Idempotency-Key':nonce},json={'version':row['version']})
    assert replay.status_code==409 and (await usage(identity))['daily_requests']==2


async def test_tool_tainted_result_is_not_saved(client,identity,connectors,monkeypatch):
    row=await granted(client,identity,await connected(client,identity));rid=await pinned_run(client,identity,row)
    queued=await propose(client,identity,row,rid)
    assert queued.status_code==202
    original=connectors.respond
    async def reply(request):
        response=await original(request)
        if json.loads(request.content)['method']=='tools/call':
            value=response.json();value['result']['content']=[{'text':'synthetic-secret-marker-1234'}]
            return httpx.Response(200,json=value)
        return response
    monkeypatch.setattr(service,'Client',lambda url,token=None:Client(url,token,httpx.MockTransport(reply)))
    await execute_tool({},queued.json()['id'])
    from pao.models import ToolCall
    async with Session() as db:
        call=await db.get(ToolCall,queued.json()['id'])
        assert call.status=='failed' and call.result=={} and call.error_code=='connector_sensitive_result'
    assert connectors.calls==1


async def test_tool_replacement_adapter_cannot_save_reflected_token(client,identity,connectors,monkeypatch):
    row=await granted(client,identity,await connected(client,identity));rid=await pinned_run(client,identity,row)
    queued=await propose(client,identity,row,rid)
    assert queued.status_code==202
    class Replacement:
        async def exchange(self,pin):return {'text':'synthetic-secret-marker-1234'}
    monkeypatch.setattr(service,'Client',lambda *args:Replacement())
    await execute_tool({},queued.json()['id'])
    from pao.models import ToolCall
    async with Session() as db:
        call=await db.get(ToolCall,queued.json()['id'])
        assert call.status=='failed' and call.result=={} and call.error_code=='connector_sensitive_result'
