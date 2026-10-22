"""Owner plan approval and atomic draft materialization into the native Task model."""
from datetime import datetime,time,timedelta,timezone
from typing import Literal
from uuid import UUID,uuid5
from zoneinfo import ZoneInfo
from pydantic import Field
from fastapi import HTTPException
from sqlalchemy import select,text
from ...models import (BusinessPlanReview,BusinessPlanAdmission,BusinessPlanTask,
    Project,Goal,Task,TaskActivity,TaskDependency,Member,User,now)
from .contracts import Closed,digest,missing

def reject(code,status=409):raise HTTPException(status,code)


class ReviewInput(Closed):
    request_key: UUID
    revision: int=Field(ge=1,strict=True)
    content_hash: str=Field(pattern=r'^[a-f0-9]{64}$')
    decision: Literal['approve','reject']
    self_review: bool=Field(default=False,strict=True)
    acknowledge_missing: bool=Field(default=False,strict=True)
    expiry_hours: int=Field(default=168,ge=1,le=720,strict=True)


class MaterializeInput(Closed):
    request_key: UUID
    revision: int=Field(ge=1,strict=True)
    review_id: UUID
    content_hash: str=Field(pattern=r'^[a-f0-9]{64}$')
    confirm_drafts_only: bool=Field(strict=True)


async def owner(db,wid,actor):
    member=await db.get(Member,(wid,actor))
    if not member or member.role!='owner':reject('business_plan_owner_approval_required',403)


async def summary(db,row,version):
    from .access import profile_scope,profile_version
    if digest(version.content)!=version.content_hash:reject('business_planning_integrity_failed')
    review=await db.scalar(select(BusinessPlanReview).where(BusinessPlanReview.plan_version_id==version.id,BusinessPlanReview.workspace_id==row.workspace_id))
    if not review:return {'status':'not_requested','effective':False}
    member=await db.get(Member,(row.workspace_id,review.actor_id));user=await db.get(User,review.actor_id)
    profile=await profile_scope(db,row.workspace_id,row.profile_id)
    source=await profile_version(db,profile)
    valid=bool(review.decision=='approve' and review.expires_at>now() and member and member.role=='owner' and user and user.active
        and version.revision==row.revision and version.profile_version_id==source.id and version.content_hash==review.source_hash)
    admission=await db.scalar(select(BusinessPlanAdmission).where(BusinessPlanAdmission.plan_version_id==version.id))
    return {'id':review.id,'status':review.decision,'effective':valid,'expires_at':review.expires_at.isoformat(),
        'scope':'internal_draft_preparation_only','external_actions_allowed':False,
        'admission_id':admission.id if admission else None,'project_id':admission.project_id if admission else None,'goal_id':admission.goal_id if admission else None,
        'admission':await admission_view(db,admission) if admission else None}


async def decide(db,row,version,who,body):
    from .access import profile_scope,profile_version
    await owner(db,row.workspace_id,who.id)
    if row.revision!=body.revision or version.content_hash!=body.content_hash:reject('business_plan_review_source_changed')
    profile=await profile_scope(db,row.workspace_id,row.profile_id);source=await profile_version(db,profile)
    if version.profile_version_id!=source.id:reject('business_planning_profile_changed')
    fingerprint=digest({'plan_version_id':version.id,'body':body.model_dump(mode='json')})
    prior=await db.scalar(select(BusinessPlanReview).where(BusinessPlanReview.workspace_id==row.workspace_id,BusinessPlanReview.actor_id==who.id,BusinessPlanReview.request_key==str(body.request_key)))
    if prior:
        if prior.fingerprint!=fingerprint:reject('business_plan_review_request_conflict')
        return await summary(db,row,version)
    if version.actor_id==who.id and not body.self_review:reject('business_plan_self_review_confirmation_required',422)
    if missing(source.content) and body.decision=='approve' and not body.acknowledge_missing:reject('business_plan_missing_data_confirmation_required',422)
    if await db.scalar(select(BusinessPlanReview.id).where(BusinessPlanReview.plan_version_id==version.id)):reject('business_plan_version_already_reviewed')
    review=BusinessPlanReview(workspace_id=row.workspace_id,plan_version_id=version.id,actor_id=who.id,
        decision=body.decision,source_hash=version.content_hash,request_key=str(body.request_key),fingerprint=fingerprint,
        self_review=body.self_review,acknowledge_missing=body.acknowledge_missing,expires_at=now()+timedelta(hours=body.expiry_hours))
    db.add(review);await db.flush();result=await summary(db,row,version);await db.commit();return result


def deadline(day,zone):
    parsed=datetime.fromisoformat(day).date();local=datetime.combine(parsed,time(23,59,59),tzinfo=ZoneInfo(zone))
    if local.utcoffset()!=local.replace(fold=1).utcoffset() or local.astimezone(timezone.utc).astimezone(local.tzinfo).replace(tzinfo=None)!=local.replace(tzinfo=None):reject('business_plan_ambiguous_deadline',422)
    return local.astimezone(timezone.utc)


def task_snapshot(task):
    return {'workspace_id':task.workspace_id,'project_id':task.project_id,'goal_id':task.goal_id,'title':task.title,
        'description':task.description,'due_at':task.due_at.isoformat(),'success_criteria':task.success_criteria,
        'input_references':task.input_references,'dependencies':task.dependencies}


