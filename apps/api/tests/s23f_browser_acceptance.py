"""Team/account mobile Settings: real local HTTP, no business/provider writes."""
from sqlalchemy import select
from pao.db import Session
from pao.models import Brand,Member,User,Workspace,TenantConnectionGrant,TenantConnectionReference
from pao.config import ROOT
from pao.modules.operations.checkpoint import digest
from p6_browser_harness import browser

async def test_team_account_settings_context_recovery_all_tabs_mobile(client,identity):
    baseline=digest(ROOT/'.env')
    async with Session.begin() as db:
        second=Workspace(name='Operator SME');db.add(second);await db.flush()
        db.add(Member(workspace_id=second.id,user_id=identity['user_id'],role='operator'))
        other=await db.scalar(select(User).where(User.email=='other@example.test'))
        other.email='team-'+('very-long-name-'*9)+'@example.test'
        brand=Brand(workspace_id=identity['workspace'],name='Marketing '+('long-brand-'*9));db.add(brand);await db.flush()
        wid=second.id;email=other.email;bid=brand.id
    report=await browser('scripts/verify_s23f_browser.cjs','PAO_TEAM_BROWSER',{'workspace':identity['workspace'],'second':wid,'email':email,'brand':bid},'s23f-team')
    assert all(report[key] for key in ('unknown_recovery','partial_warning','late_response','operator_no_manager_get','all_tabs_mobile','focus_hit_test','copilot_preserved','no_mutations'))
    assert digest(ROOT/'.env')==baseline
    async with Session() as db:
        assert await db.scalar(select(TenantConnectionGrant.id).limit(1)) is None
        assert await db.scalar(select(TenantConnectionReference.id).limit(1)) is None
