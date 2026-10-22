"""Native Ads OAuth/cookies/DB; browser provider landing and transport synthetic."""
from datetime import timedelta
from unittest.mock import AsyncMock
from sqlalchemy import select,func
from pao.db import Session
from pao.models import Workspace,Member,MetaConnection,GoogleAdsConnection,MetaSyncJob,MetaSnapshot,GoogleAdsSyncJob,AdEntity,MetaOAuthState,GoogleAdsOAuthState
from pao.config import settings
from pao.integrations.meta.client import MetaClient
from pao.integrations.google_ads.client import GoogleAdsClient,SCOPE
from p6_browser_harness import browser
from test_meta import meta
from test_google_ads import google_ads


async def test_ads_settings_real_oauth_lifecycle_cookie_loss_popup_and_sme(client,identity,meta,google_ads,monkeypatch):
    for name in ('meta','google_ads'):monkeypatch.setattr(settings(),name+'_redirect_uri','http://127.0.0.1:3201/v1/integrations/'+('meta' if name=='meta' else 'google-ads')+'/callback')
    monkeypatch.setattr(settings(),'meta_write_enabled',False)
    monkeypatch.setattr('pao.integrations.meta.app_config.runtime_ready',lambda:True)
    exchange=AsyncMock(return_value=('fixture-meta-token-not-real',3600));remote=AsyncMock(return_value=('42',['ads_read']))
    google_exchange=AsyncMock(return_value=('fixture-google-refresh-not-real',[SCOPE]));accessible=AsyncMock(return_value=('fixture-access-not-real',['1234567890']))
    monkeypatch.setattr(MetaClient,'exchange',exchange);monkeypatch.setattr(MetaClient,'identity',remote)
    monkeypatch.setattr(GoogleAdsClient,'exchange',google_exchange);monkeypatch.setattr(GoogleAdsClient,'accessible',accessible)
    async with Session.begin() as db:
        second=Workspace(name='Ads Settings SME B');employee=Workspace(name='Ads Settings operator');db.add_all([second,employee]);await db.flush()
        db.add_all([Member(workspace_id=second.id,user_id=identity['user_id'],role='admin'),Member(workspace_id=employee.id,user_id=identity['user_id'],role='operator')]);b,c=second.id,employee.id
        m=MetaConnection(workspace_id=identity['workspace'],user_id=identity['user_id']);g=GoogleAdsConnection(workspace_id=identity['workspace'],user_id=identity['user_id']);db.add_all([m,g]);await db.flush()
        # Synthetic cache belongs to generation2, published by the native callback.
        mj=MetaSyncJob(connection_id=m.id,connection_version=2,api_version='v25.0',request_key='fixture-cache-meta',kind='accounts',status='completed',row_count=1)
        gj=GoogleAdsSyncJob(connection_id=g.id,connection_version=2,api_version='v25',request_key='fixture-cache-google',kind='accounts',status='completed',row_count=1);db.add_all([mj,gj]);await db.flush()
        db.add(MetaSnapshot(job_id=mj.id,kind='accounts',remote_key='act_123',payload={'id':'act_123','name':'Fixture Meta SME A','currency':'USD'}))
        db.add(AdEntity(google_connection_id=g.id,connection_version=2,platform='google',kind='account',remote_id='1234567890',account_id='1234567890',name='Fixture Google SME A',currency='USD',timezone='UTC',google_source_job_id=gj.id))
    report=await browser('scripts/verify_s23d_browser.cjs','PAO_ADS_SETTINGS_BROWSER',{'workspace':identity['workspace'],'second':b,'employee':c},'s23d-ads')
    assert all(report[key] for key in ('popup_blocked','untrusted_url_denied','oauth_cookie_callback','cached_accounts','job_metadata','lost_disconnect','late_response','tenant_switch','operator','mobile'))
    assert exchange.await_count==remote.await_count==google_exchange.await_count==accessible.await_count==1
    async with Session() as db:
        m=await db.scalar(select(MetaConnection));g=await db.scalar(select(GoogleAdsConnection))
        assert m.workspace_id==g.workspace_id==identity['workspace']
        assert m.status==g.status=='disconnected' and m.token_ciphertext is None and g.refresh_token_ciphertext is None
        assert all(row.used for row in await db.scalars(select(MetaOAuthState)))
        assert all(row.used for row in await db.scalars(select(GoogleAdsOAuthState)))
        assert await db.scalar(select(func.count()).select_from(MetaSyncJob).where(MetaSyncJob.status.in_(('queued','running'))))==0
        assert await db.scalar(select(func.count()).select_from(GoogleAdsSyncJob).where(GoogleAdsSyncJob.status.in_(('queued','running'))))==0
