"""Native Run/Studio adapter. No new queue, model loop or credential resolver."""
import json
import time
from types import SimpleNamespace
from uuid import UUID, uuid4, uuid5
from pydantic import Field
from sqlalchemy import select, text
from ...models import (BusinessJob, BusinessPlanEvent as BusinessEvent, BusinessPlanTask, BusinessPlanAdmission,
    BusinessProfileVersion, BusinessRoutingVersion, Task, TaskAttempt, TaskActivity,
    Run, ChatSession, StudioVersion, StudioDefinition, Member, User, now)
from ...config import settings
from ...auth import Principal
from .contracts import Closed, digest
from .routing_contracts import RoutingPreview
from .access import reject, authorize, selected_plan
from . import review, routing


class JobStart(RoutingPreview):
    request_key: UUID
    confirm_model_call: bool = Field(strict=True)


class Decision(Closed):
    request_key: UUID
    decision: str = Field(pattern='^(approve|reject)$')
    artifact_hash: str = Field(pattern='^[a-f0-9]{64}$')
    confirm_review: bool = Field(strict=True)
    expiry_hours: int = Field(default=168, ge=1, le=720, strict=True)


def ident(subject, key): return str(uuid5(UUID(subject), key))


async def event(db, wid, actor, kind, subject, action, key, data, fingerprint=None):
    value = {'subject_kind': kind, 'subject_id': subject, 'action': action, 'data': data}
    hashed = digest(value); fingerprint = fingerprint or hashed
    old = await db.scalar(select(BusinessEvent).where(BusinessEvent.workspace_id == wid, BusinessEvent.request_key == str(key)))
    if old:
        if old.actor_id != actor or old.fingerprint != fingerprint or old.content_hash != hashed:
            reject('business_event_request_conflict')
        return old
    row = BusinessEvent(workspace_id=wid, actor_id=actor, subject_kind=kind, subject_id=subject,
        action=action, request_key=str(key), fingerprint=fingerprint, data=data, content_hash=hashed)
    db.add(row); await db.flush(); return row


async def events(db, wid, subject, action=None):
    query = select(BusinessEvent).where(BusinessEvent.workspace_id == wid, BusinessEvent.subject_id == subject)
    if action: query = query.where(BusinessEvent.action == action)
    rows = list(await db.scalars(query.order_by(BusinessEvent.created_at, BusinessEvent.id)))
    for row in rows:
        if digest({'subject_kind': row.subject_kind, 'subject_id': row.subject_id, 'action': row.action, 'data': row.data}) != row.content_hash:
            reject('business_event_integrity_failed')
    return rows


async def active_owner(db, wid, actor):
    member = await db.get(Member, (wid, actor), populate_existing=True)
    user = await db.get(User, actor, populate_existing=True)
    return bool(member and member.role == 'owner' and user and user.active)


async def stopped(db, wid):
    rows = await events(db, wid, wid, 'control')
    return rows[-1].data['stopped'] if rows else False


async def job_scope(db, wid, jid):
    row = await db.scalar(select(BusinessJob).where(BusinessJob.id == jid, BusinessJob.workspace_id == wid))
    if not row: reject('business_job_not_found', 404)
    if digest(row.selection) != row.selection_hash: reject('business_job_integrity_failed')
    return row


async def visible(db,job,who):
    if job.selection.get('brain_id'):
        from ..brains.access import require_brain
        await require_brain(db,who,job.selection['brain_id'])


async def artifact(db, job):
    run = await db.get(Run, job.run_id)
    if not run or run.workspace_id != job.workspace_id or run.status != 'completed': reject('business_draft_not_ready')
    try: value = json.loads(run.response)
    except (ValueError, TypeError): reject('business_draft_invalid')
    return value, digest({'run_id': run.id, 'response': value})


async def approved_content(db, job):
    value, hashed = await artifact(db, job)
    rows = await events(db, job.workspace_id, job.id, 'content_review')
    if not rows: return False
    row = rows[-1]
    from datetime import datetime
    return (row.data['decision'] == 'approve' and row.data['artifact_hash'] == hashed
        and datetime.fromisoformat(row.data['expires_at']) > now()
        and await active_owner(db, job.workspace_id, row.actor_id))


