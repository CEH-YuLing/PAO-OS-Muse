"""Real SME admissions around fixture loopback metadata, never cloud inference."""
import asyncio
from uuid import uuid4
import httpx
import pytest
from sqlalchemy import select,update,delete
from pao.config import settings
from pao.db import Session
from pao.models import User,Member,Workspace,ChatSession,TenantMetadataLease,now
from pao.modules.engines import api,metadata,service
from pao.modules.engines.contract import EngineFailure
from test_engine_contract import engines,session,run
from test_tenant_metadata_resources import configure,usage


async def catalog(client,identity,nonce=None,wid=None):
    return await client.get('/v1/engines',headers={**identity['owner'],**({'Idempotency-Key':str(nonce)} if nonce else {})},params={'workspace_id':wid or identity['workspace']})


async def choose(client,identity,sid,nonce=None):
    return await client.put(f'/v1/sessions/{sid}/engine',headers={**identity['owner'],**({'Idempotency-Key':str(nonce)} if nonce else {})},
        json={'provider':'ollama','model':'local-a','version':1})


async def test_local_and_cloud_metadata_share_daily_replay_pool(client,identity,engines,monkeypatch):
    assert (await configure(client,identity,daily=1)).status_code==200
    calls=[]
    async def tags():calls.append(True);return ['local-a']
    monkeypatch.setattr(api,'local_models',tags)
    nonce=uuid4();result=await catalog(client,identity,nonce)
    assert result.status_code==200 and result.headers['cache-control']=='no-store' and calls==[True]
    assert (await catalog(client,identity,nonce)).status_code==409
    sid=await session(client,identity)
    assert (await choose(client,identity,sid)).status_code==429
    def forbidden(*args):raise AssertionError('Quota before key resolution or cloud I/O')
    monkeypatch.setattr('pao.model_api.encrypt_key',forbidden)
    bad=await client.post('/v1/model-providers/openai/connect',headers=identity['owner'],json={'workspace_id':identity['workspace'],'api_key':'fixture-never-resolved'})
    assert bad.status_code==429 and calls==[True]
    used=await usage(identity);assert used['daily_requests']==1 and used['active_requests']==0
    async with Session() as db:assert (await db.get(ChatSession,sid)).engine_version==1


async def test_local_selection_one_admission_no_second_discovery(client,identity,engines,monkeypatch):
    sid=await session(client,identity);calls=[]
    async def tags():calls.append(True);return ['local-a']
    monkeypatch.setattr(api,'local_models',tags)
    async def forbidden():raise AssertionError('No unaccounted nested /api/tags')
    monkeypatch.setattr(service,'local_models',forbidden)
    result=await choose(client,identity,sid,uuid4())
    assert result.status_code==200 and result.json()['version']==2 and calls==[True]
    used=await usage(identity);assert used['daily_requests']==1 and used['active_requests']==0
    async with Session() as db:
        lease=await db.scalar(select(TenantMetadataLease));assert lease.kind=='model_select' and lease.status=='released'


async def test_read_member_keeps_catalogue_but_no_model_write(client,identity,engines):
    sid=await session(client,identity)
    async with Session.begin() as db:await db.execute(update(Member).where(Member.user_id==identity['user_id']).values(role='viewer'))
    assert (await catalog(client,identity)).status_code==200
    assert (await choose(client,identity,sid)).status_code==403
    assert (await usage(identity))['daily_requests']==1


