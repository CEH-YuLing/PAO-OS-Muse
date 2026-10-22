"""Actual planner + two specialist calls + Chief, isolated synthetic pao_test data."""
import os
import asyncio
import json
import time
from uuid import uuid4
from pathlib import Path
from pao.config import settings

os.environ['DATABASE_URL'] = settings().database_url.rsplit('/',1)[0] + '/pao_test'
settings.cache_clear()
assert settings().database_url.endswith('/pao_test')
from sqlalchemy import select
from pao.db import Session, engine
from pao.models import User, Workspace, Member, ChatSession, Run, Message, AgentRun, ToolCall
from pao.tool_gateway import propose, decide, execute_tool
from pao.runtime import execute_run


async def main():
    started = time.monotonic()
    prompt = 'Please use web.search to find official PostgreSQL documentation. Query: PostgreSQL official documentation. No specialist steps needed. Answer in one sentence with the official URL from search results.'
    async with Session.begin() as db:
        user=User(email=f'agents-{uuid4().hex}@example.test',password_hash='disabled-test-identity')
        workspace=Workspace(name='Synthetic Phase 5 acceptance')
        db.add_all([user,workspace]);await db.flush()
        db.add(Member(workspace_id=workspace.id,user_id=user.id,role='owner'))
        chat=ChatSession(workspace_id=workspace.id,user_id=user.id,memory_enabled=False)
        db.add(chat);await db.flush()
        run=Run(workspace_id=workspace.id,session_id=chat.id,prompt=prompt,request_key=uuid4().hex)
        db.add(run);await db.flush()
        db.add(Message(workspace_id=workspace.id,session_id=chat.id,run_id=run.id,role='user',content=prompt))
    print('Running real planner, SearXNG and Chief in pao_test',flush=True)
    await execute_run({},run.id)
    async with Session() as db:
        result=await db.get(Run,run.id)
        agents=list(await db.scalars(select(AgentRun).where(AgentRun.run_id==run.id).order_by(AgentRun.step_index)))
        calls=list(await db.scalars(select(ToolCall).where(ToolCall.run_id==run.id)))
        report={'tools':[{'name':c.name,'status':c.status,'result':c.result} for c in calls], 'database':'pao_test','run_id':run.id,'status':result.status,'error_code':result.error_code,
            'plan':result.execution_plan,'agents':[{'key':a.agent_key,'status':a.status,'output':a.output,'usage':a.usage} for a in agents],
            'elapsed_seconds':round(time.monotonic()-started,1),'answer':result.response}
    Path('.runtime/phase-5-local-acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True),flush=True)
    assert result.status=='completed',result.error_code
    assert any(c.name=='web.search' and c.status=='completed' and c.result.get('results') for c in calls)
    assert 'postgresql.org' in result.response
    call=await propose(run.id,user.id,'acceptance-mock-email',{'name':'email.mock_send','agent':'chief_of_staff','arguments':{'to':'qa@example.test','subject':'Phase 5 QA','body':'Synthetic local acceptance'}})
    await execute_tool({},call.id)
    async with Session() as db:
        assert (await db.get(ToolCall,call.id)).status=='pending'
    await decide(call.id,user.id,'approve',call.version)
    await execute_tool({},call.id)
    async with Session() as db:
        completed=await db.get(ToolCall,call.id)
        assert completed.status=='completed' and completed.result['delivered'] is False
        report['mock_approval']={'status':completed.status,'result':completed.result}
    Path('.runtime/phase-5-local-acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('PASS real search, planner, cited Chief answer and approved mock with no delivery',flush=True)
    await engine.dispose()

asyncio.run(main())
