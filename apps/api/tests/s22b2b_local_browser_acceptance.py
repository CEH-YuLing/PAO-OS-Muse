"""Owned HTTP/browser local chooser/quota fixtures, no Ollama or cloud calls."""
from sqlalchemy import select,func
from pao.config import settings
from pao.db import Session
from pao.models import Workspace,Member,ChatSession,TenantMetadataLease
from p6_browser_harness import browser
from test_engine_contract import engines
from test_tenant_metadata_resources import configure


async def test_local_model_chooser_quota_reload_switch_mobile(client,identity,engines,monkeypatch):
    calls=[]
    async def tags():calls.append(True);return ['local-a','local-b']
    monkeypatch.setattr('pao.modules.engines.api.local_models',tags)
    def forbidden(*args,**kwargs):raise AssertionError('No real local/cloud inference')
    monkeypatch.setattr('pao.model_router.cloud_gateway',forbidden)
    async with Session.begin() as db:
        b=Workspace(name='Local metadata SME B');db.add(b);await db.flush();wid=b.id
        db.add(Member(workspace_id=wid,user_id=identity['user_id'],role='owner'))
        a=ChatSession(workspace_id=identity['workspace'],user_id=identity['user_id'],title='Local quota A',memory_enabled=False)
        second=ChatSession(workspace_id=wid,user_id=identity['user_id'],title='Local quota B',memory_enabled=False)
        db.add_all([a,second]);await db.flush();sid=a.id;other=second.id
    assert (await configure(client,identity,daily=30)).status_code==200
    report=await browser('scripts/verify_s22b2b_local_browser.cjs','PAO_S22B2B_LOCAL_BROWSER_FIXTURE',{
        'workspace':identity['workspace'],'second':wid,'session':sid,'otherSession':other},'s22b2b-local')
    assert report['local_selection'] and report['quota_denial'] and report['reload'] and report['tenant_switch'] and not report['real_provider_calls']
    async with Session() as db:
        assert (await db.get(ChatSession,sid)).engine_config['model']=='local-b'
        assert (await db.get(ChatSession,other)).engine_config is None
        assert len(calls)==await db.scalar(select(func.count()).select_from(TenantMetadataLease))
        assert not await db.scalar(select(func.count()).select_from(TenantMetadataLease).where(TenantMetadataLease.status=='active'))
