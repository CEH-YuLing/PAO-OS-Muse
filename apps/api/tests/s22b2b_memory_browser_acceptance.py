"""Memory CRUD/query/SME browser through owned HTTP; fake embeddings only."""
from sqlalchemy import select,func
from pao.db import Session
from pao.models import Workspace,Member,ChatSession,Memory,TenantModelLease
from test_memory import memory_on
from test_engine_contract import engines
from p6_browser_harness import browser

async def test_memory_embedding_quota_fallback_reload_and_sme_switch(client,identity,memory_on,engines):
    async with Session.begin() as db:
        other=Workspace(name='Memory SME B');db.add(other);await db.flush();wid=other.id
        db.add(Member(workspace_id=wid,user_id=identity['user_id'],role='owner'))
    sessions=[]
    for workspace,title in ((identity['workspace'],'Embedding Memory A'),(wid,'Embedding Memory B')):
        row=await client.post('/v1/sessions',headers=identity['owner'],json={'workspace_id':workspace,'title':title})
        assert row.status_code==201;sessions.append(row.json()['id'])
    report=await browser('scripts/verify_s22b2b_memory_browser.cjs','PAO_MEMORY_EMBEDDING_BROWSER',{
        'workspace':identity['workspace'],'second':wid,'session':sessions[0],'otherSession':sessions[1]},'s22b2b-memory')
    assert report['quota_fallback'] and report['reload'] and report['tenant_switch'] and not report['real_provider_calls']
    async with Session() as db:
        a=list(await db.scalars(select(Memory).where(Memory.workspace_id==identity['workspace'])))
        b=list(await db.scalars(select(Memory).where(Memory.workspace_id==wid)))
        assert len(a)==len(b)==1 and a[0].value!=b[0].value
        assert await db.scalar(select(func.count()).select_from(TenantModelLease).where(TenantModelLease.kind=='embedding'))==3
        assert not await db.scalar(select(func.count()).select_from(TenantModelLease).where(TenantModelLease.status=='active'))
