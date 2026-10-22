"""P5 fixture protocol/permissions; no external services or real credentials."""
import json,asyncio
import httpx,pytest
from sqlalchemy import select,text
from sqlalchemy.exc import DBAPIError
from cryptography.fernet import Fernet
from pao.config import settings
from pao.db import Session
from pao.models import ToolCall,ConnectorSecret,ConnectorConnection,ConnectorEvent
from pao.modules.connectors import service
from pao.modules.connectors.transport import Client,ConnectorFailure,endpoint,public_addresses,PinnedBackend,PROTOCOL
from pao.tool_gateway import execute_tool
from test_studio import make,publish,SCHEMA

class Server:
    def __init__(self):self.calls=0;self.mode='good';self.requests=[];self.sse=False;self.width=80
    async def respond(self,request):
        body=json.loads(request.content);method=body['method'];self.requests.append(method)
        if self.mode=='timeout':raise httpx.ReadTimeout('synthetic')
        if self.mode=='redirect':return httpx.Response(302,headers={'location':'https://private.example/mcp'})
        if self.mode=='large':return httpx.Response(200,headers={'content-type':'application/json'},content=b'x'*65537)
        if method=='notifications/initialized':return httpx.Response(202)
        if method=='initialize':result={'protocolVersion':PROTOCOL,'capabilities':{'tools':{}},'serverInfo':{'name':'Fixture','version':'1'}}
        elif method=='tools/list':
            result={'tools':[{'name':'read_report','inputSchema':SCHEMA,
                'outputSchema':{**SCHEMA,'properties':{'text':{'type':'string','maxLength':self.width}}},
                'annotations':{'readOnlyHint':True,'destructiveHint':False}}]}
            if self.mode=='pagination':
                result['nextCursor']='repeated'
                if body.get('params',{}).get('cursor'):result['tools']=[]
        elif method=='tools/call':
            self.calls+=1;assert body['params']['arguments']=={'text':'Synthetic request'}
            result={'structuredContent':{'text':'Synthetic read result'},'content':[]}
        else:raise AssertionError('Unexpected method')
        payload={'jsonrpc':'2.0','id':body['id'],'result':result}
        if self.mode=='malformed':payload['id']='wrong-id'
        if self.sse:return httpx.Response(200,headers={'content-type':'text/event-stream'},content=('data: '+json.dumps(payload)+'\n\n').encode())
        return httpx.Response(200,json=payload)

@pytest.fixture
def connectors(monkeypatch):
    config=settings()
    for flag in ('connectors_enabled','studio_enabled','tools_enabled','engine_contract_enabled','chat_features_enabled'):
        monkeypatch.setattr(config,flag,True)
    monkeypatch.setattr(config,'integration_encryption_key',Fernet.generate_key().decode())
    monkeypatch.setattr(config,'ollama_model','synthetic-p5')
    async def tags():return ['synthetic-p5']
    monkeypatch.setattr('pao.modules.engines.service.local_models',tags)
    server=Server()
    monkeypatch.setattr(service,'Client',lambda url,token=None:Client(url,token,httpx.MockTransport(server.respond)))
    return server

async def connected(client,identity):
    response=await client.post('/v1/connectors/connections',headers=identity['owner'],json={
        'workspace_id':identity['workspace'],'endpoint':'https://fixture.example/mcp','token':'synthetic-secret-marker-1234',
        'readonly_credentials_ack':True})
    assert response.status_code==201,response.text
    row=response.json();assert row['status']=='draft' and row['tools']==[]
    response=await client.post(f"/v1/connectors/connections/{row['id']}/test",headers=identity['owner'],json={'version':row['version']})
    assert response.status_code==200,response.text
    row=response.json();assert row['permissions']==[]
    return row

async def granted(client,identity,row):
    tool=row['tools'][0]
    response=await client.put(f"/v1/connectors/connections/{row['id']}/permissions",headers=identity['owner'],json={
        'version':row['version'],'tool_id':tool['id'],'schema_hash':tool['hash'],
        'bound_arguments':{'text':'Synthetic request'},'readonly_server_ack':True})
    assert response.status_code==200,response.text
    return response.json()

async def pinned_run(client,identity,row):
    agent=await publish(client,identity,await make(client,identity))
    skill=await publish(client,identity,await make(client,identity,'skills','p5-probe',{
        'instruction':'Return only JSON.','agent_version_id':agent['version']['id'],
        'input_schema':SCHEMA,'output_schema':SCHEMA,'allowed_tools':[row['tools'][0]['id']]}))
    sid=(await client.post('/v1/sessions',headers=identity['owner'],json={'workspace_id':identity['workspace']})).json()['id']
    response=await client.post('/v1/runs',headers=identity['owner'],json={'session_id':sid,
        'message':'/p5-probe {"text":"Synthetic"}','request_key':'p5-fixture-run'})
    assert response.status_code==202,response.text
    return response.json()['id']

