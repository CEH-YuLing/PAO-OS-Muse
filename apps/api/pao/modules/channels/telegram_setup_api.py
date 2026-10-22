"""Authenticated enterprise setup. No secret echo, implicit grant or activation."""
from dataclasses import asdict
from uuid import UUID,uuid4
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import Field,SecretStr
from sqlalchemy import select
from typing import Literal
from pao.auth import principal,rate_limit
from pao.db import database,Session
from pao.access import membership
from pao.models import TelegramConnection,TelegramRuntimeProfile,TelegramBotIdentity,TelegramPairing,TelegramPeer,ChannelBinding,now
from pao.modules.studio.contracts import Closed
from . import telegram_runtime as rt,telegram_store as store,telegram_identity as identities,telegram_scoped as scoped,telegram_setup as team,telegram_transport as transport

router=APIRouter(prefix='/v1/telegram/scoped',tags=['telegram-scoped'])


class Create(Closed):
    workspace_id:UUID=Field(strict=False)
    bot_user_id:str=Field(pattern=r'^[1-9][0-9]{0,15}$')
    token:SecretStr=Field(min_length=30,max_length=512)
    consent:Literal[True]

class Save(Closed):
    generation:int=Field(ge=0,le=2147483645)
    request_key:UUID=Field(strict=False)
    token:SecretStr=Field(min_length=30,max_length=512)
    consent:Literal[True]

class Verify(Closed):
    bot_user_id:str=Field(pattern=r'^[1-9][0-9]{0,15}$')
    token:SecretStr=Field(min_length=30,max_length=512)
    request_key:UUID=Field(strict=False)
    consent:Literal[True]

class Control(Closed):
    generation:int=Field(ge=1,le=2147483645)
    request_key:UUID=Field(strict=False)
    action:Literal['enable','disable','revoke','polling','webhook','test']
    consent:Literal[True]

class Pair(Closed):
    expected_user_id:str=Field(pattern=r'^[1-9][0-9]{0,15}$')
    brain_id:UUID|None=Field(default=None,strict=False)

class Confirm(Closed):
    pairing_id:UUID=Field(strict=False)
    consent:Literal[True]

class Grant(Closed):
    peer_id:UUID=Field(strict=False)
    request_key:UUID=Field(strict=False)
    version:int=Field(ge=0)
    allow_chat:bool=False
    allow_reports:bool=False
    confirm_destination:bool=False


async def pin_for(db,cid,who,*,owner=False,admin=False,candidate=None):
    row=await db.get(TelegramConnection,str(cid))
    if not row:raise HTTPException(404,'telegram_connection_not_found')
    member=await membership(db,row.workspace_id,who)
    if admin and member.role not in ('owner','admin') or owner and row.owner_id!=who.id:
        raise HTTPException(403,'telegram_setup_owner_required')
    if member.role=='viewer':raise HTTPException(403,'telegram_team_permission_denied')
    identity=await db.scalar(select(TelegramBotIdentity).where(TelegramBotIdentity.connection_id==row.id))
    bot=identity.bot_user_id if identity else row.bot_user_id or (candidate if row.kind=='legacy' else None)
    if not bot:raise HTTPException(409,'telegram_identity_unverified')
    pin=rt.RuntimePin(row.workspace_id,row.id,row.owner_id,row.version,bot)
    await db.rollback()  # Never hold an auth/read connection while owning bot.
    return pin


def failure(error):
    code=str(error)
    return HTTPException(409,code if code.startswith('telegram_') and len(code)<100 else 'telegram_setup_unavailable')


@router.get('')
async def connections(workspace_id:UUID,who=Depends(principal),db=Depends(database)):
    member=await membership(db,str(workspace_id),who)
    rows=list(await db.scalars(select(TelegramConnection).where(TelegramConnection.workspace_id==str(workspace_id)).order_by(TelegramConnection.created_at).limit(100)))
    result=[]
    for row in rows:
        profile=await db.scalar(select(TelegramRuntimeProfile).where(TelegramRuntimeProfile.connection_id==row.id))
        verified=bool(await db.scalar(select(TelegramBotIdentity.id).where(TelegramBotIdentity.connection_id==row.id)))
        result.append({'id':row.id,'workspace_id':row.workspace_id,'bot_user_id':row.bot_user_id,'kind':row.kind,
            'editable':row.owner_id==who.id and member.role in ('owner','admin'),'generation':profile.generation if profile else 0,
            'status':profile.status if profile else 'empty','identity_verified':verified,
            'mode':profile.transport_mode if profile else 'polling','live_accepted':False})
    return {'workspace_id':str(workspace_id),'runtime_available':rt.settings().telegram_scoped_runtime_enabled and not rt.settings().telegram_enabled,
        'can_manage':member.role in ('owner','admin'),'can_pair':member.role!='viewer','connections':result}


