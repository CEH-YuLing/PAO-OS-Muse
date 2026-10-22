"""One real Ollama Studio generation on synthetic pao_test data only."""
import asyncio,json,os,secrets
from uuid import uuid4
from urllib.parse import urlsplit,urlunsplit
from pao.config import settings
config=settings()
assert config.database_url.endswith('/pao_acos_local')
config.database_url=config.database_url.rsplit('/',1)[0]+'/pao_test'
redis=urlsplit(config.redis_url)
config.redis_url=urlunsplit((redis.scheme,redis.netloc,'/15','',''))
config.studio_enabled=config.engine_contract_enabled=config.chat_features_enabled=config.brain_manager_enabled=True
config.agent_runtime_enabled=True
config.memory_enabled=config.tools_enabled=config.knowledge_enabled=False
config.meta_enabled=config.google_ads_enabled=config.telegram_enabled=config.temporal_enabled=False
from httpx import ASGITransport,AsyncClient
from sqlalchemy import select
from pao.app import create_app
from pao.auth import issue_token,passwords
from pao.db import Session,engine
from pao.models import User,Workspace,Member,Run,LlmAttempt
from pao.runtime import execute_run

async def main():
    assert config.database_url.endswith('/pao_test') and config.redis_url.endswith('/15')
    async with Session.begin() as db:
        owner=User(email='p4-real-'+uuid4().hex+'@example.test',password_hash=passwords.hash(secrets.token_urlsafe(24)))
        workspace=Workspace(name='P4 synthetic real Ollama fixture')
        db.add_all([owner,workspace]);await db.flush()
        db.add(Member(workspace_id=workspace.id,user_id=owner.id,role='owner'))
    app=create_app();headers={'Authorization':'Bearer '+issue_token(owner.id)}
    async with app.router.lifespan_context(app),AsyncClient(transport=ASGITransport(app=app),base_url='http://test',headers=headers) as client:
        async def post(path,body):
            response=await client.post(path,json=body)
            assert response.status_code in (200,201,202),(path,response.status_code)
            return response.json()
        async def publish(data):
            for action in ('validate','review','publish'):
                data=await post(f"/v1/studio/definitions/{data['definition']['id']}/versions/{data['version']['id']}/actions/{action}",
                    {'revision':data['definition']['revision'],'self_review':True})
            return data
        agent=await publish(await post('/v1/studio/definitions',{'workspace_id':workspace.id,'kind':'agents','slug':'synthetic-agent','name':'Synthetic agent',
            'payload':{'instruction':'Return only the requested JSON object. No Markdown.'}}))
        schema={'type':'object','properties':{'text':{'type':'string','maxLength':80}},'required':['text'],'additionalProperties':False}
        skill=await post('/v1/studio/definitions',{'workspace_id':workspace.id,'kind':'skills','slug':'synthetic-echo','name':'Synthetic echo',
            'payload':{'instruction':'Copy input.text exactly into output.text. Return only JSON, no explanation and no Markdown.',
                'agent_version_id':agent['version']['id'],'input_schema':schema,'output_schema':schema,
                'exit_criteria':['equals_input:text'],'timeout_seconds':120,'token_budget':4096,'output_tokens':256}})
        await post(f"/v1/studio/definitions/{skill['definition']['id']}/versions/{skill['version']['id']}/fixture",
            {'input':{'text':'P4 synthetic'},'expected_output':{'text':'P4 synthetic'}})
        skill=await publish(skill)
        chat=await post('/v1/sessions',{'workspace_id':workspace.id})
        run=await post('/v1/runs',{'session_id':chat['id'],'request_key':uuid4().hex,'message':'/synthetic-echo {"text":"P4 synthetic"}'})
        await execute_run({'redis':app.state.redis},run['id'])
        async with Session() as db:
            current=await db.get(Run,run['id'])
            rows=list(await db.scalars(select(LlmAttempt).where(LlmAttempt.run_id==run['id'])))
            assert current.status=='completed',(current.status,current.error_code)
            assert json.loads(current.response)=={'text':'P4 synthetic'}
            assert len(rows)==1 and rows[0].usage_state=='reported'
            row=rows[0]
            print(json.dumps({'pass':True,'database':'pao_test','provider':'ollama','model':row.model,
                'source':row.source,'attempts':1,'input_tokens':row.input_tokens,'output_tokens':row.output_tokens,
                'ttft_ms':row.ttft_ms,'elapsed_ms':row.elapsed_ms,'tool_calls':0,'exit_criteria_passed':True}))
        await app.state.redis.zrem('arq:queue','run:'+run['id'])
        await app.state.redis.delete('arq:job:run:'+run['id'])
    await engine.dispose()
if __name__=='__main__':asyncio.run(main())
