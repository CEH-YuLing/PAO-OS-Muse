"""Read-only Settings observation gates; no real provider credentials/calls."""
from sqlalchemy import select,func
from pao.db import Session
from pao.models import Workspace,Member,MetaConnection,GoogleAdsConnection,ModelProviderConnection
from p6_browser_harness import browser


async def test_settings_unknown_partial_refresh_switch_reload_and_mobile(client,identity):
    async with Session.begin() as db:
        other=Workspace(name='Settings SME B');db.add(other);await db.flush();wid=other.id
        db.add(Member(workspace_id=wid,user_id=identity['user_id'],role='operator'))
    result=await browser('scripts/verify_s23a_browser.cjs','PAO_SETTINGS_OBSERVATIONS_BROWSER',{
        'workspace':identity['workspace'],'second':wid},'s23a-settings')
    assert all(result[key] for key in ('partial_unknown','malformed_unknown','late_response','tenant_switch','reload','mobile','no_mutations','safety_unknown'))
    async with Session() as db:
        for model in (MetaConnection,GoogleAdsConnection,ModelProviderConnection):assert await db.scalar(select(func.count()).select_from(model))==0