async def test_flag_acl_stale_version_bad_nonce_or_grant_before_io(client,identity,engines,monkeypatch):
    sid=await session(client,identity)
    async def forbidden():raise AssertionError('No local or remote I/O')
    monkeypatch.setattr(api,'local_models',forbidden)
    result=await client.get('/v1/engines',headers=identity['outsider'],params={'workspace_id':identity['workspace']});assert result.status_code==404
    result=await client.get('/v1/engines',headers={**identity['owner'],'Idempotency-Key':'fixture-invalid-sensitive'},params={'workspace_id':identity['workspace']})
    assert result.status_code==422 and 'fixture-invalid-sensitive' not in result.text and result.headers['cache-control']=='no-store'
    result=await client.put(f'/v1/sessions/{sid}/engine',headers=identity['owner'],json={'provider':'ollama','model':'local-a','version':99});assert result.status_code==409
    result=await client.put(f'/v1/sessions/{sid}/engine',headers=identity['owner'],json={'provider':'ollama','model':'local-a','version':1,'grant_id':str(uuid4())});assert result.status_code==409
    monkeypatch.setattr(settings(),'engine_contract_enabled',False)
    result=await catalog(client,identity);assert result.status_code==200 and result.json()['available'] is False
    assert (await usage(identity))['daily_requests']==0


@pytest.mark.parametrize('action',['catalogue','selection'])
@pytest.mark.parametrize('change',['remove','deactivate','expire','feature','endpoint'])
@pytest.mark.parametrize('failed',[False,True])
async def test_late_actor_source_changes_never_publish(client,identity,engines,monkeypatch,action,change,failed):
    sid=await session(client,identity)
    original=metadata.actor;seen=[]
    async def tracked(db,*args,**kwargs):seen.append(db);return await original(db,*args,**kwargs)
    monkeypatch.setattr(metadata,'actor',tracked)
    async def tags():
        assert not seen[-1].in_transaction()
        async with asyncio.timeout(3),Session.begin() as db:
            if change=='remove':await db.execute(delete(Member).where(Member.workspace_id==identity['workspace'],Member.user_id==identity['user_id']))
            elif change=='deactivate':await db.execute(update(User).where(User.id==identity['user_id']).values(active=False))
        if change=='expire':monkeypatch.setattr(metadata.time,'time',lambda:10**12)
        elif change=='feature':monkeypatch.setattr(settings(),'engine_contract_enabled',False)
        elif change=='endpoint':monkeypatch.setattr(settings(),'ollama_url','http://127.0.0.1:11435')
        if failed:raise RuntimeError('fixture-private-error')
        return ['local-a','never-publish-fixture']
    monkeypatch.setattr(api,'local_models',tags)
    result=await (catalog(client,identity) if action=='catalogue' else choose(client,identity,sid))
    assert result.status_code==({'feature':503,'endpoint':409}.get(change,403)) and 'never-publish-fixture' not in result.text
    async with Session() as db:
        assert (await db.get(ChatSession,sid)).engine_version==1
        assert (await db.scalar(select(TenantMetadataLease))).status=='released'


@pytest.mark.parametrize('change',['viewer','archive','owner','version','config','profile','scope','run'])
async def test_selection_session_changed_during_io_no_update(client,identity,engines,monkeypatch,change):
    sid=await session(client,identity)
    async with Session.begin() as db:
        other=Workspace(name='Other SME');db.add(other);await db.flush();wid=other.id
        db.add(Member(workspace_id=wid,user_id=identity['user_id'],role='owner'))
        other_user=await db.scalar(select(User.id).where(User.email=='other@example.test'))
    async def tags():
        if change=='run':await run(client,identity,sid)
        else:
            async with asyncio.timeout(3),Session.begin() as db:
                if change=='viewer':await db.execute(update(Member).where(Member.workspace_id==identity['workspace'],Member.user_id==identity['user_id']).values(role='viewer'))
                else:
                    values={'archive':{'archived_at':now()},'owner':{'user_id':other_user},
                        'version':{'engine_version':2},'config':{'engine_config':{'provider':'ollama','model':'local-b'}},
                        'profile':{'chat_revision':ChatSession.chat_revision+1},'scope':{'workspace_id':wid,'brain_id':None,'brand_id':None}}[change]
                    await db.execute(update(ChatSession).where(ChatSession.id==sid).values(**values))
        return ['local-a']
    monkeypatch.setattr(api,'local_models',tags)
    result=await choose(client,identity,sid)
    assert result.status_code==({'viewer':403,'archive':404,'owner':404,'scope':403}.get(change,409)),result.text
    async with Session() as db:
        chat=await db.get(ChatSession,sid)
        assert (chat.engine_config or {}).get('model')!='local-a' or change=='run'
        lease=await db.scalar(select(TenantMetadataLease));assert lease.workspace_id==identity['workspace'] and lease.status=='released'


