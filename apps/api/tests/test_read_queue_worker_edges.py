"""Native worker/scheduler edge gates; no provider network or real credentials."""
import importlib
from datetime import timedelta
import pytest
from sqlalchemy import select,func
from pao.db import Session
from pao.models import MetaSyncJob,GoogleAdsSyncJob,AdEntity,AdSyncSchedule,now
from test_meta import meta
from test_google_ads import google_ads
from test_tenant_read_resources import configure,setup,insert,second


@pytest.mark.parametrize('kind',['meta','google'])
async def test_ads_wait_before_decrypt_then_release(client,identity,meta,google_ads,monkeypatch,kind):
    sources=await setup(identity);assert (await configure(client,identity,active=1)).status_code==200
    holder_kind='google' if kind=='meta' else 'meta'
    holder=await insert(identity,sources,holder_kind,'running');jid=await insert(identity,sources,kind)
    module=importlib.import_module('pao.integrations.'+('meta' if kind=='meta' else 'google_ads')+'.sync')
    execute=module.sync_meta if kind=='meta' else module.sync_google_ads
    original=module.decrypt
    def forbidden(*args):raise AssertionError('Busy SME resolved credential')
    monkeypatch.setattr(module,'decrypt',forbidden)
    await execute({},jid)
    model=MetaSyncJob if kind=='meta' else GoogleAdsSyncJob
    async with Session() as db:
        row=await db.get(model,jid);assert row.status=='queued' and row.attempts==0 and row.error_code=='tenant_read_concurrency_wait'
    async with Session.begin() as db:(await db.get(GoogleAdsSyncJob if kind=='meta' else MetaSyncJob,holder)).status='completed'
    monkeypatch.setattr(module,'decrypt',original)
    if kind=='meta':
        async def rows(*args):return;yield
        monkeypatch.setattr(module.MetaClient,'rows',rows)
    else:
        async def fetch(*args):return []
        monkeypatch.setattr(module,'fetch_accounts',fetch)
    await execute({},jid)
    async with Session() as db:assert (await db.get(model,jid)).status=='completed'


async def test_due_schedule_many_quota_blocked_a_b_admitted(client,identity,meta,google_ads):
    from pao.modules.business.warehouse_scheduler import schedule_warehouse
    a=await setup(identity);b=await second(identity);bs=await setup(b)
    assert (await configure(client,identity,daily=1)).status_code==200
    aid=await insert(identity,a,'meta','completed');bid=await insert(b,bs,'meta','completed')
    async with Session.begin() as db:
        for ctx,sources,count in ((identity,a,25),(b,bs,1)):
            for n in range(count):
                account=f'act_{n+1}'
                db.add(AdEntity(connection_id=sources['meta'],connection_version=1,platform='meta',kind='account',
                    account_id=account,remote_id=account,currency='USD',timezone='UTC',
                    source_job_id=aid if ctx['workspace']==identity['workspace'] else bid))
                db.add(AdSyncSchedule(connection_id=sources['meta'],connection_version=1,account_id=account,
                    granularity='daily',enabled=True,interval_minutes=15,lookback_days=1,next_at=now()-timedelta(minutes=5)))
    await schedule_warehouse({});await schedule_warehouse({})
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(MetaSyncJob).where(MetaSyncJob.connection_id==a['meta']))==1
        assert await db.scalar(select(func.count()).select_from(MetaSyncJob).where(MetaSyncJob.connection_id==bs['meta'],MetaSyncJob.status=='queued'))==1
