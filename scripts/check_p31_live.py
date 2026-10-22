"""Read-only live P3.1 gates; optional synthetic loopback text smoke only."""
import asyncio,json,sys,time
from pathlib import Path
import httpx
from sqlalchemy import select
from pao.config import ROOT,settings
from pao.db import Session,engine
from pao.auth import issue_token
from pao.models import ChatSession,Member,User
from pao.gateway import OllamaGateway
from pao.modules.engines.contract import ManagedEngine,capabilities
from pao.modules.engines.service import local_url

async def main():
    config=settings()
    assert ROOT.resolve()==Path('F:/PAO-ACOS') and config.database_url.endswith('/pao_acos_local') and config.engine_contract_enabled
    assert not any((config.meta_enabled,config.meta_write_enabled,config.google_ads_enabled,config.telegram_enabled,config.temporal_enabled,config.ads_autopilot_global_enabled,config.meta_autopilot_enabled))
    try:
        async with Session() as db,httpx.AsyncClient(base_url='http://127.0.0.1:8100',timeout=10,trust_env=False) as client:
            member=await db.scalar(select(Member).join(User,User.id==Member.user_id).where(Member.role=='owner',User.active.is_(True)).limit(1));assert member
            headers={'Authorization':'Bearer '+issue_token(member.user_id)}
            response=await client.get('/v1/engines',params={'workspace_id':member.workspace_id},headers=headers)
            assert response.status_code==200 and response.json()['available']
            rows=response.json()['engines'];local=next(row for row in rows if row['provider']=='ollama')
            assert local['error'] is None and config.ollama_model in local['models']
            session=await db.scalar(select(ChatSession).where(ChatSession.user_id==member.user_id,ChatSession.workspace_id==member.workspace_id,ChatSession.archived_at.is_(None)).limit(1))
            if session:
                before=(session.engine_config,session.engine_version)
                selected=await client.get(f'/v1/sessions/{session.id}/engine',headers=headers)
                assert selected.status_code==200 and selected.json()['available']
                await db.refresh(session);assert before==(session.engine_config,session.engine_version),'GET must not pin/mutate legacy session'
            result={'pass':True,'engine_enabled':True,'catalog_readonly':True,'installed_models':local['models'],
                    'configured_cloud_adapters':len(rows)-1,'legacy_get_non_mutating':bool(session),'cloud_calls':0}
        if '--local-smoke' in sys.argv:
            gateway=ManagedEngine(OllamaGateway(model=config.ollama_model,url=local_url()),capabilities('ollama'))
            started=time.monotonic();first=None;size=0;usage={}
            async with asyncio.timeout(90):
                async for chunk in gateway.stream([{'role':'system','content':'Synthetic local health check. Reply briefly.'},
                                                    {'role':'user','content':'Reply PAO OK.'}],max_tokens=16):
                    if chunk.text:
                        if first is None:first=time.monotonic()-started
                        size+=len(chunk.text)
                    if chunk.usage:usage=chunk.usage
            assert size>0
            result['local_text_smoke']={'provider':'ollama','model':gateway.model_name,'text_chars':size,
                'ttft_seconds':round(first,3),'latency_seconds':round(time.monotonic()-started,3),'usage_state':'reported' if usage else 'unknown',
                'synthetic_prompt_only':True,'database_writes':0,'tool_compatibility_verified':False}
        print(json.dumps(result))
    finally:await engine.dispose()
if __name__=='__main__':asyncio.run(main())