@pytest.mark.parametrize('action',['catalogue','selection'])
@pytest.mark.parametrize('failure',['timeout','exception','malformed'])
async def test_failure_release_daily_kept_no_secret_or_selection(client,identity,engines,monkeypatch,action,failure):
    sid=await session(client,identity)
    monkeypatch.setattr(metadata,'TIMEOUT',.03)
    async def tags():
        if failure=='timeout':await asyncio.sleep(2)
        elif failure=='exception':raise RuntimeError('fixture-private-error')
        else:return {'private':'fixture-private-error'}
    monkeypatch.setattr(api,'local_models',tags)
    result=await (catalog(client,identity) if action=='catalogue' else choose(client,identity,sid))
    assert result.status_code==(200 if action=='catalogue' else 409) and 'fixture-private-error' not in result.text
    assert result.headers['cache-control']=='no-store'
    used=await usage(identity);assert used['daily_requests']==1 and used['active_requests']==0
    async with Session() as db:assert (await db.get(ChatSession,sid)).engine_config is None


async def test_busy_sme_a_does_not_block_b_and_cancel_releases(client,identity,engines,monkeypatch):
    assert (await configure(client,identity,daily=3,slots=1)).status_code==200
    async with Session.begin() as db:
        b=Workspace(name='SME B');db.add(b);await db.flush();wid=b.id
        db.add(Member(workspace_id=wid,user_id=identity['user_id'],role='owner'))
    entered=asyncio.Event();blocked=asyncio.Event();calls=0
    async def tags():
        nonlocal calls
        calls+=1
        if calls==1:entered.set();await blocked.wait()
        return ['local-a']
    monkeypatch.setattr(api,'local_models',tags)
    task=asyncio.create_task(catalog(client,identity))
    try:
        async with asyncio.timeout(5):
            await entered.wait()
            assert (await catalog(client,identity)).status_code==429
            assert (await catalog(client,identity,wid=wid)).status_code==200
        task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
        assert calls==2 and (await usage(identity))['active_requests']==0
        assert (await catalog(client,identity)).status_code==200
    finally:
        blocked.set()
        if not task.done():task.cancel()
        await asyncio.gather(task,return_exceptions=True)


@pytest.mark.parametrize('payload',[[],{'models':None},{'models':{}},{'models':[{'name':'x'}]*501}])
async def test_native_local_catalogue_schema_limits(payload):
    with pytest.raises(EngineFailure,match='^engine_local_offline$'):
        await service.local_models(httpx.MockTransport(lambda request:httpx.Response(200,json=payload)))


async def test_native_loopback_pin_bytes_json_redirect_and_no_proxy(monkeypatch):
    calls=[]
    def reply(request):
        calls.append(request)
        assert request.url.host=='127.0.0.1' and request.url.path=='/api/tags' and not request.url.query
        assert 'authorization' not in request.headers
        return httpx.Response(200,json={'models':[{'name':'local-a'},{'name':'local-a'},{'name':'local-b'}]})
    monkeypatch.setattr(settings(),'ollama_url','http://127.0.0.1:11434')
    monkeypatch.setenv('HTTP_PROXY','http://fixture-never-used:9000')
    assert await service.local_models(httpx.MockTransport(reply))==['local-a','local-b'] and len(calls)==1
    for response in (httpx.Response(302,headers={'location':'http://private.invalid/tags'}),
        httpx.Response(200,headers={'content-type':'text/plain'},text='fixture-private-error'),
        httpx.Response(200,headers={'content-type':'application/json'},content=b'x'*262145)):
        with pytest.raises(EngineFailure,match='^engine_local_offline$') as exc:
            await service.local_models(httpx.MockTransport(lambda request:response))
        assert 'fixture-private-error' not in str(exc.value)
