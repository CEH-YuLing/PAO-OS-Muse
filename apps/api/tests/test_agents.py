import asyncio
import pytest
from sqlalchemy import select, text
from pao.agents import route, ExecutionPlan
from pao.config import settings
from pao.db import Session, engine
from pao.gateway import Chunk
from pao.models import AgentRun, Member, Run, RunEvent
from pao.runtime import execute_run
from test_memory import run_chat, add, Gateway as MemoryGateway, memory_on


@pytest.fixture
def agent_on(monkeypatch):
    monkeypatch.setattr(settings(), 'agent_runtime_enabled', True)
    monkeypatch.setattr(settings(), 'engine_contract_enabled', True)
    monkeypatch.setattr(settings(), 'chat_features_enabled', True)


PLAN = {'goal':'Phân tích rồi biên tập', 'steps':[
    {'agent':'researcher','task':'Phân tích dữ liệu đã cung cấp','depends_on':[]},
    {'agent':'editor','task':'Biên tập kết quả phân tích','depends_on':[0]}]}


class Gateway:
    provider_name = 'ollama'
    def __init__(self):
        self.calls = []
        self.model_name = settings().ollama_model
    async def plan(self, messages):
        self.planning = messages
        return ExecutionPlan.model_validate(PLAN)
    async def stream(self, messages, max_tokens=None):
        self.calls.append(messages)
        chief='Chief of Staff' in messages[0]['content']
        yield Chunk(text='Chief final answer' if chief else 'specialist draft', usage={'eval_count':3})


async def test_sequential_plan_dependencies_final_only_and_owned_trace(client, identity, agent_on):
    _, rid = await run_chat(client, identity, 'Phân tích rồi biên tập nội dung giúp tôi.')
    gateway = Gateway()
    await execute_run({'gateway':gateway}, rid)
    await execute_run({'gateway':gateway}, rid)
    assert len(gateway.calls) == 3
    assert 'specialist draft' in gateway.calls[1][-1]['content']
    assert 'Specialist reference drafts' in gateway.calls[2][-1]['content']
    response = await client.get(f'/v1/runs/{rid}/execution', headers=identity['owner'])
    snapshot = response.json()
    assert snapshot['plan']['steps'][1]['depends_on'] == [0]
    assert [a['agent_key'] for a in snapshot['agents']] == ['chief_of_staff','researcher','editor']
    assert all(a['status'] == 'completed' and a['finished_at'] for a in snapshot['agents'])
    assert all(a['usage']['output_tokens'] == 3 for a in snapshot['agents'])
    assert (await client.get(f'/v1/runs/{rid}/execution',headers=identity['other'])).status_code == 404
    async with Session() as db:
        run = await db.get(Run,rid)
        assert run.response == 'Chief final answer'
        events = list(await db.scalars(select(RunEvent).where(RunEvent.run_id==rid).order_by(RunEvent.seq)))
        assert [e.data['text'] for e in events if e.type=='response.delta'] == ['Chief final answer']
        agent_events = [(e.type,e.data['agent_key']) for e in events if e.type.startswith('agent.')]
        assert agent_events == [('agent.started','chief_of_staff'),('agent.started','researcher'),
            ('agent.completed','researcher'),('agent.started','editor'),('agent.completed','editor'),('agent.completed','chief_of_staff')]


@pytest.mark.parametrize('steps', [
    [{'agent':'email','task':'Send something','depends_on':[]}],
    [{'agent':'editor','task':'Edit something','depends_on':[0]}],
    [{'agent':'editor','task':'Edit something','depends_on':[-1]}],
    [{'agent':'editor','task':'Edit something','depends_on':[]},{'agent':'editor','task':'Edit again','depends_on':[]}],
    [{'agent':'researcher','task':'Analyze facts','depends_on':[]},{'agent':'editor','task':'Edit facts','depends_on':[]},{'agent':'marketing','task':'Write copy','depends_on':[]}],
])
def test_router_rejects_unknown_cycles_duplicates_and_unbounded_steps(steps):
    with pytest.raises(ValueError):
        route({'goal':'Test', 'steps':steps})


