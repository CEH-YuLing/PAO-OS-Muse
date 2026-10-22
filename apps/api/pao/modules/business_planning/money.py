"""Exact minor-unit simulated campaign ledger. Never calls an Ads/publishing API."""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Literal
from uuid import UUID
from pydantic import Field, field_validator, model_validator
from sqlalchemy import select
from ...models import BusinessBudget, BusinessBudgetEntry, BusinessAction, BusinessPlanAdmission, BusinessPlanTask, now
from .contracts import Closed, digest
from .access import reject, selected_plan
from . import jobs, review

MINOR = {'VND': 0, 'USD': 2, 'EUR': 2, 'GBP': 2, 'JPY': 0}


def minor(value, currency):
    if currency not in MINOR: reject('business_currency_not_supported', 422)
    if isinstance(value, (float, bool)): reject('business_money_exact_decimal_required', 422)
    number = Decimal(value); scaled = number * (10 ** MINOR[currency])
    if not number.is_finite() or scaled != scaled.to_integral_value() or not 0 <= scaled <= 10**15:
        reject('business_money_precision_invalid', 422)
    return int(scaled)


class BudgetCreate(Closed):
    request_key: UUID
    plan_revision: int = Field(ge=1, strict=True)
    account_id: str = Field(pattern=r'^mock:[a-zA-Z0-9_-]{1,60}$')
    campaign_id: str = Field(pattern=r'^mock:[a-zA-Z0-9_-]{1,60}$')
    currency: Literal['VND','USD','EUR','GBP','JPY']
    cap: Decimal = Field(gt=0,max_digits=18,decimal_places=2)
    headroom: Decimal = Field(ge=0,max_digits=18,decimal_places=2)
    opening_spent: Decimal = Field(ge=0,max_digits=18,decimal_places=2)
    observed_at: datetime
    max_age_seconds: int = Field(default=3600, ge=60, le=86400, strict=True)
    confirm_simulation: bool = Field(strict=True)

    @field_validator('cap','headroom','opening_spent',mode='before')
    @classmethod
    def exact(cls, value):
        if isinstance(value,(float,bool)): raise ValueError('Use decimal strings')
        return value

    @model_validator(mode='after')
    def valid(self):
        if self.observed_at.utcoffset() is None: raise ValueError('Timezone required')
        if self.headroom+self.opening_spent > self.cap: raise ValueError('No available budget')
        for value in (self.cap,self.headroom,self.opening_spent): minor(value,self.currency)
        return self


class ActionCreate(Closed):
    request_key: UUID
    job_id: UUID
    budget_id: UUID
    kind: Literal['mock_publish','mock_ads_budget']
    amount: Decimal = Field(gt=0,max_digits=18,decimal_places=2)
    artifact_hash: str = Field(pattern='^[a-f0-9]{64}$')
    confirm_simulation: bool = Field(strict=True)

    @field_validator('amount',mode='before')
    @classmethod
    def exact(cls,value):
        if isinstance(value,(float,bool)):raise ValueError('Use decimal strings')
        return value


class ActionDecision(Closed):
    request_key: UUID
    decision: Literal['approve','reject']
    confirm_simulation: bool = Field(strict=True)
    expiry_hours: int = Field(default=24,ge=1,le=168,strict=True)


class Simulation(Closed):
    request_key: UUID
    outcome: Literal['success','unknown']
    confirm_simulation: bool = Field(strict=True)


class Reconciliation(Closed):
    request_key: UUID
    outcome: Literal['success','failure']
    note: str = Field(min_length=5,max_length=500)
    confirm_simulation: bool = Field(strict=True)


class CancelAction(Closed):
    request_key: UUID
    confirm_simulation: bool = Field(strict=True)


async def budget_scope(db,wid,bid,lock=False):
    query=select(BusinessBudget).where(BusinessBudget.id==bid,BusinessBudget.workspace_id==wid)
    if lock:query=query.with_for_update()
    row=await db.scalar(query)
    if not row:reject('business_budget_not_found',404)
    return row