@router.get('/destinations')
async def destinations(workspace_id:UUID,who=Depends(principal),db=Depends(database)):
    await membership(db,str(workspace_id),who)
    from .telegram_reports import destination
    result=[]
    for binding in await db.scalars(select(ChannelBinding).where(ChannelBinding.workspace_id==str(workspace_id),
        ChannelBinding.actor_id==who.id,ChannelBinding.connection_id.is_not(None),ChannelBinding.reports_enabled.is_(True)).limit(100)):
        try:await destination(db,str(workspace_id),who.id,binding.id)
        except (HTTPException,rt.TelegramRuntimeError):continue
        peer=await db.get(TelegramPeer,binding.peer_id);connection=await db.get(TelegramConnection,binding.connection_id)
        result.append({'binding_id':binding.id,'connection_id':binding.connection_id,'bot_user_id':connection.bot_user_id,
            'telegram_user_id':peer.telegram_user_id,'version':binding.version})
    return result


@router.post('',status_code=201)
async def create(body:Create,request:Request,who=Depends(principal),db=Depends(database)):
    member=await membership(db,str(body.workspace_id),who)
    if member.role not in ('owner','admin'):raise HTTPException(403,'telegram_setup_owner_required')
    await rate_limit(request.app.state.redis,'telegram-setup-create',who.id,10,60)
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.ext.asyncio import AsyncSession
    pin=rt.RuntimePin(str(body.workspace_id),str(uuid4()),who.id,1,body.bot_user_id)
    await db.rollback()
    try:
        rt._enabled()
        async with rt.own_bot(pin) as lease,AsyncSession(bind=lease.connection,expire_on_commit=False) as session:
            async with session.begin():
                await rt._require_lease(session,lease);await team.member(session,pin,who.id,admin=True)
                # Proof precedes reservation: an SME cannot claim somebody
                # else's bot ID merely by guessing its public number.
                capsule=rt.seal_credentials(pin,body.token)
                await rt._metadata(pin,capsule,'getMe',None)
                await rt._require_lease(session,lease)
                row=TelegramConnection(id=pin.connection_id,workspace_id=pin.workspace_id,owner_id=pin.owner_id,bot_user_id=pin.bot_user_id)
                session.add(row);await session.flush()
                session.add(TelegramBotIdentity(workspace_id=pin.workspace_id,connection_id=pin.connection_id,owner_id=who.id,
                    connection_version=1,bot_user_id=pin.bot_user_id,request_key=str(uuid4()),content_hash=store._fingerprint(pin,'create',0,str(uuid4()),body.token)))
        return {'id':pin.connection_id,'workspace_id':pin.workspace_id,'status':'empty','identity_verified':True,'external_calls':True}
    except IntegrityError:raise HTTPException(409,'telegram_identity_claimed') from None
    except rt.TelegramRuntimeError as error:raise failure(error) from None


@router.post('/{connection_id}/credential')
async def save(connection_id:UUID,body:Save,request:Request,who=Depends(principal),db=Depends(database)):
    pin=await pin_for(db,connection_id,who,owner=True,admin=True)
    await rate_limit(request.app.state.redis,'telegram-setup-save',who.id,10,60)
    try:
        async with rt.own_bot(pin) as lease:
            # Saving never contacts Telegram. Verification is a separate action.
            return asdict(await store.save_profile(lease,body.token,expected_generation=body.generation,
                request_key=str(body.request_key),consent=body.consent))
    except rt.TelegramRuntimeError as error:raise failure(error) from None


@router.post('/{connection_id}/identity')
async def verify(connection_id:UUID,body:Verify,request:Request,who=Depends(principal),db=Depends(database)):
    pin=await pin_for(db,connection_id,who,owner=True,admin=True,candidate=body.bot_user_id)
    if body.bot_user_id!=pin.bot_user_id:raise HTTPException(409,'telegram_identity_scope_changed')
    await rate_limit(request.app.state.redis,'telegram-setup-verify',who.id,10,60)
    try:
        async with rt.own_bot(pin) as lease:
            result=await identities.verify_identity(lease,body.token,request_key=str(body.request_key),consent=True)
            return {'identity_verified':True,'bot_user_id':result.bot_user_id,'live_accepted':False}
    except rt.TelegramRuntimeError as error:raise failure(error) from None


@router.post('/{connection_id}/control')
async def control(connection_id:UUID,body:Control,request:Request,who=Depends(principal),db=Depends(database)):
    pin=await pin_for(db,connection_id,who,owner=True,admin=True)
    await rate_limit(request.app.state.redis,'telegram-setup-control',who.id,10,60)
    try:
        async with rt.own_bot(pin) as lease:
            if body.action=='revoke':return asdict(await store.revoke_profile(lease,expected_generation=body.generation,request_key=str(body.request_key),consent=True))
            if body.action in ('polling','webhook'):
                return asdict(await transport.configure(lease,generation=body.generation,request_key=str(body.request_key),mode=body.action,consent=True))
            if body.action=='test':
                async with store._transaction(lease) as session:
                    row=await store._profile(session,pin,body.generation)
                    if not row or row.status=='revoked':raise rt.TelegramRuntimeError('telegram_store_revoked')
                    token=rt._open_credentials(pin,store._unseal(pin,row.generation,row.token_ciphertext))
                    known=await session.scalar(select(TelegramBotIdentity.id).where(TelegramBotIdentity.connection_id==pin.connection_id))
                if not known:await identities.verify_identity(lease,token,request_key=str(body.request_key),consent=True)
                result=await rt.probe(lease,store.credential_loader(body.generation),method='getMe')
                return {'identity_verified':True,'bot_user_id':result.bot_user_id,'username':result.username,'live_accepted':False}
            if body.action=='enable':
                info=await rt.probe(lease,store.credential_loader(body.generation),method='getWebhookInfo')
                async with store._transaction(lease) as session:
                    row=await store._profile(session,pin,body.generation)
                    if (row.transport_mode=='polling')==bool(info.webhook_present):raise rt.TelegramRuntimeError('telegram_transport_mode_conflict')
                    if row.transport_mode=='webhook' and info.webhook_matches is not True:raise rt.TelegramRuntimeError('telegram_transport_mode_conflict')
            return asdict(await scoped.control_profile(lease,generation=body.generation,request_key=str(body.request_key),action=body.action,consent=True))
    except rt.TelegramRuntimeError as error:raise failure(error) from None


