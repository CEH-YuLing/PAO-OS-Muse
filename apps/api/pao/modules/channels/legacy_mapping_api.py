"""Mount onto existing Telegram router; no second transport or credential API."""
from typing import Literal
from uuid import UUID
from fastapi import Depends,Response
from pydantic import Field
from pao.auth import principal
from pao.db import database
from pao.modules.studio.contracts import Closed
from . import legacy_mapping as service

class TelegramLegacyPeerPreview(Closed):
    source_peer_id:str
    actor_id:str
    telegram_user_id:str
    chat_id:str
    bound:bool

class TelegramLegacyPreview(Closed):
    workspace_id:str
    eligible:bool
    reason:str
    expected_version:int
    preview_hash:str|None
    peer_count:int
    binding_count:int
    held_delivery_count:int
    peers:list[TelegramLegacyPeerPreview]
    authority:Literal['storage_only']
    transport_active:Literal[False]
    provider_calls:Literal[False]
    history_rewritten:Literal[False]

class TelegramLegacyMappingOut(Closed):
    mapping_id:str
    connection_id:str
    workspace_id:str
    owner_id:str
    version:int
    status:Literal['staged','revoked']
    peer_count:int
    binding_count:int
    held_delivery_count:int
    authority:Literal['storage_only']
    transport_active:Literal[False]
    provider_calls:Literal[False]
    history_rewritten:Literal[False]

class TelegramLegacyApply(Closed):
    request_key:UUID=Field(strict=False)
    expected_version:int=Field(ge=0,le=0)
    preview_hash:str=Field(pattern=r'^[0-9a-f]{64}$')
    data_only_ack:Literal[True]
    no_history_replay_ack:Literal[True]

class TelegramLegacyRevoke(Closed):
    request_key:UUID=Field(strict=False)
    mapping_id:UUID=Field(strict=False)
    version:int=Field(ge=1)
    no_legacy_fallback_ack:Literal[True]

def mount(router):
    @router.get('/legacy/{workspace_id}/preview',response_model=TelegramLegacyPreview)
    async def preview(workspace_id:UUID,response:Response,who=Depends(principal),db=Depends(database)):
        response.headers['Cache-Control']='no-store'
        return (await service.snapshot(db,str(workspace_id),who))[0]

    @router.get('/legacy/{workspace_id}/mapping',response_model=TelegramLegacyMappingOut|None)
    async def mapping(workspace_id:UUID,response:Response,who=Depends(principal),db=Depends(database)):
        response.headers['Cache-Control']='no-store';await service.owner(db,str(workspace_id),who)
        return await service.current(db,str(workspace_id))

    @router.post('/legacy/{workspace_id}/apply',response_model=TelegramLegacyMappingOut,status_code=201)
    async def apply(workspace_id:UUID,body:TelegramLegacyApply,response:Response,who=Depends(principal),db=Depends(database)):
        response.headers['Cache-Control']='no-store'
        return await service.apply(db,str(workspace_id),who,body)

    @router.post('/legacy/{workspace_id}/revoke',response_model=TelegramLegacyMappingOut)
    async def revoke(workspace_id:UUID,body:TelegramLegacyRevoke,response:Response,who=Depends(principal),db=Depends(database)):
        response.headers['Cache-Control']='no-store'
        return await service.revoke(db,str(workspace_id),who,body)
