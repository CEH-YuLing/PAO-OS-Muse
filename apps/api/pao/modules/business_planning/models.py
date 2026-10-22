from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import DateTime, Boolean
from datetime import datetime
from ...models import Base, Identity


class BusinessProfile(Identity, Base):
    __tablename__='business_profiles'
    workspace_id: Mapped[str]=mapped_column(ForeignKey('workspaces.id'))
    brand_id: Mapped[str|None]=mapped_column(ForeignKey('brands.id'))
    scope_key: Mapped[str]=mapped_column(String(40))
    revision: Mapped[int]=mapped_column(Integer)
    __table_args__=(UniqueConstraint('id','workspace_id'),UniqueConstraint('workspace_id','scope_key'),
        CheckConstraint("revision>=1 AND scope_key=coalesce(brand_id::text,'enterprise')",name='business_profile_scope'),
        ForeignKeyConstraint(['id','workspace_id','revision'],['business_profile_versions.profile_id','business_profile_versions.workspace_id','business_profile_versions.revision'],name='business_profile_head',deferrable=True,initially='DEFERRED',use_alter=True))


class BusinessProfileVersion(Identity, Base):
    __tablename__='business_profile_versions'
    workspace_id: Mapped[str]=mapped_column(ForeignKey('workspaces.id'))
    profile_id: Mapped[str]=mapped_column(ForeignKey('business_profiles.id'))
    revision: Mapped[int]=mapped_column(Integer)
    request_key: Mapped[str]=mapped_column(String(36))
    actor_id: Mapped[str]=mapped_column(ForeignKey('users.id'))
    content: Mapped[dict]=mapped_column(JSONB)
    content_hash: Mapped[str]=mapped_column(String(64))
    __table_args__=(ForeignKeyConstraint(['profile_id','workspace_id'],['business_profiles.id','business_profiles.workspace_id']),
        UniqueConstraint('profile_id','revision'),UniqueConstraint('profile_id','workspace_id','revision'),UniqueConstraint('profile_id','request_key'),UniqueConstraint('id','workspace_id'),
        CheckConstraint('revision>=1 AND length(content_hash)=64',name='business_profile_version_value'),)


class MonthlyPlan(Identity, Base):
    __tablename__='monthly_plans'
    workspace_id: Mapped[str]=mapped_column(ForeignKey('workspaces.id'))
    profile_id: Mapped[str]=mapped_column(ForeignKey('business_profiles.id'))
    revision: Mapped[int]=mapped_column(Integer)
    __table_args__=(UniqueConstraint('id','workspace_id'),
        ForeignKeyConstraint(['profile_id','workspace_id'],['business_profiles.id','business_profiles.workspace_id']),
        CheckConstraint('revision>=1',name='monthly_plan_revision'),
        ForeignKeyConstraint(['id','workspace_id','revision'],['monthly_plan_versions.plan_id','monthly_plan_versions.workspace_id','monthly_plan_versions.revision'],name='monthly_plan_head',deferrable=True,initially='DEFERRED',use_alter=True))


class MonthlyPlanVersion(Identity, Base):
    __tablename__='monthly_plan_versions'
    workspace_id: Mapped[str]=mapped_column(ForeignKey('workspaces.id'))
    plan_id: Mapped[str]=mapped_column(ForeignKey('monthly_plans.id'))
    profile_version_id: Mapped[str]=mapped_column(ForeignKey('business_profile_versions.id'))
    revision: Mapped[int]=mapped_column(Integer)
    request_key: Mapped[str]=mapped_column(String(36))
    actor_id: Mapped[str]=mapped_column(ForeignKey('users.id'))
    content: Mapped[dict]=mapped_column(JSONB)
    content_hash: Mapped[str]=mapped_column(String(64))
    __table_args__=(ForeignKeyConstraint(['plan_id','workspace_id'],['monthly_plans.id','monthly_plans.workspace_id']),
        ForeignKeyConstraint(['profile_version_id','workspace_id'],['business_profile_versions.id','business_profile_versions.workspace_id']),
        UniqueConstraint('plan_id','revision'),UniqueConstraint('plan_id','workspace_id','revision'),UniqueConstraint('plan_id','request_key'),
        CheckConstraint('revision>=1 AND length(content_hash)=64',name='monthly_plan_version_value'),)


