"""Business progress snapshots under the existing P6 scheduler owner, no delivery."""
from datetime import datetime, timedelta, timezone
from uuid import UUID
from pydantic import Field, model_validator
from sqlalchemy import select, text
from ...db import Session
from ...models import (BusinessJob, BusinessPlanTask, BusinessPlanAdmission, BusinessBudget, BusinessAction,
    BusinessPlanEvent as BusinessEvent, TaskAttempt, LlmAttempt, Run, now)
from ...auth import Principal
from ...config import settings
from .contracts import Closed, digest
from .access import reject, selected_plan, authorize
from . import jobs, money, review


class ReportInput(Closed):
    request_key: UUID
    window_from: datetime
    window_to: datetime

    @model_validator(mode='after')
    def window(self):
        if self.window_from.utcoffset() is None or self.window_to.utcoffset() is None:
            raise ValueError('Offset required')
        if not self.window_from < self.window_to <= now() or self.window_to-self.window_from > timedelta(days=31):
            raise ValueError('Invalid report window')
        return self


class ScheduleInput(Closed):
    request_key: UUID
    enabled: bool = Field(strict=True)
    cadence: str = Field(pattern='^(hourly|daily)$')
    confirm_internal_only: bool = Field(strict=True)


async def snapshot(db, wid, pid, start, end, actor_id):
    from .access import profile_scope, profile_version
    plan, version = await selected_plan(db,wid,pid)
    profile = await profile_scope(db,wid,plan.profile_id)
    from ...models import BusinessProfileVersion
    source=await db.get(BusinessProfileVersion,version.profile_version_id)
    if not source or source.workspace_id!=wid or source.profile_id!=profile.id or digest(source.content)!=source.content_hash:
        reject('business_report_source_integrity_failed')
    admission=await db.scalar(select(BusinessPlanAdmission).where(BusinessPlanAdmission.plan_version_id==version.id))
    bindings=list(await db.scalars(select(BusinessPlanTask).where(BusinessPlanTask.admission_id==admission.id))) if admission else []
    task_ids=[v.id for v in bindings]
    rows=list(await db.scalars(select(BusinessJob).where(BusinessJob.workspace_id==wid,BusinessJob.plan_task_id.in_(task_ids)))) if task_ids else []
    progress=[];actual_input=0;actual_output=0;unknown=0
    for job in rows:
        try:await jobs.visible(db,job,Principal(actor_id,0))
        except Exception:continue
        value=await jobs.view(db,job);progress.append({k:value[k] for k in ('id','item_key','status','model','provider','content_approved')})
        attempts=list(await db.scalars(select(LlmAttempt).where(LlmAttempt.run_id==job.run_id,
            LlmAttempt.created_at>=start,LlmAttempt.created_at<end)))
        for attempt in attempts:
            if attempt.input_tokens is None or attempt.output_tokens is None:unknown+=1
            else:actual_input+=attempt.input_tokens;actual_output+=attempt.output_tokens
    budgets=list(await db.scalars(select(BusinessBudget).where(BusinessBudget.workspace_id==wid,BusinessBudget.plan_version_id==version.id)))
    missing=['actual_ads_spend','measured_business_kpis','provider_remaining_quota']
    return {'version':'s5-report-v1','as_of':now().isoformat(),'workspace_id':wid,'plan_id':pid,'plan_version_id':version.id,
        'plan_hash':version.content_hash,'profile_version_id':source.id,'profile_hash':source.content_hash,
        'profile_stale':source.revision!=profile.revision,'window_from':start.isoformat(),'window_to':end.isoformat(),
        'timezone':source.content['timezone'],'currency':source.content['currency'],
        'metric_definitions':{'progress':'current_native_run_state_and_owner_content_review',
            'model_usage':'reported_native_llm_attempts_created_in_half_open_window',
            'money':'simulation_ledger_lifetime_per_pinned_plan_not_provider_spend'},
        'tasks':progress,'planned_tasks':len(bindings),'not_started':len(bindings)-len(rows),
        'model_usage':{'input_tokens':None if unknown else actual_input,'output_tokens':None if unknown else actual_output,
            'unknown_attempts':unknown,'provider_billed_cost':None},
        'simulated_budgets':[await money.balance(db,b) for b in budgets],
        'kpis':[{'name':k['name'],'target':k['target'],'unit':k['unit'],'measured':None,'source':None} for k in source.content['kpis']],
        'missing_data':missing,'source_pins':{'native_job_ids':[j['id'] for j in progress],'budget_ids':[b.id for b in budgets]},
        'proposal':'Bổ sung dữ liệu còn thiếu và duyệt bản nháp; không tự thay đổi quảng cáo.',
        'external_delivery':False,'provider_calls':False}


