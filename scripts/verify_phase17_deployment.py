"""Read-only Phase 17 compatibility check on the current local deployment."""
import asyncio,json,re
from pathlib import Path
import httpx
from sqlalchemy import text
from pao.auth import issue_token
from pao.db import engine
from pao.config import settings
async def main():
    async with engine.connect() as db:
        user=await db.scalar(text('select id from users order by created_at limit 1'));revision=await db.scalar(text('select version_num from alembic_version'))
        counts={x:await db.scalar(text(f'select count(*) from {x}')) for x in ('automation_workflows','automation_workflow_audits')}
    headers={'Authorization':'Bearer '+issue_token(str(user))}
    async with httpx.AsyncClient(timeout=10) as client:
        ready=(await client.get('http://127.0.0.1:8000/ready')).status_code;page=await client.get('http://127.0.0.1:3100/')
        assets=sorted(set(re.findall(r'(?:src|href)="([^"?]+\.(?:js|css))',page.text)));codes=[(await client.get('http://127.0.0.1:3100'+x)).status_code for x in assets]
        status=(await client.get('http://127.0.0.1:8000/v1/automation/status',headers=headers)).json();autopilot=(await client.get('http://127.0.0.1:8000/v1/ads/autopilot/status',headers=headers)).json()
    report={'revision':revision,'ready':ready,'web':page.status_code,'assets_all_200':bool(assets) and all(x==200 for x in codes),'automation_tables':counts,
      'temporal_enabled':status.get('enabled'),'meta_write_enabled':settings().meta_write_enabled,'autopilot_global_enabled':autopilot.get('global_enabled'),'provider_write_attempted':False}
    assert revision in ('0016','0017') and ready==page.status_code==200 and report['assets_all_200'];assert settings().temporal_enabled and status.get('enabled') and not settings().meta_write_enabled and not autopilot.get('global_enabled')
    Path('.runtime/phase-17-health.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report));await engine.dispose()
asyncio.run(main())