@router.get('/{connection_id}/team')
async def team_list(connection_id:UUID,who=Depends(principal),db=Depends(database)):
    pin=await pin_for(db,connection_id,who)
    async with Session() as session:
        me=await session.get(team.Member,(pin.workspace_id,who.id));admin=me and me.role in ('owner','admin')
        query=select(TelegramPeer).where(TelegramPeer.connection_id==pin.connection_id)
        if not admin:query=query.where(TelegramPeer.user_id==who.id)
        peers=[]
        for peer in await session.scalars(query.order_by(TelegramPeer.created_at).limit(100)):
            binding=await session.scalar(select(ChannelBinding).where(ChannelBinding.peer_id==peer.id))
            peers.append({'id':peer.id,'user_id':peer.user_id,'telegram_user_id':peer.telegram_user_id,
                'enabled':peer.enabled,'version':binding.version if binding else 0,
                'allow_chat':bool(binding and binding.enabled and binding.mode=='auto'),
                'allow_reports':bool(binding and binding.enabled and binding.reports_enabled)})
        pairings=[{'id':p.id,'status':p.status,'expected_user_id':p.expected_user_id,'observed_user_id':p.observed_user_id,
            'expires_at':p.expires_at,'expired':p.expires_at<=now()} for p in await session.scalars(select(TelegramPairing).where(
                TelegramPairing.connection_id==pin.connection_id,TelegramPairing.user_id==who.id).order_by(TelegramPairing.created_at.desc()).limit(10))]
    return {'peers':peers,'pairings':pairings}


@router.post('/{connection_id}/pairing',status_code=201)
async def pairing(connection_id:UUID,body:Pair,request:Request,who=Depends(principal),db=Depends(database)):
    pin=await pin_for(db,connection_id,who)
    await rate_limit(request.app.state.redis,'telegram-pair-create',who.id,5,60)
    try:
        async with rt.own_bot(pin) as lease:
            async with store._transaction(lease) as session:
                profile=await store._profile(session,pin)
                if not profile:raise HTTPException(409,'telegram_setup_enable_first')
                row,code=await team.pairing(session,pin,profile,who.id,body.expected_user_id,str(body.brain_id) if body.brain_id else None)
                return {'id':row.id,'command':'/start pao_'+code,'expires_at':row.expires_at,'granted':False}
    except rt.TelegramRuntimeError as error:raise failure(error) from None


@router.post('/{connection_id}/pairing/confirm')
async def confirm(connection_id:UUID,body:Confirm,who=Depends(principal),db=Depends(database)):
    pin=await pin_for(db,connection_id,who)
    try:
        async with rt.own_bot(pin) as lease:
            async with store._transaction(lease) as session:
                profile=await store._profile(session,pin)
                if not profile:raise HTTPException(409,'telegram_setup_enable_first')
                peer=await team.confirm(session,pin,profile,who.id,str(body.pairing_id))
                return {'peer_id':peer.id,'enabled':peer.enabled,'granted':False}
    except rt.TelegramRuntimeError as error:raise failure(error) from None


@router.post('/{connection_id}/team/grant')
async def grant(connection_id:UUID,body:Grant,request:Request,who=Depends(principal),db=Depends(database)):
    pin=await pin_for(db,connection_id,who,admin=True)
    await rate_limit(request.app.state.redis,'telegram-team-grant',who.id,20,60)
    try:
        async with rt.own_bot(pin) as lease:
            async with store._transaction(lease) as session:
                await session.execute(team.text("SET LOCAL lock_timeout='200ms'"))
                profile=await store._profile(session,pin)
                if not profile:raise HTTPException(409,'telegram_setup_enable_first')
                row=await team.grant(session,pin,profile,who.id,str(body.peer_id),allow_chat=body.allow_chat,
                    allow_reports=body.allow_reports,confirm_destination=body.confirm_destination,version=body.version,request_key=str(body.request_key))
                return {'binding_id':row.id,'version':row.version,'enabled':row.enabled,'reports_enabled':row.reports_enabled}
    except rt.TelegramRuntimeError as error:raise failure(error) from None