async def create(db,wid,pid,who,body):
    fingerprint=digest({'plan_id':pid,'body':body.model_dump(mode='json')})
    old=await db.scalar(select(BusinessEvent).where(BusinessEvent.workspace_id==wid,BusinessEvent.request_key==str(body.request_key)))
    if old:
        if old.actor_id!=who.id or old.subject_kind!='report' or old.subject_id!=pid or old.fingerprint!=fingerprint:
            reject('business_report_request_conflict')
        await jobs.events(db,wid,pid,'report')
        return {'id':old.id,'report':old.data}
    data=await snapshot(db,wid,pid,body.window_from,body.window_to,who.id)
    row=await jobs.event(db,wid,who.id,'report',pid,'report',body.request_key,data,fingerprint)
    await db.commit();return {'id':row.id,'report':row.data}


async def schedule(db,wid,pid,who,body):
    if not body.confirm_internal_only:reject('business_report_internal_confirmation_required',422)
    plan,version=await selected_plan(db,wid,pid)
    if body.enabled and not (await review.summary(db,plan,version))['effective']:reject('business_report_effective_plan_required',403)
    from ...skills import execution_binding
    data={'enabled':body.enabled,'cadence':body.cadence,'plan_version_id':version.id,'plan_hash':version.content_hash,'source_binding':execution_binding(),
        'owner':'runtime.dispatch_studio_schedules.v1','external_delivery':False}
    row=await jobs.event(db,wid,who.id,'schedule',pid,'schedule',body.request_key,data)
    await db.commit();return {'id':row.id,**row.data}


async def dispatch_owned(stamp=None):
    if not settings().business_planning_enabled:return
    stamp=stamp or now()
    async with Session() as db:
        if not await db.scalar(text("SELECT to_regclass('public.business_jobs') IS NOT NULL")):return
        ids=list(await db.scalars(select(BusinessJob.id).join(TaskAttempt,TaskAttempt.id==BusinessJob.attempt_id)
            .join(Run,Run.id==BusinessJob.run_id).where(TaskAttempt.status=='running',Run.status.in_(['completed','failed','cancelled']))
            .order_by(BusinessJob.created_at).limit(100)))
        schedules=list(await db.scalars(select(BusinessEvent).where(BusinessEvent.subject_kind=='schedule',BusinessEvent.action=='schedule')
            .distinct(BusinessEvent.subject_id).order_by(BusinessEvent.subject_id,BusinessEvent.created_at.desc(),BusinessEvent.id.desc()).limit(100)))
    for jid in ids:
        async with Session.begin() as db:
            job=await db.get(BusinessJob,jid)
            from ...models import Workspace
            await db.scalar(select(Workspace.id).where(Workspace.id==job.workspace_id).with_for_update(key_share=True))
            await jobs.collect(db,job)
    from ..schedules.policy import SchedulePreview,preview
    from zoneinfo import ZoneInfo
    for row in schedules:
        if not row.data['enabled']:continue
        try:
            async with Session() as db:
                who=Principal(row.actor_id,0);await authorize(db,row.workspace_id,who)
                current=(await jobs.events(db,row.workspace_id,row.subject_id,'schedule'))[-1]
                if current.id!=row.id or await jobs.stopped(db,row.workspace_id):continue
                from ...skills import execution_binding
                if row.data.get('source_binding')!=execution_binding():continue
                plan,version=await selected_plan(db,row.workspace_id,row.subject_id)
                if version.id!=row.data['plan_version_id'] or not (await review.summary(db,plan,version))['effective']:continue
                prior=await jobs.events(db,row.workspace_id,row.subject_id,'report')
                after=max(row.created_at,datetime.fromisoformat(prior[-1].data['window_to']) if prior else row.created_at,stamp-timedelta(days=7))
                if after>=stamp:continue
                from .access import profile_scope,profile_version
                source=await profile_version(db,await profile_scope(db,row.workspace_id,plan.profile_id));zone=source.content['timezone']
                evaluated=preview(SchedulePreview(kind='business_plan_report',mode='cron',timezone=zone,
                    cron='0 * * * *' if row.data['cadence']=='hourly' else '0 0 * * *',after=after.isoformat(),now=stamp.isoformat()))
                if not evaluated['occurrences']:continue
                end=datetime.fromisoformat(evaluated['occurrences'][-1]['utc'])
                start=end-timedelta(hours=1) if row.data['cadence']=='hourly' else (end.astimezone(ZoneInfo(zone))-timedelta(days=1)).astimezone(timezone.utc)
                data=await snapshot(db,row.workspace_id,row.subject_id,start,end,row.actor_id)
                await jobs.event(db,row.workspace_id,row.actor_id,'report',row.subject_id,'report',jobs.ident(row.id,'report:'+end.isoformat()),data)
                await db.commit()
        except Exception:
            # No provider calls or retries; invalid/revoked schedules stay denied.
            continue
