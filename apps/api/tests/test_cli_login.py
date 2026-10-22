"""Native auth/SME/lease tests with synthetic Codex ceremonies, no provider I/O."""
import asyncio
from uuid import uuid4
import pytest
from sqlalchemy import select
from pao.config import settings
from pao.db import Session
from pao.auth import issue_token
from pao.models import CliModelConnection,Member,User
from pao.modules.cli_connections import login_manager,runtime
from pao.modules.cli_connections.login_transport import challenge


class FakeLogin:
    events={}
    closed=[]
    def __init__(self,pin,operation,authorize=None):
        self.pin,self.operation=pin,operation
        self.cleanup_verified=False
    async def authenticate(self,publish):
        self.events[self.operation]=asyncio.Event()
        await publish({'verificationUrl':'https://auth.openai.com/codex/device','userCode':'ABCD-EFGH'})
        await self.events[self.operation].wait()
    async def close(self):self.cleanup_verified=True;self.closed.append(self.operation)
    async def recover(self):self.cleanup_verified=True


@pytest.fixture
def login(monkeypatch):
    config={'device_id':str(uuid4()),'image_id':'sha256:'+'a'*64,'binary_sha256':'3e2584f3f3829a43a0495011a1cecb2facbe64a2403e2b682351fd9c2983f970','binary_version':'0.157.1','host_runtime_sha256':'b'*64}
    monkeypatch.setattr(settings(),'cli_connections_enabled',True)
    monkeypatch.setattr(settings(),'cli_browser_login_enabled',True)
    monkeypatch.setattr(settings(),'cli_device_id',config['device_id'])
    monkeypatch.setattr(runtime,'device_config',lambda:config)
    monkeypatch.setattr(login_manager,'LoginTransport',FakeLogin)
    from pao.modules.cli_connections import login_transport
    monkeypatch.setattr(login_transport,'LoginTransport',FakeLogin)
    FakeLogin.events={};FakeLogin.closed=[]
    return config


async def prepared(client,identity,login):
    base=f"/v1/workspaces/{identity['workspace']}/cli-connections"
    response=await client.post(base,headers=identity['owner'],json={'request_key':str(uuid4()),'model':'synthetic-model'})
    assert response.status_code==201,response.text
    row=response.json()
    async with Session.begin() as db:
        current=await db.get(CliModelConnection,row['id'])
        current.binary_sha256=login['binary_sha256'];current.binary_version=login['binary_version'];current.runtime_image_id=login['image_id']
    return base+'/'+row['id'],row


async def start(client,identity,base,row,**extra):
    return await client.post(base+'/login',headers=identity['owner'],json={'version':row['version'],'request_key':str(uuid4()),'allow_personal_login':True,**extra})


async def state(client,identity,base,target):
    for _ in range(120):
        response=await client.get(base+'/login',headers=identity['owner'])
        assert response.status_code==200,response.text
        value=response.json()
        if value['status']==target:return value
        await asyncio.sleep(.025)
    raise AssertionError('Auth state did not reach '+target)


def test_challenge_validates_fixed_official_url_and_never_passes_token_fields():
    data={'type':'chatgptDeviceCode','loginId':str(uuid4()),'verificationUrl':'https://auth.openai.com/codex/device','userCode':'ABCD-EFGH','token':'never-return'}
    assert set(challenge(data))=={'loginId','verificationUrl','userCode'}
    for change in ({'verificationUrl':'https://auth.openai.com.evil.test/codex/device'},{'verificationUrl':'https://auth.openai.com/codex/device?token=secret'},{'verificationUrl':'http://auth.openai.com/codex/device'},{'verificationUrl':'https://user@auth.openai.com/codex/device'},{'userCode':'secret\nCODE'},{'loginId':'not-uuid'},{'type':'apiKey'}):
        with pytest.raises(Exception):challenge({**data,**change})


async def test_default_gate_denies_browser_login(client,identity,login,monkeypatch):
    base,row=await prepared(client,identity,login)
    monkeypatch.setattr(settings(),'cli_browser_login_enabled',False)
    response=await start(client,identity,base,row)
    assert response.status_code==503 and not FakeLogin.events


