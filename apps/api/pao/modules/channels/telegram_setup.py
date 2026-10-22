"""Pairing observes Telegram then requires the same authenticated PAO account.

A challenge never creates membership, Brain access or permission to use tools.
Only an explicit administrator grant creates/enables a Channels binding.
"""
import hashlib,re,secrets
from datetime import timedelta
from sqlalchemy import select,text
from fastapi import HTTPException
from pao.auth import Principal,rate_limit
from pao.models import TelegramPairing,TelegramPeer,Member,User,ChannelBinding,ChannelAudit,Brain,BrainMember,now
from . import telegram_runtime as rt,telegram_store as store,service


async def member(db,pin,user_id,*,admin=False):
    row=await db.get(Member,(pin.workspace_id,user_id),with_for_update={'read':True},populate_existing=True)
    user=await db.get(User,user_id,with_for_update={'read':True},populate_existing=True)
    if not row or not user or not user.active or row.role=='viewer' or admin and row.role not in ('owner','admin'):
        raise HTTPException(403,'telegram_team_permission_denied')
    return row


async def pairing(db,pin,profile,user_id,expected_user_id,brain_id=None):
    await member(db,pin,user_id)
    if profile.status!='enabled':raise HTTPException(409,'telegram_setup_enable_first')
    if not re.fullmatch(r'[1-9][0-9]{0,15}',expected_user_id):raise HTTPException(422,'telegram_numeric_identity_required')
    if brain_id:
        from pao.modules.brains.access import require_brain
        brain=await require_brain(db,Principal(user_id,0),brain_id,True)
        if brain.workspace_id!=pin.workspace_id:raise HTTPException(403,'telegram_brain_scope_denied')
    for previous in await db.scalars(select(TelegramPairing).where(TelegramPairing.connection_id==pin.connection_id,
        TelegramPairing.user_id==user_id,TelegramPairing.status.in_(('pending','observed'))).with_for_update()):previous.status='revoked'
    code=secrets.token_urlsafe(24)
    row=TelegramPairing(workspace_id=pin.workspace_id,connection_id=pin.connection_id,user_id=user_id,
        generation=profile.generation,expected_user_id=expected_user_id,brain_id=brain_id,
        code_hash=hashlib.sha256(code.encode()).hexdigest(),status='pending',expires_at=now()+timedelta(minutes=10))
    db.add(row);await db.flush()
    return row,code


async def observe_pairing(db,pin,profile,body,telegram_user_id,redis):
    if not body.startswith('/start pao_'):return False
    # Always intercept challenge-like messages: never persist code in inbound,
    # chat history, logs, Run prompts or model context, including malformed codes.
    code=body.removeprefix('/start pao_')
    if not re.fullmatch(r'[A-Za-z0-9_-]{32}',code):return True
    await rate_limit(redis,'telegram-pair-observe',pin.connection_id+':'+telegram_user_id,10,60)
    row=await db.scalar(select(TelegramPairing).where(TelegramPairing.connection_id==pin.connection_id,
        TelegramPairing.workspace_id==pin.workspace_id,TelegramPairing.code_hash==hashlib.sha256(code.encode()).hexdigest()).with_for_update())
    if not row or row.status!='pending' or row.expires_at<=now() or row.generation!=profile.generation:return True
    try:await member(db,pin,row.user_id)
    except HTTPException:return True
    # A forwarded code is burned, not linked to the forwarding sender.
    if row.expected_user_id!=telegram_user_id:row.status='revoked';return True
    row.observed_user_id=telegram_user_id;row.status='observed'
    return True


