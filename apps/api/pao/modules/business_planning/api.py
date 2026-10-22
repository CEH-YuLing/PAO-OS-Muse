"""S5 planning and native text jobs; all publishing/Ads actions are simulation only."""
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ...auth import Principal, principal
from ...config import settings
from ...db import database
from ...models import Brand, Member, User, Workspace
from .models import BusinessProfile, BusinessProfileVersion, MonthlyPlan, MonthlyPlanVersion
from .contracts import ProfileSave, PlanSave, digest, missing
from .access import reject,authorize,brand_scope,profile_scope,profile_version,selected_plan

router=APIRouter(prefix='/v1/workspaces/{workspace_id}/business-planning',tags=['business-planning'])


def execution_available():
    cfg=settings()
    return bool(cfg.business_planning_enabled and cfg.studio_enabled and cfg.engine_contract_enabled and cfg.chat_features_enabled)


def view(row,version):
    return {'id':row.id,'workspace_id':row.workspace_id,'revision':version.revision,
        'current_revision':row.revision,'version_id':version.id,'content':version.content,
        'content_hash':version.content_hash,'created_at':version.created_at.isoformat(),'actor_id':version.actor_id}


def profile_view(row,version):
    return {**view(row,version),'brand_id':row.brand_id,'missing_fields':missing(version.content)}


async def plan_view(db,row,version):
    from .review import summary
    profile=await profile_scope(db,row.workspace_id,row.profile_id)
    source=await db.get(BusinessProfileVersion,version.profile_version_id)
    if not source or source.profile_id!=profile.id or source.workspace_id!=row.workspace_id or digest(source.content)!=source.content_hash or digest(version.content)!=version.content_hash:
        reject('business_planning_integrity_failed')
    review=await summary(db,row,version)
    return {**view(row,version),'profile_id':profile.id,'profile_revision':source.revision,
        'profile_hash':source.content_hash,'profile_stale':profile.revision!=source.revision,
        'status':'draft','execution_enabled':False,'approval_status':review['status'],'plan_review':review,
        'currency':source.content['currency'],'timezone':source.content['timezone'],
        'missing_fields':missing(source.content)}