async def balance(db,row):
    entries=list(await db.scalars(select(BusinessBudgetEntry).where(BusinessBudgetEntry.budget_id==row.id)))
    sums={kind:sum(e.amount_minor for e in entries if e.kind==kind) for kind in ('reserved','spent','released')}
    return {'id':row.id,'account_id':row.account_id,'campaign_id':row.campaign_id,'currency':row.currency,
        'minor_digits':MINOR[row.currency], 'cap_minor':row.cap_minor,'headroom_minor':row.headroom_minor,
        'opening_spent_minor':row.opening_spent_minor,'reserved_minor':sums['reserved']-sums['spent']-sums['released'],
        'spent_minor':row.opening_spent_minor+sums['spent'],'released_minor':sums['released'],
        'available_minor':row.cap_minor-row.headroom_minor-row.opening_spent_minor-sums['reserved']+sums['released'],
        'observed_at':row.observed_at.isoformat(),'stale':now()-row.observed_at>timedelta(seconds=row.max_age_seconds),
        'mode':'simulation_only','provider_balance':None}


async def create_budget(db,wid,pid,who,body):
    await review.owner(db,wid,who.id)
    if not body.confirm_simulation:reject('business_simulation_confirmation_required',422)
    plan,version=await selected_plan(db,wid,pid)
    if plan.revision!=body.plan_revision or not (await review.summary(db,plan,version))['effective']:reject('business_budget_plan_approval_required',403)
    from .access import profile_scope,profile_version
    profile=await profile_scope(db,wid,plan.profile_id);source=await profile_version(db,profile)
    if body.currency!=source.content['currency']:reject('business_budget_currency_mismatch',422)
    fingerprint=digest({'plan_version_id':version.id,'body':body.model_dump(mode='json')})
    old=await db.scalar(select(BusinessBudget).where(BusinessBudget.workspace_id==wid,BusinessBudget.request_key==str(body.request_key)))
    if old:
        if old.fingerprint!=fingerprint or old.actor_id!=who.id:reject('business_budget_request_conflict')
        return await balance(db,old)
    if body.observed_at>now() or now()-body.observed_at>timedelta(seconds=body.max_age_seconds):reject('business_budget_observation_stale',422)
    # Revisions must not reset the monthly business cap for the same brand/account.
    from ...models import MonthlyPlanVersion,MonthlyPlan,BusinessProfile
    existing=await db.scalar(select(BusinessBudget.id).join(MonthlyPlanVersion,MonthlyPlanVersion.id==BusinessBudget.plan_version_id)
        .join(MonthlyPlan,MonthlyPlan.id==MonthlyPlanVersion.plan_id).join(BusinessProfile,BusinessProfile.id==MonthlyPlan.profile_id)
        .where(BusinessBudget.workspace_id==wid,BusinessProfile.scope_key==profile.scope_key,
            MonthlyPlanVersion.content['month'].as_string()==version.content['month'],BusinessBudget.account_id==body.account_id,
            BusinessBudget.campaign_id==body.campaign_id,BusinessBudget.currency==body.currency))
    if existing:reject('business_budget_month_scope_already_exists')
    cap=minor(body.cap,body.currency)
    if source.content.get('monthly_budget') is not None:
        assigned=list(await db.scalars(select(BusinessBudget.cap_minor).join(MonthlyPlanVersion,MonthlyPlanVersion.id==BusinessBudget.plan_version_id)
            .join(MonthlyPlan,MonthlyPlan.id==MonthlyPlanVersion.plan_id).join(BusinessProfile,BusinessProfile.id==MonthlyPlan.profile_id)
            .where(BusinessBudget.workspace_id==wid,BusinessProfile.scope_key==profile.scope_key,
                MonthlyPlanVersion.content['month'].as_string()==version.content['month'],BusinessBudget.currency==body.currency)))
        if sum(assigned)+cap>minor(source.content['monthly_budget'],body.currency):reject('business_budget_month_cap_exceeded')
    row=BusinessBudget(workspace_id=wid,plan_version_id=version.id,actor_id=who.id,request_key=str(body.request_key),fingerprint=fingerprint,
        account_id=body.account_id,campaign_id=body.campaign_id,currency=body.currency,cap_minor=cap,
        headroom_minor=minor(body.headroom,body.currency),opening_spent_minor=minor(body.opening_spent,body.currency),
        observed_at=body.observed_at,max_age_seconds=body.max_age_seconds)
    db.add(row);await db.flush();result=await balance(db,row);await db.commit();return result