class BusinessPlanReview(Identity, Base):
    __tablename__='business_plan_reviews'
    workspace_id: Mapped[str]=mapped_column(ForeignKey('workspaces.id'))
    plan_version_id: Mapped[str]=mapped_column(ForeignKey('monthly_plan_versions.id'),unique=True)
    actor_id: Mapped[str]=mapped_column(ForeignKey('users.id'))
    decision: Mapped[str]=mapped_column(String(16))
    source_hash: Mapped[str]=mapped_column(String(64))
    request_key: Mapped[str]=mapped_column(String(36))
    fingerprint: Mapped[str]=mapped_column(String(64))
    self_review: Mapped[bool]=mapped_column(Boolean)
    acknowledge_missing: Mapped[bool]=mapped_column(Boolean)
    expires_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    __table_args__=(UniqueConstraint('id','workspace_id'),UniqueConstraint('workspace_id','actor_id','request_key'),
        CheckConstraint("decision IN ('approve','reject') AND length(source_hash)=64 AND length(fingerprint)=64",name='business_review_value'))


class BusinessPlanAdmission(Identity, Base):
    __tablename__='business_plan_admissions'
    workspace_id: Mapped[str]=mapped_column(ForeignKey('workspaces.id'))
    plan_version_id: Mapped[str]=mapped_column(ForeignKey('monthly_plan_versions.id'),unique=True)
    review_id: Mapped[str]=mapped_column(ForeignKey('business_plan_reviews.id'),unique=True)
    project_id: Mapped[str]=mapped_column(ForeignKey('projects.id'),unique=True)
    goal_id: Mapped[str]=mapped_column(ForeignKey('goals.id'),unique=True)
    actor_id: Mapped[str]=mapped_column(ForeignKey('users.id'))
    request_key: Mapped[str]=mapped_column(String(36))
    fingerprint: Mapped[str]=mapped_column(String(64))
    __table_args__=(UniqueConstraint('id','workspace_id'),UniqueConstraint('workspace_id','actor_id','request_key'),
        ForeignKeyConstraint(['review_id','workspace_id'],['business_plan_reviews.id','business_plan_reviews.workspace_id']),
        ForeignKeyConstraint(['project_id','workspace_id'],['projects.id','projects.workspace_id']),
        ForeignKeyConstraint(['goal_id','workspace_id'],['goals.id','goals.workspace_id']),CheckConstraint('length(fingerprint)=64',name='business_admission_value'))


class BusinessPlanTask(Identity, Base):
    __tablename__='business_plan_tasks'
    workspace_id: Mapped[str]=mapped_column(ForeignKey('workspaces.id'))
    admission_id: Mapped[str]=mapped_column(ForeignKey('business_plan_admissions.id'))
    task_id: Mapped[str]=mapped_column(ForeignKey('tasks.id'),unique=True)
    item_key: Mapped[str]=mapped_column(String(40))
    task_hash: Mapped[str]=mapped_column(String(64))
    __table_args__=(ForeignKeyConstraint(['admission_id','workspace_id'],['business_plan_admissions.id','business_plan_admissions.workspace_id']),
        ForeignKeyConstraint(['task_id','workspace_id'],['tasks.id','tasks.workspace_id']),
        UniqueConstraint('admission_id','item_key'),CheckConstraint('length(task_hash)=64',name='business_task_value'))


class BusinessRoutingVersion(Identity, Base):
    __tablename__ = 'business_routing_versions'
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'))
    revision: Mapped[int] = mapped_column(Integer)
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    request_key: Mapped[str] = mapped_column(String(36))
    content: Mapped[dict] = mapped_column(JSONB)
    content_hash: Mapped[str] = mapped_column(String(64))
    __table_args__ = (UniqueConstraint('workspace_id', 'revision'),
        UniqueConstraint('workspace_id', 'request_key'),
        CheckConstraint('revision>=1 AND length(content_hash)=64', name='business_routing_value'))