async def source_check(db, job, *, execution=False):
    if not settings().business_planning_enabled or await stopped(db, job.workspace_id): reject('business_execution_stopped', 403)
    member = await db.get(Member, (job.workspace_id, job.actor_id), populate_existing=True)
    user = await db.get(User, job.actor_id, populate_existing=True)
    if not member or member.role not in ('owner', 'admin') or not user or not user.active: reject('business_job_actor_revoked', 403)
    pin = job.selection
    from ...skills import execution_binding
    if pin.get('execution_binding')!=execution_binding():reject('business_job_source_binding_changed')
    control=await events(db,job.workspace_id,job.workspace_id,'control')
    if (control[-1].id if control else None)!=pin.get('control_epoch'):reject('business_job_stop_epoch_changed',403)
    row, version = await selected_plan(db, job.workspace_id, pin['plan_id'])
    state = await review.summary(db, row, version)
    if version.id != pin['plan_version_id'] or not state['effective'] or state['id'] != pin['review_id']:
        reject('business_job_approval_stale', 403)
    binding = await db.get(BusinessPlanTask, job.plan_task_id)
    task = await db.get(Task, binding.task_id)
    if (binding.workspace_id != job.workspace_id or digest(review.task_snapshot(task)) != binding.task_hash
            or binding.task_hash != pin['task_hash']): reject('business_job_task_changed')
    configured = await db.get(BusinessRoutingVersion, pin['routing_version_id'])
    if not configured or configured.workspace_id != job.workspace_id or configured.content_hash != pin['routing_hash'] or digest(configured.content) != pin['routing_hash']:
        reject('business_job_routing_changed')
    for key in ('skill', 'agent'):
        version_id = pin[key + '_version_id']; row = await db.get(StudioVersion, version_id)
        definition = await db.get(StudioDefinition, row.definition_id) if row else None
        if (not row or row.workspace_id != job.workspace_id or row.content_hash != pin[key + '_hash']
                or row.status not in ('published', 'deprecated') or not definition or definition.archived_at):
            reject('business_job_definition_revoked')
    for dep in pin['dependencies']:
        parent = await job_scope(db, job.workspace_id, dep['job_id'])
        await visible(db,parent,Principal(job.actor_id,0))
        if parent.selection.get('brain_id') and (parent.selection['brain_id']!=pin.get('brain_id') or pin['target']['provider']!='ollama'):
            reject('business_job_dependency_brain_mismatch',403)
        _, hashed = await artifact(db, parent)
        if hashed != dep['artifact_hash'] or not await approved_content(db, parent): reject('business_job_dependency_revoked', 403)
    run = await db.get(Run, job.run_id)
    if (not run or (run.engine_snapshot or {}).get('sha256') != pin['engine_hash']
            or (run.studio_snapshot or {}).get('sha256') != pin['studio_hash']): reject('business_job_run_changed')
    if execution and (run.cancel_requested or run.status not in ('queued', 'running')): reject('business_job_not_active')
    return task


async def guard_run(db, run):
    if not await db.scalar(text("SELECT to_regclass('public.business_jobs') IS NOT NULL")): return
    job = await db.scalar(select(BusinessJob).where(BusinessJob.run_id == run.id))
    if not job: return
    from ..engines.contract import EngineFailure
    try:
        await job_scope(db, run.workspace_id, job.id)
        await source_check(db, job)
    except Exception:
        raise EngineFailure('business_job_authority_unavailable') from None


async def execution_timeout(db,run,default):
    if not await db.scalar(text("SELECT to_regclass('public.business_jobs') IS NOT NULL")):return default
    row=await db.scalar(select(BusinessJob).where(BusinessJob.run_id==run.id))
    if not row:return default
    await job_scope(db,run.workspace_id,row.id)
    return min(default,row.selection['limits']['timeout_seconds'])


