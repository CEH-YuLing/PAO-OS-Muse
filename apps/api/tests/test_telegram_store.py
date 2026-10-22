"""S3.2B real PostgreSQL store. All credentials synthetic; real HTTP forbidden."""
from dataclasses import asdict,replace
import asyncio,json
from uuid import uuid4
import httpx,pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import select,text,func
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession
from pao.config import settings
from pao.db import Session
from pao.models import (Workspace,Member,User,TelegramConnection,TelegramRuntimeProfile,
    TelegramRuntimeAudit,TelegramRuntimeReceipt,ChannelOutbox,TelegramUpdate)
from pao.modules.channels import telegram_runtime as rt,telegram_store as store

TOKEN=SecretStr('111:'+'SYNTHETIC_STORE_A_'*3)
ROTATED=SecretStr('111:'+'SYNTHETIC_ROTATED_A_'*3)


@pytest.fixture
async def durable(identity,monkeypatch):
    def no_network(*a,**k):raise AssertionError('Unexpected live Telegram HTTP')
    monkeypatch.setattr(httpx,'AsyncHTTPTransport',no_network)
    monkeypatch.setattr(settings(),'telegram_scoped_runtime_enabled',True)
    monkeypatch.setattr(settings(),'telegram_enabled',False)
    monkeypatch.setattr(settings(),'integration_encryption_key',Fernet.generate_key().decode())
    async with Session.begin() as db:
        space=Workspace(name='Store SME B');db.add(space);await db.flush()
        db.add(Member(workspace_id=space.id,user_id=identity['user_id'],role='owner'))
        rows=[TelegramConnection(workspace_id=wid,owner_id=identity['user_id'],bot_user_id=bot)
            for wid,bot in ((identity['workspace'],'111'),(space.id,'222'))]
        db.add_all(rows);await db.flush()
        pins=[rt.RuntimePin(r.workspace_id,r.id,r.owner_id,r.version,r.bot_user_id) for r in rows]
    return pins


async def save(pin,token=TOKEN,generation=0,key=None):
    async with rt.own_bot(pin) as lease:
        return await store.save_profile(lease,token,expected_generation=generation,request_key=key or str(uuid4()),consent=True)


async def quarantine(pin,generation=1,offset=0,updates=None,reason='unlinked'):
    async with rt.own_bot(pin) as lease:
        return await store.record_quarantine(lease,generation=generation,expected_offset=offset,
            updates=updates if updates is not None else [{'update_id':7,'message':{'text':'private content'}}],reason=reason)


async def test_persisted_two_sme_credentials_no_authority_or_plaintext(client,durable):
    a,b=durable;other=SecretStr('222:'+'SYNTHETIC_STORE_B_'*3)
    for pin,token in ((a,TOKEN),(b,other)):
        result=await save(pin,token)
        assert asdict(result)=={'connection_id':pin.connection_id,'generation':1,'status':'disabled','next_offset':0}
        seen=[]
        def handler(request):
            seen.append(request.url.path)
            return httpx.Response(200,json={'ok':True,'result':{'id':int(pin.bot_user_id),'is_bot':True}})
        async with rt.own_bot(pin) as lease:
            probe=await rt.probe(lease,store.credential_loader(1),transport=httpx.MockTransport(handler))
            assert probe.bot_user_id==pin.bot_user_id
        assert seen==['/bot'+token.get_secret_value()+'/getMe']
    async with Session() as db:
        for row in await db.scalars(select(TelegramRuntimeProfile)):
            assert TOKEN.get_secret_value() not in row.token_ciphertext and other.get_secret_value() not in row.token_ciphertext
        events=list(await db.scalars(select(TelegramRuntimeAudit)))
        assert len(events)==2 and all(e.action=='stored' for e in events)
        assert all(TOKEN.get_secret_value() not in e.content_hash for e in events)
        for model in (TelegramUpdate,ChannelOutbox):assert await db.scalar(select(func.count()).select_from(model))==0