async def test_invalid_accounted_planner_fails_closed_without_inference(client, identity, agent_on):
    class Invalid(Gateway):
        async def plan(self, messages):
            return {'goal':'Bad plan', 'steps':[{'agent':'email','task':'Send mail','depends_on':[]}]}
    _,rid = await run_chat(client,identity,'Xin chào trợ lý.')
    gateway = Invalid()
    await execute_run({'gateway':gateway},rid)
    snapshot = (await client.get(f'/v1/runs/{rid}/execution',headers=identity['owner'])).json()
    # Accounted planning normalizes malformed provider output to EngineFailure;
    # it cannot silently make an extra inference call to repair that response.
    assert len(snapshot['agents'])==1 and len(gateway.calls)==0
    assert snapshot['agents'][0]['status']=='failed'
    async with Session() as db:
        run=await db.get(Run,rid)
        assert run.status=='failed' and run.response==''


async def test_specialist_failure_preserves_partial_and_stops_dependents(client, identity, agent_on):
    class Broken(Gateway):
        async def stream(self, messages, max_tokens=None):
            yield Chunk(text='partial specialist')
            raise RuntimeError('private provider error')
    _,rid = await run_chat(client,identity,'Phân tích rồi biên tập giúp tôi.')
    await execute_run({'gateway':Broken()},rid)
    snapshot = (await client.get(f'/v1/runs/{rid}/execution',headers=identity['owner'])).json()
    assert [a['status'] for a in snapshot['agents']]==['failed','failed']
    assert snapshot['agents'][1]['output']=='partial specialist'
    async with Session() as db:
        run = await db.get(Run,rid)
        assert run.status=='failed' and run.response=='' and 'private' not in run.error_code


@pytest.mark.parametrize('revoke',[False,True])
async def test_cancel_or_revoke_stops_active_specialist(client, identity, agent_on, revoke):
    started = asyncio.Event()
    class Slow(Gateway):
        async def stream(self, messages, max_tokens=None):
            yield Chunk(text='partial')
            started.set()
            await asyncio.sleep(30)
    _,rid=await run_chat(client,identity,'Phân tích dữ liệu giúp tôi.')
    task=asyncio.create_task(execute_run({'gateway':Slow()},rid))
    await asyncio.wait_for(started.wait(),5)
    if revoke:
        async with Session.begin() as db:
            member=await db.get(Member,(identity['workspace'],identity['user_id']));member.role='viewer'
    else:
        assert (await client.post(f'/v1/runs/{rid}/cancel',headers=identity['owner'])).status_code==200
    await asyncio.wait_for(task,5)
    async with Session() as db:
        run=await db.get(Run,rid)
        agents=list(await db.scalars(select(AgentRun).where(AgentRun.run_id==rid)))
        assert run.status == ('failed' if revoke else 'cancelled')
        assert len(agents)==2 and all(a.status==run.status for a in agents)


async def test_registry_is_authenticated_and_has_only_implemented_agents(client, identity, agent_on):
    assert (await client.get('/v1/agents')).status_code==401
    rows=(await client.get('/v1/agents',headers=identity['owner'])).json()
    assert {r['key'] for r in rows}=={'chief_of_staff','researcher','editor','marketing','performance_analyst'}
    assert all(r['enabled'] and r['tools']==[] for r in rows)


