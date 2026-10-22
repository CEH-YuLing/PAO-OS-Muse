"""Real browser/API/DB, native Ads worker with synthetic normalized fixture."""
import asyncio
from datetime import date,timedelta
from uuid import uuid4
from unittest.mock import AsyncMock
from sqlalchemy import select
from pao.db import Session
from pao.models import AdEntity,MetaSyncJob,Member,Workspace,ConnectionReadActivation,AdMetric
from pao.integrations.meta.sync import sync_meta
from p6_browser_harness import browser
from test_meta import meta,connected


async def test_meta_consent_sync_report_revoke_switch(client,identity,meta,monkeypatch):
    c=identity;cid=await connected(c)
    async with Session.begin() as db:
        second=Workspace(name='Second Ads SME');db.add(second);await db.flush()
        db.add(Member(workspace_id=second.id,user_id=c['user_id'],role='owner'))
        discovery=MetaSyncJob(connection_id=cid,connection_version=1,api_version='v25.0',request_key='discovery',kind='accounts',status='completed')
        db.add(discovery);await db.flush()
        db.add(AdEntity(connection_id=cid,connection_version=1,platform='meta',account_id='act_123',
            kind='account',remote_id='act_123',currency='USD',timezone='UTC',source_job_id=discovery.id))
        second_id=second.id
    async def fetch(client,job):
        return [dict(connection_id=cid,connection_version=1,platform='meta',account_id='act_123',
            kind='account',remote_id='act_123',currency='USD',timezone='UTC',source_job_id=job.id)], [dict(connection_id=cid,connection_version=1,platform='meta',account_id='act_123',
            level='campaign',entity_id='123',day=date.fromisoformat(job.since),granularity='daily',
            currency='USD',timezone='UTC',attribution='fixture',source_job_id=job.id,spend=None)]
    monkeypatch.setattr('pao.integrations.meta.sync.fetch_warehouse',AsyncMock(side_effect=fetch))
    async def executor():
        for _ in range(900):
            async with Session() as db:
                job=await db.scalar(select(MetaSyncJob).where(MetaSyncJob.status=='queued',MetaSyncJob.connection_id==cid))
            if job:await sync_meta({},job.id);return job.id
            await asyncio.sleep(.1)
        raise AssertionError('Browser never admitted Ads fixture sync')
    task=asyncio.create_task(executor())
    try:
        report=await browser('scripts/verify_s21b2d_browser.cjs','PAO_S21B2D_BROWSER_FIXTURE',{
            'workspace':c['workspace'],'second':second_id,'actor':c['user_id'],'source':cid,
            'day':(date.today()-timedelta(days=1)).isoformat()},'s21b2d')
        jid=await asyncio.wait_for(task,5)
        assert report['actual_fixture_sync'] and report['tenant_switch'] and report['read_only']
        async with Session() as db:
            job=await db.get(MetaSyncJob,jid);assert job.status=='completed' and job.authority_pin['actor_id']==c['user_id']
            assert await db.scalar(select(ConnectionReadActivation.id))
            assert (await db.scalar(select(AdMetric))).spend is None
    finally:
        if not task.done():task.cancel()
        await asyncio.gather(task,return_exceptions=True)
