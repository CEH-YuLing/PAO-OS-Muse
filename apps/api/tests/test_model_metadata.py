"""Catalogue fixtures only: bounded transport and current SME/source authority."""
import asyncio
import json
from cryptography.fernet import Fernet
import httpx
import pytest
from sqlalchemy import select, update, delete
from pao.config import settings
from pao.db import Session
from pao.models import Member, User, Workspace, ModelProviderConnection, now
from pao.model_router import fetch_models, ModelRouterError, encrypt_key
from pao import model_router
from pao.modules.connections import model_metadata

KEY='fixture-metadata-secret-not-real'


async def test_catalogue_four_provider_headers_and_schema(client):
    calls=[]
    async def reply(request):
        calls.append(request)
        if request.url.host=='generativelanguage.googleapis.com':
            assert request.headers['x-goog-api-key']==KEY and 'key' not in request.url.params
            return httpx.Response(200,json={'models':[{'name':'models/gemini-fixture','supportedGenerationMethods':['generateContent']},
                {'name':'models/embed-fixture','supportedGenerationMethods':['embedContent']}]})
        if request.url.host=='api.anthropic.com':
            assert request.headers['x-api-key']==KEY and request.headers['anthropic-version']=='2023-06-01'
        else:assert request.headers['authorization']=='Bearer '+KEY
        return httpx.Response(200,json={'data':[{'id':'fixture-model'}]})
    transport=httpx.MockTransport(reply)
    for provider in model_router.PROVIDERS:
        assert await fetch_models(provider,KEY,transport)==(['gemini-fixture'] if provider=='gemini' else ['fixture-model'])
    assert len(calls)==4


@pytest.mark.parametrize('provider', ['anthropic','gemini'])
async def test_catalogue_fixed_origin_pagination(client,provider):
    calls=[]
    def reply(request):
        calls.append(request)
        if len(calls)==1:
            data={'models':[{'name':'models/first','supportedGenerationMethods':['generateContent']}], 'nextPageToken':'opaque-cursor'} if provider=='gemini' else {'data':[{'id':'first'}],'has_more':True,'last_id':'opaque-cursor'}
        else:
            assert request.url.params['pageToken' if provider=='gemini' else 'after_id']=='opaque-cursor'
            data={'models':[{'name':'models/second','supportedGenerationMethods':['generateContent']}]} if provider=='gemini' else {'data':[{'id':'second'}],'has_more':False}
        return httpx.Response(200,json=data)
    assert await fetch_models(provider,KEY,httpx.MockTransport(reply))==['first','second']
    assert len(calls)==2 and calls[0].url.host==calls[1].url.host and calls[0].url.path==calls[1].url.path


@pytest.mark.parametrize('payload',[[], {'data':{}}, {'data':[None]}, {'data':[{'id':42}]}, {'data':[{'id':'bad\nmodel'}]}])
async def test_catalogue_invalid_schema_sanitized(client,payload):
    with pytest.raises(ModelRouterError,match='^provider_models_invalid$'):
        await fetch_models('openai',KEY,httpx.MockTransport(lambda request:httpx.Response(200,json=payload)))


@pytest.mark.parametrize('status,code',[(302,'provider_unavailable'),(401,'provider_authentication_failed'),(403,'provider_authentication_failed'),(429,'provider_unavailable'),(500,'provider_unavailable')])
async def test_catalogue_status_never_follows_redirect_or_retries(client,status,code):
    count=0
    def reply(request):
        nonlocal count
        count+=1
        return httpx.Response(status,headers={'location':'https://evil.example.test/'+KEY},text=KEY)
    with pytest.raises(ModelRouterError,match='^'+code+'$') as exc:
        await fetch_models('openai',KEY,httpx.MockTransport(reply))
    assert count==1 and KEY not in str(exc.value) and exc.value.__cause__ is None


async def test_catalogue_decoded_byte_and_row_limits(client,monkeypatch):
    monkeypatch.setattr(model_router,'MODEL_DISCOVERY_BYTES',128)
    with pytest.raises(ModelRouterError,match='^provider_models_limit$'):
        await fetch_models('openai',KEY,httpx.MockTransport(lambda request:httpx.Response(200,json={'data':[{'id':'test','description':'x'*256}]})))
    monkeypatch.setattr(model_router,'MODEL_DISCOVERY_BYTES',4096)
    monkeypatch.setattr(model_router,'MODEL_DISCOVERY_ROWS',1)
    with pytest.raises(ModelRouterError,match='^provider_models_limit$'):
        await fetch_models('openai',KEY,httpx.MockTransport(lambda request:httpx.Response(200,json={'data':[{'id':'first'},{'id':'second'}]})))


@pytest.mark.parametrize('mime,raw',[('text/html',KEY.encode()),('application/json',b'{broken'),
    ('application/json',b'['*1100+b']'*1100)])
async def test_catalogue_mime_json_and_depth_sanitized(client,mime,raw):
    with pytest.raises(ModelRouterError) as exc:
        await fetch_models('openai',KEY,httpx.MockTransport(lambda request:httpx.Response(200,headers={'content-type':mime},content=raw)))
    assert str(exc.value) in ('provider_models_invalid','provider_unavailable') and KEY not in str(exc.value)
    assert exc.value.__cause__ is None