async def confirm(db,pin,profile,user_id,pairing_id):
    await member(db,pin,user_id)
    row=await db.scalar(select(TelegramPairing).where(TelegramPairing.id==pairing_id,
        TelegramPairing.connection_id==pin.connection_id,TelegramPairing.user_id==user_id).with_for_update())
    if (not row or row.status!='observed' or row.generation!=profile.generation or profile.status!='enabled' or
        row.expires_at<=now() or row.expected_user_id!=row.observed_user_id):raise HTTPException(409,'telegram_pairing_not_confirmable')
    if row.brain_id:
        from pao.modules.brains.access import require_brain
        await require_brain(db,Principal(user_id,0),row.brain_id,True)
    peer=await db.scalar(select(TelegramPeer).where(TelegramPeer.connection_id==pin.connection_id,
        TelegramPeer.telegram_user_id==row.observed_user_id).with_for_update())
    if peer and peer.user_id!=user_id:raise HTTPException(409,'telegram_identity_already_linked')
    if not peer:
        peer=TelegramPeer(connection_id=pin.connection_id,workspace_id=pin.workspace_id,user_id=user_id,
            telegram_user_id=row.observed_user_id,chat_id=row.observed_user_id,enabled=False)
        db.add(peer);await db.flush()
    row.status='confirmed';return peer


async def grant(db,pin,profile,admin_id,peer_id,*,allow_chat,allow_reports,confirm_destination,version,request_key):
    await member(db,pin,admin_id,admin=True)
    peer=await db.scalar(select(TelegramPeer).where(TelegramPeer.id==peer_id,TelegramPeer.connection_id==pin.connection_id,
        TelegramPeer.workspace_id==pin.workspace_id).with_for_update())
    if not peer:raise HTTPException(404,'telegram_peer_not_found')
    await member(db,pin,peer.user_id)
    linked=await db.scalar(select(TelegramPairing).where(TelegramPairing.connection_id==pin.connection_id,
        TelegramPairing.user_id==peer.user_id,TelegramPairing.observed_user_id==peer.telegram_user_id,
        TelegramPairing.status=='confirmed',TelegramPairing.generation==profile.generation)
        .order_by(TelegramPairing.created_at.desc()).limit(1))
    binding=await db.scalar(select(ChannelBinding).where(ChannelBinding.peer_id==peer.id).with_for_update())
    key=store._request_key(request_key)
    if not linked and (allow_chat or allow_reports):raise HTTPException(409,'telegram_pairing_confirmation_required')
    if binding and linked and binding.brain_id!=linked.brain_id and (allow_chat or allow_reports):
        # Never reinterpret a historical session after a new pairing chooses a
        # different Brain. Use a separate connection instead of repinning it.
        raise HTTPException(409,'telegram_binding_brain_immutable')
    fingerprint=service.digest({'peer_id':peer.id,'allow_chat':allow_chat,'allow_reports':allow_reports,
        'version':version,'generation':profile.generation,'confirm_destination':confirm_destination})
    if binding:
        saved=await db.scalar(select(ChannelAudit).where(ChannelAudit.binding_id==binding.id,ChannelAudit.request_key==key))
        if saved:
            if saved.content_hash!=fingerprint:raise HTTPException(409,'telegram_grant_request_conflict')
            return binding
    if (binding.version if binding else 0)!=version:raise HTTPException(409,'telegram_grant_version_conflict')
    enabled=allow_chat or allow_reports
    if enabled and (not confirm_destination or profile.status!='enabled'):raise HTTPException(409,'telegram_destination_confirmation_required')
    if linked and linked.brain_id:
        from pao.modules.brains.access import require_brain
        await require_brain(db,Principal(peer.user_id,0),linked.brain_id,True)
    if not binding:
        binding=ChannelBinding(connection_id=pin.connection_id,workspace_id=pin.workspace_id,actor_id=peer.user_id,
            peer_id=peer.id,channel='telegram',kind='personal',identity_hash=service.identity('telegram',peer.telegram_user_id+':'+peer.chat_id,pin.connection_id),
            brain_id=linked.brain_id if linked else None,version=1)
        db.add(binding)
    else:binding.version+=1
    peer.enabled=enabled;binding.enabled=enabled;binding.mode='auto' if allow_chat else 'quiet'
    binding.outbound_confirmed=enabled and confirm_destination;binding.reports_enabled=allow_reports
    await db.flush()
    await db.refresh(binding)
    db.add(ChannelAudit(workspace_id=pin.workspace_id,connection_id=pin.connection_id,binding_id=binding.id,
        actor_id=admin_id,request_key=key,content_hash=fingerprint,
        data={'action':'team_grant','allow_chat':allow_chat,'allow_reports':allow_reports,'version':binding.version}))
    return binding
