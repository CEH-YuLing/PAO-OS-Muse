"""Owner onboarding and names; no account signup, data copying or execution authority."""
from uuid import UUID, uuid5
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, func, text, cast, Integer
from ...access import membership
from ...auth import Principal, principal, rate_limit
from ...db import database
from ...models import Workspace, Member, Brand, LifecycleAudit
from .lifecycle import fingerprint

router=APIRouter(prefix='/v1/workspaces/{workspace_id}/organization',tags=['organization'])
class NameInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    name:str=Field(min_length=1,max_length=120)
    request_key:UUID
    @field_validator('name')
    @classmethod
    def clean_name(cls,value):
        value=value.strip()
        if not value or any(ord(c)<32 or ord(c)==127 for c in value):raise ValueError('Tên không hợp lệ')
        try:value.encode('utf-8')
        except UnicodeError:raise ValueError('Tên không hợp lệ') from None
        return value
class Rename(NameInput):
    expected_revision:int=Field(ge=0,strict=True)
def deny(message,status=409):raise HTTPException(status,message)
async def scope(db,wid,who,write=False,owner=False):
    # Organization writes serialize per actor before the workspace lock. No User
    # row lock: lifecycle operations take Workspace first, so that would invert
    # their lock order. This transaction-scoped advisory namespace is local here.
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {'key':'organization:'+who.id})
    row=await db.scalar(select(Workspace).where(Workspace.id==str(wid)).with_for_update())
    member=await membership(db,str(wid),who)
    if not row:deny('Không tìm thấy doanh nghiệp',404)
    if (owner and member.role!='owner') or (write and member.role not in ('owner','admin')):deny('Bạn không có quyền quản lý mục này',403)
    return row,member
def receipt_id(who,key):return str(uuid5(UUID(who.id),'organization:'+str(key)))
async def previous(db,who,body,action,wid,subject=None):
    row=await db.get(LifecycleAudit,receipt_id(who,body.request_key))
    hashed=fingerprint({'action':action,'workspace':str(wid),'subject':subject,'body':body.model_dump(mode='json')})
    if row and (row.actor_id!=who.id or row.action!=action or row.details.get('fingerprint')!=hashed):deny('Mã yêu cầu đã dùng cho nội dung khác')
    return row,hashed
def audit(db,who,body,action,wid,subject,hashed,revision):
    db.add(LifecycleAudit(id=receipt_id(who,body.request_key),actor_id=who.id,workspace_id=wid,subject_id=subject,action=action,details={'fingerprint':hashed,'revision':revision}))
async def brand_version(db,row):
    revision=await db.scalar(select(func.max(cast(LifecycleAudit.details['revision'].as_string(),Integer))).where(LifecycleAudit.workspace_id==row.workspace_id,LifecycleAudit.subject_id==row.id,
        LifecycleAudit.action.in_(['organization.brand_created','organization.brand_renamed'])))
    return revision or 0
async def brand_out(db,row):return {'id':row.id,'workspace_id':row.workspace_id,'name':row.name,'revision':await brand_version(db,row)}
def company_out(row):return {'id':row.id,'name':row.name,'revision':row.lifecycle_version}

@router.get('')
async def status(workspace_id:UUID,response:Response,who:Principal=Depends(principal),db=Depends(database)):
    member=await membership(db,str(workspace_id),who);workspace=await db.get(Workspace,str(workspace_id))
    rows=list(await db.scalars(select(Brand).where(Brand.workspace_id==str(workspace_id)).order_by(Brand.name,Brand.id).limit(101)))
    response.headers['Cache-Control']='no-store'
    return {'enterprise':company_out(workspace),'brands':[await brand_out(db,row) for row in rows[:100]],'has_more':len(rows)>100,
        'can_create_enterprise':member.role=='owner','can_rename_enterprise':member.role=='owner','can_manage_brands':member.role in ('owner','admin'),
        'public_signup':False,'deletion_supported':False,'copies_connections_or_permissions':False}

