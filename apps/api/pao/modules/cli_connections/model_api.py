"""Own-profile model discovery/change. Never inference or an implicit repin."""
import asyncio
from uuid import UUID,uuid4
from fastapi import APIRouter,Depends,HTTPException,Request,Response
from pydantic import Field,StrictBool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ...auth import principal,Principal,rate_limit
from ...db import Session,database
from ...models import CliModelConnection,CliModelDispatch
from .api import Revision,managed,public
from .catalog import CatalogTransport
from . import runtime,service
router=APIRouter(prefix='/v1/workspaces/{workspace_id}/cli-connections',tags=['cli-connections'])

class ModelChange(Revision):
    model:str=Field(min_length=1,max_length=120,pattern=r'^[a-zA-Z0-9][a-zA-Z0-9._:/+-]*$')
    confirm_model_change:StrictBool

async def operation(db,wid,who,cid,body,request,response,change=False):
    response.headers['Cache-Control']='no-store'
    response.headers['Pragma']='no-cache'
    row=await managed(db,wid,who,cid,body.version)
    if row.status!='connected' or not row.auth_checked_at:raise HTTPException(409,'cli_connection_unavailable')
    if row.setup_operation_id or await db.scalar(select(CliModelDispatch.id).where(CliModelDispatch.connection_id==cid,CliModelDispatch.status.in_(('dispatched','unknown')))):
        raise HTTPException(409,'cli_profile_busy')
    if change and not body.confirm_model_change:raise HTTPException(422,'cli_model_change_confirmation_required')
    await rate_limit(request.app.state.redis,'cli-models',wid+':'+who.id,10,60)
    try:config=runtime.device_config();selected=service.pin(row);runtime.resolve(selected)
    except Exception:raise HTTPException(503,'cli_runtime_pin_invalid') from None
    op=str(uuid4());row.setup_operation_id=op;await db.commit()
    async def authorize():
        async with Session() as check:
            current=await managed(check,wid,who,cid,body.version)
            if current.status!='connected' or current.setup_operation_id!=op or service.pin(current)!=selected or runtime.device_config()!=config:
                raise HTTPException(409,'cli_connection_changed')
    transport=CatalogTransport(selected,op,authorize)
    try:
        try:
            async with asyncio.timeout(45):
                choices=await transport.read()
            await transport.close()
            if not transport.cleanup_verified:raise HTTPException(503,'cli_profile_cleanup_unverified')
        except Exception:
            raise HTTPException(503,'cli_model_catalog_unavailable') from None
        await authorize()
        row=await managed(db,wid,who,cid,body.version)
        if row.setup_operation_id!=op or service.pin(row)!=selected or runtime.device_config()!=config:
            raise HTTPException(409,'cli_connection_changed')
        if change:
            if body.model not in {item['model'] for item in choices}:raise HTTPException(422,'cli_model_not_in_catalog')
            if body.model!=row.model:row.model=body.model;row.version+=1
        row.setup_operation_id=None
        from .model_catalog import capture
        await capture(db,wid,who.id,service.pin(row),choices)
        result={'workspace_id':wid,'actor_id':who.id,'connection_id':cid,'version':row.version,
                'current_model':row.model,'models':choices,'inference_called':False,
                'consent_required':change,'scope':'local_personal_self_only'}
        await db.commit();return result
    finally:
        await db.rollback()
        # Best effort, bounded cleanup. Leave the durable fence on uncertainty.
        if not transport.cleanup_verified:
            try:await asyncio.wait_for(asyncio.shield(transport.close()),10)
            except Exception:pass
        if transport.cleanup_verified:
            async with Session.begin() as cleanup:
                owned=await cleanup.scalar(select(CliModelConnection).where(CliModelConnection.id==cid,CliModelConnection.workspace_id==wid,CliModelConnection.setup_operation_id==op).with_for_update())
                if owned:owned.setup_operation_id=None

@router.post('/{connection_id}/models')
async def read_models(workspace_id:UUID,connection_id:UUID,body:Revision,request:Request,response:Response,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    return await operation(db,str(workspace_id),who,str(connection_id),body,request,response)

@router.post('/{connection_id}/model')
async def change_model(workspace_id:UUID,connection_id:UUID,body:ModelChange,request:Request,response:Response,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    return await operation(db,str(workspace_id),who,str(connection_id),body,request,response,True)