async def action_scope(db,wid,aid):
    row=await db.scalar(select(BusinessAction).where(BusinessAction.id==aid,BusinessAction.workspace_id==wid))
    if not row:reject('business_action_not_found',404)
    return row


async def action_view(db,row):
    events=await jobs.events(db,row.workspace_id,row.id)
    result=next((e for e in reversed(events) if e.action in ('simulated','reconciled','abandoned')),None)
    decision=next((e for e in reversed(events) if e.action=='action_review'),None)
    return {'id':row.id,'job_id':row.job_id,'budget_id':row.budget_id,'kind':row.kind,'amount_minor':row.amount_minor,
        'artifact_hash':row.artifact_hash,'decision':decision.data['decision'] if decision else None,
        'status':result.data['outcome'] if result else 'awaiting_execution' if decision and decision.data['decision']=='approve' else 'awaiting_approval',
        'mode':'simulation_only','external_calls':False}


async def propose(db,wid,who,body):
    if not body.confirm_simulation:reject('business_simulation_confirmation_required',422)
    fingerprint=digest(body.model_dump(mode='json'))
    old=await db.scalar(select(BusinessAction).where(BusinessAction.workspace_id==wid,BusinessAction.request_key==str(body.request_key)))
    if old:
        if old.fingerprint!=fingerprint or old.actor_id!=who.id:reject('business_action_request_conflict')
        return await action_view(db,old)
    job=await jobs.job_scope(db,wid,str(body.job_id));await jobs.source_check(db,job)
    if not await jobs.approved_content(db,job):reject('business_action_content_approval_required',403)
    _,hashed=await jobs.artifact(db,job)
    if hashed!=body.artifact_hash:reject('business_action_artifact_changed')
    budget=await budget_scope(db,wid,str(body.budget_id),True)
    if budget.plan_version_id!=job.selection['plan_version_id']:reject('business_action_plan_budget_mismatch',422)
    available=await balance(db,budget);amount=minor(body.amount,budget.currency)
    if available['stale']:reject('business_budget_observation_stale')
    if amount>available['available_minor']:reject('business_budget_exhausted')
    row=BusinessAction(workspace_id=wid,actor_id=who.id,request_key=str(body.request_key),fingerprint=fingerprint,
        job_id=job.id,budget_id=budget.id,kind=body.kind,amount_minor=amount,artifact_hash=hashed)
    db.add(row);await db.flush()
    db.add(BusinessBudgetEntry(workspace_id=wid,budget_id=budget.id,action_id=row.id,kind='reserved',amount_minor=amount))
    await db.flush();result=await action_view(db,row);await db.commit();return result


async def check_action(db,row):
    job=await jobs.job_scope(db,row.workspace_id,row.job_id);await jobs.source_check(db,job)
    if not await jobs.approved_content(db,job):reject('business_action_content_approval_required',403)
    _,hashed=await jobs.artifact(db,job)
    if row.artifact_hash!=hashed:reject('business_action_artifact_changed')
    return job