async def session_guard(db, sid):
    if not await db.scalar(text("SELECT to_regclass('public.business_jobs') IS NOT NULL")): return
    if await db.scalar(select(BusinessJob.id).join(Run, Run.id == BusinessJob.run_id).where(Run.session_id == sid)):
        reject('business_session_owned_by_adapter')


async def view(db, job, who=None):
    if who:await visible(db,job,who)
    run = await db.get(Run, job.run_id)
    binding = await db.get(BusinessPlanTask, job.plan_task_id)
    rows = await events(db, job.workspace_id, job.id, 'content_review')
    content = None; hashed = None
    if run.status == 'completed': content, hashed = await artifact(db, job)
    task=await db.get(Task,binding.task_id)
    return {'id': job.id, 'task_id': binding.task_id, 'item_key': binding.item_key, 'run_id': run.id,'due_at':task.due_at.isoformat(),
        'status': run.status, 'error_code': run.error_code, 'cancel_requested': run.cancel_requested,
        'model': job.selection['target']['model'], 'provider': job.selection['target']['provider'],
        'routing_revision': job.selection['routing_revision'], 'artifact': content, 'artifact_hash': hashed,
        'content_decision': rows[-1].data['decision'] if rows else None,
        'content_approved': await approved_content(db, job) if content else False, 'external_actions_allowed': False}


async def prepare(db, wid, who, pid, body):
    await authorize(db, wid, who)
    if await stopped(db, wid): reject('business_execution_stopped', 403)
    row, version = await selected_plan(db, wid, pid)
    state = await review.summary(db, row, version)
    if not state['effective'] or not state.get('admission_id'): reject('business_job_effective_plan_required', 403)
    selected = (await routing.preview(db, wid, who, row, version, RoutingPreview.model_validate(
        {k: v for k, v in body.model_dump(mode='json',exclude_none=True).items() if k not in ('request_key','confirm_model_call')})))['selection']
    binding = await db.scalar(select(BusinessPlanTask).where(BusinessPlanTask.admission_id == state['admission_id'], BusinessPlanTask.item_key == body.item_key))
    if not binding: reject('business_job_task_not_found', 404)
    task = await db.get(Task, binding.task_id)
    if digest(review.task_snapshot(task)) != binding.task_hash: reject('business_job_task_changed')
    parents = []; inputs = []
    for dependency in task.dependencies:
        parent_binding = await db.scalar(select(BusinessPlanTask).where(BusinessPlanTask.task_id == dependency, BusinessPlanTask.workspace_id == wid))
        parent = await db.scalar(select(BusinessJob).where(BusinessJob.plan_task_id == parent_binding.id)) if parent_binding else None
        if not parent or not await approved_content(db, parent): reject('business_job_dependency_not_approved', 403)
        await visible(db,parent,who)
        # Never copy private results into an unscoped conversation, a different
        # Brain, or cloud. Native session/search ACLs must continue to apply.
        if parent.selection.get('brain_id') and (parent.selection['brain_id']!=selected.get('brain_id') or selected['target']['provider']!='ollama'):
            reject('business_job_dependency_brain_mismatch',403)
        value, hashed = await artifact(db, parent); parents.append({'job_id': parent.id, 'artifact_hash': hashed}); inputs.append(value)
    selected.update(plan_id=pid, review_id=state['id'], task_hash=binding.task_hash, dependencies=parents)
    from ...skills import execution_binding
    selected['execution_binding']=execution_binding()
    control=await events(db,wid,wid,'control');selected['control_epoch']=control[-1].id if control else None
    return selected, binding, task, inputs


