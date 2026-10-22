import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock
import httpx
import pytest
from sqlalchemy import select
from pao.config import settings
from pao.db import Session
from pao.models import ToolCall, ToolAudit, Member, Run, now
from pao.tool_gateway import execute_tool, dispatch_tools, invoke
from pao.runtime import execute_run
from test_memory import run_chat


@pytest.fixture
def tools_on(monkeypatch):
    monkeypatch.setattr(settings(),'tools_enabled',True)
    monkeypatch.setattr(settings(),'engine_contract_enabled',True)
    monkeypatch.setattr(settings(),'chat_features_enabled',True)


EMAIL={'name':'email.mock_send','agent':'chief_of_staff','arguments':{'to':'qa@example.test','subject':'Test mock','body':'Synthetic content only'}}


async def submit(client,identity,rid,payload=None,key='tool-test-key-01',headers=None):
    return await client.post(f'/v1/runs/{rid}/tools',headers=headers or identity['owner'],json={**(payload or EMAIL),'request_key':key})


async def decision(client,identity,call,action='approve',version=None,headers=None):
    return await client.post(f'/v1/tools/calls/{call["id"]}/decision',headers=headers or identity['owner'],json={
        'decision':action,'version':version or call['version']})


async def test_pending_never_executes_without_approval_and_audits(client,identity,tools_on):
    _,rid=await run_chat(client,identity,'Mô phỏng email kiểm thử.')
    call=(await submit(client,identity,rid)).json()
    provider=AsyncMock(return_value={'simulated':True,'delivered':False})
    await execute_tool({'tool_invoke':provider},call['id'])
    provider.assert_not_awaited()
    assert (await decision(client,identity,call,version=99)).status_code==409
    approved=await decision(client,identity,call)
    assert approved.status_code==200 and approved.json()['status']=='queued'
    assert (await decision(client,identity,call)).status_code==200
    await asyncio.gather(execute_tool({'tool_invoke':provider},call['id']),execute_tool({'tool_invoke':provider},call['id']))
    await execute_tool({'tool_invoke':provider},call['id'])
    provider.assert_awaited_once()
    snapshot=(await client.get(f'/v1/runs/{rid}/tools',headers=identity['owner'])).json()
    assert snapshot['calls'][0]['status']=='completed'
    assert [a['event'] for a in snapshot['audit']]==['tool.proposed','approval.approve','tool.started','tool.completed']
    assert (await client.get(f'/v1/runs/{rid}/tools',headers=identity['other'])).status_code==404
    assert (await decision(client,identity,call,headers=identity['other'])).status_code==404


async def test_concurrent_idempotency_and_changed_payload_conflict(client,identity,tools_on):
    _,rid=await run_chat(client,identity,'Test tool idempotency')
    responses=await asyncio.gather(submit(client,identity,rid),submit(client,identity,rid))
    assert all(r.status_code==201 for r in responses)
    assert responses[0].json()['id']==responses[1].json()['id']
    changed={**EMAIL,'arguments':{**EMAIL['arguments'],'body':'Changed content'}}
    assert (await submit(client,identity,rid,changed)).status_code==409


async def test_rejection_expiry_and_no_dispatch(client,identity,tools_on):
    _,rid=await run_chat(client,identity,'Reject tool')
    call=(await submit(client,identity,rid)).json()
    assert (await decision(client,identity,call,'reject')).json()['status']=='rejected'
    assert (await decision(client,identity,call)).status_code==409
    second=(await submit(client,identity,rid,key='another-request')).json()
    async with Session.begin() as db:
        row=await db.get(ToolCall,second['id']);row.created_at=now()-timedelta(hours=25)
    assert (await decision(client,identity,second)).status_code==409
    redis=AsyncMock()
    await dispatch_tools({'redis':redis})
    redis.enqueue_job.assert_not_awaited()
    async with Session() as db:
        assert (await db.get(ToolCall,second['id'])).status=='expired'


@pytest.mark.parametrize('revoke',[False,True])
async def test_recheck_after_approval_prevents_cancelled_or_revoked_execution(client,identity,tools_on,revoke):
    _,rid=await run_chat(client,identity,'Test changed permissions')
    call=(await submit(client,identity,rid)).json()
    await decision(client,identity,call)
    async with Session.begin() as db:
        if revoke:
            member=await db.get(Member,(identity['workspace'],identity['user_id']));member.role='viewer'
        else:
            run=await db.get(Run,rid);run.cancel_requested=True
    provider=AsyncMock()
    await execute_tool({'tool_invoke':provider},call['id'])
    provider.assert_not_awaited()
    async with Session() as db:
        assert (await db.get(ToolCall,call['id'])).status=='cancelled'


async def test_permissions_schema_and_audit(client,identity,tools_on):
    _,rid=await run_chat(client,identity,'Permission tests')
    assert (await submit(client,identity,rid,{**EMAIL,'agent':'editor'})).status_code==403
    assert (await submit(client,identity,rid,{'name':'web.search','arguments':{'query':'valid query','url':'http://localhost/private'}})).status_code==422
    async with Session.begin() as db:
        member=await db.get(Member,(identity['workspace'],identity['user_id']));member.role='analyst'
    assert (await submit(client,identity,rid)).status_code==403
    async with Session() as db:
        events=list(await db.scalars(select(ToolAudit.event).where(ToolAudit.run_id==rid)))
        assert events==['permission.denied']*3