async def admission_view(db,row):
    tasks=list(await db.scalars(select(BusinessPlanTask).where(BusinessPlanTask.admission_id==row.id,BusinessPlanTask.workspace_id==row.workspace_id).order_by(BusinessPlanTask.item_key)))
    return {'id':row.id,'project_id':row.project_id,'goal_id':row.goal_id,'tasks':[{'key':task.item_key,'task_id':task.task_id,'hash':task.task_hash} for task in tasks],
        'execution_enabled':False,'external_actions_allowed':False,'status':'native_drafts_only'}


async def materialize(db,row,version,who,body):
    from .access import profile_scope,profile_version
    await owner(db,row.workspace_id,who.id)
    if not body.confirm_drafts_only:reject('business_plan_draft_confirmation_required',422)
    if body.revision!=row.revision or body.content_hash!=version.content_hash:reject('business_plan_review_source_changed')
    review=await summary(db,row,version)
    if not review['effective'] or review['id']!=str(body.review_id):reject('business_plan_effective_review_required',403)
    fingerprint=digest({'plan_version_id':version.id,'body':body.model_dump(mode='json')})
    existing=await db.scalar(select(BusinessPlanAdmission).where(BusinessPlanAdmission.plan_version_id==version.id))
    prior=await db.scalar(select(BusinessPlanAdmission).where(BusinessPlanAdmission.workspace_id==row.workspace_id,BusinessPlanAdmission.actor_id==who.id,BusinessPlanAdmission.request_key==str(body.request_key)))
    if existing or prior:
        if not existing or not prior or prior.id!=existing.id or existing.fingerprint!=fingerprint or existing.actor_id!=who.id:reject('business_plan_admission_request_conflict')
        return await admission_view(db,existing)
    profile=await profile_scope(db,row.workspace_id,row.profile_id);source=await profile_version(db,profile)
    namespace=UUID(version.id);ident=lambda key:str(uuid5(namespace,key))
    data=version.content;wid=row.workspace_id;project_id=ident('project');goal_id=ident('goal')
    ids={item['key']:ident('task:'+item['key']) for item in data['deliverables']}
    due={item['key']:deadline(item['due_date'],source.content['timezone']) for item in data['deliverables']}
    db.add(Project(id=project_id,workspace_id=wid,name=data['title'][:160],description=data['campaign_brief'],status='active',owner_id=who.id,created_by=who.id,due_at=max(due.values())))
    await db.flush()
    db.add(Goal(id=goal_id,workspace_id=wid,project_id=project_id,title=data['title'],description=data['campaign_brief'],success_criteria=['Hoàn thành các đầu việc bắt buộc và có bằng chứng được duyệt.'],status='draft',owner_id=who.id,created_by=who.id,due_at=max(due.values())))
    await db.flush()
    admission=BusinessPlanAdmission(id=ident('admission'),workspace_id=wid,plan_version_id=version.id,review_id=review['id'],project_id=project_id,goal_id=goal_id,actor_id=who.id,request_key=str(body.request_key),fingerprint=fingerprint)
    db.add(admission);await db.flush()
    from ...task_api import TaskCreate
    tasks=[]
    for item in data['deliverables']:
        validated=TaskCreate(workspace_id=wid,project_id=project_id,goal_id=goal_id,title=item['title'],description=item['brief'],status='draft',kind='agent',source='pao',due_at=due[item['key']],success_criteria=item['acceptance'],input_references=[{'kind':'s5_plan_version','id':version.id,'hash':version.content_hash,'profile_version_id':version.profile_version_id,'specialist':item['specialist'],'key':item['key']}])
        task=Task(id=ids[item['key']],workspace_id=wid,project_id=project_id,goal_id=goal_id,title=validated.title,description=validated.description,status='draft',kind='agent',priority='medium',assignee_type='unassigned',assignee_id=None,due_at=validated.due_at,source='pao',success_criteria=validated.success_criteria,input_references=validated.input_references,dependencies=[ids[key] for key in item['depends_on']],created_by=who.id)
        db.add(task);tasks.append((task,item))
    await db.flush()
    for task,item in tasks:
        for dependency in task.dependencies:db.add(TaskDependency(workspace_id=wid,task_id=task.id,depends_on_task_id=dependency,created_by=who.id))
        db.add(TaskActivity(task_id=task.id,workspace_id=wid,actor_id=who.id,event='task.created',data={'status':'draft','source':'pao','plan_version_id':version.id}))
        db.add(BusinessPlanTask(workspace_id=wid,admission_id=admission.id,task_id=task.id,item_key=item['key'],task_hash=digest(task_snapshot(task))))
    await db.flush();result=await admission_view(db,admission);await db.commit();return result


async def guard_native(db,*,task_id=None,goal_id=None):
    # Primary may still be the accepted pre-S5 schema while source is staged.
    # The gate never bypasses persisted pins when the S5 tables exist.
    if not await db.scalar(text("SELECT to_regclass('public.business_plan_tasks') IS NOT NULL")):return
    if task_id and await db.scalar(select(BusinessPlanTask.id).where(BusinessPlanTask.task_id==str(task_id))):reject('business_plan_task_owned_by_adapter')
    if goal_id and await db.scalar(select(BusinessPlanAdmission.id).where(BusinessPlanAdmission.goal_id==str(goal_id))):reject('business_plan_goal_owned_by_adapter')
