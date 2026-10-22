import asyncio
import json
from pathlib import Path
import pytest
from sqlalchemy import delete
from pao.db import Session
from pao.models import Member
from pao.modules.cli_connections import antigravity_native as agy


@pytest.fixture
def native(identity, monkeypatch):
    cfg={'binary':'synthetic-not-executed','binary_sha256':'0'*64}
    def provisioned(wid,actor):
        from fastapi import HTTPException
        if (wid,actor)!=(identity['workspace'],identity['user_id']):raise HTTPException(503,'not_provisioned')
        return cfg,'synthetic-pin'
    agy._state.clear();agy._busy.clear();agy._generation.clear()
    monkeypatch.setattr(agy,'configuration',provisioned)
    calls=[]
    async def read(value):calls.append(value);return ['gemini-fixture-high','claude-fixture']
    monkeypatch.setattr(agy,'native_catalog',read)
    return '/v1/workspaces/'+identity['workspace']+'/antigravity-native',calls


ACK={'acknowledge_local_session':True,'acknowledge_unsupported_consumer_wrapper':True}
SMOKE_ACK={**ACK,'acknowledge_fixed_model_test':True}


async def test_native_connect_no_password_cache_and_disconnect(client,identity,native):
    base,calls=native;h=identity['owner']
    initial=await client.get(base,headers=h)
    assert initial.status_code==200 and initial.json()['status']=='not_checked' and calls==[]
    result=await client.post(base+'/connect',headers=h,json=ACK)
    assert result.status_code==200,result.text
    value=result.json();assert value['status']=='catalog_available' and len(value['models'])==2
    assert value['inference_called'] is value['inference_enabled'] is value['credentials_stored_in_PAO'] is False
    assert value['provider_support_confirmed'] is False and len(calls)==1
    assert (await client.get(base,headers=h)).json()['models']==value['models'] and len(calls)==1
    result=await client.post(base+'/disconnect',headers=h)
    assert result.status_code==200 and result.json()['status']=='not_checked'
    assert result.json()['provider_logout_performed'] is False and len(calls)==1


@pytest.mark.parametrize('body',[{}, {'acknowledge_local_session':True}, {**ACK,'password':'never-accepted'}, {**ACK,'acknowledge_local_session':False}, {**ACK,'acknowledge_unsupported_consumer_wrapper':False}, {**ACK,'acknowledge_local_session':'true'}])
async def test_native_requires_exact_explicit_ack(client,identity,native,body):
    base,calls=native
    assert (await client.post(base+'/connect',headers=identity['owner'],json=body)).status_code==422
    assert not calls


async def test_native_wrong_actor_workspace_and_role(client,identity,native):
    base,calls=native
    for headers in ({},identity['outsider'],identity['other']):
        result=await client.post(base+'/connect',headers=headers,json=ACK)
        assert result.status_code in (401,403,404,503)
    async with Session.begin() as db:
        member=await db.get(Member,(identity['workspace'],identity['user_id']));member.role='viewer'
    assert (await client.post(base+'/connect',headers=identity['owner'],json=ACK)).status_code==403
    assert not calls


async def test_native_recheck_membership_and_redact_error(client,identity,native,monkeypatch):
    base,_=native
    async def revoked(cfg):
        async with Session.begin() as db:
            await db.execute(delete(Member).where(Member.workspace_id==identity['workspace'],Member.user_id==identity['user_id']))
        return ['gemini-fixture']
    monkeypatch.setattr(agy,'native_catalog',revoked)
    assert (await client.post(base+'/connect',headers=identity['owner'],json=ACK)).status_code==404
    assert not agy._state and not agy._busy


async def test_native_upstream_failure_not_exposed(client,identity,native,monkeypatch):
    base,_=native
    async def fail(cfg):raise ValueError('PRIVATE-MARKER')
    monkeypatch.setattr(agy,'native_catalog',fail)
    response=await client.post(base+'/connect',headers=identity['owner'],json=ACK)
    assert response.status_code==503 and 'PRIVATE-MARKER' not in response.text
    assert not agy._state and not agy._busy


