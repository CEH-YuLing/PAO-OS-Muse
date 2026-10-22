"""Owned Cloud Settings HTTP workflow, synthetic fetch/gateway only."""
from uuid import uuid4
from cryptography.fernet import Fernet
from sqlalchemy import select,func
from pao.config import settings
from pao.db import Session
from pao.models import Workspace,Member,ModelProviderConnection,TenantMetadataLease,TenantModelLease
from pao.gateway import Chunk
from p6_browser_harness import browser


async def test_cloud_settings_nonce_lost_response_consent_and_sme_isolation(client,identity,monkeypatch):
    monkeypatch.setattr(settings(),'integration_encryption_key',Fernet.generate_key().decode())
    calls={'catalogue':0,'factory':0,'inference':0}
    async def fake_fetch(provider,key):calls['catalogue']+=1;return ['fixture-first','fixture-second']
    class Fake:
        provider_name='openai';model_name='fixture-second'
        async def stream(self,messages,max_tokens=None):calls['inference']+=1;yield Chunk(text='PAO OK')
    def fake_gateway(*args):calls['factory']+=1;return Fake()
    monkeypatch.setattr('pao.model_api.fetch_models',fake_fetch)
    monkeypatch.setattr('pao.model_api.cloud_gateway',fake_gateway)
    async with Session.begin() as db:
        b=Workspace(name='Cloud SME B');c=Workspace(name='Cloud SME employee');db.add_all([b,c]);await db.flush()
        db.add_all([Member(workspace_id=b.id,user_id=identity['user_id'],role='admin'),Member(workspace_id=c.id,user_id=identity['user_id'],role='operator')]);second,employee=b.id,c.id
    seeded=await client.post('/v1/model-providers/openai/connect',headers=identity['owner'],json={'workspace_id':second,'api_key':'fixture-cloud-key-B-not-real'})
    assert seeded.status_code==200
    async with Session() as db:source=await db.scalar(select(ModelProviderConnection.id).where(ModelProviderConnection.workspace_id==second))
    base=f'/v1/workspaces/{second}/connection-inventory'
    proposal={'kind':'model','connection_id':source,'expected_version':None,'brand_id':None,'grantee_id':identity['user_id'],'permission':'read_only'}
    preview=await client.post(base+'/mapping-preview',headers=identity['owner'],json=proposal);assert preview.status_code==200
    staged=await client.post(base+'/references',headers=identity['owner'],json={**proposal,'preview_hash':preview.json()['preview_hash'],
        'request_key':str(uuid4()),'ttl_minutes':60,'manager_id':identity['user_id'],'apply_data_only_ack':True})
    assert staged.status_code==201
    report=await browser('scripts/verify_s23b_browser.cjs','PAO_CLOUD_SETTINGS_BROWSER',{'workspace':identity['workspace'],'second':second,'employee':employee},'s23b-cloud')
    assert all(report[key] for key in ('lost_response','no_auto_catalogue','explicit_probe','registered_denial','selection','default_disconnect','tenant_switch','mobile','credentials_cleared','late_response'))
    assert calls=={'catalogue':7,'factory':1,'inference':1}
    async with Session() as db:
        a=await db.scalar(select(ModelProviderConnection).where(ModelProviderConnection.workspace_id==identity['workspace']))
        b=await db.scalar(select(ModelProviderConnection).where(ModelProviderConnection.workspace_id==second))
        assert a.provider==b.provider=='openai' and a.model=='fixture-second' and b.model=='fixture-first'
        assert await db.scalar(select(func.count()).select_from(ModelProviderConnection))==2
        assert await db.scalar(select(func.count()).select_from(TenantMetadataLease))==7
        assert await db.scalar(select(func.count()).select_from(TenantModelLease))==1
