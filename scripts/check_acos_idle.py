"""Refuse planned runtime restart while chat or tool jobs are active."""
import asyncio
import sys
from sqlalchemy import text
from pao.config import settings
from pao.db import engine


async def main():
    if not settings().database_url.endswith('/pao_acos_local'):
        raise SystemExit('Refusing to check a non-ACOS database.')
    try:
        async with engine.connect() as db:
            counts = {
                'runs': await db.scalar(text("SELECT count(*) FROM runs WHERE status IN ('queued','running')")),
                'tool_calls': await db.scalar(text("SELECT count(*) FROM tool_calls WHERE status IN ('queued','running')")),
                'pending_tools': await db.scalar(text("SELECT count(*) FROM tool_calls WHERE status IN ('pending','unknown')")),
                'task_attempts': await db.scalar(text("SELECT count(*) FROM task_attempts WHERE status IN ('queued','running','waiting_approval')")),
                'memory_jobs': await db.scalar(text("SELECT count(*) FROM memory_jobs WHERE status IN ('queued','running')")),
                'meta_sync_jobs': await db.scalar(text("SELECT count(*) FROM meta_sync_jobs WHERE status IN ('queued','running')")),
                'google_ads_sync_jobs': await db.scalar(text("SELECT count(*) FROM google_ads_sync_jobs WHERE status IN ('queued','running')")),
                'ads_actions': await db.scalar(text("SELECT count(*) FROM ads_actions WHERE execution_status IN ('pending','queued','executing','unknown')")),
                'automation_workflows': await db.scalar(text("SELECT count(*) FROM automation_workflows WHERE status IN ('starting','running','waiting_approval','waiting_timer')")),
                'automation_outbox': await db.scalar(text("SELECT count(*) FROM automation_outbox WHERE status IN ('pending','processing')")),
            }
            if await db.scalar(text("SELECT to_regclass('public.knowledge_ingestion_jobs') IS NOT NULL")):
                counts['source_ingestion_jobs']=await db.scalar(text("SELECT count(*) FROM knowledge_ingestion_jobs WHERE status IN ('queued','running')"))
            if await db.scalar(text("SELECT to_regclass('public.knowledge_index_jobs') IS NOT NULL")):
                counts['source_index_jobs']=await db.scalar(text("SELECT count(*) FROM knowledge_index_jobs WHERE status IN ('queued','running')"))
            if await db.scalar(text("SELECT to_regclass('public.studio_executions') IS NOT NULL")):
                counts['studio_executions']=await db.scalar(text("SELECT count(*) FROM studio_executions WHERE status NOT IN ('completed','cancelled','manual_review')"))
                counts['studio_commands']=await db.scalar(text("SELECT count(*) FROM studio_commands WHERE status IN ('pending','processing')"))
            if await db.scalar(text("SELECT to_regclass('public.goal_executions') IS NOT NULL")):
                counts['goal_executions']=await db.scalar(text("SELECT count(*) FROM goal_executions WHERE status NOT IN ('completed','cancelled','budget_exhausted','deadline_exceeded','manual_review') OR reserved_cost_microusd>0"))
                counts['goal_commands']=await db.scalar(text("SELECT count(*) FROM goal_commands WHERE status IN ('pending','processing')"))
            for name in ('result_deliveries','goal_result_deliveries'):
                if await db.scalar(text("SELECT to_regclass('public."+name+"') IS NOT NULL")):
                    counts[name]=await db.scalar(text('SELECT count(*) FROM '+name+" WHERE status='pending'"))
            if await db.scalar(text("SELECT to_regclass('public.voice_turns') IS NOT NULL")):
                counts['voice_transcribing']=await db.scalar(text("SELECT count(*) FROM voice_turns WHERE status='transcribing'"))
            if await db.scalar(text("SELECT to_regclass('public.channel_outbox') IS NOT NULL")):
                counts['channel_sending']=await db.scalar(text("SELECT count(*) FROM channel_outbox WHERE status='sending'"))
        print('Active jobs:', counts)
        if any(counts.values()):
            raise SystemExit('Wait for active jobs to complete before restarting.')
        if '--safe-repair' in sys.argv:
            config = settings()
            if any(getattr(config, key) for key in ('meta_enabled','meta_write_enabled',
                'google_ads_enabled','telegram_enabled','temporal_enabled','ads_autopilot_global_enabled')):
                raise SystemExit('Safe repair refuses enabled external integrations.')
            async with engine.connect() as db:
                schedules = await db.scalar(text('SELECT (SELECT count(*) FROM ad_sync_schedules WHERE enabled) + (SELECT count(*) FROM ad_report_schedules WHERE enabled)'))
            if schedules:
                raise SystemExit('Safe repair refuses enabled sync/report schedules.')
    finally:
        await engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