async def test_rotation_generation_cursor_and_revoke_are_durable(client,durable):
    pin=durable[0];await save(pin);await quarantine(pin)
    rotated=await save(pin,ROTATED,1)
    assert (rotated.generation,rotated.next_offset,rotated.status)==(2,8,'disabled')
    async with rt.own_bot(pin) as lease:
        with pytest.raises(rt.TelegramRuntimeError,match='generation_stale'):
            await rt.probe(lease,store.credential_loader(1))
    key=str(uuid4())
    async with rt.own_bot(pin) as lease:
        revoked=await store.revoke_profile(lease,expected_generation=2,request_key=key,consent=True)
    assert (revoked.generation,revoked.status,revoked.next_offset)==(3,'revoked',8)
    async with rt.own_bot(pin) as lease:
        assert await store.revoke_profile(lease,expected_generation=2,request_key=key,consent=True)==revoked
    with pytest.raises(rt.TelegramRuntimeError,match='revoked'):await save(pin,ROTATED,3)
    with pytest.raises(rt.TelegramRuntimeError,match='revoked'):await quarantine(pin,3,8,[{'update_id':8}])
    async with Session() as db:
        profile=await db.scalar(select(TelegramRuntimeProfile).where(TelegramRuntimeProfile.connection_id==pin.connection_id))
        assert profile.token_ciphertext is None
        assert list(await db.scalars(select(TelegramRuntimeAudit.action).order_by(TelegramRuntimeAudit.generation)))==['stored','rotated','revoked']
        assert (await db.get(TelegramConnection,pin.connection_id)).status=='staged'


async def test_same_request_retry_deduplicated_conflict_and_superseded(client,durable):
    pin=durable[0];key=str(uuid4());first=await save(pin,key=key)
    assert await save(pin,key=key)==first
    with pytest.raises(rt.TelegramRuntimeError,match='request_conflict'):await save(pin,ROTATED,key=key)
    await save(pin,ROTATED,1)
    with pytest.raises(rt.TelegramRuntimeError,match='request_superseded'):await save(pin,key=key)
    async with Session() as db:assert await db.scalar(select(func.count()).select_from(TelegramRuntimeAudit))==2


@pytest.mark.parametrize('change',['member','viewer','inactive','connection','version','bot','workspace'])
async def test_fresh_owner_scope_denied_before_any_store_write(client,durable,change):
    pin=durable[0]
    if change in ('version','bot','workspace'):
        pin=replace(pin,**{'version':{'connection_version':2},'bot':{'bot_user_id':'999'},'workspace':{'workspace_id':durable[1].workspace_id}}[change])
    else:
        async with Session.begin() as db:
            if change=='member':await db.delete(await db.get(Member,(pin.workspace_id,pin.owner_id)))
            elif change=='viewer':(await db.get(Member,(pin.workspace_id,pin.owner_id))).role='viewer'
            elif change=='inactive':(await db.get(User,pin.owner_id)).active=False
            else:
                row=await db.get(TelegramConnection,pin.connection_id);row.status='revoked';row.version+=1
    token=SecretStr(pin.bot_user_id+':'+'SYNTHETIC_FORGED_SCOPE_'*3) if change=='bot' else TOKEN
    with pytest.raises(rt.TelegramRuntimeError,match='owner_unavailable|scope_changed'):await save(pin,token)
    async with Session() as db:assert await db.scalar(select(func.count()).select_from(TelegramRuntimeProfile))==0


@pytest.mark.parametrize('change',['gate','legacy','consent','token','bool_generation','invalid_key','missing_key'])
async def test_disabled_or_invalid_setup_never_persists(client,durable,monkeypatch,change):
    pin=durable[0];kwargs={'expected_generation':0,'request_key':str(uuid4()),'consent':True};token=TOKEN
    if change=='gate':monkeypatch.setattr(settings(),'telegram_scoped_runtime_enabled',False)
    elif change=='legacy':monkeypatch.setattr(settings(),'telegram_enabled',True)
    elif change=='consent':kwargs['consent']=False
    elif change=='token':token=SecretStr('222:'+'SYNTHETIC_OTHER_'*3)
    elif change=='bool_generation':kwargs['expected_generation']=False
    elif change=='invalid_key':kwargs['request_key']='not-a-uuid'
    else:monkeypatch.setattr(settings(),'integration_encryption_key','')
    async with rt.own_bot(pin) as lease:
        with pytest.raises(rt.TelegramRuntimeError):await store.save_profile(lease,token,**kwargs)
    async with Session() as db:assert await db.scalar(select(func.count()).select_from(TelegramRuntimeAudit))==0


@pytest.mark.parametrize('mutation',['ciphertext','generation','pin','purpose','bool_generation','extra_field'])
async def test_encrypted_store_generation_pin_and_purpose_are_authenticated(client,durable,mutation):
    pin=durable[0];await save(pin)
    async with Session() as db:
        row=await db.scalar(select(TelegramRuntimeProfile));ciphertext=row.token_ciphertext
    capsule=store._unseal(pin,1,ciphertext)
    assert rt._open_credentials(pin,capsule).get_secret_value()==TOKEN.get_secret_value()
    data=json.loads(rt._cipher().decrypt(ciphertext.encode()))
    if mutation=='ciphertext':ciphertext=ciphertext[:-10]+'bad'
    else:
        if mutation=='generation':data['generation']=2
        elif mutation=='pin':data['pin']['workspace_id']=durable[1].workspace_id
        elif mutation=='purpose':data['purpose']='other-purpose'
        elif mutation=='bool_generation':data['generation']=True
        else:data['extra']='denied'
        ciphertext=rt._cipher().encrypt(json.dumps(data).encode()).decode()
    with pytest.raises(rt.TelegramRuntimeError):store._unseal(pin,1,ciphertext)


