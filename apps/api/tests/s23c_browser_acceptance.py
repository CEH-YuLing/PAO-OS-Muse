"""MCP Settings real HTTP/DB with native mock transport; no real credentials."""
import asyncio
from sqlalchemy import select,func
from pao.db import Session
from pao.models import Workspace,Member,ConnectorConnection,ConnectorSecret,TenantMetadataLease,ToolCall
from p6_browser_harness import browser
from pao.tool_gateway import execute_tool
from test_connectors import connectors,connected,granted,pinned_run


async def test_mcp_settings_lifecycle_unknown_revision_nonce_and_isolation(client,identity,connectors):
    async with Session.begin() as db:
        second=Workspace(name='MCP SME B');employee=Workspace(name='MCP operator SME');db.add_all([second,employee]);await db.flush()
        db.add_all([Member(workspace_id=second.id,user_id=identity['user_id'],role='admin'),Member(workspace_id=employee.id,user_id=identity['user_id'],role='operator')]);b,c=second.id,employee.id
    report=await browser('scripts/verify_s23c_browser.cjs','PAO_MCP_SETTINGS_BROWSER',{'workspace':identity['workspace'],'second':b,'employee':c},'s23c-mcp')
    assert all(report[key] for key in ('lost_response','explicit_discovery','nonce','revision_conflict','rotation','permission','late_response','credentials_cleared','tenant_switch','disconnect','audit','mobile'))
    assert connectors.calls==0
    assert connectors.requests==['initialize','notifications/initialized','tools/list']*3
    async with Session() as db:
        rows=list(await db.scalars(select(ConnectorConnection)));assert len(rows)==1
        assert rows[0].workspace_id==identity['workspace'] and rows[0].status=='revoked' and rows[0].permissions=={}
        assert (await db.scalar(select(ConnectorSecret))).ciphertext is None
        assert await db.scalar(select(func.count()).select_from(TenantMetadataLease))==3
        assert await db.scalar(select(func.count()).select_from(ToolCall))==0


async def test_mcp_settings_legacy_call_requires_intent_and_native_skill(client,identity,connectors):
    row=await granted(client,identity,await connected(client,identity));run=await pinned_run(client,identity,row)
    async def execute():
        for _ in range(900):
            async with Session() as db:call=await db.scalar(select(ToolCall).where(ToolCall.run_id==run,ToolCall.status=='queued'))
            if call:await execute_tool({},call.id);return call.id
            await asyncio.sleep(.1)
        raise AssertionError('No legacy MCP call admitted')
    task=asyncio.create_task(execute())
    try:
        report=await browser('scripts/verify_s23c_legacy_browser.cjs','PAO_MCP_LEGACY_BROWSER',{'workspace':identity['workspace'],'source':row['id'],'run':run},'s23c-legacy')
        cid=await asyncio.wait_for(task,5)
        assert report['explicit_call'] and report['native_result'] and report['drafts_cleared']
        async with Session() as db:
            calls=list(await db.scalars(select(ToolCall)));assert len(calls)==1 and calls[0].id==cid
            assert calls[0].status=='completed' and calls[0].result=={'text':'Synthetic read result'}
        assert connectors.calls==1
    finally:
        if not task.done():task.cancel()
        await asyncio.gather(task,return_exceptions=True)