async def test_catalogue_limit_applies_after_decompression(client,monkeypatch):
    import gzip
    raw=json.dumps({'data':[{'id':'fixture','description':'x'*10000}]}).encode()
    compressed=gzip.compress(raw)
    assert len(compressed)<256
    monkeypatch.setattr(model_router,'MODEL_DISCOVERY_BYTES',256)
    with pytest.raises(ModelRouterError,match='^provider_models_limit$'):
        await fetch_models('openai',KEY,httpx.MockTransport(lambda request:httpx.Response(200,
            headers={'content-type':'application/json','content-encoding':'gzip'},content=compressed)))


@pytest.mark.parametrize('repeat', [True,False])
async def test_catalogue_cursor_loop_and_page_limit(client,repeat):
    count=0
    def reply(request):
        nonlocal count
        count+=1
        return httpx.Response(200,json={'data':[{'id':str(count)}],'has_more':True,'last_id':'repeat' if repeat else str(count)})
    with pytest.raises(ModelRouterError,match='^provider_models_'+('invalid' if repeat else 'limit')+'$'):
        await fetch_models('anthropic',KEY,httpx.MockTransport(reply))
    assert count==(2 if repeat else 3)


async def test_catalogue_deadline_and_cancellation_close_stream(client,monkeypatch):
    closed=[]
    class Slow(httpx.AsyncByteStream):
        async def __aiter__(self):
            await asyncio.sleep(2)
            yield b'{}'
        async def aclose(self):closed.append(True)
    monkeypatch.setattr(model_router,'MODEL_DISCOVERY_TIMEOUT',.05)
    with pytest.raises(ModelRouterError,match='^provider_unavailable$'):
        await fetch_models('openai',KEY,httpx.MockTransport(lambda request:httpx.Response(200,headers={'content-type':'application/json'},stream=Slow())))
    assert closed==[True]
    monkeypatch.setattr(model_router,'MODEL_DISCOVERY_TIMEOUT',30)
    task=asyncio.create_task(fetch_models('openai',KEY,httpx.MockTransport(lambda request:httpx.Response(200,headers={'content-type':'application/json'},stream=Slow()))))
    await asyncio.sleep(.05);task.cancel()
    with pytest.raises(asyncio.CancelledError):await task
    assert closed==[True,True]


async def configured(identity,monkeypatch):
    monkeypatch.setattr(settings(),'integration_encryption_key',Fernet.generate_key().decode())
    async with Session.begin() as db:
        row=ModelProviderConnection(workspace_id=identity['workspace'],provider='openai',api_key_ciphertext=encrypt_key(KEY),model='fixture-old',is_default=True)
        db.add(row);await db.flush();return row.id


async def request_metadata(client,identity,route):
    path='/v1/model-providers/openai/'
    if route=='connect':return await client.post(path+route,json={'workspace_id':identity['workspace'],'api_key':KEY,'model':'fixture-new'},headers=identity['owner'])
    if route=='model':return await client.put(path+route,json={'workspace_id':identity['workspace'],'model':'fixture-new'},headers=identity['owner'])
    return await client.get(path+route,params={'workspace_id':identity['workspace']},headers=identity['owner'])


@pytest.mark.parametrize('route',['connect','models','model'])
@pytest.mark.parametrize('change',['rotate','disconnect','demote','deactivate','remove_membership','touch'])
async def test_metadata_late_source_actor_changes_no_publication(client,identity,monkeypatch,route,change):
    cid=await configured(identity,monkeypatch)
    async def loader(provider,key):
        assert key==KEY
        # A second DB connection can mutate the exact source/member/user during
        # network I/O. A held source/actor lock would stall this test.
        async with asyncio.timeout(3),Session.begin() as db:
            if change=='rotate':await db.execute(update(ModelProviderConnection).where(ModelProviderConnection.id==cid).values(api_key_ciphertext=encrypt_key('fixture-rotated-secret'),updated_at=now()))
            elif change=='disconnect':await db.execute(delete(ModelProviderConnection).where(ModelProviderConnection.id==cid))
            elif change=='demote':await db.execute(update(Member).where(Member.workspace_id==identity['workspace'],Member.user_id==identity['user_id']).values(role='operator'))
            elif change=='deactivate':await db.execute(update(User).where(User.id==identity['user_id']).values(active=False))
            elif change=='remove_membership':
                # Admission history now deliberately prevents parent deletion;
                # membership revocation remains supported and must fence publish.
                await db.execute(delete(Member).where(Member.workspace_id==identity['workspace']))
            else:await db.execute(update(ModelProviderConnection).where(ModelProviderConnection.id==cid).values(updated_at=now()))
        return ['fixture-new']
    monkeypatch.setattr('pao.model_api.fetch_models',loader)
    result=await request_metadata(client,identity,route)
    assert result.status_code==(409 if change in ('rotate','disconnect','touch') else 403),result.text
    assert result.headers['cache-control']=='no-store'
    assert KEY not in result.text and 'fixture-new' not in result.text
    async with Session() as db:
        row=await db.get(ModelProviderConnection,cid)
        if row:assert row.model=='fixture-old' and row.model_count==0 and row.last_checked_at is None
        else:assert change=='disconnect'


