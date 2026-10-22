"""Native Settings connect/catalogue/select via HTTP, test-only key/providers."""
from cryptography.fernet import Fernet
from sqlalchemy import select
from pao.config import settings
from pao.db import Session
from pao.models import Workspace, Member, ModelProviderConnection
from p6_browser_harness import browser


async def test_native_model_metadata_settings_browser(client,identity,monkeypatch):
    monkeypatch.setattr(settings(),'integration_encryption_key',Fernet.generate_key().decode())
    key='fixture-browser-metadata-not-real';calls=[]
    async def catalogue(provider,secret):
        assert provider=='openai' and secret==key
        calls.append(provider);return ['gpt-4.1-mini','fixture-new']
    def forbidden(*args,**kwargs):raise AssertionError('No inference or real provider')
    monkeypatch.setattr('pao.model_api.fetch_models',catalogue)
    monkeypatch.setattr('pao.model_api.cloud_gateway',forbidden)
    async with Session.begin() as db:
        second=Workspace(name='Metadata SME B');db.add(second);await db.flush()
        db.add(Member(workspace_id=second.id,user_id=identity['user_id'],role='owner'));wid=second.id
    report=await browser('scripts/verify_s22b2b_metadata_browser.cjs','PAO_S22B2B_METADATA_BROWSER_FIXTURE',{
        'workspace':identity['workspace'],'second':wid,'fixtureKey':key},'s22b2b-metadata')
    assert report['metadata_quota'] is True and report['quota_form_ui'] is False and report['provider_calls'] is False
    assert calls==['openai']*3
    async with Session() as db:
        rows=list(await db.scalars(select(ModelProviderConnection)))
        assert len(rows)==1 and rows[0].workspace_id==identity['workspace'] and rows[0].model=='fixture-new'