async def propose(client,identity,row,rid,key='p5-call'):
    return await client.post(f"/v1/connectors/connections/{row['id']}/calls",headers=identity['owner'],json={
        'run_id':rid,'tool_id':row['tools'][0]['id'],'request_key':key})

async def test_catalog_is_not_connection_and_acl(client,identity,connectors):
    response=await client.get('/v1/connectors/templates',headers=identity['owner'],params={'workspace_id':identity['workspace']})
    assert response.status_code==200 and not response.json()['templates'][0]['connected']
    assert connectors.requests==[]
    response=await client.post('/v1/connectors/connections',headers=identity['other'],json={
        'workspace_id':identity['workspace'],'endpoint':'https://fixture.example/mcp','readonly_credentials_ack':True})
    assert response.status_code==403 and connectors.requests==[]
    row=await connected(client,identity)
    assert (await client.post(f"/v1/connectors/connections/{row['id']}/test",headers=identity['outsider'],json={'version':row['version']})).status_code==404

async def test_encrypt_refresh_purge_audit_and_revision(client,identity,connectors):
    row=await connected(client,identity)
    response=await client.get('/v1/connectors/connections',headers=identity['owner'],params={'workspace_id':identity['workspace']})
    assert 'synthetic-secret-marker' not in response.text and 'ciphertext' not in response.text
    async with Session() as db:
        secret=await db.scalar(select(ConnectorSecret).where(ConnectorSecret.connection_id==row['id']))
        assert secret.ciphertext and 'synthetic-secret-marker' not in secret.ciphertext
    response=await client.put(f"/v1/connectors/connections/{row['id']}/credential",headers=identity['owner'],
        json={'version':1,'token':'synthetic-rotated-marker'})
    assert response.status_code==409
    response=await client.post(f"/v1/connectors/connections/{row['id']}/disconnect",headers=identity['owner'],json={'version':row['version']})
    assert response.status_code==200
    async with Session() as db:assert (await db.scalar(select(ConnectorSecret).where(ConnectorSecret.connection_id==row['id']))).ciphertext is None
    response=await client.get(f"/v1/connectors/connections/{row['id']}/audit",headers=identity['owner'])
    assert 'synthetic-secret-marker' not in response.text and 'credential_purged' in response.text
    with pytest.raises(DBAPIError):
        async with Session.begin() as db:await db.execute(text("UPDATE connector_events SET action='forged'"))

@pytest.mark.parametrize('sse',[False,True])
async def test_gateway_claim_replay_and_fixed_args(client,identity,connectors,sse):
    connectors.sse=sse
    row=await granted(client,identity,await connected(client,identity));rid=await pinned_run(client,identity,row)
    response=await propose(client,identity,row,rid);assert response.status_code==202,response.text
    call=response.json()['id']
    await execute_tool({},call);await execute_tool({},call)
    assert connectors.calls==1
    async with Session() as db:
        record=await db.get(ToolCall,call);assert record.status=='completed',record.error_code
        assert record.result=={'text':'Synthetic read result'}
    assert (await propose(client,identity,row,rid)).json()['id']==call
    response=await client.post(f"/v1/connectors/connections/{row['id']}/calls",headers=identity['owner'],json={
        'run_id':rid,'tool_id':row['tools'][0]['id'],'request_key':'tamper','arguments':{'text':'Other tenant'}})
    assert response.status_code==422 and connectors.calls==1
    with pytest.raises(DBAPIError):
        async with Session.begin() as db:await db.execute(text("UPDATE tool_calls SET arguments='{}' WHERE id=:id"),{'id':call})

@pytest.mark.parametrize('reason',['revoke','drift','feature_off','membership'])
async def test_worker_recheck_denied_no_provider_call(client,identity,connectors,reason):
    row=await granted(client,identity,await connected(client,identity));rid=await pinned_run(client,identity,row)
    response=await propose(client,identity,row,rid);assert response.status_code==202,response.text
    call=response.json()['id']
    if reason=='revoke':
        await client.post(f"/v1/connectors/connections/{row['id']}/disconnect",headers=identity['owner'],json={'version':row['version']})
    elif reason=='drift':connectors.width=79
    elif reason=='feature_off':settings().connectors_enabled=False
    else:
        async with Session.begin() as db:await db.execute(text("UPDATE workspace_members SET role='viewer' WHERE user_id=:id"),{'id':identity['user_id']})
    await execute_tool({},call)
    assert connectors.calls==0
    async with Session() as db:assert (await db.get(ToolCall,call)).status in ('cancelled','failed')

@pytest.mark.parametrize('mode,code',[('timeout','connector_timeout'),('malformed','connector_protocol_invalid'),
    ('large','connector_response_limit'),('redirect','connector_http_denied'),('pagination','connector_pagination_invalid')])