async def test_atomic_quarantine_cursor_duplicate_body_free_and_two_bots(client,durable):
    a,b=durable;await save(a);await save(b,SecretStr('222:'+'SYNTHETIC_B_'*4))
    for pin in (a,b):
        first=await quarantine(pin);assert first.next_offset==8
        assert (await quarantine(pin,offset=8)).next_offset==8
    async with Session() as db:
        receipts=list(await db.scalars(select(TelegramRuntimeReceipt)))
        assert len(receipts)==2 and all(r.update_id==7 and r.reason=='unlinked' for r in receipts)
        assert 'body' not in TelegramRuntimeReceipt.__table__.columns
        assert await db.scalar(select(func.count()).select_from(ChannelOutbox))==0
    # Conflict in a later batch rolls back even the earlier new receipt.
    with pytest.raises(rt.TelegramRuntimeError,match='update_conflict'):
        await quarantine(a,offset=8,updates=[{'update_id':9},{'update_id':7,'changed':True}])
    async with Session() as db:
        row=await db.scalar(select(TelegramRuntimeProfile).where(TelegramRuntimeProfile.connection_id==a.connection_id))
        assert row.next_offset==8
        assert await db.scalar(select(func.count()).select_from(TelegramRuntimeReceipt))==2


async def test_rotation_never_replays_or_resets_old_update_history(client,durable):
    pin=durable[0];await save(pin);await quarantine(pin);await save(pin,ROTATED,1)
    assert (await quarantine(pin,2,8)).next_offset==8
    with pytest.raises(rt.TelegramRuntimeError,match='generation_stale'):await quarantine(pin,1,8)
    with pytest.raises(rt.TelegramRuntimeError,match='cursor_stale'):await quarantine(pin,2,0)
    with pytest.raises(rt.TelegramRuntimeError,match='behind_cursor'):await quarantine(pin,2,8,[{'update_id':6}])
    async with Session() as db:
        assert await db.scalar(select(func.count()).select_from(TelegramRuntimeReceipt))==1
        assert (await db.scalar(select(TelegramRuntimeReceipt))).generation==1


@pytest.mark.parametrize('updates',[[],[{'update_id':True}],[{'update_id':-1}],[{'update_id':2**63-1}],[{}],
    [{'update_id':1,'data':'x'*65536}],[{'update_id':1,'bad':float('nan')}],[{'update_id':1}]*101])
async def test_bad_or_unbounded_batch_no_cursor_or_receipt(client,durable,updates):
    pin=durable[0];await save(pin)
    with pytest.raises(rt.TelegramRuntimeError,match='input_invalid'):await quarantine(pin,updates=updates)
    async with Session() as db:
        assert (await db.scalar(select(TelegramRuntimeProfile))).next_offset==0
        assert await db.scalar(select(func.count()).select_from(TelegramRuntimeReceipt))==0


@pytest.mark.parametrize('operation',[
    'UPDATE telegram_runtime_audits SET action=action',
    'DELETE FROM telegram_runtime_audits',
    'UPDATE telegram_runtime_receipts SET reason=reason',
    'DELETE FROM telegram_runtime_receipts',
    "UPDATE telegram_runtime_profiles SET status='revoked',token_ciphertext=NULL",  # generation not advanced
    'UPDATE telegram_runtime_profiles SET next_offset=0',
    'DELETE FROM telegram_runtime_profiles',
])
async def test_database_guards_append_only_audit_receipt_and_monotonic_profile(client,durable,operation):
    await save(durable[0]);await quarantine(durable[0])
    with pytest.raises(DBAPIError):
        async with Session.begin() as db:await db.execute(text(operation))


async def test_database_requires_atomic_generation_audit_and_global_unique_bot(client,durable):
    await save(durable[0])
    with pytest.raises(DBAPIError,match='telegram_runtime_audit_required'):
        async with Session.begin() as db:
            await db.execute(text("UPDATE telegram_runtime_profiles SET generation=2,token_ciphertext='synthetic-new-ciphertext'"))
    with pytest.raises(DBAPIError):
        async with Session.begin() as db:
            db.add(TelegramConnection(workspace_id=durable[1].workspace_id,owner_id=durable[1].owner_id,
                bot_user_id=durable[0].bot_user_id))


