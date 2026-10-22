import asyncio
from datetime import timedelta
from uuid import uuid4
import pytest
import pytest_asyncio
import hashlib
from cryptography.fernet import Fernet
from sqlalchemy import select
from pao.auth import issue_token, Principal, check_session
from pao.config import settings
from pao.db import Session
from pao.models import (User, Workspace, Member, Brain, BrainMember, WorkspaceInvitation,
    LoginSession, LifecycleAudit, DataLifecycleRequest, now)


@pytest_asyncio.fixture(autouse=True)
async def isolate_invitation_rate_key(client):
    from pao.main import app
    assert settings().redis_url.endswith('/15')
    await app.state.redis.delete('limit:invite-accept-ip:'+hashlib.sha256(b'127.0.0.1').hexdigest())
    await app.state.redis.delete('limit:login-ip:'+hashlib.sha256(b'127.0.0.1').hexdigest())


def path(identity, suffix=''):
    return f"/v1/workspaces/{identity['workspace']}/lifecycle{suffix}"


async def invite(client, identity, email='new@example.test', **extra):
    response = await client.post(path(identity, '/invitations'), headers=identity['owner'],
        json={'email':email, 'role':'viewer', **extra})
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def encryption(monkeypatch):
    monkeypatch.setattr(settings(), 'integration_encryption_key', Fernet.generate_key().decode())


async def test_invite_new_account_single_use_hashed_and_not_sent(client, identity):
    value = await invite(client, identity)
    async with Session() as db:
        row = await db.get(WorkspaceInvitation, value['id'])
        assert row.code_hash != value['code'] and len(row.code_hash)==64
    payload={'email':'NEW@example.test','code':value['code'],'password':'new-test-password-123'}
    accepted=await client.post('/v1/auth/invitations/accept',json=payload)
    assert accepted.status_code==200 and accepted.json()['login_required']
    assert (await client.post('/v1/auth/invitations/accept',json=payload)).status_code==422
    listed=await client.get(path(identity,'/invitations'),headers=identity['owner'])
    assert value['code'] not in listed.text and 'code_hash' not in listed.text
    assert value['delivery']=='manual_once_not_sent'


async def test_invite_existing_requires_same_authenticated_user_and_no_password_reset(client, identity):
    value=await invite(client,identity,'outside@example.test')
    body={'email':'outside@example.test','code':value['code'],'password':'replacement-test-password'}
    assert (await client.post('/v1/auth/invitations/accept',json=body)).status_code==422
    assert (await client.post('/v1/auth/invitations/accept',json=body,headers=identity['owner'])).status_code==422
    assert (await client.post('/v1/auth/invitations/accept',json=body,headers=identity['outsider'])).status_code==200
    login=await client.post('/v1/auth/token',json={'email':'outside@example.test','password':'test-password-123'})
    assert login.status_code==200


@pytest.mark.parametrize('kind',['expired','revoked','inviter_demoted','inviter_inactive'])
async def test_invalid_invitation_states(client, identity, kind):
    value=await invite(client,identity)
    async with Session.begin() as db:
        row=await db.get(WorkspaceInvitation,value['id'])
        if kind=='expired':row.expires_at=now()-timedelta(seconds=1)
        elif kind=='revoked':row.status='revoked'
        elif kind=='inviter_demoted':(await db.get(Member,(identity['workspace'],identity['user_id']))).role='admin'
        else:(await db.get(User,identity['user_id'])).active=False
    response=await client.post('/v1/auth/invitations/accept',json={'email':'new@example.test','code':value['code'],'password':'test-password-123'})
    assert response.status_code==422


async def test_invite_concurrent_accept_only_once(client, identity):
    value=await invite(client,identity)
    body={'email':'new@example.test','code':value['code'],'password':'test-password-123'}
    results=await asyncio.gather(*(client.post('/v1/auth/invitations/accept',json=body) for _ in range(2)))
    assert sorted(row.status_code for row in results)==[200,422]


async def test_owner_only_and_no_owner_invites(client, identity):
    for headers in (identity['other'],identity['outsider']):
        response=await client.post(path(identity,'/invitations'),headers=headers,json={'email':'new@example.test'})
        assert response.status_code in (403,404)
    assert (await client.post(path(identity,'/invitations'),headers=identity['owner'],json={'email':'new@example.test','role':'owner'})).status_code==422
    assert (await client.post(path(identity,f"/members/{identity['user_id']}/remove"),headers=identity['owner'],json={'confirm':True})).status_code==409


