"""Read-only Phase 16 verification; never calls Google or changes Ads."""
import asyncio,json,re
from pathlib import Path
import httpx
from sqlalchemy import text
from pao.auth import issue_token
from pao.db import engine
from pao.config import settings
async def main():
    async with engine.connect() as db:
        user=await db.scalar(text('select id from users order by created_at limit 1'));workspace=await db.scalar(text('select workspace_id from workspace_members where user_id=:u limit 1'),{'u':user});revision=await db.scalar(text('select version_num from alembic_version'));counts={x:await db.scalar(text(f'select count(*) from {x}')) for x in ('google_ads_connections','google_ads_oauth_states','google_ads_sync_jobs')};google_columns=await db.scalar(text("select count(*) from information_schema.columns where table_name='ad_metrics' and column_name in ('google_connection_id','google_source_job_id','conversions','conversion_value')"))
    headers={'Authorization':'Bearer '+issue_token(str(user))}
    async with httpx.AsyncClient(timeout=10) as client:
        ready=(await client.get('http://127.0.0.1:8000/ready')).status_code;page=await client.get('http://127.0.0.1:3100/');assets=sorted(set(re.findall(r'(?:src|href)="([^"?]+\.(?:js|css))',page.text)));codes=[(await client.get('http://127.0.0.1:3100'+x)).status_code for x in assets];status=(await client.get(f'http://127.0.0.1:8000/v1/integrations/google-ads/connection?workspace_id={workspace}',headers=headers)).json();autopilot=(await client.get('http://127.0.0.1:8000/v1/ads/autopilot/status',headers=headers)).json()
    report={'revision':revision,'ready':ready,'web':page.status_code,'assets_all_200':bool(assets) and all(x==200 for x in codes),'google_tables':counts,'google_metric_columns':google_columns,'google_configured':status.get('configured'),'google_status':status.get('status'),'google_ads_enabled':settings().google_ads_enabled,'meta_write_enabled':settings().meta_write_enabled,'autopilot_global_enabled':autopilot.get('global_enabled'),'provider_write_attempted':False}
    assert revision=='0015' and ready==page.status_code==200 and report['assets_all_200'] and google_columns==4;assert not settings().google_ads_enabled and not settings().meta_write_enabled and not autopilot.get('global_enabled');Path('.runtime/phase-16-health.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report));await engine.dispose()
asyncio.run(main())
