"""Shared Telegram permission and durable outbox helpers; no HTTP adapter."""
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import select

from ...models import TelegramDelivery, User, Member,ChannelBinding,TelegramConnection
from ...config import settings


async def legacy_blocked(db):
    # Revocation does not resurrect the global host token or old unknown queue.
    return bool(await db.scalar(select(TelegramConnection.id).where(TelegramConnection.kind=='legacy').limit(1)))


async def permitted(db, peer):
    if not peer or not peer.enabled or getattr(peer,'connection_id',None) is not None:
        return False
    if await legacy_blocked(db):return False
    binding=await db.scalar(select(ChannelBinding).where(ChannelBinding.peer_id==peer.id))
    if binding and (binding.kind=='customer' or not settings().channels_enabled or not binding.enabled or binding.mode!='auto'):
        return False
    user = await db.get(User, peer.user_id)
    member = await db.get(Member, (peer.workspace_id, peer.user_id))
    return bool(user and user.active and member and member.role != 'viewer')


async def queue(db, peer, key, text, markup=None):
    if getattr(peer,'connection_id',None) is None and await legacy_blocked(db):
        from fastapi import HTTPException
        raise HTTPException(409,'telegram_legacy_mapped')
    # Plain text avoids markup injection and Telegram's 4096 character limit.
    parts=[]; part=''; units=0
    for character in text:
        size=len(character.encode('utf-16-le'))//2
        if units+size > 3500:
            parts.append(part);part='';units=0
        part+=character;units+=size
    if part: parts.append(part)
    if not parts: parts=['Không có nội dung.']
    for index, part in enumerate(parts):
        payload = {'chat_id':peer.chat_id, 'text':part, 'link_preview_options':{'is_disabled':True}}
        if markup and index == len(parts)-1:
            payload['reply_markup'] = markup
        connection=getattr(peer,'connection_id',None)
        statement=insert(TelegramDelivery).values(peer_id=peer.id,connection_id=connection,
            dedup_key=f'{key}:{index}',payload=payload,status='queued')
        if connection is None:
            statement=statement.on_conflict_do_nothing(index_elements=['dedup_key'],index_where=TelegramDelivery.connection_id.is_(None))
        else:
            statement=statement.on_conflict_do_nothing(index_elements=['connection_id','dedup_key'])
        await db.execute(statement)