async def test_member_removal_preserves_other_sme_and_private_brain(client, identity):
    async with Session.begin() as db:
        other=await db.scalar(select(User).where(User.email=='other@example.test'))
        second=Workspace(name='Other SME');db.add(second);await db.flush()
        db.add(Member(workspace_id=second.id,user_id=other.id,role='owner'))
        brain=Brain(workspace_id=identity['workspace'],owner_id=identity['user_id'],name='Shared test',legacy_default=False)
        db.add(brain);await db.flush()
        db.add(BrainMember(brain_id=brain.id,workspace_id=identity['workspace'],user_id=other.id,role='reader'))
        uid=other.id;wid=second.id;bid=brain.id
    response=await client.post(path(identity,f'/members/{uid}/remove'),headers=identity['owner'],json={'confirm':True})
    assert response.status_code==200,response.text
    assert (await client.get(f"/v1/workspaces/{identity['workspace']}/context",headers=identity['other'])).status_code==404
    assert (await client.get(f'/v1/workspaces/{wid}/context',headers=identity['other'])).status_code==200
    async with Session() as db:
        assert (await db.get(User,uid)).active
        assert await db.get(BrainMember,(bid,uid)) is None
        assert await db.get(Brain,bid)
        assert await db.scalar(select(LifecycleAudit).where(LifecycleAudit.action=='member.removed'))


async def test_role_change_revokes_old_grants_and_respects_workspace(client, identity):
    async with Session() as db:uid=await db.scalar(select(User.id).where(User.email=='other@example.test'))
    response=await client.patch(path(identity,f'/members/{uid}'),headers=identity['owner'],json={'role':'viewer'})
    assert response.status_code==200
    assert (await client.post('/v1/sessions',headers=identity['other'],json={'workspace_id':identity['workspace']})).status_code==403


async def test_logout_current_denies_old_token_but_not_other_session(client, identity):
    signed=[]
    for _ in range(2):
        signed.append((await client.post('/v1/auth/token',json={'email':'owner@example.test','password':'test-password-123'})).json()['access_token'])
    first={'Authorization':'Bearer '+signed[0]};second={'Authorization':'Bearer '+signed[1]}
    assert signed[0]!=signed[1]
    assert (await client.post('/v1/auth/sessions/revoke-current',headers=first)).status_code==200
    assert (await client.get('/v1/me',headers=first)).status_code==401
    assert (await client.get('/v1/me',headers=second)).status_code==200
    sessions=(await client.get('/v1/auth/sessions',headers=second)).json()['sessions']
    assert len(sessions)==2 and any(row['revoked'] for row in sessions)
    assert all('token_hash' not in row for row in sessions)


async def test_logout_all_legacy_and_relogin(client, identity):
    assert (await client.post('/v1/auth/sessions/revoke-all',headers=identity['owner'],json={'confirm':False})).status_code==422
    assert (await client.post('/v1/auth/sessions/revoke-all',headers=identity['owner'],json={'confirm':True})).status_code==200
    assert (await client.get('/v1/me',headers=identity['owner'])).status_code==401
    response=await client.post('/v1/auth/token',json={'email':'owner@example.test','password':'test-password-123'})
    assert response.status_code==200
    assert (await client.get('/v1/me',headers={'Authorization':'Bearer '+response.json()['access_token']})).status_code==200
    assert (await client.get('/v1/me',headers=identity['other'])).status_code==200


async def test_export_encrypted_scoped_download_and_expiry(client,identity,encryption):
    response=await client.post(path(identity,'/data/exports'),headers=identity['owner'],json={})
    assert response.status_code==201,response.text
    rid=response.json()['id']
    async with Session() as db:
        row=await db.get(DataLifecycleRequest,rid)
        assert b'workspace_id' not in row.payload
    downloaded=await client.get(path(identity,f'/data/exports/{rid}/download'),headers=identity['owner'])
    assert downloaded.status_code==200 and downloaded.headers['cache-control']=='no-store'
    payload=downloaded.json()
    assert payload['workspace_id']==identity['workspace']
    assert 'password_hash' not in downloaded.text and 'code_hash' not in downloaded.text
    assert (await client.get(path(identity,f'/data/exports/{rid}/download'),headers=identity['other'])).status_code==403
    async with Session.begin() as db:(await db.get(DataLifecycleRequest,rid)).expires_at=now()-timedelta(seconds=1)
    assert (await client.get(path(identity,f'/data/exports/{rid}/download'),headers=identity['owner'])).status_code==409


