"""Verify idle local DB, back up, and apply additive Phase 18 migration."""
import asyncio,json,os,shutil,subprocess,sys
from datetime import datetime
from pathlib import Path
from sqlalchemy import text
from pao.config import settings
from pao.db import engine
DOCKER = os.environ.get("DOCKER_EXECUTABLE") or shutil.which("docker") or "docker"
OLD_TABLES=('users','workspaces','sessions','messages','runs','agent_runs','memories','tool_calls','tool_audits','telegram_peers','telegram_updates','telegram_deliveries','meta_connections','meta_oauth_states','meta_sync_jobs','meta_snapshots','ad_entities','ad_metrics','ad_sync_schedules','ad_reports','ad_report_deliveries','ad_report_schedules','ad_targets','ads_rules','ad_intelligence_runs','ad_anomalies','ad_recommendations','ads_actions','ads_action_audits','ads_autopilot_policies','ads_policy_audits','creative_assets','creative_metadata','creative_analysis_runs','creative_performance','creative_features','creative_learnings','attribution_sources','analytics_events','crm_leads','crm_stage_events','business_orders','attribution_runs','attribution_metrics','tracking_alerts','google_ads_connections','google_ads_oauth_states','google_ads_sync_jobs','automation_workflows','automation_workflow_audits')
async def snapshot():
    async with engine.connect() as db:
        for table,states in [('runs',"'queued','running'"),('tool_calls',"'queued','running'"),('memory_jobs',"'queued','running'"),('telegram_deliveries',"'queued','sending'"),('meta_sync_jobs',"'queued','running'")]:
            if await db.scalar(text(f'SELECT count(*) FROM {table} WHERE status IN ({states})')):raise RuntimeError(f'Wait until {table} is idle')
        if await db.scalar(text("select count(*) from ads_actions where execution_status in ('queued','executing')")):raise RuntimeError('Wait until Ads actions are idle')
        if await db.scalar(text("select count(*) from automation_workflows where status in ('starting','running')")):raise RuntimeError('Wait until automation workflows are idle')
        return {table:await db.scalar(text(f'SELECT count(*) FROM {table}')) for table in OLD_TABLES}
async def main():
    assert settings().database_url.endswith('/apex'),'Expected existing local apex database';before=await snapshot()
    if '--check' in sys.argv:print(json.dumps({'idle':True,'counts':before}));await engine.dispose();return
    stamp=datetime.now().strftime('%Y%m%d-%H%M%S');backup=Path(f'.runtime/pre-phase-18-{stamp}.dump')
    with backup.open('xb') as stream:subprocess.run([DOCKER,'exec','pao-postgres-1','pg_dump','-U','apex','-d','apex','-Fc'],stdout=stream,check=True)
    with backup.open('rb') as stream:subprocess.run([DOCKER,'exec','-i','pao-postgres-1','pg_restore','--list'],stdin=stream,stdout=subprocess.DEVNULL,check=True)
    subprocess.run([sys.executable,'-m','alembic','upgrade','0017'],check=True);after=await snapshot();assert before==after,'Existing counts changed'
    report={'backup':str(backup),'bytes':backup.stat().st_size,'before':before,'after':after,'revision':'0017'};Path('.runtime/phase-18-migration.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report));await engine.dispose()
asyncio.run(main())