async def decide(db,row,who,body):
    await review.owner(db,row.workspace_id,who.id)
    if not body.confirm_simulation:reject('business_simulation_confirmation_required',422)
    await check_action(db,row)
    if await jobs.events(db,row.workspace_id,row.id,'abandoned'):reject('business_action_closed')
    prior=await jobs.events(db,row.workspace_id,row.id,'action_review');fingerprint=digest(body.model_dump(mode='json'))
    if prior:
        if prior[-1].fingerprint!=fingerprint or prior[-1].actor_id!=who.id:reject('business_action_already_reviewed')
        return await action_view(db,row)
    await jobs.event(db,row.workspace_id,who.id,'action',row.id,'action_review',body.request_key,
        {'decision':body.decision,'artifact_hash':row.artifact_hash,'expires_at':(now()+timedelta(hours=body.expiry_hours)).isoformat()},fingerprint)
    if body.decision=='reject':
        db.add(BusinessBudgetEntry(workspace_id=row.workspace_id,budget_id=row.budget_id,action_id=row.id,kind='released',amount_minor=row.amount_minor))
    await db.flush();result=await action_view(db,row);await db.commit();return result


async def simulate(db,row,who,body,reconcile=False):
    await review.owner(db,row.workspace_id,who.id)
    if not body.confirm_simulation:reject('business_simulation_confirmation_required',422)
    budget=await budget_scope(db,row.workspace_id,row.budget_id,True)
    prior=await jobs.events(db,row.workspace_id,row.id,'reconciled' if reconcile else 'simulated')
    fingerprint=digest(body.model_dump(mode='json'))
    if prior:
        if prior[-1].fingerprint!=fingerprint or prior[-1].actor_id!=who.id:reject('business_simulation_already_recorded')
        return await action_view(db,row)
    if reconcile:
        simulated=await jobs.events(db,row.workspace_id,row.id,'simulated')
        if not simulated or simulated[-1].data['outcome']!='unknown':reject('business_action_not_unknown')
        # Reconciliation records a past simulation, never executes/retries it.
    else:
        if await jobs.events(db,row.workspace_id,row.id,'abandoned'):reject('business_action_closed')
        await check_action(db,row)
        decision=await jobs.events(db,row.workspace_id,row.id,'action_review')
        if (not decision or decision[-1].data['decision']!='approve' or datetime.fromisoformat(decision[-1].data['expires_at'])<=now()
                or not await jobs.active_owner(db,row.workspace_id,decision[-1].actor_id)):reject('business_action_effective_approval_required',403)
        if (await balance(db,budget))['stale']:reject('business_budget_observation_stale')
    outcome=body.outcome
    if outcome!='unknown':
        db.add(BusinessBudgetEntry(workspace_id=row.workspace_id,budget_id=row.budget_id,action_id=row.id,
            kind='spent' if outcome=='success' else 'released',amount_minor=row.amount_minor))
    await jobs.event(db,row.workspace_id,who.id,'action',row.id,'reconciled' if reconcile else 'simulated',body.request_key,
        {'outcome':outcome,'mode':'simulation_only','external_calls':False,**({'note':body.note} if reconcile else {})},fingerprint)
    await db.flush();result=await action_view(db,row);await db.commit();return result


async def abandon(db,row,who,body):
    await review.owner(db,row.workspace_id,who.id)
    if not body.confirm_simulation:reject('business_simulation_confirmation_required',422)
    await budget_scope(db,row.workspace_id,row.budget_id,True)
    if await jobs.events(db,row.workspace_id,row.id,'simulated'):reject('business_action_requires_reconciliation')
    fingerprint=digest(body.model_dump(mode='json'));old=await jobs.events(db,row.workspace_id,row.id,'abandoned')
    if old:
        if old[-1].fingerprint!=fingerprint or old[-1].actor_id!=who.id:reject('business_action_already_closed')
        return await action_view(db,row)
    entries=list(await db.scalars(select(BusinessBudgetEntry).where(BusinessBudgetEntry.action_id==row.id)))
    if not any(e.kind in ('spent','released') for e in entries):
        db.add(BusinessBudgetEntry(workspace_id=row.workspace_id,budget_id=row.budget_id,action_id=row.id,kind='released',amount_minor=row.amount_minor))
    await jobs.event(db,row.workspace_id,who.id,'action',row.id,'abandoned',body.request_key,{'outcome':'cancelled','external_calls':False},fingerprint)
    await db.flush();result=await action_view(db,row);await db.commit();return result