async def test_export_owner_does_not_gain_private_brain(client,identity,encryption,monkeypatch):
    monkeypatch.setattr(settings(),'brain_manager_enabled',True)
    async with Session.begin() as db:
        other=await db.scalar(select(User).where(User.email=='other@example.test'))
        brain=Brain(workspace_id=identity['workspace'],owner_id=other.id,name='Private',legacy_default=False)
        db.add(brain);await db.flush();bid=brain.id
    response=await client.post(path(identity,'/data/exports'),headers=identity['owner'],json={'brain_ids':[bid]})
    assert response.status_code==404


async def test_deletion_request_confirmation_no_actual_delete_and_stale_preview(client,identity):
    response=await client.post(path(identity,'/data/deletions/preview'),headers=identity['owner'],json={})
    assert response.status_code==201,response.text
    preview=response.json();rid=preview['id'];body={'confirm':True,'preview_hash':preview['preview_hash']}
    route=path(identity,f'/data/deletions/{rid}')
    assert (await client.post(route+'/confirm',headers=identity['owner'],json=body)).status_code==409
    assert (await client.post(route+'/request',headers=identity['owner'],json=body)).json()['status']=='requested'
    confirmed=await client.post(route+'/confirm',headers=identity['owner'],json=body)
    assert confirmed.status_code==200 and not confirmed.json()['deletion_executed']
    assert (await client.get('/v1/me',headers=identity['owner'])).status_code==200
    async with Session.begin() as db:(await db.get(Workspace,identity['workspace'])).lifecycle_version+=1
    assert (await client.post(route+'/confirm',headers=identity['owner'],json=body)).status_code==409


async def test_validation_never_echoes_codes_passwords_and_bounded_json(client,identity):
    secret='not-a-real-secret-for-validation'
    response=await client.post('/v1/auth/invitations/accept',json={'code':secret,'password':secret,'unexpected':secret})
    assert response.status_code==422 and secret not in response.text
    assert response.headers['cache-control']=='no-store'


async def test_retention_default_off_even_when_collect_runs(client,identity,monkeypatch):
    from pao.modules.channels import service
    monkeypatch.setattr(settings(),'channel_retention_enabled',False)
    monkeypatch.setattr(settings(),'channels_enabled',False)
    assert await service.purge_expired()=={'purged':0}
    assert await service.collect()=={'processed':0}


async def test_accept_cannot_choose_elevated_invited_role(client,identity):
    value=await invite(client,identity)
    response=await client.post('/v1/auth/invitations/accept',json={
        'email':'new@example.test','code':value['code'],'password':'test-password-123','role':'admin'})
    assert response.status_code==200 and response.json()['role']=='viewer'


async def test_invite_revocation_and_random_id_are_scoped(client,identity):
    value=await invite(client,identity)
    assert (await client.post(path(identity,f"/invitations/{value['id']}/revoke"),headers=identity['other'])).status_code==403
    assert (await client.post(path(identity,f'/invitations/{uuid4()}/revoke'),headers=identity['owner'])).status_code==404
    assert (await client.post(path(identity,f"/invitations/{value['id']}/revoke"),headers=identity['owner'])).status_code==200
    assert (await client.post('/v1/auth/invitations/accept',json={
        'email':'new@example.test','code':value['code'],'password':'test-password-123'})).status_code==422


async def test_accept_rate_limit_not_disabled(client,identity):
    for _ in range(10):
        assert (await client.post('/v1/auth/invitations/accept',json={'email':'new@example.test','code':'x'*43,'password':'test-password-123'})).status_code==422
    assert (await client.post('/v1/auth/invitations/accept',json={'email':'new@example.test','code':'x'*43,'password':'test-password-123'})).status_code==429


async def test_stream_principal_rechecks_revocation_with_cached_session(client,identity):
    from pao.auth import principal
    from fastapi.security import HTTPAuthorizationCredentials
    from fastapi import HTTPException
    token=identity['owner']['Authorization'].split()[1]
    async with Session() as db:
        who=await principal(HTTPAuthorizationCredentials(scheme='Bearer',credentials=token),db)
        assert (await client.post('/v1/auth/sessions/revoke-current',headers=identity['owner'])).status_code==200
        with pytest.raises(HTTPException) as error:await check_session(db,who)
        assert error.value.status_code==401


async def test_oversized_lifecycle_body_is_bounded_and_redacted(client,identity):
    response=await client.post(path(identity,'/invitations'),headers={**identity['owner'],'Content-Type':'application/json'},
        content='{"email":"'+('a'*9000)+'"}')
    assert response.status_code==413 and 'a'*100 not in response.text