async def start(db, wid, who, pid, body, request):
    if not body.confirm_model_call: reject('business_job_confirmation_required', 422)
    fingerprint = digest({'plan_id': pid, 'body': body.model_dump(mode='json')})
    async def existing():
        old = await db.scalar(select(BusinessJob).where(BusinessJob.workspace_id == wid,
            BusinessJob.actor_id == who.id, BusinessJob.request_key == str(body.request_key)))
        if old and old.fingerprint != fingerprint: reject('business_job_request_conflict')
        return old
    await authorize(db, wid, who)
    old = await existing()
    if old: return await view(db, old)
    selected, binding, task, parents = await prepare(db, wid, who, pid, body)
    if await db.scalar(select(BusinessJob.id).where(BusinessJob.plan_task_id == binding.id)): reject('business_job_already_admitted')
    initial_hash = digest(selected)
    async def check():
        current, *_ = await prepare(db, wid, who, pid, body)
        return None, digest(current)
    async def admit(catalogue=None):
        from ..engines.service import choose_config
        from ..conversations.requests import admit_run
        from ...schemas import RunCreate
        from ..chat.policy import default_policy
        from ..studio.contracts import validate_value
        current, bound, native_task, dependencies = await prepare(db, wid, who, pid, body)
        if digest(current) != initial_hash: reject('business_job_selection_changed')
        old = await existing()
        if old: return await view(db, old)
        if await db.scalar(select(BusinessJob.id).where(BusinessJob.plan_task_id == bound.id)): reject('business_job_already_admitted')
        skill = await db.get(StudioVersion, current['skill_version_id']); definition = await db.get(StudioDefinition, skill.definition_id)
        source = await db.get(BusinessProfileVersion, current['profile_version_id'])
        context = {'brief': native_task.description, 'acceptance': native_task.success_criteria,
            'brand_voice': source.content['brand_voice'], 'products': source.content['products'],
            'audience': source.content['audience'], 'approved_dependencies': dependencies}
        inputs = {'text': json.dumps(context, ensure_ascii=False, separators=(',',':'))}
        try: validate_value(skill.payload['input_schema'], inputs)
        except ValueError: reject('business_job_skill_context_schema_mismatch', 422)
        prompt = '/' + definition.slug + ' ' + json.dumps(inputs, ensure_ascii=False)
        if len(prompt.encode()) > 1048576: reject('business_job_context_too_large', 422)
        limits = current['limits']; target = current['target']
        policy = default_policy(); policy.update(privacy='local_only' if target['provider']=='ollama' else 'cloud_allowed',
            cloud_references=target['provider']!='ollama', max_run_tokens=limits['token_budget'], max_calls=1,
            max_output_tokens=limits['output_tokens'], require_reported_usage=True)
        if target['provider']=='muse':
            from ..cli_connections.muse_resource import MIN_CONTEXT,MIN_JOB_BUDGET
            from ..chat.token_policy import automatic
            if not automatic(policy) and limits['token_budget']<MIN_JOB_BUDGET:reject('muse_job_budget_too_small',422)
            policy['context_tokens']=MIN_CONTEXT
        config = await choose_config(db, wid, target['provider'], target['model'], grant_id=str(body.grant_id) if body.grant_id else None,
            actor_id=who.id, brand_id=current['brand_id'], local_catalogue=catalogue,
            **({'installation_resource_id':target['installation_resource_id'],'reasoning_effort':target.get('reasoning_effort')}
               if target.get('installation_resource_id') else {}))
        chat = ChatSession(workspace_id=wid, user_id=who.id, title=native_task.title[:160], memory_enabled=False,
            brain_id=current['brain_id'], brand_id=current['brand_id'], engine_config=config, chat_profile={'policy':policy})
        db.add(chat); await db.flush()
        run = await admit_run(RunCreate(session_id=chat.id,message=prompt,request_key=str(body.request_key)), request, who, db, commit=False)
        if run.studio_snapshot['skill']['id'] != current['skill_version_id'] or run.studio_snapshot['agent']['id'] != current['agent_version_id']:
            reject('business_job_definition_changed')
        attempt = TaskAttempt(workspace_id=wid,task_id=native_task.id,run_id=run.id,request_key=str(body.request_key),
            input_fingerprint=fingerprint,attempt_no=1,input={'plan_version_id':current['plan_version_id']},status='running')
        db.add(attempt); await db.flush()
        current.update(engine_hash=run.engine_snapshot['sha256'], studio_hash=run.studio_snapshot['sha256'])
        job = BusinessJob(workspace_id=wid,plan_task_id=bound.id,actor_id=who.id,request_key=str(body.request_key),fingerprint=fingerprint,
            run_id=run.id,attempt_id=attempt.id,selection=current,selection_hash=digest(current))
        db.add(job); await db.flush()
        native_task.status='running';native_task.run_id=run.id;native_task.assignee_type='agent';native_task.assignee_id=current['agent_version_id'];native_task.version+=1
        db.add(TaskActivity(workspace_id=wid,task_id=native_task.id,actor_id=who.id,event='s5.job.admitted',data={'job_id':job.id,'run_id':run.id}))
        await db.commit(); return await view(db, job)
    if selected['target']['provider'] == 'ollama':
        from ..engines import metadata, service
        await db.rollback()  # No business row locks across model discovery I/O.
        async with metadata.discovery(db,wid,who,service.local_models,'model_select',body.request_key) as (models,error,_):
            if error: reject(error,503)
            await db.rollback()  # Release metadata KEY SHARE/advisory before business UPDATE lock.
            return await admit(models)
    return await admit()