async def test_worker_loss_unknown_never_auto_replays(client,identity,tools_on):
    _,rid=await run_chat(client,identity,'Recovery test')
    call=(await submit(client,identity,rid)).json()
    await decision(client,identity,call)
    async with Session.begin() as db:
        row=await db.get(ToolCall,call['id']);row.status='running';row.updated_at=now()-timedelta(minutes=5)
    redis=AsyncMock();await dispatch_tools({'redis':redis})
    redis.enqueue_job.assert_not_awaited()
    async with Session() as db:
        assert (await db.get(ToolCall,call['id'])).status=='unknown'


async def test_provider_failure_is_bounded_and_redacted(client,identity,tools_on):
    _,rid=await run_chat(client,identity,'Search test')
    call=(await submit(client,identity,rid,{'name':'web.search','arguments':{'query':'PAO test'}})).json()
    provider=AsyncMock(side_effect=RuntimeError('SECRET provider exception'))
    await execute_tool({'tool_invoke':provider},call['id'])
    await execute_tool({'tool_invoke':provider},call['id'])
    provider.assert_awaited_once()
    snapshot=(await client.get(f'/v1/runs/{rid}/tools',headers=identity['owner'])).json()
    assert snapshot['calls'][0]['status']=='failed' and 'SECRET' not in str(snapshot)


async def test_search_adapter_validates_urls_and_caps_results(monkeypatch):
    real_client=httpx.AsyncClient
    def response(request):
        assert request.url.params['format']=='json' and request.url.params['q']=='test query'
        return httpx.Response(200,json={'results':[{'url':'javascript:alert(1)','title':'bad'}]+[
            {'url':f'https://example.test/{i}','title':'Title','content':'Reference snippet'} for i in range(10)]})
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:real_client(transport=httpx.MockTransport(response),**kwargs))
    result=await invoke('web.search',{'query':'test query'},'test')
    assert len(result['results'])==5 and all(r['url'].startswith('https://') for r in result['results'])


async def test_calendar_and_email_are_explicit_simulations():
    email=await invoke('email.mock_send',EMAIL['arguments'],'stable-call')
    event=await invoke('calendar.mock_create',{},'stable-call')
    assert email['simulated'] and email['delivered'] is False
    assert event['simulated'] and event['external_event_created'] is False


async def test_planned_read_search_feeds_chief_but_mock_waits_for_approval(client,identity,tools_on,monkeypatch):
    from pao.gateway import Chunk
    from pao.agents import ExecutionPlan
    monkeypatch.setattr(settings(),'agent_runtime_enabled',True)
    class Gateway:
        provider_name='ollama'
        model_name=settings().ollama_model
        async def plan(self,messages):
            return ExecutionPlan.model_validate({'goal':'Use tools','steps':[],'tools':[
                {'name':'web.search','agent':'chief_of_staff','arguments':{'query':'synthetic topic'}},EMAIL]})
        async def stream(self,messages,max_tokens=None):
            self.context=messages
            yield Chunk(text='Mock email still requires approval.')
    _,rid=await run_chat(client,identity,'Search and prepare mock email.')
    gateway=Gateway();provider=AsyncMock(return_value={'results':[{'title':'Source','url':'https://example.test','snippet':'Synthetic evidence'}]})
    await execute_run({'gateway':gateway,'tool_invoke':provider},rid)
    assert provider.await_count==1 and 'Synthetic evidence' in str(gateway.context) and 'pending' in str(gateway.context)
    snapshot=(await client.get(f'/v1/runs/{rid}/tools',headers=identity['owner'])).json()
    assert [c['status'] for c in snapshot['calls']]==['completed','pending']


async def test_stopped_parent_cancels_pending_approval(client,identity,tools_on):
    _,rid=await run_chat(client,identity,'Stop approval')
    call=(await submit(client,identity,rid)).json()
    async with Session.begin() as db:
        run=await db.get(Run,rid);run.cancel_requested=True
    redis=AsyncMock();await dispatch_tools({'redis':redis})
    redis.enqueue_job.assert_not_awaited()
    async with Session() as db:
        assert (await db.get(ToolCall,call['id'])).status=='cancelled'


async def test_tool_quota_and_calendar_validation(client,identity,tools_on):
    _,rid=await run_chat(client,identity,'Bounded tools')
    for index in range(4):
        response=await submit(client,identity,rid,key=f'bounded-{index}')
        assert response.status_code==201
    assert (await submit(client,identity,rid,key='bounded-extra')).status_code==409
    invalid={'name':'calendar.mock_create','arguments':{'title':'Invalid interval','starts_at':'2026-09-13T15:00:00','ends_at':'2026-09-13T14:00:00'}}
    assert (await submit(client,identity,rid,invalid,key='calendar-invalid')).status_code==422