@router.get('/status')
async def status(workspace_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    member=await authorize(db,str(workspace_id),who,enabled=False)
    return {'available':settings().business_planning_enabled,'can_manage':member.role in ('owner','admin'),
        'execution_enabled':execution_available(),'scope':'owner_admin_planning_and_text_jobs','milestone':'S5_in_progress',
        'external_actions_enabled':False,'model_health_verified':False}


@router.get('/profile')
async def get_profile(workspace_id:UUID,brand_id:UUID|None=None,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    wid=str(workspace_id);await authorize(db,wid,who);brand=str(brand_id) if brand_id else None
    await brand_scope(db,wid,brand)
    row=await db.scalar(select(BusinessProfile).where(BusinessProfile.workspace_id==wid,BusinessProfile.scope_key==(brand or 'enterprise')))
    return {'item':profile_view(row,await profile_version(db,row)) if row else None}


@router.put('/profile')
async def save_profile(workspace_id:UUID,body:ProfileSave,brand_id:UUID|None=None,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    wid=str(workspace_id);await authorize(db,wid,who);brand=str(brand_id) if brand_id else None
    await brand_scope(db,wid,brand)
    content=body.content.model_dump(mode='json');hashed=digest(content)
    row=await db.scalar(select(BusinessProfile).where(BusinessProfile.workspace_id==wid,BusinessProfile.scope_key==(brand or 'enterprise')))
    if row:
        prior=await db.scalar(select(BusinessProfileVersion).where(BusinessProfileVersion.profile_id==row.id,BusinessProfileVersion.request_key==str(body.request_key)))
        if prior:
            if prior.content_hash!=hashed or prior.actor_id!=who.id or prior.revision!=body.expected_revision+1 or prior.revision!=row.revision:reject('business_planning_request_conflict')
            return profile_view(row,prior)
    if (row.revision if row else 0)!=body.expected_revision:reject('business_planning_revision_conflict')
    if not row:
        row=BusinessProfile(id=str(uuid4()),workspace_id=wid,brand_id=brand,scope_key=brand or 'enterprise',revision=1);db.add(row)
    else:row.revision+=1
    await db.flush()
    version=BusinessProfileVersion(workspace_id=wid,profile_id=row.id,revision=row.revision,
        request_key=str(body.request_key),actor_id=who.id,content=content,content_hash=hashed)
    db.add(version);await db.flush();result=profile_view(row,version);await db.commit();return result


@router.get('/profiles/{profile_id}/versions/{revision}')
async def read_profile_version(workspace_id:UUID,profile_id:UUID,revision:int=Path(ge=1),who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    wid=str(workspace_id);await authorize(db,wid,who);row=await profile_scope(db,wid,str(profile_id))
    return profile_view(row,await profile_version(db,row,revision))


@router.get('/plans')
async def list_plans(workspace_id:UUID,profile_id:UUID,limit:int=Query(default=20,ge=1,le=50),who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    wid=str(workspace_id);await authorize(db,wid,who);profile=await profile_scope(db,wid,str(profile_id))
    rows=list(await db.scalars(select(MonthlyPlan).where(MonthlyPlan.workspace_id==wid,MonthlyPlan.profile_id==profile.id).order_by(MonthlyPlan.created_at.desc(),MonthlyPlan.id).limit(limit+1)))
    items=[]
    for row in rows[:limit]:
        version=await db.scalar(select(MonthlyPlanVersion).where(MonthlyPlanVersion.plan_id==row.id,MonthlyPlanVersion.revision==row.revision))
        items.append(await plan_view(db,row,version))
    return {'items':items,'has_more':len(rows)>limit}


@router.get('/plans/{plan_id}')
async def read_plan(workspace_id:UUID,plan_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    wid=str(workspace_id);await authorize(db,wid,who);row,version=await selected_plan(db,wid,str(plan_id))
    return await plan_view(db,row,version)


@router.get('/plans/{plan_id}/versions/{revision}')
async def read_plan_version(workspace_id:UUID,plan_id:UUID,revision:int=Path(ge=1),who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    wid=str(workspace_id);await authorize(db,wid,who);row,version=await selected_plan(db,wid,str(plan_id),revision)
    return await plan_view(db,row,version)


@router.put('/plans/{plan_id}')
async def save_plan(workspace_id:UUID,plan_id:UUID,body:PlanSave,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    wid=str(workspace_id);await authorize(db,wid,who);profile=await profile_scope(db,wid,str(body.profile_id))
    if profile.revision!=body.profile_revision:reject('business_planning_profile_changed')
    source=await profile_version(db,profile);content=body.content.model_dump(mode='json')
    hashed=digest({'profile_version_id':source.id,'content':content})
    # Stored content hash covers content bytes; request identity additionally pins profile.
    row=await db.scalar(select(MonthlyPlan).where(MonthlyPlan.id==str(plan_id)))
    if row and (row.workspace_id!=wid or row.profile_id!=profile.id):reject('business_planning_not_found',404)
    if row:
        prior=await db.scalar(select(MonthlyPlanVersion).where(MonthlyPlanVersion.plan_id==row.id,MonthlyPlanVersion.request_key==str(body.request_key)))
        if prior:
            if digest({'profile_version_id':prior.profile_version_id,'content':prior.content})!=hashed or prior.actor_id!=who.id or prior.revision!=body.expected_revision+1 or prior.revision!=row.revision:reject('business_planning_request_conflict')
            return await plan_view(db,row,prior)
    if (row.revision if row else 0)!=body.expected_revision:reject('business_planning_revision_conflict')
    if not row:row=MonthlyPlan(id=str(plan_id),workspace_id=wid,profile_id=profile.id,revision=1);db.add(row)
    else:row.revision+=1
    await db.flush()
    version=MonthlyPlanVersion(workspace_id=wid,plan_id=row.id,profile_version_id=source.id,revision=row.revision,
        request_key=str(body.request_key),actor_id=who.id,content=content,content_hash=digest(content))
    db.add(version);await db.flush();result=await plan_view(db,row,version);await db.commit();return result


from .review import ReviewInput,MaterializeInput


@router.get('/plans/{plan_id}/review')
async def read_review(workspace_id:UUID,plan_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    from .review import summary
    wid=str(workspace_id);await authorize(db,wid,who);row,version=await selected_plan(db,wid,str(plan_id))
    return await summary(db,row,version)


@router.post('/plans/{plan_id}/review')
async def decide_plan(workspace_id:UUID,plan_id:UUID,body:ReviewInput,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    from .review import decide
    wid=str(workspace_id);await authorize(db,wid,who);row,version=await selected_plan(db,wid,str(plan_id))
    return await decide(db,row,version,who,body)


@router.post('/plans/{plan_id}/materialize')
async def materialize_plan(workspace_id:UUID,plan_id:UUID,body:MaterializeInput,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    from .review import materialize
    wid=str(workspace_id);await authorize(db,wid,who);row,version=await selected_plan(db,wid,str(plan_id))
    return await materialize(db,row,version,who,body)


from .routing_contracts import RoutingSave, RoutingPreview


@router.get('/routing')
async def read_routing(workspace_id: UUID, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    from .routing import latest, public
    wid = str(workspace_id); await authorize(db, wid, who)
    row = await latest(db, wid)
    return {'item': public(row) if row else None}


@router.put('/routing')
async def save_routing(workspace_id: UUID, body: RoutingSave, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    from .routing import save
    wid = str(workspace_id); await authorize(db, wid, who)
    return await save(db, wid, who, body)


@router.get('/routing/versions/{revision}')
async def read_routing_version(workspace_id: UUID, revision: int = Path(ge=1), who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    from .routing import latest, public
    wid = str(workspace_id); await authorize(db, wid, who)
    row = await latest(db, wid, revision)
    if not row: reject('business_routing_not_found', 404)
    return public(row)


@router.post('/plans/{plan_id}/routing-preview')
async def preview_routing(workspace_id: UUID, plan_id: UUID, body: RoutingPreview, who: Principal = Depends(principal), db: AsyncSession = Depends(database)):
    from .routing import preview
    wid = str(workspace_id); await authorize(db, wid, who)
    row, version = await selected_plan(db, wid, str(plan_id))
    return await preview(db, wid, who, row, version, body)


from .jobs import JobStart, Decision
from .money import BudgetCreate, ActionCreate, ActionDecision, Simulation, Reconciliation, CancelAction
from .reports import ReportInput, ScheduleInput
from .contracts import Closed
from pydantic import Field


class Control(Closed):
    request_key: UUID
    stopped: bool = Field(strict=True)
    confirm: bool = Field(strict=True)


class CancelJob(Closed):
    request_key: UUID


@router.post('/plans/{plan_id}/jobs',status_code=202)
async def start_business_job(workspace_id:UUID,plan_id:UUID,body:JobStart,request:Request,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    from .jobs import start
    return await start(db,str(workspace_id),who,str(plan_id),body,request)


@router.get('/jobs/{job_id}')
async def read_business_job(workspace_id:UUID,job_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    from . import jobs
    wid=str(workspace_id);await authorize(db,wid,who)
    return await jobs.view(db,await jobs.job_scope(db,wid,str(job_id)),who)


@router.post('/jobs/{job_id}/review')
async def review_business_content(workspace_id:UUID,job_id:UUID,body:Decision,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    from . import jobs
    wid=str(workspace_id);await authorize(db,wid,who);job=await jobs.job_scope(db,wid,str(job_id));await jobs.visible(db,job,who)
    return await jobs.decide_content(db,job,who,body)


@router.post('/jobs/{job_id}/cancel')
async def cancel_business_job(workspace_id:UUID,job_id:UUID,body:CancelJob,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    from . import jobs
    from ...models import Run
    wid=str(workspace_id);await authorize(db,wid,who);job=await jobs.job_scope(db,wid,str(job_id));await jobs.visible(db,job,who)
    run=await db.scalar(select(Run).where(Run.id==job.run_id).with_for_update())
    await jobs.event(db,wid,who.id,'job',job.id,'cancel',body.request_key,{'run_id':run.id})
    if run.status in ('queued','running'):run.cancel_requested=True
    await db.commit();return await jobs.view(db,job,who)


@router.post('/control')
async def business_control(workspace_id:UUID,body:Control,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    from . import jobs,review
    wid=str(workspace_id);await authorize(db,wid,who);await review.owner(db,wid,who.id)
    if not body.confirm:reject('business_control_confirmation_required',422)
    row=await jobs.event(db,wid,who.id,'control',wid,'control',body.request_key,{'stopped':body.stopped})
    await db.commit();return {'id':row.id,'stopped':await jobs.stopped(db,wid),'external_actions_enabled':False}


@router.post('/plans/{plan_id}/budgets')
async def create_business_budget(workspace_id:UUID,plan_id:UUID,body:BudgetCreate,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    from .money import create_budget
    wid=str(workspace_id);await authorize(db,wid,who)
    return await create_budget(db,wid,str(plan_id),who,body)


@router.post('/actions')
async def propose_business_action(workspace_id:UUID,body:ActionCreate,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    from . import jobs,money
    wid=str(workspace_id);await authorize(db,wid,who);await jobs.visible(db,await jobs.job_scope(db,wid,str(body.job_id)),who)
    return await money.propose(db,wid,who,body)


@router.post('/actions/{action_id}/review')
async def review_business_action(workspace_id:UUID,action_id:UUID,body:ActionDecision,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    from . import jobs,money
    wid=str(workspace_id);await authorize(db,wid,who);row=await money.action_scope(db,wid,str(action_id));await jobs.visible(db,await jobs.job_scope(db,wid,row.job_id),who)
    return await money.decide(db,row,who,body)


@router.post('/actions/{action_id}/simulate')
async def simulate_business_action(workspace_id:UUID,action_id:UUID,body:Simulation,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    from . import jobs,money
    wid=str(workspace_id);await authorize(db,wid,who);row=await money.action_scope(db,wid,str(action_id));await jobs.visible(db,await jobs.job_scope(db,wid,row.job_id),who)
    return await money.simulate(db,row,who,body)


@router.post('/actions/{action_id}/reconcile')
async def reconcile_business_action(workspace_id:UUID,action_id:UUID,body:Reconciliation,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    from . import jobs,money
    wid=str(workspace_id);await authorize(db,wid,who);row=await money.action_scope(db,wid,str(action_id));await jobs.visible(db,await jobs.job_scope(db,wid,row.job_id),who)
    return await money.simulate(db,row,who,body,reconcile=True)


@router.post('/actions/{action_id}/cancel')
async def abandon_business_action(workspace_id:UUID,action_id:UUID,body:CancelAction,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    from . import jobs,money
    wid=str(workspace_id);await authorize(db,wid,who);row=await money.action_scope(db,wid,str(action_id));await jobs.visible(db,await jobs.job_scope(db,wid,row.job_id),who)
    return await money.abandon(db,row,who,body)


@router.post('/plans/{plan_id}/reports')
async def create_business_report(workspace_id:UUID,plan_id:UUID,body:ReportInput,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    from .reports import create
    wid=str(workspace_id);await authorize(db,wid,who)
    return await create(db,wid,str(plan_id),who,body)


@router.post('/plans/{plan_id}/report-schedule')
async def configure_business_reports(workspace_id:UUID,plan_id:UUID,body:ScheduleInput,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    from .reports import schedule
    wid=str(workspace_id);await authorize(db,wid,who)
    return await schedule(db,wid,str(plan_id),who,body)


@router.get('/plans/{plan_id}/operations')
async def business_operations(workspace_id:UUID,plan_id:UUID,who:Principal=Depends(principal),db:AsyncSession=Depends(database)):
    from . import jobs,money
    from ...models import BusinessJob,BusinessPlanTask,BusinessPlanAdmission,BusinessBudget,BusinessAction
    wid=str(workspace_id);await authorize(db,wid,who);plan,version=await selected_plan(db,wid,str(plan_id))
    admission=await db.scalar(select(BusinessPlanAdmission).where(BusinessPlanAdmission.plan_version_id==version.id))
    bindings=list(await db.scalars(select(BusinessPlanTask).where(BusinessPlanTask.admission_id==admission.id))) if admission else []
    receipts=list(await db.scalars(select(BusinessJob).where(BusinessJob.plan_task_id.in_([b.id for b in bindings])))) if bindings else []
    visible=[];hidden=[]
    for receipt in receipts:
        try:await jobs.visible(db,receipt,who)
        except HTTPException:hidden.append(receipt.id);continue
        visible.append(receipt)
    budgets=list(await db.scalars(select(BusinessBudget).where(BusinessBudget.workspace_id==wid,BusinessBudget.plan_version_id==version.id)))
    actions=list(await db.scalars(select(BusinessAction).where(BusinessAction.workspace_id==wid,BusinessAction.job_id.in_([j.id for j in visible])))) if visible else []
    reports=await jobs.events(db,wid,plan.id,'report');schedules=await jobs.events(db,wid,plan.id,'schedule')
    return {'stopped':await jobs.stopped(db,wid),'jobs':[await jobs.view(db,j,who) for j in visible],
        'restricted_jobs':len(hidden),'budgets':[await money.balance(db,b) for b in budgets],
        'actions':[await money.action_view(db,a) for a in actions],
        'reports':[{'id':r.id,'report':r.data} for r in reports[-20:] if r.actor_id==who.id],'schedule':schedules[-1].data if schedules else None,
        'external_actions_enabled':False,'milestone':'S5_in_progress'}
