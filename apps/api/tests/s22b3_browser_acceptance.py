"""Quota Settings through owned HTTP; policies/leases exist only in pao_test."""
from uuid import uuid4
from sqlalchemy import select,func
from pao.db import Session
from pao.models import Workspace,Member,TenantResourcePolicy,TenantReadPolicy,TenantMetadataPolicy,TenantModelLease
from pao.modules.connections import resources
from test_tenant_model_resources import configure
from p6_browser_harness import browser


async def test_quota_settings_cas_unknown_switch_reload_and_mobile(client,identity):
    async with Session.begin() as db:
        b=Workspace(name='Quota SME B');c=Workspace(name='Quota SME employee');db.add_all([b,c]);await db.flush()
        db.add_all([Member(workspace_id=b.id,user_id=identity['user_id'],role='admin'),Member(workspace_id=c.id,user_id=identity['user_id'],role='operator')])
        second,employee=b.id,c.id
    assert (await configure(client,identity,calls=17)).status_code==200
    async with Session.begin() as db:
        await resources.lock(db,identity['workspace'])
        lease=await resources.admit(db,identity['workspace'],identity['user_id'],'management_probe',uuid4().hex,96)
        await db.flush();lid=lease.id
    async with Session.begin() as db:await resources.release(db,identity['workspace'],lease=lid)
    report=await browser('scripts/verify_s22b3_browser.cjs','PAO_QUOTA_BROWSER',{
        'workspace':identity['workspace'],'second':second,'employee':employee},'s22b3-quota')
    assert all(report[key] for key in ('cas','unknown_save','late_response','mobile_save','roles','reload','tenant_switch'))
    async with Session() as db:
        a=await db.get(TenantResourcePolicy,identity['workspace']);b=await db.get(TenantResourcePolicy,second)
        assert a.daily_model_calls==23 and a.version==4 and b.daily_model_calls==500 and b.version==1
        assert (await db.get(TenantReadPolicy,second)).daily_read_jobs==22
        assert (await db.get(TenantMetadataPolicy,second)).daily_metadata_requests==19
        for model in (TenantResourcePolicy,TenantReadPolicy,TenantMetadataPolicy):assert await db.get(model,employee) is None
        assert await db.scalar(select(func.count()).select_from(TenantModelLease))==1
