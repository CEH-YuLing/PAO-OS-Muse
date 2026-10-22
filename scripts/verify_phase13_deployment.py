"""Read-only Phase 13 verification; does not enable Autopilot or call Meta."""
import asyncio,json,re
from pathlib import Path
import httpx
from sqlalchemy import text
from pao.auth import issue_token
from pao.db import engine


async def main():
    async with engine.connect() as db:
        user=await db.scalar(text('select id from users order by created_at limit 1'))
        workspace=await db.scalar(text('select workspace_id from workspace_members where user_id=:uid limit 1'),{'uid':user})
        revision=await db.scalar(text('select version_num from alembic_version'))
        counts={table:await db.scalar(text(f'select count(*) from {table}')) for table in
            ('ads_autopilot_policies','ads_policy_audits','ads_actions','ads_action_audits')}
    headers={'Authorization':'Bearer '+issue_token(str(user))}
    async with httpx.AsyncClient(timeout=10) as client:
        ready=(await client.get('http://127.0.0.1:8000/ready')).status_code
        page=await client.get('http://127.0.0.1:3100/')
        assets=sorted(set(re.findall(r'(?:src|href)="([^"?]+\.(?:js|css))',page.text)))
        asset_codes=[(await client.get('http://127.0.0.1:3100'+path)).status_code for path in assets]
        runtime_response=await client.get('http://127.0.0.1:8000/v1/ads/autopilot/status',headers=headers)
        policies_response=await client.get(f'http://127.0.0.1:8000/v1/ads/autopilot/policies?workspace_id={workspace}',headers=headers)
    runtime=runtime_response.json()
    report={'revision':revision,'ready':ready,'web':page.status_code,'asset_count':len(assets),
        'assets_all_200':bool(assets) and all(code==200 for code in asset_codes),
        'runtime_api':runtime_response.status_code,'policies_api':policies_response.status_code,
        'global_enabled':runtime.get('global_enabled'),'meta_enabled':runtime.get('meta_enabled'),
        'default_mode':runtime.get('default_mode'),'policies_empty':policies_response.json()==[],
        'counts':counts,'provider_write_attempted':False}
    assert report['revision']=='0012' and report['ready']==report['web']==200 and report['assets_all_200']
    assert report['runtime_api']==report['policies_api']==200
    assert report['global_enabled'] is False and report['meta_enabled'] is False and report['default_mode']=='observer'
    assert report['policies_empty'] and all(value==0 for value in counts.values())
    Path('.runtime/phase-13-health.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report));await engine.dispose()


asyncio.run(main())
