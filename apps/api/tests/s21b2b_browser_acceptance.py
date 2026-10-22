"""Real browser / HTTP / DB consent and selection. Never calls a provider."""
from sqlalchemy import select
from pao.db import Session
from pao.models import ModelGrantActivation, TenantConnectionGrant, TenantConnectionReference, ChatSession
from p6_browser_harness import browser
from test_model_connection_fence import fenced
from test_connection_inventory import corpus
from test_engine_contract import engines


async def test_manager_consent_engine_selection_revoke_and_sme_switch(client,fenced):
    c,calls,_=fenced
    result=await client.post('/v1/sessions',headers=c['owner'],json={
        'workspace_id':c['workspace'],'title':'S21B2b model grant UI','memory_enabled':False})
    assert result.status_code==201
    profile=await client.put(f"/v1/sessions/{result.json()['id']}/chat",headers=c['owner'],json={'version':1,'policy':{'privacy':'cloud_allowed'}})
    assert profile.status_code==200,profile.text
    report=await browser('scripts/verify_s21b2b_browser.cjs','PAO_S21B2B_BROWSER_FIXTURE',{
        'workspace':c['workspace'],'second':c['second'],'actor':c['user_id'],
        'source':c['connections']['a']['model'],'session':result.json()['id']},'s21b2b')
    assert report['explicit_consent'] and report['grant_selection'] and report['revoke_disappears'] and report['tenant_switch']
    async with Session() as db:
        rows=list(await db.scalars(select(ModelGrantActivation)));assert len(rows)==1
        grant=await db.get(TenantConnectionGrant,rows[0].grant_id);assert grant.status=='revoked' and grant.revision==2
        ref=await db.get(TenantConnectionReference,grant.reference_id);assert ref.status=='staged' and ref.revision==1
        chat=await db.get(ChatSession,result.json()['id'])
        assert chat.engine_config['connection_authority']['grant_id']==grant.id
    assert calls['factory']==calls['stream']==calls['plan']==calls['extract']==0
