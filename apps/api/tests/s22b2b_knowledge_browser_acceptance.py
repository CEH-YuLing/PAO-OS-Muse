"""Owned HTTP/browser semantic+quota search; index execution is tested separately."""
from sqlalchemy import select
from pao.db import Session
from pao.gateway import OllamaGateway
from pao.models import Workspace,Member,KnowledgeIndexJob
from pao.config import settings
from pao.modules.knowledge import index
from test_knowledge_workspace import source,p2_on,sources_on,brains_on
from test_tenant_model_resources import configure
from p6_browser_harness import browser

async def test_knowledge_quota_query_reload_sme_switch_and_explicit_rebuild(client,identity,p2_on,monkeypatch):
    a=await source(client,identity,content=b'Return policy A: 7 days.')
    async with Session.begin() as db:
        other=Workspace(name='Knowledge quota SME B');db.add(other);await db.flush();wid=other.id
        db.add(Member(workspace_id=wid,user_id=identity['user_id'],role='owner'))
    second={**identity,'workspace':wid};b=await source(client,second,content=b'Return policy B: 14 days.')
    calls=[]
    async def fake(self,value):calls.append(value);return [1.0]+[0.0]*767
    monkeypatch.setattr(OllamaGateway,'embed',fake)
    monkeypatch.setattr(settings(),'knowledge_embeddings_enabled',True)
    for who,data in ((identity,a),(second,b)):
        result=await client.post(f'/v1/brains/{data[0]}/sources/{data[2]["id"]}/index',headers=who['owner'],json={'confirmed':True})
        assert result.status_code==200;await index.index_source({},data[4])
    assert (await configure(client,identity,calls=2)).status_code==200
    report=await browser('scripts/verify_s22b2b_knowledge_browser.cjs','PAO_KNOWLEDGE_EMBEDDING_BROWSER',{
        'workspace':identity['workspace'],'second':wid,'brain':a[0],'otherBrain':b[0],
        'source':a[2]['id'],'job':a[4]},'s22b2b-knowledge')
    assert report['hybrid'] and report['quota_fallback'] and report['reload'] and report['tenant_switch'] and report['rebuild_queued']
    assert len(calls)==4 # A/B index, A/B query; no embed at denial or UI rebuild admission
    async with Session() as db:
        job=await db.get(KnowledgeIndexJob,a[4]);assert job.status=='queued' and job.embedding_generation==2
