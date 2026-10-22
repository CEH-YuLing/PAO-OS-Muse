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
from pao.models import User, Workspace, Member, ChatSession, Run, Message, AgentRun
from pao.runtime import execute_run


async def main():
    started = time.monotonic()
    prompt = ('Tôi yêu cầu đúng hai bước: Researcher phân tích dữ liệu sau trong tối đa hai câu, '
        'sau đó Editor dùng kết quả Researcher để viết một đoạn báo cáo ngắn. '
        'Dữ liệu giả lập: chiến dịch có 100 lượt xem và 5 đơn hàng; chưa có dữ liệu doanh thu hoặc chi phí. '
        'Không tìm kiếm web. Chief chỉ trả lời cuối cùng trong hai câu, không giải thích quy trình.')
    async with Session.begin() as db:
        user=User(email=f'agents-{uuid4().hex}@example.test',password_hash='disabled-test-identity')
        workspace=Workspace(name='Synthetic Phase 4 acceptance')
        db.add_all([user,workspace]);await db.flush()
        db.add(Member(workspace_id=workspace.id,user_id=user.id,role='owner'))
        chat=ChatSession(workspace_id=workspace.id,user_id=user.id,memory_enabled=False)
        db.add(chat);await db.flush()
        run=Run(workspace_id=workspace.id,session_id=chat.id,prompt=prompt,request_key=uuid4().hex)
        db.add(run);await db.flush()
        db.add(Message(workspace_id=workspace.id,session_id=chat.id,run_id=run.id,role='user',content=prompt))
    print('Running real planner, specialists and Chief in pao_test',flush=True)
    await execute_run({},run.id)
    async with Session() as db:
        result=await db.get(Run,run.id)
        agents=list(await db.scalars(select(AgentRun).where(AgentRun.run_id==run.id).order_by(AgentRun.step_index)))
        report={'database':'pao_test','run_id':run.id,'status':result.status,'error_code':result.error_code,
            'plan':result.execution_plan,'agents':[{'key':a.agent_key,'status':a.status,'output':a.output,'usage':a.usage} for a in agents],
            'elapsed_seconds':round(time.monotonic()-started,1),'answer':result.response}
    Path('.runtime/phase-4-local-acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True),flush=True)
    assert result.status=='completed',result.error_code
    assert [a.agent_key for a in agents]==['chief_of_staff','researcher','editor']
    assert all(a.status=='completed' and a.output.strip() for a in agents)
    assert result.execution_plan['steps'][1]['depends_on']==[0]
    assert '5' in result.response and result.response.strip()
    await engine.dispose()

asyncio.run(main())