async def test_connect_concurrent_creation_does_not_overwrite_winner(client,identity,monkeypatch):
    monkeypatch.setattr(settings(),'integration_encryption_key',Fernet.generate_key().decode())
    async def loader(provider,key):
        async with asyncio.timeout(3),Session.begin() as db:
            db.add(ModelProviderConnection(workspace_id=identity['workspace'],provider=provider,api_key_ciphertext=encrypt_key('fixture-winner-secret'),model='fixture-winner'))
        return ['fixture-new']
    monkeypatch.setattr('pao.model_api.fetch_models',loader)
    result=await request_metadata(client,identity,'connect')
    assert result.status_code==409
    async with Session() as db:
        assert (await db.scalar(select(ModelProviderConnection))).model=='fixture-winner'


@pytest.mark.parametrize('route',['connect','models','model'])
async def test_metadata_success_no_store_and_no_open_transaction(client,identity,monkeypatch,route):
    await configured(identity,monkeypatch)
    original=model_metadata.fetch
    async def wrapped(db,provider,key,loader):
        async def checked(provider,key):
            assert not db.in_transaction()
            return ['fixture-new','fixture-old']
        return await original(db,provider,key,checked)
    monkeypatch.setattr(model_metadata,'fetch',wrapped)
    result=await request_metadata(client,identity,route)
    assert result.status_code==200 and result.headers['cache-control']=='no-store',result.text
    assert KEY not in result.text


@pytest.mark.parametrize('route',['connect','models','model'])
async def test_metadata_custom_loader_deadline_no_publish(client,identity,monkeypatch,route):
    cid=await configured(identity,monkeypatch)
    async def loader(provider,key):await asyncio.sleep(2)
    monkeypatch.setattr('pao.model_api.fetch_models',loader)
    monkeypatch.setattr(model_metadata,'TIMEOUT',.05)
    result=await request_metadata(client,identity,route)
    assert result.status_code==503 and result.json()['detail']=='model_metadata_timeout'
    async with Session() as db:assert (await db.get(ModelProviderConnection,cid)).last_checked_at is None


async def test_metadata_input_body_and_validation_redaction(client,identity,monkeypatch):
    def forbidden(*args):raise AssertionError('no discovery')
    monkeypatch.setattr('pao.model_api.fetch_models',forbidden)
    body={'workspace_id':identity['workspace'],'api_key':KEY,'unexpected':KEY}
    result=await client.post('/v1/model-providers/openai/connect',headers=identity['owner'],json=body)
    assert result.status_code==422 and KEY not in result.text and result.headers['cache-control']=='no-store'
    result=await client.post('/v1/model-providers/openai/connect',headers=identity['owner'],json={**body,'api_key':KEY+'x'*9000})
    assert result.status_code==413 and KEY not in result.text and result.headers['cache-control']=='no-store'


async def test_metadata_other_sme_and_operator_denied_before_decrypt(client,identity,monkeypatch):
    await configured(identity,monkeypatch)
    def forbidden(*args):raise AssertionError('no credential or discovery')
    monkeypatch.setattr('pao.model_api.decrypt_key',forbidden)
    monkeypatch.setattr('pao.model_api.fetch_models',forbidden)
    async with Session.begin() as db:
        other=Workspace(name='Other SME');db.add(other);await db.flush();wid=other.id
    for headers,scope,code in ((identity['other'],identity['workspace'],403),(identity['owner'],wid,404)):
        result=await client.get('/v1/model-providers/openai/models',params={'workspace_id':scope},headers=headers)
        assert result.status_code==code


async def test_slow_metadata_does_not_hold_another_sme_hostage(client,identity,monkeypatch):
    await configured(identity,monkeypatch)
    async with Session.begin() as db:
        other=Workspace(name='SME B');db.add(other);await db.flush();wid=other.id
        db.add(Member(workspace_id=wid,user_id=identity['user_id'],role='owner'))
        db.add(ModelProviderConnection(workspace_id=wid,provider='openai',model='fixture-b',api_key_ciphertext=encrypt_key('fixture-b-secret')))
    entered=asyncio.Event();release=asyncio.Event()
    async def loader(provider,key):
        if key==KEY:
            entered.set();await release.wait()
            return ['fixture-old']
        assert key=='fixture-b-secret'
        return ['fixture-b']
    monkeypatch.setattr('pao.model_api.fetch_models',loader)
    task=asyncio.create_task(request_metadata(client,identity,'models'))
    try:
        async with asyncio.timeout(5):
            await entered.wait()
            result=await client.get('/v1/model-providers/openai/models',params={'workspace_id':wid},headers=identity['owner'])
        assert result.status_code==200 and result.json()['models']==['fixture-b'] and not task.done()
    finally:
        release.set();await task