async def test_downgrade_refuses_to_discard_multi_agent_history(client, identity, agent_on):
    from importlib import import_module
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    _,rid=await run_chat(client,identity,'Phân tích rồi biên tập nội dung.')
    await execute_run({'gateway':Gateway()},rid)
    async with Session() as db:
        agents=list(await db.scalars(select(AgentRun).where(AgentRun.run_id==rid)))
        assert len(agents)==3 and all(row.status=='completed' for row in agents)
        before=await db.scalar(text('SELECT version_num FROM alembic_version'))
    # Exercise the exact native 0003 guard, not a destructive full-chain CLI
    # downgrade of the shared test schema. Newer accounting guards also apply.
    migration=import_module('migrations.versions.0003_agent_runtime')
    async with engine.connect() as connection:
        transaction=await connection.begin()
        def guard(sync):
            with Operations.context(MigrationContext.configure(sync)):
                migration.downgrade()
        try:
            with pytest.raises(RuntimeError,match='Multi-agent history exists'):
                await connection.run_sync(guard)
        finally:
            await transaction.rollback()  # Also safe if the guard regresses.
    async with Session() as db:
        assert await db.scalar(text('SELECT version_num FROM alembic_version'))==before
        assert len(list(await db.scalars(select(AgentRun).where(AgentRun.run_id==rid))))==3


async def test_marketing_and_independent_dependencies(client, identity, agent_on):
    class Independent(Gateway):
        async def plan(self, messages):
            return ExecutionPlan.model_validate({'goal':'Drafts', 'steps':[{'agent':'marketing','task':'Draft campaign copy','depends_on':[]},
                {'agent':'editor','task':'Edit original text','depends_on':[]}]})
    _,rid=await run_chat(client,identity,'Soạn nội dung marketing và biên tập câu gốc riêng.')
    gateway=Independent()
    await execute_run({'gateway':gateway},rid)
    assert 'PAO Marketing' in gateway.calls[0][0]['content']
    assert 'specialist draft' not in gateway.calls[1][-1]['content']


async def test_performance_analyst_uses_only_scoped_structured_records(client,identity,agent_on):
    class Performance(Gateway):
        async def plan(self,messages):
            return ExecutionPlan.model_validate({'goal':'Explain Ads intelligence','steps':[{'agent':'performance_analyst','task':'Explain current Ads signals','depends_on':[]}]})
    _,rid=await run_chat(client,identity,'Có gì cần tối ưu?')
    gateway=Performance();await execute_run({'gateway':gateway},rid)
    specialist=gateway.calls[0]
    assert 'PAO Performance Analyst' in specialist[0]['content']
    assert 'Verified PAO intelligence records' in specialist[-1]['content']
    assert specialist[-1]['content'].endswith('[]')
    snapshot=(await client.get(f'/v1/runs/{rid}/execution',headers=identity['owner'])).json()
    assert snapshot['agents'][1]['agent_key']=='performance_analyst'


async def test_final_failure_retains_completed_specialists(client, identity, agent_on):
    class FinalFailure(Gateway):
        async def stream(self,messages,max_tokens=None):
            if 'Chief of Staff' in messages[0]['content']:
                raise RuntimeError('final provider failure')
            yield Chunk(text='Completed draft')
    _,rid=await run_chat(client,identity,'Phân tích rồi viết báo cáo ngắn.')
    await execute_run({'gateway':FinalFailure()},rid)
    snapshot=(await client.get(f'/v1/runs/{rid}/execution',headers=identity['owner'])).json()
    assert [a['status'] for a in snapshot['agents']]==['failed','completed','completed']


async def test_specialists_only_receive_session_brand_memory(client, identity, agent_on, memory_on):
    brands=[]
    for name in ['A','B']:
        brands.append((await client.post('/v1/brands',headers=identity['owner'],json={'workspace_id':identity['workspace'],'name':name})).json()['id'])
    await add(client,identity,value='Private A market Malaysia',brand_id=brands[0])
    await add(client,identity,value='Private B market Malaysia',brand_id=brands[1])
    sid=(await client.post('/v1/sessions',headers=identity['owner'],json={'workspace_id':identity['workspace'],'brand_id':brands[0]})).json()['id']
    _,rid=await run_chat(client,identity,'Analyze Malaysia market',session=sid)
    gateway=Gateway()
    await execute_run({'gateway':gateway,'memory_gateway':MemoryGateway()},rid)
    for context in [gateway.planning,*gateway.calls]:
        content=' '.join(m['content'] for m in context)
        assert 'Private A market Malaysia' in content and 'Private B market Malaysia' not in content
