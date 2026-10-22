"""S5 adapter receipts and append-only business evidence; native Run owns execution."""
from datetime import datetime
from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from ...models import Base, Identity


class BusinessJob(Identity, Base):
    __tablename__ = 'business_jobs'
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'))
    plan_task_id: Mapped[str] = mapped_column(ForeignKey('business_plan_tasks.id'), unique=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    request_key: Mapped[str] = mapped_column(String(36))
    fingerprint: Mapped[str] = mapped_column(String(64))
    run_id: Mapped[str] = mapped_column(ForeignKey('runs.id'), unique=True)
    attempt_id: Mapped[str] = mapped_column(ForeignKey('task_attempts.id'), unique=True)
    selection: Mapped[dict] = mapped_column(JSONB)
    selection_hash: Mapped[str] = mapped_column(String(64))
    __table_args__ = (UniqueConstraint('id','workspace_id'), UniqueConstraint('workspace_id','actor_id','request_key'),
        ForeignKeyConstraint(['run_id','workspace_id'],['runs.id','runs.workspace_id']),
        ForeignKeyConstraint(['attempt_id','workspace_id'],['task_attempts.id','task_attempts.workspace_id']),
        CheckConstraint('length(fingerprint)=64 AND length(selection_hash)=64',name='business_job_hash'))


class BusinessPlanEvent(Identity, Base):
    __tablename__ = 'business_plan_events'
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'))
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    subject_kind: Mapped[str] = mapped_column(String(16))
    subject_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    action: Mapped[str] = mapped_column(String(32))
    request_key: Mapped[str] = mapped_column(String(36))
    fingerprint: Mapped[str] = mapped_column(String(64))
    data: Mapped[dict] = mapped_column(JSONB)
    content_hash: Mapped[str] = mapped_column(String(64))
    __table_args__ = (UniqueConstraint('workspace_id','request_key'),
        CheckConstraint("subject_kind IN ('job','action','budget','control','schedule','report') AND length(content_hash)=64 AND length(fingerprint)=64",name='business_event_value'))


class BusinessBudget(Identity, Base):
    __tablename__ = 'business_budgets'
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'))
    plan_version_id: Mapped[str] = mapped_column(ForeignKey('monthly_plan_versions.id'))
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    request_key: Mapped[str] = mapped_column(String(36))
    fingerprint: Mapped[str] = mapped_column(String(64))
    account_id: Mapped[str] = mapped_column(String(80))
    campaign_id: Mapped[str] = mapped_column(String(80))
    currency: Mapped[str] = mapped_column(String(3))
    cap_minor: Mapped[int] = mapped_column(BigInteger)
    headroom_minor: Mapped[int] = mapped_column(BigInteger)
    opening_spent_minor: Mapped[int] = mapped_column(BigInteger)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    max_age_seconds: Mapped[int] = mapped_column(Integer)
    __table_args__ = (UniqueConstraint('id','workspace_id'), UniqueConstraint('workspace_id','request_key'),
        UniqueConstraint('workspace_id','plan_version_id','account_id','campaign_id','currency'),
        CheckConstraint('cap_minor>0 AND headroom_minor>=0 AND opening_spent_minor>=0 AND headroom_minor+opening_spent_minor<=cap_minor AND max_age_seconds BETWEEN 60 AND 86400',name='business_budget_values'))


class BusinessAction(Identity, Base):
    __tablename__ = 'business_actions'
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'))
    job_id: Mapped[str] = mapped_column(ForeignKey('business_jobs.id'))
    budget_id: Mapped[str] = mapped_column(ForeignKey('business_budgets.id'))
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    request_key: Mapped[str] = mapped_column(String(36))
    fingerprint: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(24))
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    artifact_hash: Mapped[str] = mapped_column(String(64))
    __table_args__ = (UniqueConstraint('id','workspace_id'), UniqueConstraint('workspace_id','request_key'),
        ForeignKeyConstraint(['job_id','workspace_id'],['business_jobs.id','business_jobs.workspace_id']),
        ForeignKeyConstraint(['budget_id','workspace_id'],['business_budgets.id','business_budgets.workspace_id']),
        CheckConstraint("kind IN ('mock_publish','mock_ads_budget') AND amount_minor>0 AND length(artifact_hash)=64",name='business_action_values'))


class BusinessBudgetEntry(Identity, Base):
    __tablename__ = 'business_budget_entries'
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'))
    budget_id: Mapped[str] = mapped_column(ForeignKey('business_budgets.id'))
    action_id: Mapped[str] = mapped_column(ForeignKey('business_actions.id'))
    kind: Mapped[str] = mapped_column(String(16))
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    __table_args__ = (UniqueConstraint('action_id','kind'),
        ForeignKeyConstraint(['budget_id','workspace_id'],['business_budgets.id','business_budgets.workspace_id']),
        ForeignKeyConstraint(['action_id','workspace_id'],['business_actions.id','business_actions.workspace_id']),
        CheckConstraint("kind IN ('reserved','spent','released') AND amount_minor>0",name='business_budget_entry_values'))