async def test_transaction_and_lost_lease_fail_closed(client,durable):
    pin=durable[0]
    async with rt.own_bot(pin) as lease:
        await lease.connection.execute(text('SELECT 1'))
        with pytest.raises(rt.TelegramRuntimeError,match='transaction_busy'):
            await store.save_profile(lease,TOKEN,expected_generation=0,request_key=str(uuid4()),consent=True)
        await lease.connection.rollback()
    with pytest.raises(rt.TelegramRuntimeError,match='lease_lost'):
        await store.save_profile(lease,TOKEN,expected_generation=0,request_key=str(uuid4()),consent=True)


async def test_same_identity_bot_cannot_be_released_by_profile_revoke(client,durable):
    pin=durable[0];await save(pin)
    async with rt.own_bot(pin) as lease:
        await store.revoke_profile(lease,expected_generation=1,request_key=str(uuid4()),consent=True)
    with pytest.raises(DBAPIError):
        async with Session.begin() as db:
            db.add(TelegramConnection(workspace_id=durable[1].workspace_id,owner_id=pin.owner_id,
                kind='legacy',bot_user_id=pin.bot_user_id))


async def test_database_cursor_cannot_advance_without_matching_durable_receipt(client,durable):
    await save(durable[0])
    with pytest.raises(DBAPIError,match='telegram_runtime_cursor_receipt_required'):
        async with Session.begin() as db:await db.execute(text('UPDATE telegram_runtime_profiles SET next_offset=123'))


async def test_quarantine_batch_duplicate_dedup_then_cancellation_rolls_back(client,durable):
    pin=durable[0];await save(pin)
    result=await quarantine(pin,updates=[{'update_id':7},{'update_id':7}])
    assert result.next_offset==8
    async with rt.own_bot(pin) as lease:
        with pytest.raises(asyncio.CancelledError):
            async with store._transaction(lease) as db:
                row=await store._profile(db,pin,1)
                db.add(TelegramRuntimeReceipt(workspace_id=pin.workspace_id,connection_id=pin.connection_id,
                    generation=1,update_id=9,content_hash='a'*64,reason='unlinked'))
                row.next_offset=10;await db.flush()
                raise asyncio.CancelledError()
    async with Session() as db:
        assert (await db.scalar(select(TelegramRuntimeProfile))).next_offset==8
        assert await db.scalar(select(func.count()).select_from(TelegramRuntimeReceipt))==1


@pytest.mark.parametrize('expected',[True,-1,2**31-1,'0',None])
async def test_bad_generation_rejected_before_write(client,durable,expected):
    with pytest.raises(rt.TelegramRuntimeError,match='input_invalid'):await save(durable[0],generation=expected)


async def test_legacy_without_verified_identity_stays_denied_no_inferred_host_token(client,durable):
    pin=durable[0]
    async with Session.begin() as db:
        legacy=TelegramConnection(workspace_id=pin.workspace_id,owner_id=pin.owner_id,kind='legacy',bot_user_id=None)
        db.add(legacy);await db.flush();ident=legacy.id
    forged=replace(pin,connection_id=ident)
    with pytest.raises(rt.TelegramRuntimeError,match='scope_changed'):await save(forged)


@pytest.mark.parametrize('role,allowed',[('owner',True),('admin',True),('operator',False),('viewer',False)])
async def test_storing_credential_does_not_inherit_operator_or_viewer_authority(client,durable,role,allowed):
    pin=durable[0]
    async with Session.begin() as db:(await db.get(Member,(pin.workspace_id,pin.owner_id))).role=role
    if allowed:assert (await save(pin)).status=='disabled'
    else:
        with pytest.raises(rt.TelegramRuntimeError,match='owner_unavailable'):await save(pin)


async def test_request_key_cannot_be_reused_for_another_bot_or_revoke(client,durable):
    pin=durable[0];key=str(uuid4());await save(pin,key=key)
    async with Session.begin() as db:
        other=TelegramConnection(workspace_id=pin.workspace_id,owner_id=pin.owner_id,bot_user_id='333')
        db.add(other);await db.flush()
        other_pin=rt.RuntimePin(other.workspace_id,other.id,other.owner_id,other.version,other.bot_user_id)
    with pytest.raises(rt.TelegramRuntimeError,match='request_conflict'):
        await save(other_pin,SecretStr('333:'+'SYNTHETIC_THIRD_'*3),key=key)
    async with rt.own_bot(pin) as lease:
        with pytest.raises(rt.TelegramRuntimeError,match='request_conflict'):
            await store.revoke_profile(lease,expected_generation=1,request_key=key,consent=True)