async def test_explicit_consent_and_no_caller_command_credentials(client,identity,login):
    base,row=await prepared(client,identity,login)
    assert (await start(client,identity,base,row,allow_personal_login=False)).status_code==400
    assert (await start(client,identity,base,row,command='arbitrary')).status_code==422
    assert not FakeLogin.events


async def test_same_request_replayed_once_session_scope_and_success(client,identity,login):
    base,row=await prepared(client,identity,login)
    body={'version':row['version'],'request_key':str(uuid4()),'allow_personal_login':True}
    first=await client.post(base+'/login',headers=identity['owner'],json=body)
    assert first.status_code==200,first.text
    replay=await client.post(base+'/login',headers=identity['owner'],json=body)
    assert replay.status_code==200 and replay.json()['operation_id']==first.json()['operation_id']
    pending=await state(client,identity,base,'awaiting_user')
    assert pending['user_code']=='ABCD-EFGH' and not pending['grant_activated']
    assert (await client.get(base+'/login',headers=identity['other'])).status_code==403
    another={'Authorization':'Bearer '+issue_token(identity['user_id'])}
    private=await client.get(base+'/login',headers=another)
    assert private.json()['status']=='another_session' and private.json()['user_code'] is None
    FakeLogin.events[first.json()['operation_id']].set()
    done=await state(client,identity,base,'connected')
    assert done['user_code'] is None and done['verification_url'] is None
    assert done['provider_inference_verified'] is False and done['grant_activated'] is False
    async with Session() as db:
        current=await db.get(CliModelConnection,row['id'])
        assert current.status=='connected' and current.auth_checked_at and not current.setup_operation_id


async def test_cancel_fences_and_clears_challenge_without_logout(client,identity,login):
    base,row=await prepared(client,identity,login)
    assert (await start(client,identity,base,row)).status_code==200
    pending=await state(client,identity,base,'awaiting_user')
    response=await client.post(base+'/login/cancel',headers=identity['owner'],json={'version':pending['version'],'operation_id':pending['operation_id']})
    assert response.status_code==200,response.text
    assert response.json()['cleanup_verified'] and response.json()['provider_logout_performed'] is False
    after=await client.get(base+'/login',headers=identity['owner'])
    assert after.json()['user_code'] is None
    async with Session() as db:
        current=await db.get(CliModelConnection,row['id'])
        assert not current.setup_operation_id and current.auth_checked_at is None


@pytest.mark.parametrize('reason',['membership','session'])
async def test_authority_revocation_stops_ceremony(client,identity,login,reason):
    from pao.main import app
    base,row=await prepared(client,identity,login)
    await start(client,identity,base,row)
    pending=await state(client,identity,base,'awaiting_user')
    async with Session.begin() as db:
        if reason=='membership':
            member=await db.scalar(select(Member).where(Member.workspace_id==identity['workspace'],Member.user_id==identity['user_id']))
            await db.delete(member)
        else:
            user=await db.get(User,identity['user_id']);user.auth_version+=1
    item=app.state.cli_logins.entries[pending['operation_id']]
    await asyncio.wait_for(asyncio.shield(item.task),4)
    assert item.state=='failed' and item.code is None
    assert pending['operation_id'] in FakeLogin.closed


async def test_restart_fence_is_recoverable_only_with_exact_operation(client,identity,login):
    base,row=await prepared(client,identity,login)
    operation=str(uuid4())
    async with Session.begin() as db:
        current=await db.get(CliModelConnection,row['id']);current.setup_operation_id=operation
    result=await client.get(base+'/login',headers=identity['owner'])
    assert result.json()['status']=='interrupted' and result.json()['user_code'] is None
    wrong=await client.post(base+'/login/cancel',headers=identity['owner'],json={'version':row['version'],'operation_id':str(uuid4())})
    assert wrong.status_code==409
    recovery=await client.post(base+'/login/cancel',headers=identity['owner'],json={'version':row['version'],'operation_id':operation})
    assert recovery.status_code==200,recovery.text


async def test_stale_version_and_profile_prepare_gate(client,identity,login):
    base,row=await prepared(client,identity,login)
    assert (await start(client,identity,base,row,version=999)).status_code==409
    async with Session.begin() as db:
        current=await db.get(CliModelConnection,row['id']);current.runtime_image_id=None
    response=await start(client,identity,base,row)
    assert response.status_code==409 and not FakeLogin.events
