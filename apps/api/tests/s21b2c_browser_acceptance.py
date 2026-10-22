"""Actual HTTP/browser/DB plus fixture MCP execution; no external server."""
import asyncio
from sqlalchemy import select
from pao.db import Session
from pao.models import ConnectionReadActivation, Member, TenantConnectionGrant, ToolCall, Workspace
from pao.tool_gateway import execute_tool
from p6_browser_harness import browser
from test_connectors import connectors, connected, granted, pinned_run


async def test_mcp_consent_scoped_call_replay_revoke_and_switch(client,identity,connectors):
    c=identity;row=await granted(client,c,await connected(client,c));rid=await pinned_run(client,c,row)
    async with Session.begin() as db:
        second=Workspace(name='Second MCP SME');db.add(second);await db.flush()
        db.add(Member(workspace_id=second.id,user_id=c['user_id'],role='owner'));wid=second.id
    async def executor():
        for _ in range(900):
            async with Session() as db:
                call=await db.scalar(select(ToolCall).where(ToolCall.run_id==rid,ToolCall.status=='queued'))
            if call:await execute_tool({},call.id);return call.id
            await asyncio.sleep(.1)
        raise AssertionError('Browser never admitted MCP fixture call')
    task=asyncio.create_task(executor())
    try:
        report=await browser('scripts/verify_s21b2c_browser.cjs','PAO_S21B2C_BROWSER_FIXTURE',{
            'workspace':c['workspace'],'second':wid,'actor':c['user_id'],'source':row['id'],'run':rid},'s21b2c')
        cid=await asyncio.wait_for(task,5)
        assert report['explicit_consent'] and report['actual_fixture_tool_result'] and report['tenant_switch']
        async with Session() as db:
            consent=await db.scalar(select(ConnectionReadActivation));assert consent
            grant=await db.get(TenantConnectionGrant,consent.grant_id);assert grant.status=='revoked'
            calls=list(await db.scalars(select(ToolCall)));assert len(calls)==1 and calls[0].id==cid
            assert calls[0].status=='completed' and calls[0].result=={'text':'Synthetic read result'}
        assert connectors.calls==1
    finally:
        if not task.done():task.cancel()
        await asyncio.gather(task,return_exceptions=True)