async def collect(db, job):
    run = await db.get(Run, job.run_id)
    task_binding = await db.get(BusinessPlanTask, job.plan_task_id)
    task = await db.get(Task, task_binding.task_id, with_for_update=True)
    attempt = await db.get(TaskAttempt, job.attempt_id, with_for_update=True)
    if run.status not in ('completed','failed','cancelled') or attempt.status != 'running': return
    try: await source_check(db, job)
    except Exception:
        task.status='blocked';attempt.status='failed';attempt.error_code='business_job_authority_unavailable'
    else:
        task.status='waiting_approval' if run.status=='completed' else run.status
        attempt.status=run.status;attempt.error_code=run.error_code
        if run.status=='completed':
            value, hashed = await artifact(db, job); attempt.result={'artifact_hash':hashed,'run_id':run.id}
            task.result_reference={'kind':'business_draft','job_id':job.id,'hash':hashed};task.progress=90
    attempt.finished_at=now();attempt.version+=1;task.version+=1


async def decide_content(db, job, who, body):
    from datetime import timedelta
    if not body.confirm_review: reject('business_content_review_confirmation_required',422)
    await review.owner(db,job.workspace_id,who.id);await source_check(db,job)
    value, hashed = await artifact(db,job)
    if hashed != body.artifact_hash: reject('business_content_hash_changed')
    old = await events(db,job.workspace_id,job.id,'content_review')
    fingerprint=digest(body.model_dump(mode='json'))
    if old:
        if old[-1].fingerprint != fingerprint or old[-1].actor_id != who.id: reject('business_content_already_reviewed')
        return await view(db,job)
    await collect(db,job)
    row=await event(db,job.workspace_id,who.id,'job',job.id,'content_review',body.request_key,
        {'decision':body.decision,'artifact_hash':hashed,'expires_at':(now()+timedelta(hours=body.expiry_hours)).isoformat()},fingerprint)
    bound=await db.get(BusinessPlanTask,job.plan_task_id);task=await db.get(Task,bound.task_id)
    task.status='completed' if body.decision=='approve' else 'blocked';task.progress=100 if body.decision=='approve' else 90
    task.completed_at=now() if body.decision=='approve' else None;task.version+=1
    from ...models import Goal,Project
    await db.flush()
    siblings=list(await db.scalars(select(Task).where(Task.goal_id==task.goal_id)))
    goal=await db.get(Goal,task.goal_id,with_for_update=True)
    complete=bool(siblings and all(t.status=='completed' for t in siblings if t.required))
    goal.status='completed' if complete else 'active';goal.completed_at=now() if complete else None;goal.version+=1
    project=await db.get(Project,task.project_id,with_for_update=True)
    project.status='completed' if complete else 'active';project.version+=1
    await db.commit();return await view(db,job)
