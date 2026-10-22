"""Opt-in synthetic actual planner/final acceptance ONLY pao_test/Redis15."""
import asyncio,json
from uuid import uuid4
from urllib.parse import urlsplit
from httpx import ASGITransport,AsyncClient
from sqlalchemy import select
from pao.config import settings
from pao.db import Session,engine
from pao.main import app
from pao.models import User,Workspace,Member,Run,LlmAttempt
from pao.auth import issue_token
from pao.runtime import execute_run

async def main():
    config=settings()
    assert config.database_url.endswith('/pao_test') and urlsplit(config.redis_url).path=='/15'
    assert config.chat_features_enabled and config.engine_contract_enabled and config.agent_runtime_enabled
    assert not any((config.memory_enabled,config.tools_enabled,config.meta_enabled,config.google_ads_enabled,config.telegram_enabled))
    try:
        async with Session.begin() as db:
            owner=User(email='p3-real-'+uuid4().hex+'@example.test',password_hash='synthetic-no-login')
            workspace=Workspace(name='Synthetic P3 actual local model');db.add_all([owner,workspace]);await db.flush()
            db.add(Member(workspace_id=workspace.id,user_id=owner.id,role='owner'))
        headers={'Authorization':'Bearer '+issue_token(owner.id)}
        async with app.router.lifespan_context(app),AsyncClient(transport=ASGITransport(app=app),base_url='http://test') as client:
            chat=await client.post('/v1/sessions',headers=headers,json={'workspace_id':workspace.id});assert chat.status_code==201
            res=await client.post('/v1/runs',headers=headers,json={'session_id':chat.json()['id'],
                'message':'Synthetic local P3 verification. Reply exactly PAO OK. Use no tools and no specialist steps.', 'request_key':uuid4().hex})
            assert res.status_code==202,res.status_code;rid=res.json()['id']
            await execute_run({},rid)
        async with Session() as db:
            run=await db.get(Run,rid)
            rows=list(await db.scalars(select(LlmAttempt).where(LlmAttempt.run_id==rid).order_by(LlmAttempt.created_at)))
            report={'pass':run.status=='completed' and 'PAO OK' in run.response and len(rows)==2 and all(row.usage_state=='reported' for row in rows),
                'synthetic_only':True,'database':'pao_test','provider':'ollama','model':config.ollama_model,'status':run.status,
                'error_code':run.error_code,'attempts':[{'source':row.source,'status':row.status,'usage_state':row.usage_state,
                    'input_tokens':row.input_tokens,'output_tokens':row.output_tokens,'ttft_ms':row.ttft_ms,'elapsed_ms':row.elapsed_ms} for row in rows],
                'cloud_calls':0,'business_tools':0}
            print(json.dumps(report))
            if not report['pass']:raise SystemExit('Actual P3 Ollama runtime gate not met')
    finally:await engine.dispose()
if __name__=='__main__':asyncio.run(main())