async def test_export_requires_encryption_and_caps_rows(client,identity,monkeypatch):
    from pao.modules.platform import lifecycle
    from pao.models import Brand
    monkeypatch.setattr(settings(),'integration_encryption_key','')
    assert (await client.post(path(identity,'/data/exports'),headers=identity['owner'],json={})).status_code==503
    async with Session.begin() as db:db.add(Brand(workspace_id=identity['workspace'],name='Test brand'))
    monkeypatch.setattr(lifecycle,'MAX_EXPORT_ROWS',0)
    assert (await client.post(path(identity,'/data/exports'),headers=identity['owner'],json={})).status_code==413


async def test_deletion_confirmation_expiry_and_wrong_hash(client,identity):
    preview=(await client.post(path(identity,'/data/deletions/preview'),headers=identity['owner'],json={})).json()
    route=path(identity,f"/data/deletions/{preview['id']}/request")
    assert (await client.post(route,headers=identity['owner'],json={'confirm':True,'preview_hash':'0'*64})).status_code==409
    async with Session.begin() as db:(await db.get(DataLifecycleRequest,preview['id'])).expires_at=now()-timedelta(seconds=1)
    assert (await client.post(route,headers=identity['owner'],json={'confirm':True,'preview_hash':preview['preview_hash']})).status_code==409


async def test_membership_revocation_cancels_queued_run_only_in_its_sme(client,identity):
    from pao.models import ChatSession,Run
    session=await client.post('/v1/sessions',headers=identity['other'],json={'workspace_id':identity['workspace'],'memory_enabled':False})
    assert session.status_code==201
    response=await client.post('/v1/runs',headers=identity['other'],json={'session_id':session.json()['id'],'request_key':str(uuid4()),'message':'Synthetic task'})
    assert response.status_code==202,response.text
    async with Session() as db:uid=await db.scalar(select(User.id).where(User.email=='other@example.test'))
    assert (await client.post(path(identity,f'/members/{uid}/remove'),headers=identity['owner'],json={'confirm':True})).status_code==200
    assert (await client.get('/v1/runs/'+response.json()['id'],headers=identity['other'])).status_code==404
    async with Session() as db:assert (await db.get(Run,response.json()['id'])).cancel_requested


async def test_brain_export_rejects_size_before_loading_file_bytes(client,identity,encryption,monkeypatch):
    from sqlalchemy import event
    from pao.db import engine
    from pao.models import BrainFile
    from pao.modules.platform import lifecycle
    monkeypatch.setattr(settings(),'brain_manager_enabled',True)
    async with Session.begin() as db:
        brain=Brain(workspace_id=identity['workspace'],owner_id=identity['user_id'],name='Bounded Brain',legacy_default=False)
        db.add(brain);await db.flush();bid=brain.id
        content=b'0123456789abcdef'
        db.add(BrainFile(brain_id=bid,workspace_id=identity['workspace'],created_by=identity['user_id'],
            name='source.txt',mime='text/plain',size=len(content),sha256=hashlib.sha256(content).hexdigest(),content=content))
    seen=[]
    def inspect_sql(conn,cursor,statement,parameters,context,many):
        if statement.lstrip().upper().startswith('SELECT'):seen.append(statement)
    event.listen(engine.sync_engine,'before_cursor_execute',inspect_sql)
    monkeypatch.setattr(lifecycle,'MAX_EXPORT_BYTES',8)
    try:
        response=await client.post(path(identity,'/data/exports'),headers=identity['owner'],json={'include_business':False,'brain_ids':[bid]})
        assert response.status_code==413,response.text
        assert not any('brain_files.content' in sql for sql in seen)
    finally:event.remove(engine.sync_engine,'before_cursor_execute',inspect_sql)


async def test_export_download_rechecks_brain_grant(client,identity,encryption,monkeypatch):
    monkeypatch.setattr(settings(),'brain_manager_enabled',True)
    async with Session.begin() as db:
        uid=await db.scalar(select(User.id).where(User.email=='other@example.test'))
        brain=Brain(workspace_id=identity['workspace'],owner_id=uid,name='Granted Brain',legacy_default=False)
        db.add(brain);await db.flush();bid=brain.id
        db.add(BrainMember(brain_id=bid,workspace_id=identity['workspace'],user_id=identity['user_id'],role='reader'))
    response=await client.post(path(identity,'/data/exports'),headers=identity['owner'],json={'include_business':False,'brain_ids':[bid]})
    assert response.status_code==201,response.text
    async with Session.begin() as db:await db.delete(await db.get(BrainMember,(bid,identity['user_id'])))
    assert (await client.get(path(identity,f"/data/exports/{response.json()['id']}/download"),headers=identity['owner'])).status_code==404
