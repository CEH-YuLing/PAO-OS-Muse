"""Read-only Phase 14 verification; never calls Meta or changes Ads."""
import asyncio,json,re
from pathlib import Path
import httpx
from sqlalchemy import text
from pao.auth import issue_token
from pao.db import engine
from pao.config import settings

async def main():
    async with engine.connect() as db:
        user=await db.scalar(text('select id from users order by created_at limit 1'));workspace=await db.scalar(text('select workspace_id from workspace_members where user_id=:uid limit 1'),{'uid':user})
        revision=await db.scalar(text('select version_num from alembic_version'))
        counts={table:await db.scalar(text(f'select count(*) from {table}')) for table in ('creative_assets','creative_metadata','creative_analysis_runs','creative_performance','creative_features','creative_learnings')}
    headers={'Authorization':'Bearer '+issue_token(str(user))}
    async with httpx.AsyncClient(timeout=10) as client:
        ready=(await client.get('http://127.0.0.1:8000/ready')).status_code;page=await client.get('http://127.0.0.1:3100/')
        assets=sorted(set(re.findall(r'(?:src|href)="([^"?]+\.(?:js|css))',page.text)));asset_codes=[(await client.get('http://127.0.0.1:3100'+path)).status_code for path in assets]
        connections=(await client.get(f'http://127.0.0.1:8000/v1/integrations/meta/connections?workspace_id={workspace}',headers=headers)).json()
        creative_status=None if not connections else 'requires_account'
        runtime=(await client.get('http://127.0.0.1:8000/v1/ads/autopilot/status',headers=headers)).json()
    report={'revision':revision,'ready':ready,'web':page.status_code,'asset_count':len(assets),'assets_all_200':bool(assets) and all(x==200 for x in asset_codes),
        'creative_tables':counts,'creative_api':creative_status,'meta_write_enabled':settings().meta_write_enabled,'autopilot_global_enabled':runtime.get('global_enabled'),
        'meta_autopilot_enabled':runtime.get('meta_enabled'),'provider_write_attempted':False}
    assert revision=='0013' and ready==page.status_code==200 and report['assets_all_200']
    assert settings().meta_write_enabled is False and runtime.get('global_enabled') is False and runtime.get('meta_enabled') is False
    Path('.runtime/phase-14-health.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report));await engine.dispose()
asyncio.run(main())