@router.post('/enterprises',status_code=201)
async def create_enterprise(workspace_id:UUID,body:NameInput,request:Request,who:Principal=Depends(principal),db=Depends(database)):
    await scope(db,workspace_id,who,owner=True)
    old,hashed=await previous(db,who,body,'organization.enterprise_created',workspace_id)
    if old:
        await membership(db,old.subject_id,who);return company_out(await db.get(Workspace,old.subject_id))
    if await db.scalar(select(func.count()).select_from(Member).where(Member.user_id==who.id,Member.role=='owner'))>=20:deny('Đã đạt giới hạn 20 doanh nghiệp sở hữu; liên hệ quản trị vận hành')
    await rate_limit(request.app.state.redis,'enterprise-create',who.id,10,3600)
    row=Workspace(name=body.name);db.add(row);await db.flush();db.add(Member(workspace_id=row.id,user_id=who.id,role='owner'))
    audit(db,who,body,'organization.enterprise_created',row.id,row.id,hashed,row.lifecycle_version)
    await db.commit();return company_out(row)

@router.post('/name')
async def rename_enterprise(workspace_id:UUID,body:Rename,who:Principal=Depends(principal),db=Depends(database)):
    row,_=await scope(db,workspace_id,who,owner=True)
    old,hashed=await previous(db,who,body,'organization.enterprise_renamed',workspace_id,row.id)
    if old:return company_out(row)
    if body.expected_revision!=row.lifecycle_version:deny('Thông tin đã đổi; đọc lại trước khi lưu')
    row.name=body.name;row.lifecycle_version+=1
    audit(db,who,body,'organization.enterprise_renamed',row.id,row.id,hashed,row.lifecycle_version)
    await db.commit();return company_out(row)

@router.post('/brands',status_code=201)
async def create_brand(workspace_id:UUID,body:NameInput,who:Principal=Depends(principal),db=Depends(database)):
    workspace,_=await scope(db,workspace_id,who,write=True)
    old,hashed=await previous(db,who,body,'organization.brand_created',workspace_id)
    if old:return await brand_out(db,await db.get(Brand,old.subject_id))
    if await db.scalar(select(Brand.id).where(Brand.workspace_id==workspace.id,func.lower(Brand.name)==body.name.lower())):deny('Tên nhãn hàng đã tồn tại trong doanh nghiệp')
    if await db.scalar(select(func.count()).select_from(Brand).where(Brand.workspace_id==workspace.id))>=100:deny('Danh mục đã đạt 100 nhãn hàng')
    row=Brand(workspace_id=workspace.id,name=body.name);db.add(row);await db.flush();workspace.lifecycle_version+=1
    audit(db,who,body,'organization.brand_created',workspace.id,row.id,hashed,1)
    await db.commit();return await brand_out(db,row)

@router.post('/brands/{brand_id}/name')
async def rename_brand(workspace_id:UUID,brand_id:UUID,body:Rename,who:Principal=Depends(principal),db=Depends(database)):
    workspace,_=await scope(db,workspace_id,who,write=True)
    row=await db.get(Brand,str(brand_id))
    if not row or row.workspace_id!=workspace.id:deny('Không tìm thấy nhãn hàng',404)
    old,hashed=await previous(db,who,body,'organization.brand_renamed',workspace_id,row.id)
    if old:return await brand_out(db,row)
    revision=await brand_version(db,row)
    if body.expected_revision!=revision:deny('Nhãn hàng đã đổi; đọc lại trước khi lưu')
    if await db.scalar(select(Brand.id).where(Brand.workspace_id==workspace.id,Brand.id!=row.id,func.lower(Brand.name)==body.name.lower())):deny('Tên nhãn hàng đã tồn tại trong doanh nghiệp')
    row.name=body.name;workspace.lifecycle_version+=1
    audit(db,who,body,'organization.brand_renamed',workspace.id,row.id,hashed,revision+1)
    await db.commit();return await brand_out(db,row)