async def test_native_busy_and_disconnect_fence(client,identity,native,monkeypatch):
    base,_=native;started=asyncio.Event();release=asyncio.Event()
    async def delayed(cfg):started.set();await release.wait();return ['gemini-fixture']
    monkeypatch.setattr(agy,'native_catalog',delayed)
    pending=asyncio.create_task(client.post(base+'/connect',headers=identity['owner'],json=ACK))
    await asyncio.wait_for(started.wait(),3)
    assert (await client.post(base+'/connect',headers=identity['owner'],json=ACK)).status_code==409
    assert (await client.post(base+'/disconnect',headers=identity['owner'])).status_code==200
    release.set();assert (await pending).status_code==409
    assert not agy._state and not agy._busy


@pytest.mark.parametrize('raw',[b'',b'Fetching available models...\n',b'gemini-a\ngemini-a',b'\xff',b'x'*262145],
                         ids=['empty','notice_only','duplicate','invalid_utf8','oversized'])
def test_native_catalog_rejects_invalid(raw):
    with pytest.raises((ValueError,UnicodeError)):agy.catalog_text(raw)


def test_native_catalog_keeps_ids_not_display_text():
    assert agy.catalog_text('Fetching available models...\ngemini-3.8-flash-high\tGemini Flash\nclaude-sonnet-4-6  Claude\n'.encode())==['gemini-3.8-flash-high','claude-sonnet-4-6']


async def test_native_test_requires_connection_ack_and_does_not_run_on_get(client,identity,native,monkeypatch):
    base,calls=native
    async def forbidden(*args):raise AssertionError('must not run')
    monkeypatch.setattr(agy,'native_smoke',forbidden)
    assert (await client.get(base,headers=identity['owner'])).status_code==200
    assert (await client.post(base+'/test',headers=identity['owner'],json=SMOKE_ACK)).status_code==409
    assert (await client.post(base+'/test',headers=identity['owner'],json=ACK)).status_code==422
    assert (await client.post(base+'/test',headers=identity['owner'],json={})).status_code==422
    assert (await client.post(base+'/test',json=SMOKE_ACK)).status_code==401
    assert not calls


async def test_native_test_tools_gate_is_redacted_and_busy_cleared(client,identity,native,monkeypatch):
    base,_=native
    async def catalog(cfg):return [agy.MODEL]
    async def smoke(cfg,recheck):
        await recheck()
        raise agy.SmokeFailure('tools_not_disabled')
    monkeypatch.setattr(agy,'native_catalog',catalog);monkeypatch.setattr(agy,'native_smoke',smoke)
    assert (await client.post(base+'/connect',headers=identity['owner'],json=ACK)).status_code==200
    result=await client.post(base+'/test',headers=identity['owner'],json=SMOKE_ACK)
    assert result.status_code==409 and result.json()['detail']=='antigravity_native_tools_not_disabled'
    assert not agy._busy and agy._state


async def test_native_connect_binary_drift_is_actionable(client,identity,native,monkeypatch):
    base,_=native
    async def drift(cfg):raise agy.SmokeFailure('binary_changed')
    monkeypatch.setattr(agy,'native_catalog',drift)
    result=await client.post(base+'/connect',headers=identity['owner'],json=ACK)
    assert result.status_code==409 and result.json()['detail']=='antigravity_native_binary_changed'


async def test_native_smoke_postcheck_disconnect_fences_success(client,identity,native,monkeypatch):
    base,_=native
    async def catalog(cfg):return [agy.MODEL]
    async def smoke(cfg,recheck):
        await recheck()
        key=(identity['workspace'],identity['user_id']);agy._generation[key]=1
        return {'status':'passed'}
    monkeypatch.setattr(agy,'native_catalog',catalog);monkeypatch.setattr(agy,'native_smoke',smoke)
    assert (await client.post(base+'/connect',headers=identity['owner'],json=ACK)).status_code==200
    result=await client.post(base+'/test',headers=identity['owner'],json=SMOKE_ACK)
    assert result.status_code==409 and not agy._busy