async def test_bad_provider_never_connected(mode,code):
    server=Server();server.mode=mode
    with pytest.raises(ConnectorFailure,match=code):await Client('https://fixture.example/mcp',transport=httpx.MockTransport(server.respond)).exchange()
    assert server.calls==0

@pytest.mark.parametrize('url',['http://fixture.example/mcp','https://127.0.0.1/mcp','https://localhost/mcp',
    'https://user:secret@fixture.example/mcp','https://fixture.example:8443/mcp','https://fixture.example/mcp?secret=x',
    'https://fixture.example/%2fprivate','https://fixture.example/../mcp','https://fixture.example/mcp#token'])
def test_endpoint_denied(url):
    with pytest.raises(ConnectorFailure):endpoint(url)

@pytest.mark.parametrize('address',['127.0.0.1','10.0.0.1','169.254.169.254','::1','fc00::1','::ffff:8.8.8.8','224.0.0.1'])
def test_dns_denied(address):
    with pytest.raises(ConnectorFailure):public_addresses(['8.8.8.8',address])

async def test_no_second_dns_resolution(monkeypatch):
    from httpcore._backends.auto import AutoBackend
    seen=[]
    async def resolve(host):assert host=='fixture.example';return ['8.8.8.8']
    async def delegate(self,host,port,**kwargs):seen.append((host,port));return object()
    monkeypatch.setattr('pao.modules.connectors.transport.resolve',resolve)
    monkeypatch.setattr(AutoBackend,'connect_tcp',delegate)
    await PinnedBackend().connect_tcp('fixture.example',443)
    assert seen==[('8.8.8.8',443)]

async def test_circuit_breaker_and_credential_rotation(client,identity,connectors):
    row=await connected(client,identity)
    assert row['secret_present']
    connectors.mode='timeout'
    for _ in range(3):
        response=await client.post(f"/v1/connectors/connections/{row['id']}/test",headers=identity['owner'],json={'version':row['version']})
        assert response.status_code==502
    count=len(connectors.requests)
    response=await client.post(f"/v1/connectors/connections/{row['id']}/test",headers=identity['owner'],json={'version':row['version']})
    assert response.status_code==409 and len(connectors.requests)==count
    response=await client.put(f"/v1/connectors/connections/{row['id']}/credential",headers=identity['owner'],json={'version':row['version'],'token':'synthetic-new-credential'})
    assert response.status_code==200 and response.json()['status']=='draft' and response.json()['secret_present']

async def test_other_principal_cannot_queue(client,identity,connectors):
    row=await granted(client,identity,await connected(client,identity));rid=await pinned_run(client,identity,row)
    for who in ('other','outsider'):
        response=await client.post(f"/v1/connectors/connections/{row['id']}/calls",headers=identity[who],json={
            'run_id':rid,'tool_id':row['tools'][0]['id'],'request_key':'forged'})
        assert response.status_code==404
    assert connectors.calls==0

async def test_inflight_revocation_discards_result(client,identity,connectors,monkeypatch):
    row=await granted(client,identity,await connected(client,identity));rid=await pinned_run(client,identity,row)
    response=await propose(client,identity,row,rid);assert response.status_code==202
    started=asyncio.Event();release=asyncio.Event();original=connectors.respond
    async def slow(request):
        if json.loads(request.content)['method']=='tools/call':
            started.set();await release.wait()
        return await original(request)
    monkeypatch.setattr(service,'Client',lambda url,token=None:Client(url,token,httpx.MockTransport(slow)))
    task=asyncio.create_task(execute_tool({},response.json()['id']))
    try:
        await asyncio.wait_for(started.wait(),5)
        revoked=await client.post(f"/v1/connectors/connections/{row['id']}/disconnect",headers=identity['owner'],json={'version':row['version']})
        assert revoked.status_code==200
        release.set();await asyncio.wait_for(task,5)
        async with Session() as db:
            record=await db.get(ToolCall,response.json()['id'])
            assert record.status=='cancelled' and record.result=={}
    finally:
        release.set()
        if not task.done():task.cancel()
        await asyncio.gather(task,return_exceptions=True)

async def test_unsupported_protocol_and_server_requests_fail_closed():
    from pao.modules.connectors.transport import decode
    server=Server()
    async def newer(request):
        response=await server.respond(request)
        if json.loads(request.content)['method']=='initialize':
            value=json.loads(response.content);value['result']['protocolVersion']='2026-07-28'
            return httpx.Response(200,json=value)
        return response
    with pytest.raises(ConnectorFailure,match='connector_capabilities_unsupported'):
        await Client('https://fixture.example/mcp',transport=httpx.MockTransport(newer)).exchange()
    with pytest.raises(ConnectorFailure,match='connector_server_message_denied'):
        decode(json.dumps({'jsonrpc':'2.0','id':'x','method':'sampling/createMessage'}).encode(),'application/json','x')
    assert server.calls==0
