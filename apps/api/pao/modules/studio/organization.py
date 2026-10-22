"""Non-executing skill labels. Agent binding remains in immutable native versions."""
from typing import Literal
from uuid import UUID
from fastapi import APIRouter,Depends,Response
from pydantic import Field
from sqlalchemy import select
from ...auth import Principal,principal
from ...db import database
from ...models import StudioDefinition,StudioVersion,StudioEvent
from .contracts import Closed
from .service import event,reject

Category=Literal['design','marketing','editor','ads','content','analysis','operations','other']
router=APIRouter(prefix='/v1/studio')
class Categorize(Closed):
    revision:int=Field(ge=1)
    category:Category
async def labels(db,definitions):
    found={};ids=[d.id for d in definitions if d.kind=='skills']
    rows=await db.scalars(select(StudioEvent).where(StudioEvent.definition_id.in_(ids),StudioEvent.action=='catalog_categorized').order_by(StudioEvent.created_at.desc(),StudioEvent.id.desc())) if ids else []
    for row in rows:
        if row.definition_id not in found:found[row.definition_id]=row.data.get('category','other')
    return found
@router.get('/skill-catalog')
async def catalog(workspace_id:UUID,response:Response,who:Principal=Depends(principal),db=Depends(database)):
    from .api import scope
    await scope(db,workspace_id,who)
    definitions=list(await db.scalars(select(StudioDefinition).where(StudioDefinition.workspace_id==str(workspace_id)).order_by(StudioDefinition.created_at,StudioDefinition.id).limit(201)))
    groups=await labels(db,definitions);items=[]
    for row in definitions[:200]:
        latest=await db.scalar(select(StudioVersion).where(StudioVersion.definition_id==row.id).order_by(StudioVersion.ordinal.desc()).limit(1))
        published=await db.get(StudioVersion,row.published_version_id) if row.published_version_id else None
        items.append({'id':row.id,'kind':row.kind,'name':row.name,'slug':row.slug,'owner_id':row.owner_id,'seed':row.seed,'archived':row.archived_at is not None,'revision':row.revision,
            'category':groups.get(row.id,'other'),'published_version_id':row.published_version_id,'latest_version_id':latest.id if latest else None,
            'agent_version_id':latest.payload.get('agent_version_id') if latest and row.kind=='skills' and not row.seed else None,
            'published_agent_version_id':published.payload.get('agent_version_id') if published and row.kind=='skills' and not row.seed else None})
    response.headers['Cache-Control']='no-store'
    return {'items':items,'has_more':len(definitions)>200,'assignment_is_execution_permission':False,'skill_mode':'llm_text'}
@router.post('/definitions/{definition_id}/category')
async def categorize(definition_id:UUID,body:Categorize,who:Principal=Depends(principal),db=Depends(database)):
    from .api import owned
    row,_=await owned(db,definition_id,who,True,body.revision)
    if row.kind!='skills' or row.seed or row.archived_at:reject('studio_category_read_only',409)
    row.revision+=1;event(db,row,who.id,'catalog_categorized',category=body.category)
    await db.commit();return {'id':row.id,'revision':row.revision,'category':body.category,'execution_changed':False}
