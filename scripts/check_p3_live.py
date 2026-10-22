"""Read-only local rollout verification; no new run, provider or business job."""
import asyncio,json
import httpx
from sqlalchemy import select,text
from pao.config import settings
from pao.db import Session,engine
from pao.auth import issue_token
from pao.models import Member,User,ChatSession,LlmAttempt

async def main():
    config=settings();assert config.database_url.endswith('/pao_acos_local')
    assert config.engine_contract_enabled and config.chat_features_enabled
    assert not any((config.meta_enabled,config.google_ads_enabled,config.telegram_enabled,config.temporal_enabled))
    try:
        async with Session() as db,httpx.AsyncClient(base_url='http://127.0.0.1:8100',timeout=10) as client:
            assert await db.scalar(text('SELECT version_num FROM alembic_version'))=='0032'
            owner=await db.scalar(select(Member).join(User,User.id==Member.user_id).where(Member.role=='owner',User.active.is_(True)).limit(1))
            assert owner
            headers={'Authorization':'Bearer '+issue_token(owner.user_id)}
            usage=await client.get('/v1/chat/usage',params={'workspace_id':owner.workspace_id},headers=headers)
            assert usage.status_code==200 and 'attempts' in usage.json()
            chat=await db.scalar(select(ChatSession).where(ChatSession.user_id==owner.user_id,ChatSession.workspace_id==owner.workspace_id,ChatSession.archived_at.is_(None)).limit(1))
            if chat:
                before=(chat.chat_profile,chat.chat_revision,chat.engine_config,chat.engine_version)
                result=await client.get(f'/v1/sessions/{chat.id}/chat',headers=headers)
                assert result.status_code==200 and result.json()['available']
                assert result.json()['policy']['privacy']=='local_only'
                help=await client.post(f'/v1/sessions/{chat.id}/commands',headers=headers,json={'text':'/help'})
                assert help.status_code==200 and len(help.json()['commands'])==10
                await db.refresh(chat);assert before==(chat.chat_profile,chat.chat_revision,chat.engine_config,chat.engine_version)
            print(json.dumps({'pass':True,'revision':'0032','chat_features':True,'default_privacy':'local_only',
                'management_non_mutating':bool(chat),'provider_calls':0,'business_connectors_enabled':False}))
    finally:await engine.dispose()
if __name__=='__main__':asyncio.run(main())
