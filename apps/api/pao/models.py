import uuid
from datetime import date, datetime, timezone, time
from decimal import Decimal

from sqlalchemy import (JSON, BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, LargeBinary,
                        ForeignKeyConstraint, Index, Integer, String, Text,
                        UniqueConstraint, Uuid, text, Date, Numeric, Time, func)
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB


def uid() -> str:
    return str(uuid.uuid4())


def now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass



class Identity:
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=uid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ResultInboxReceipt(Identity, Base):
    __tablename__='result_inbox_receipts'
    workspace_id: Mapped[str]=mapped_column(ForeignKey('workspaces.id'))
    user_id: Mapped[str]=mapped_column(ForeignKey('users.id'))
    source_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    source_hash: Mapped[str]=mapped_column(String(64))
    read_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    ack_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    __table_args__=(UniqueConstraint('workspace_id','user_id','source_id','source_hash'),
        ForeignKeyConstraint(['source_id','workspace_id'],['studio_executions.id','studio_executions.workspace_id']),
        CheckConstraint('length(source_hash)=64'),)


class ResultDelivery(Identity, Base):
    __tablename__='result_deliveries'
    workspace_id: Mapped[str]=mapped_column(ForeignKey('workspaces.id'))
    user_id: Mapped[str]=mapped_column(ForeignKey('users.id'))
    source_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    source_hash: Mapped[str]=mapped_column(String(64))
    destination: Mapped[str]=mapped_column(String(24),default='in_app')
    status: Mapped[str]=mapped_column(String(16),default='pending')
    error_code: Mapped[str|None]=mapped_column(String(64))
    delivered_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    requested_by: Mapped[str|None]=mapped_column(ForeignKey('users.id'))
    attempts: Mapped[int]=mapped_column(Integer,default=0,server_default=text('0'))
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,server_default=func.now())
    __table_args__=(UniqueConstraint('workspace_id','user_id','source_id','source_hash','destination'),
        ForeignKeyConstraint(['source_id','workspace_id'],['studio_executions.id','studio_executions.workspace_id']),
        CheckConstraint("destination='in_app' AND status IN ('pending','delivered','failed') AND length(source_hash)=64"),)


class GoalResultReceipt(Identity, Base):
    __tablename__='goal_result_receipts'
    workspace_id: Mapped[str]=mapped_column(ForeignKey('workspaces.id'))
    user_id: Mapped[str]=mapped_column(ForeignKey('users.id'))
    source_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    source_hash: Mapped[str]=mapped_column(String(64))
    read_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    ack_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    __table_args__=(UniqueConstraint('workspace_id','user_id','source_id','source_hash'),
        ForeignKeyConstraint(['source_id','workspace_id'],['goal_executions.id','goal_executions.workspace_id']),
        CheckConstraint('length(source_hash)=64'),)


class GoalResultDelivery(Identity, Base):
    __tablename__='goal_result_deliveries'
    workspace_id: Mapped[str]=mapped_column(ForeignKey('workspaces.id'))
    user_id: Mapped[str]=mapped_column(ForeignKey('users.id'))
    source_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    source_hash: Mapped[str]=mapped_column(String(64))
    destination: Mapped[str]=mapped_column(String(24),default='in_app')
    status: Mapped[str]=mapped_column(String(16),default='pending')
    error_code: Mapped[str|None]=mapped_column(String(64))
    delivered_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    requested_by: Mapped[str|None]=mapped_column(ForeignKey('users.id'))
    attempts: Mapped[int]=mapped_column(Integer,default=0,server_default=text('0'))
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,server_default=func.now())
    __table_args__=(UniqueConstraint('workspace_id','user_id','source_id','source_hash','destination'),
        ForeignKeyConstraint(['source_id','workspace_id'],['goal_executions.id','goal_executions.workspace_id']),
        CheckConstraint("destination='in_app' AND status IN ('pending','delivered','failed') AND length(source_hash)=64 AND attempts>=0 AND attempts<=5"),)


class LearningProposal(Identity, Base):
    __tablename__='learning_proposals'
    workspace_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    brain_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    actor_id: Mapped[str]=mapped_column(ForeignKey('users.id'))
    source_id: Mapped[str]=mapped_column(ForeignKey('messages.id'))
    source_hash: Mapped[str]=mapped_column(String(64))
    candidate: Mapped[str]=mapped_column(Text)
    fingerprint: Mapped[str]=mapped_column(String(64))
    status: Mapped[str]=mapped_column(String(16),default='pending')
    note_id: Mapped[str|None]=mapped_column(ForeignKey('brain_notes.id'))
    __table_args__=(ForeignKeyConstraint(['brain_id','workspace_id'],['brains.id','brains.workspace_id']),
        UniqueConstraint('brain_id','actor_id','fingerprint'),
        CheckConstraint("status IN ('pending','promoted','reverted','rejected') AND length(source_hash)=64 AND length(fingerprint)=64"),)


class LearningAudit(Identity, Base):
    __tablename__='learning_audits'
    proposal_id: Mapped[str]=mapped_column(ForeignKey('learning_proposals.id'))
    actor_id: Mapped[str]=mapped_column(ForeignKey('users.id'))
    action: Mapped[str]=mapped_column(String(16))
    data: Mapped[dict]=mapped_column(JSON)


class ArtifactLearningProposal(Identity, Base):
    __tablename__='artifact_learning_proposals'
    workspace_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    brain_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    actor_id: Mapped[str]=mapped_column(ForeignKey('users.id'))
    source_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    source_hash: Mapped[str]=mapped_column(String(64))
    candidate: Mapped[str]=mapped_column(Text)
    fingerprint: Mapped[str]=mapped_column(String(64))
    derivation: Mapped[str]=mapped_column(String(32))
    segments: Mapped[list]=mapped_column(JSON)
    status: Mapped[str]=mapped_column(String(16),default='pending')
    note_id: Mapped[str|None]=mapped_column(ForeignKey('brain_notes.id'))
    __table_args__=(ForeignKeyConstraint(['brain_id','workspace_id'],['brains.id','brains.workspace_id']),
        ForeignKeyConstraint(['source_id','brain_id','workspace_id'],['brain_files.id','brain_files.brain_id','brain_files.workspace_id']),
        UniqueConstraint('brain_id','actor_id','fingerprint'),
        CheckConstraint("status IN ('pending','promoted','reverted','rejected') AND derivation IN ('quote','extractive_summary_v1') AND length(source_hash)=64 AND length(fingerprint)=64"),)


class ArtifactLearningAudit(Identity, Base):
    __tablename__='artifact_learning_audits'
    proposal_id: Mapped[str]=mapped_column(ForeignKey('artifact_learning_proposals.id'))
    actor_id: Mapped[str]=mapped_column(ForeignKey('users.id'))
    action: Mapped[str]=mapped_column(String(16))
    data: Mapped[dict]=mapped_column(JSON)


class User(Identity, Base):
    __tablename__ = 'users'
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    auth_version: Mapped[int] = mapped_column(Integer, default=0, server_default=text('0'))


class Workspace(Identity, Base):
    __tablename__ = 'workspaces'
    name: Mapped[str] = mapped_column(String(120))
    lifecycle_version: Mapped[int] = mapped_column(Integer, default=1, server_default=text('1'))


class WorkspaceInvitation(Identity, Base):
    __tablename__ = 'workspace_invitations'
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    creator_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    email: Mapped[str] = mapped_column(String(254))
    role: Mapped[str] = mapped_column(String(20))
    code_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default='pending')
    accepted_by: Mapped[str | None] = mapped_column(ForeignKey('users.id'))
    __table_args__ = (CheckConstraint("role IN ('admin','operator','analyst','viewer') AND status IN ('pending','accepted','revoked')", name='workspace_invitation_state'),)


class LoginSession(Identity, Base):
    __tablename__ = 'login_sessions'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    auth_version: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class LifecycleAudit(Identity, Base):
    __tablename__ = 'lifecycle_audits'
    workspace_id: Mapped[str | None] = mapped_column(ForeignKey('workspaces.id'), index=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    action: Mapped[str] = mapped_column(String(48))
    subject_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    # Identifiers and state only: no email, invitation code, token or exported content.
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class DataLifecycleRequest(Identity, Base):
    __tablename__ = 'data_lifecycle_requests'
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    kind: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16))
    scope_hash: Mapped[str] = mapped_column(String(64))
    summary: Mapped[dict] = mapped_column(JSON)
    payload: Mapped[bytes | None] = mapped_column(LargeBinary)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (CheckConstraint("kind IN ('export','deletion') AND status IN ('ready','preview','requested','confirmed')", name='data_lifecycle_request_state'),)


class Member(Base):
    __tablename__ = 'workspace_members'
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), primary_key=True)
    role: Mapped[str] = mapped_column(String(20), default='owner')
    __table_args__ = (CheckConstraint("role in ('owner','admin','operator','analyst','viewer')"),)


class TenantResourcePolicy(Base):
    __tablename__ = 'tenant_resource_policies'
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    daily_model_calls: Mapped[int] = mapped_column(Integer)
    daily_model_tokens: Mapped[int] = mapped_column(Integer)
    concurrent_models: Mapped[int] = mapped_column(Integer)
    updated_by: Mapped[str] = mapped_column(ForeignKey('users.id'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (CheckConstraint('version >= 1 AND daily_model_calls BETWEEN 1 AND 10000 '
        'AND daily_model_tokens BETWEEN 1 AND 10000000 AND concurrent_models BETWEEN 1 AND 8',
        name='tenant_resource_policy_bounds'),)


class TenantReadPolicy(Base):
    __tablename__='tenant_read_policies'
    workspace_id: Mapped[str]=mapped_column(ForeignKey('workspaces.id'),primary_key=True)
    version: Mapped[int]=mapped_column(Integer,default=1)
    daily_read_jobs: Mapped[int]=mapped_column(Integer)
    queued_read_jobs: Mapped[int]=mapped_column(Integer)
    concurrent_reads: Mapped[int]=mapped_column(Integer)
    updated_by: Mapped[str]=mapped_column(ForeignKey('users.id'))
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    __table_args__=(CheckConstraint('version>=1 AND daily_read_jobs BETWEEN 1 AND 10000 '
        'AND queued_read_jobs BETWEEN 1 AND 100 AND concurrent_reads BETWEEN 1 AND 8',
        name='tenant_read_policy_bounds'),)


class TenantMetadataPolicy(Base):
    __tablename__='tenant_metadata_policies'
    workspace_id: Mapped[str]=mapped_column(ForeignKey('workspaces.id'),primary_key=True)
    version: Mapped[int]=mapped_column(Integer,default=1)
    daily_metadata_requests: Mapped[int]=mapped_column(Integer)
    concurrent_metadata: Mapped[int]=mapped_column(Integer)
    updated_by: Mapped[str]=mapped_column(ForeignKey('users.id'))
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    __table_args__=(CheckConstraint('version>=1 AND daily_metadata_requests BETWEEN 1 AND 1000 '
        'AND concurrent_metadata BETWEEN 1 AND 8',name='tenant_metadata_policy_bounds'),)


class TenantMetadataLease(Identity, Base):
    """Single metadata admission, never token/billing or a credential store."""
    __tablename__='tenant_metadata_leases'
    workspace_id: Mapped[str]=mapped_column(ForeignKey('workspaces.id'))
    actor_id: Mapped[str]=mapped_column(ForeignKey('users.id'))
    kind: Mapped[str]=mapped_column(String(24))
    request_key: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    target_hash: Mapped[str]=mapped_column(String(64))
    policy_version: Mapped[int]=mapped_column(Integer)
    status: Mapped[str]=mapped_column(String(16),default='active')
    expires_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    released_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    __table_args__=(UniqueConstraint('workspace_id','request_key'),
        CheckConstraint("policy_version>=0 AND kind IN ('model_connect','model_catalogue','model_select','mcp_discovery') "
            "AND target_hash ~ '^[0-9a-f]{64}$' AND status IN ('active','released','expired') "
            "AND expires_at=created_at+interval '90 seconds' AND "
            "((status='active' AND released_at IS NULL) OR (status<>'active' AND released_at IS NOT NULL AND released_at>=created_at))",
            name='tenant_metadata_lease_state'),
        Index('tenant_metadata_lease_usage','workspace_id','status','created_at'),)


class TenantModelLease(Identity, Base):
    """Resource admission, not a second usage or billing ledger."""
    __tablename__ = 'tenant_model_leases'
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'))
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    kind: Mapped[str] = mapped_column(String(24))
    request_key: Mapped[str] = mapped_column(String(64))
    attempt_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    policy_version: Mapped[int] = mapped_column(Integer)
    reserved_tokens: Mapped[int] = mapped_column(Integer)
    embedding_pin: Mapped[dict | None] = mapped_column(JSONB(none_as_null=True))
    status: Mapped[str] = mapped_column(String(16), default='active')
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint('workspace_id','kind','request_key'),
        UniqueConstraint('attempt_id'),
        ForeignKeyConstraint(['attempt_id','workspace_id'],['llm_attempts.id','llm_attempts.workspace_id']),
        CheckConstraint("policy_version >= 0 AND status IN ('active','released','expired') AND "
            "((kind='llm' AND attempt_id IS NOT NULL AND reserved_tokens=0 AND embedding_pin IS NULL) OR "
            "(kind='management_probe' AND attempt_id IS NULL AND reserved_tokens=96 AND embedding_pin IS NULL) OR "
            "(kind='embedding' AND attempt_id IS NULL AND reserved_tokens BETWEEN 1 AND 8192 AND embedding_pin IS NOT NULL)) AND "
            "expires_at>created_at AND expires_at<=created_at+interval '5 minutes' AND "
            "((status='active' AND released_at IS NULL) OR (status<>'active' AND released_at IS NOT NULL))",
            name='tenant_model_lease_state'),
        Index('tenant_model_lease_active','workspace_id','status','expires_at'),)


class ModelProviderConnection(Identity, Base):
    __tablename__ = 'model_provider_connections'
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    provider: Mapped[str] = mapped_column(String(24))
    api_key_ciphertext: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(20), default='connected')
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    model_count: Mapped[int] = mapped_column(Integer, default=0)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(80))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint('workspace_id', 'provider'),
        CheckConstraint("provider in ('openai','anthropic','gemini','openrouter')"),
        CheckConstraint("status in ('connected','error')"),
        CheckConstraint('model_count >= 0'),
        Index('one_default_model_provider_per_workspace', 'workspace_id', unique=True,
              postgresql_where=text('is_default')),
    )


class CliModelConnection(Identity, Base):
    """Local CLI identity/config only. OAuth remains in an isolated CLI profile."""
    __tablename__ = 'cli_model_connections'
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    provider: Mapped[str] = mapped_column(String(24), default='codex_cli')
    device_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    profile_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), unique=True)
    request_key: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    model: Mapped[str] = mapped_column(String(120))
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default='pending')
    binary_sha256: Mapped[str | None] = mapped_column(String(64))
    binary_version: Mapped[str | None] = mapped_column(String(64))
    runtime_image_id: Mapped[str | None] = mapped_column(String(71))
    auth_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    setup_operation_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    __table_args__ = (UniqueConstraint('id', 'workspace_id'), UniqueConstraint('workspace_id','owner_id','request_key'),
        CheckConstraint("provider='codex_cli' AND version>=1 AND status IN ('pending','connected','disconnected','error') "
            "AND (status<>'connected' OR (binary_sha256 IS NOT NULL AND binary_sha256 ~ '^[0-9a-f]{64}$' "
            "AND binary_version IS NOT NULL AND runtime_image_id IS NOT NULL AND runtime_image_id ~ '^sha256:[0-9a-f]{64}$' AND auth_checked_at IS NOT NULL))",
            name='cli_model_connection_state'),)


class CliModelDispatch(Identity, Base):
    """Extension of the native LlmAttempt ledger, never a second queue/runner."""
    __tablename__ = 'cli_model_dispatches'
    workspace_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    connection_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    attempt_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), unique=True)
    status: Mapped[str] = mapped_column(String(16), default='dispatched')
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        ForeignKeyConstraint(['connection_id','workspace_id'], ['cli_model_connections.id','cli_model_connections.workspace_id']),
        ForeignKeyConstraint(['attempt_id','workspace_id'], ['llm_attempts.id','llm_attempts.workspace_id']),
        CheckConstraint("status IN ('dispatched','completed','failed','cancelled','unknown') AND "
            "((status='dispatched' AND finished_at IS NULL) OR (status<>'dispatched' AND finished_at IS NOT NULL))", name='cli_model_dispatch_state'),
        Index('cli_one_unresolved_dispatch', 'connection_id', unique=True,
              postgresql_where=text("status IN ('dispatched','unknown')")),)


class ChatSession(Identity, Base):
    __tablename__ = 'sessions'
    chat_profile: Mapped[dict | None] = mapped_column(JSON)
    chat_revision: Mapped[int] = mapped_column(Integer, default=1, server_default=text('1'))
    engine_config: Mapped[dict | None] = mapped_column(JSON)
    engine_version: Mapped[int] = mapped_column(Integer, default=1, server_default=text('1'))
    knowledge_enabled: Mapped[bool]=mapped_column(Boolean,default=False,server_default=text('false'))
    knowledge_scope: Mapped[str]=mapped_column(String(16),default='brain',server_default=text("'brain'"))
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    title: Mapped[str] = mapped_column(String(160), default='Hội thoại mới')
    brand_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    memory_enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text('true'))
    brain_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    brain_version: Mapped[int] = mapped_column(Integer, default=1, server_default=text('1'))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    __table_args__ = (UniqueConstraint('id', 'workspace_id'),
        Index('chat_session_title_fts', text("to_tsvector('simple',title)"), postgresql_using='gin'),
        ForeignKeyConstraint(['brain_id', 'workspace_id'], ['brains.id', 'brains.workspace_id'], name='sessions_brain_workspace_fk'),
        ForeignKeyConstraint(['brand_id', 'workspace_id'], ['brands.id', 'brands.workspace_id'], name='sessions_brand_workspace_fk'),)


class Run(Identity, Base):
    channel_context: Mapped[dict | None] = mapped_column(JSON)
    __tablename__ = 'runs'
    studio_snapshot: Mapped[dict | None] = mapped_column(JSON)
    parent_run_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    engine_snapshot: Mapped[dict | None] = mapped_column(JSON)
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    session_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), index=True)
    request_key: Mapped[str] = mapped_column(String(64))
    brain_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    brain_revision: Mapped[int | None] = mapped_column(Integer)
    brain_context: Mapped[dict | None] = mapped_column(JSON)
    prompt: Mapped[str] = mapped_column(Text)
    execution_plan: Mapped[dict] = mapped_column(JSON, default=dict, server_default=text("'{}'"))
    status: Mapped[str] = mapped_column(String(20), default='queued')
    response: Mapped[str] = mapped_column(Text, default='')
    error_code: Mapped[str | None] = mapped_column(String(64))
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    next_seq: Mapped[int] = mapped_column(Integer, default=1)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        ForeignKeyConstraint(['parent_run_id', 'workspace_id'], ['runs.id', 'runs.workspace_id'], name='runs_retry_workspace_fk'),
        ForeignKeyConstraint(['brain_id', 'workspace_id'], ['brains.id', 'brains.workspace_id'], name='runs_brain_workspace_fk'),
        ForeignKeyConstraint(['session_id', 'workspace_id'], ['sessions.id', 'sessions.workspace_id']),
        UniqueConstraint('session_id', 'request_key'), UniqueConstraint('id', 'workspace_id'),
        CheckConstraint("status in ('queued','running','completed','failed','cancelled')"),
        Index('one_active_run_per_session', 'session_id', unique=True,
              postgresql_where=text("status in ('queued','running')")),
    )


class ChatCompaction(Identity, Base):
    __tablename__ = 'chat_compactions'
    workspace_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    session_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    brain_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    revision: Mapped[int] = mapped_column(Integer)
    version: Mapped[str] = mapped_column(String(32))
    source_hash: Mapped[str] = mapped_column(String(64))
    message_ids: Mapped[list] = mapped_column(JSON)
    content: Mapped[str] = mapped_column(Text)
    __table_args__ = (ForeignKeyConstraint(['session_id','workspace_id'],['sessions.id','sessions.workspace_id']),
        UniqueConstraint('session_id','revision'), CheckConstraint('revision >= 1',name='chat_compaction_revision_positive'))


class LlmAttempt(Identity, Base):
    __tablename__ = 'llm_attempts'
    workspace_id: Mapped[str] = mapped_column(Uuid(as_uuid=False),index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'),index=True)
    brain_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    session_id: Mapped[str] = mapped_column(Uuid(as_uuid=False),index=True)
    run_id: Mapped[str] = mapped_column(Uuid(as_uuid=False),index=True)
    task_attempt_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    request_key: Mapped[str] = mapped_column(String(64))
    source: Mapped[str] = mapped_column(String(32))
    provider: Mapped[str] = mapped_column(String(24))
    model: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(16),default='started')
    usage_state: Mapped[str] = mapped_column(String(16),default='unknown')
    estimated_input_tokens: Mapped[int] = mapped_column(Integer)
    reserved_output_tokens: Mapped[int] = mapped_column(Integer)
    estimated_output_tokens: Mapped[int | None] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_estimate: Mapped[Decimal | None] = mapped_column(Numeric(20,10))
    pricing: Mapped[dict | None] = mapped_column(JSON)
    trace: Mapped[dict] = mapped_column(JSON)
    ttft_ms: Mapped[int | None] = mapped_column(Integer)
    elapsed_ms: Mapped[int | None] = mapped_column(Integer)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (ForeignKeyConstraint(['run_id','workspace_id'],['runs.id','runs.workspace_id']),
        ForeignKeyConstraint(['session_id','workspace_id'],['sessions.id','sessions.workspace_id']),
        ForeignKeyConstraint(['task_attempt_id','workspace_id'],['task_attempts.id','task_attempts.workspace_id']),
        UniqueConstraint('run_id','request_key'),
        UniqueConstraint('id','workspace_id',name='llm_attempt_workspace_identity'),
        CheckConstraint("status in ('started','completed','failed','cancelled')",name='llm_attempt_status'),
        CheckConstraint("usage_state in ('unknown','reported','partial')",name='llm_attempt_usage_state'),
        CheckConstraint('estimated_input_tokens >= 0 AND reserved_output_tokens >= 0',name='llm_attempt_reservation_positive'))


class Message(Identity, Base):
    __tablename__ = 'messages'
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    session_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), index=True)
    run_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default='completed')
    __table_args__ = (
        Index('chat_message_content_fts', text("to_tsvector('simple',content)"), postgresql_using='gin'),
        ForeignKeyConstraint(['session_id', 'workspace_id'], ['sessions.id', 'sessions.workspace_id']),
        ForeignKeyConstraint(['run_id', 'workspace_id'], ['runs.id', 'runs.workspace_id']),
        UniqueConstraint('run_id', 'role'), CheckConstraint("role in ('user','assistant')"),
    )


class RunEvent(Base):
    __tablename__ = 'run_events'
    run_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    seq: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String(64))
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (ForeignKeyConstraint(['run_id', 'workspace_id'], ['runs.id', 'runs.workspace_id']),)


class AgentRun(Identity, Base):
    __tablename__ = 'agent_runs'
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    run_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    step_index: Mapped[int] = mapped_column(Integer, default=0, server_default=text('0'))
    task: Mapped[str] = mapped_column(Text, default='', server_default=text("''"))
    output: Mapped[str] = mapped_column(Text, default='', server_default=text("''"))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    agent_key: Mapped[str] = mapped_column(String(64))
    prompt_version: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default='running')
    usage: Mapped[dict] = mapped_column(JSON, default=dict)
    __table_args__ = (ForeignKeyConstraint(['run_id', 'workspace_id'], ['runs.id', 'runs.workspace_id']),
                     UniqueConstraint('run_id', 'step_index', name='agent_runs_run_step_key'),)


class Brand(Identity, Base):
    __tablename__ = 'brands'
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    name: Mapped[str] = mapped_column(String(120))
    __table_args__ = (UniqueConstraint('id', 'workspace_id'), UniqueConstraint('workspace_id', 'name'))


class Brain(Identity, Base):
    __tablename__ = 'brains'
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    brand_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    name: Mapped[str] = mapped_column(String(120))
    legacy_default: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text('false'))
    revision: Mapped[int] = mapped_column(Integer, default=1, server_default=text('1'))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint('id', 'workspace_id'),
        ForeignKeyConstraint(['brand_id', 'workspace_id'], ['brands.id', 'brands.workspace_id'], name='brains_brand_workspace_fk'),
        CheckConstraint('revision >= 1', name='brains_revision_positive'),
        Index('brains_legacy_scope_unique', 'workspace_id', 'owner_id', 'brand_id', unique=True,
              postgresql_nulls_not_distinct=True, postgresql_where=text('legacy_default')),
    )


class BrainMember(Base):
    __tablename__ = 'brain_members'
    brain_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), primary_key=True)
    role: Mapped[str] = mapped_column(String(16))
    __table_args__ = (
        ForeignKeyConstraint(['brain_id', 'workspace_id'], ['brains.id', 'brains.workspace_id'], name='brain_members_brain_workspace_fk'),
        ForeignKeyConstraint(['workspace_id', 'user_id'], ['workspace_members.workspace_id', 'workspace_members.user_id'], name='brain_members_workspace_member_fk'),
        CheckConstraint("role in ('reader','editor')", name='brain_members_role_valid'),
    )


class BrainFile(Identity, Base):
    __tablename__ = 'brain_files'
    brain_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), index=True)
    workspace_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    created_by: Mapped[str] = mapped_column(ForeignKey('users.id'))
    name: Mapped[str] = mapped_column(String(160))
    mime: Mapped[str] = mapped_column(String(32))
    size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    content: Mapped[bytes] = mapped_column(LargeBinary)
    revision: Mapped[int] = mapped_column(Integer, default=1, server_default=text('1'))
    trashed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint('id','brain_id','workspace_id',name='brain_files_origin_scope_unique'),
        ForeignKeyConstraint(['brain_id','workspace_id'],['brains.id','brains.workspace_id'],name='brain_files_brain_workspace_fk'),
        CheckConstraint("mime in ('text/plain','text/markdown')",name='brain_files_mime_valid'),
        CheckConstraint('size >= 0 AND size <= 1048576 AND octet_length(content) = size',name='brain_files_size_valid'),
        CheckConstraint('revision >= 1',name='brain_files_revision_positive'),
    )


class BrainNote(Identity, Base):
    __tablename__='brain_notes'
    brain_id: Mapped[str]=mapped_column(Uuid(as_uuid=False),index=True)
    workspace_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    title: Mapped[str]=mapped_column(String(120))
    revision: Mapped[int]=mapped_column(Integer,default=1,server_default=text('1'))
    content_version: Mapped[int]=mapped_column(Integer,default=1,server_default=text('1'))
    trashed_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    __table_args__=(UniqueConstraint('id','brain_id','workspace_id',name='brain_notes_origin_scope_unique'),
        ForeignKeyConstraint(['brain_id','workspace_id'],['brains.id','brains.workspace_id'],name='brain_notes_brain_workspace_fk'),
        CheckConstraint('revision >= 1 AND content_version >= 1',name='brain_notes_versions_positive'))


class BrainNoteVersion(Base):
    __tablename__='brain_note_versions'
    note_id: Mapped[str]=mapped_column(ForeignKey('brain_notes.id'),primary_key=True)
    version: Mapped[int]=mapped_column(Integer,primary_key=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    created_by: Mapped[str]=mapped_column(ForeignKey('users.id'))
    content: Mapped[str]=mapped_column(Text)
    sha256: Mapped[str]=mapped_column(String(64))
    size: Mapped[int]=mapped_column(Integer)
    __table_args__=(CheckConstraint('version >= 1 AND size >= 0 AND size <= 262144 AND octet_length(content) = size',name='brain_note_version_valid'),)


class BrainImportPlan(Identity, Base):
    __tablename__='brain_import_plans'
    brain_id: Mapped[str]=mapped_column(Uuid(as_uuid=False),index=True)
    workspace_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    actor_id: Mapped[str]=mapped_column(ForeignKey('users.id'),index=True)
    brain_revision: Mapped[int]=mapped_column(Integer)
    archive: Mapped[bytes]=mapped_column(LargeBinary)
    sha256: Mapped[str]=mapped_column(String(64))
    expires_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    __table_args__=(ForeignKeyConstraint(['brain_id','workspace_id'],['brains.id','brains.workspace_id'],name='brain_import_plans_brain_workspace_fk'),
        CheckConstraint('brain_revision >= 1 AND octet_length(archive) <= 12582912',name='brain_import_plan_valid'))


class KnowledgeSource(Identity, Base):
    __tablename__='knowledge_sources'
    brain_id: Mapped[str]=mapped_column(Uuid(as_uuid=False),index=True)
    workspace_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    file_id: Mapped[str|None]=mapped_column(Uuid(as_uuid=False))
    note_id: Mapped[str|None]=mapped_column(Uuid(as_uuid=False))
    created_by: Mapped[str]=mapped_column(ForeignKey('users.id'))
    title: Mapped[str]=mapped_column(String(160))
    current_version: Mapped[int]=mapped_column(Integer,default=1,server_default=text('1'))
    revision: Mapped[int]=mapped_column(Integer,default=1,server_default=text('1'))
    archived_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    __table_args__=(
        UniqueConstraint('id','brain_id','workspace_id',name='knowledge_sources_scope_unique'),
        UniqueConstraint('brain_id','file_id',name='knowledge_sources_file_unique'),
        UniqueConstraint('brain_id','note_id',name='knowledge_sources_note_unique'),
        ForeignKeyConstraint(['brain_id','workspace_id'],['brains.id','brains.workspace_id'],name='knowledge_sources_brain_fk'),
        ForeignKeyConstraint(['file_id','brain_id','workspace_id'],['brain_files.id','brain_files.brain_id','brain_files.workspace_id'],name='knowledge_sources_file_scope_fk'),
        ForeignKeyConstraint(['note_id','brain_id','workspace_id'],['brain_notes.id','brain_notes.brain_id','brain_notes.workspace_id'],name='knowledge_sources_note_scope_fk'),
        CheckConstraint('(file_id IS NULL) <> (note_id IS NULL)',name='knowledge_sources_one_origin'),
        CheckConstraint('current_version >= 1 AND revision >= 1',name='knowledge_sources_versions_positive'))


class KnowledgeVersion(Identity, Base):
    __tablename__='knowledge_versions'
    source_id: Mapped[str]=mapped_column(Uuid(as_uuid=False),index=True)
    brain_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    workspace_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    number: Mapped[int]=mapped_column(Integer)
    origin_version: Mapped[int]=mapped_column(Integer)
    source_sha256: Mapped[str]=mapped_column(String(64))
    source_size: Mapped[int]=mapped_column(Integer)
    title: Mapped[str]=mapped_column(String(160))
    created_by: Mapped[str]=mapped_column(ForeignKey('users.id'))
    __table_args__=(
        UniqueConstraint('id','brain_id','workspace_id',name='knowledge_versions_scope_unique'),
        UniqueConstraint('source_id','number',name='knowledge_versions_number_unique'),
        UniqueConstraint('source_id','source_sha256',name='knowledge_versions_content_unique'),
        ForeignKeyConstraint(['source_id','brain_id','workspace_id'],['knowledge_sources.id','knowledge_sources.brain_id','knowledge_sources.workspace_id'],name='knowledge_versions_source_scope_fk'),
        CheckConstraint('number >= 1 AND origin_version >= 1 AND source_size >= 0 AND source_size <= 1048576 AND length(source_sha256)=64',name='knowledge_versions_valid'))


class KnowledgeIngestion(Identity, Base):
    __tablename__='knowledge_ingestion_jobs'
    version_id: Mapped[str]=mapped_column(Uuid(as_uuid=False),index=True)
    brain_id: Mapped[str]=mapped_column(Uuid(as_uuid=False),index=True)
    workspace_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    actor_id: Mapped[str]=mapped_column(ForeignKey('users.id'))
    parser_version: Mapped[str]=mapped_column(String(32))
    status: Mapped[str]=mapped_column(String(16),default='queued',server_default=text("'queued'"))
    attempts: Mapped[int]=mapped_column(Integer,default=0,server_default=text('0'))
    claim_id: Mapped[str|None]=mapped_column(Uuid(as_uuid=False))
    locked_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    error_code: Mapped[str|None]=mapped_column(String(64))
    parsed_text: Mapped[str|None]=mapped_column(Text)
    parsed_sha256: Mapped[str|None]=mapped_column(String(64))
    line_count: Mapped[int|None]=mapped_column(Integer)
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    __table_args__=(
        UniqueConstraint('version_id','parser_version',name='knowledge_ingestion_parser_unique'),
        ForeignKeyConstraint(['version_id','brain_id','workspace_id'],['knowledge_versions.id','knowledge_versions.brain_id','knowledge_versions.workspace_id'],name='knowledge_ingestion_version_scope_fk'),
        CheckConstraint("status in ('queued','running','completed','failed') AND attempts >= 0 AND attempts <= 3",name='knowledge_ingestion_status_valid'),
        CheckConstraint("(status = 'completed' AND parsed_text IS NOT NULL AND parsed_sha256 IS NOT NULL AND line_count IS NOT NULL AND line_count >= 1 AND length(parsed_sha256)=64 AND octet_length(parsed_text) <= 1048576) OR (status <> 'completed' AND parsed_text IS NULL AND parsed_sha256 IS NULL AND line_count IS NULL)",name='knowledge_ingestion_output_valid'))


class KnowledgeChunk(Identity, Base):
    __tablename__='knowledge_chunks'
    version_id: Mapped[str]=mapped_column(Uuid(as_uuid=False),index=True)
    brain_id: Mapped[str]=mapped_column(Uuid(as_uuid=False),index=True)
    workspace_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    chunker_version: Mapped[str]=mapped_column(String(32))
    ordinal: Mapped[int]=mapped_column(Integer)
    start_char: Mapped[int]=mapped_column(Integer)
    end_char: Mapped[int]=mapped_column(Integer)
    start_line: Mapped[int]=mapped_column(Integer)
    end_line: Mapped[int]=mapped_column(Integer)
    content: Mapped[str]=mapped_column(Text)
    sha256: Mapped[str]=mapped_column(String(64))
    embedding: Mapped[list[float]|None]=mapped_column(Vector(768))
    embedding_model: Mapped[str|None]=mapped_column(String(120))
    embedding_binding: Mapped[str|None]=mapped_column(String(64))
    __table_args__=(UniqueConstraint('version_id','chunker_version','ordinal',name='knowledge_chunks_dedupe'),
        ForeignKeyConstraint(['version_id','brain_id','workspace_id'],['knowledge_versions.id','knowledge_versions.brain_id','knowledge_versions.workspace_id'],name='knowledge_chunks_scope_fk'),
        CheckConstraint('ordinal >= 0 AND start_char >= 0 AND end_char > start_char AND length(content)=end_char-start_char AND length(content)<=1800 AND start_line>=1 AND end_line>=start_line AND length(sha256)=64',name='knowledge_chunks_valid'),
        CheckConstraint("embedding_binding IS NULL OR embedding_binding ~ '^[0-9a-f]{64}$'",name='knowledge_embedding_binding_valid'))


class KnowledgeIndexJob(Identity, Base):
    __tablename__='knowledge_index_jobs'
    version_id: Mapped[str]=mapped_column(Uuid(as_uuid=False),index=True)
    brain_id: Mapped[str]=mapped_column(Uuid(as_uuid=False),index=True)
    workspace_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    actor_id: Mapped[str]=mapped_column(ForeignKey('users.id'))
    chunker_version: Mapped[str]=mapped_column(String(32))
    embedding_model: Mapped[str]=mapped_column(String(120))
    embedding_engine: Mapped[dict|None]=mapped_column(JSONB(none_as_null=True))
    embedding_generation: Mapped[int]=mapped_column(Integer,default=0,server_default=text('0'))
    status: Mapped[str]=mapped_column(String(16),default='queued',server_default=text("'queued'"))
    embedding_status: Mapped[str]=mapped_column(String(16),default='pending',server_default=text("'pending'"))
    attempts: Mapped[int]=mapped_column(Integer,default=0,server_default=text('0'))
    claim_id: Mapped[str|None]=mapped_column(Uuid(as_uuid=False))
    locked_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    error_code: Mapped[str|None]=mapped_column(String(64))
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    __table_args__=(UniqueConstraint('version_id','chunker_version','embedding_model',name='knowledge_index_jobs_dedupe'),
        ForeignKeyConstraint(['version_id','brain_id','workspace_id'],['knowledge_versions.id','knowledge_versions.brain_id','knowledge_versions.workspace_id'],name='knowledge_index_jobs_scope_fk'),
        CheckConstraint("status in ('queued','running','completed','failed') AND embedding_status in ('pending','ready','partial','offline','disabled') AND attempts BETWEEN 0 AND 3",name='knowledge_index_jobs_valid'),
        CheckConstraint("embedding_generation>=0 AND (embedding_engine IS NULL OR (jsonb_typeof(embedding_engine)='object' AND embedding_engine->>'version'='1' AND embedding_engine->>'model'=embedding_model AND jsonb_typeof(embedding_engine->'url')='string'))",name='knowledge_index_embedding_pin_valid'))


class KnowledgeWiki(Identity, Base):
    __tablename__='knowledge_wikis'
    brain_id: Mapped[str]=mapped_column(Uuid(as_uuid=False),index=True)
    workspace_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    created_by: Mapped[str]=mapped_column(ForeignKey('users.id'))
    current_version: Mapped[int]=mapped_column(Integer,default=1,server_default=text('1'))
    published_version: Mapped[int|None]=mapped_column(Integer)
    revision: Mapped[int]=mapped_column(Integer,default=1,server_default=text('1'))
    archived_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    __table_args__=(UniqueConstraint('id','brain_id','workspace_id',name='knowledge_wikis_scope_unique'),
        ForeignKeyConstraint(['brain_id','workspace_id'],['brains.id','brains.workspace_id'],name='knowledge_wikis_scope_fk'),
        CheckConstraint('current_version >= 1 AND revision >= 1 AND (published_version IS NULL OR published_version>=1)',name='knowledge_wikis_valid'))


class KnowledgeWikiVersion(Base):
    __tablename__='knowledge_wiki_versions'
    wiki_id: Mapped[str]=mapped_column(Uuid(as_uuid=False),primary_key=True)
    number: Mapped[int]=mapped_column(Integer,primary_key=True)
    brain_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    workspace_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    title: Mapped[str]=mapped_column(String(120))
    content: Mapped[str]=mapped_column(Text)
    citations: Mapped[list]=mapped_column(JSON)
    sha256: Mapped[str]=mapped_column(String(64))
    created_by: Mapped[str]=mapped_column(ForeignKey('users.id'))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    __table_args__=(ForeignKeyConstraint(['wiki_id','brain_id','workspace_id'],['knowledge_wikis.id','knowledge_wikis.brain_id','knowledge_wikis.workspace_id'],name='knowledge_wiki_versions_scope_fk'),
        CheckConstraint('number>=1 AND octet_length(content)<=65536 AND length(sha256)=64',name='knowledge_wiki_versions_valid'))


class KnowledgeWikiEvent(Identity, Base):
    __tablename__='knowledge_wiki_events'
    wiki_id: Mapped[str]=mapped_column(Uuid(as_uuid=False),index=True)
    brain_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    workspace_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    actor_id: Mapped[str]=mapped_column(ForeignKey('users.id'))
    action: Mapped[str]=mapped_column(String(16))
    from_version: Mapped[int|None]=mapped_column(Integer)
    to_version: Mapped[int]=mapped_column(Integer)
    __table_args__=(ForeignKeyConstraint(['wiki_id','brain_id','workspace_id'],['knowledge_wikis.id','knowledge_wikis.brain_id','knowledge_wikis.workspace_id'],name='knowledge_wiki_events_scope_fk'),
        CheckConstraint("action in ('draft','edit','publish','revert') AND to_version>=1",name='knowledge_wiki_events_valid'))


class SessionAttachment(Identity, Base):
    __tablename__='session_attachments'
    session_id: Mapped[str]=mapped_column(Uuid(as_uuid=False),index=True)
    brain_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    workspace_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    file_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    added_by: Mapped[str]=mapped_column(ForeignKey('users.id'))
    removed_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    __table_args__=(UniqueConstraint('session_id','brain_id','file_id',name='session_attachments_unique'),
        ForeignKeyConstraint(['session_id','workspace_id'],['sessions.id','sessions.workspace_id'],name='session_attachments_session_fk'),
        ForeignKeyConstraint(['file_id','brain_id','workspace_id'],['brain_files.id','brain_files.brain_id','brain_files.workspace_id'],name='session_attachments_origin_fk'))


class RunKnowledge(Identity, Base):
    __tablename__='run_knowledge'
    run_id: Mapped[str]=mapped_column(Uuid(as_uuid=False),unique=True)
    brain_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    workspace_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    evidence: Mapped[list]=mapped_column(JSON)
    status: Mapped[str]=mapped_column(String(32))
    mode: Mapped[str]=mapped_column(String(32))
    __table_args__=(ForeignKeyConstraint(['run_id','workspace_id'],['runs.id','runs.workspace_id'],name='run_knowledge_run_fk'),
        ForeignKeyConstraint(['brain_id','workspace_id'],['brains.id','brains.workspace_id'],name='run_knowledge_brain_fk'),
        CheckConstraint("status in ('matched','insufficient_evidence','needs_review')",name='run_knowledge_status_valid'))


class Memory(Identity, Base):
    __tablename__ = 'memories'
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    brand_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    key: Mapped[str] = mapped_column(String(120))
    value: Mapped[str] = mapped_column(Text)
    fingerprint: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default='active')
    importance: Mapped[int] = mapped_column(Integer, default=3)
    source_run_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    embedding: Mapped[list[float] | None] = mapped_column(Vector(768))
    embedding_model: Mapped[str | None] = mapped_column(String(120))
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        ForeignKeyConstraint(['brand_id', 'workspace_id'], ['brands.id', 'brands.workspace_id']),
        ForeignKeyConstraint(['source_run_id', 'workspace_id'], ['runs.id', 'runs.workspace_id']),
        CheckConstraint("status in ('active','pending','superseded','deleted')"),
        CheckConstraint('importance between 1 and 5'),
        Index('memory_content_unique', 'workspace_id', 'user_id', 'brand_id', 'fingerprint',
              unique=True, postgresql_nulls_not_distinct=True),
        Index('memory_active_key_unique', 'workspace_id', 'user_id', 'brand_id', 'key',
              unique=True, postgresql_nulls_not_distinct=True, postgresql_where=text("status = 'active'")),
    )


class MemoryJob(Base):
    __tablename__ = 'memory_jobs'
    run_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    status: Mapped[str] = mapped_column(String(20), default='queued')
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    extracted: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        ForeignKeyConstraint(['run_id', 'workspace_id'], ['runs.id', 'runs.workspace_id']),
        CheckConstraint("status in ('queued','running','completed','failed')"),
    )


class ToolCall(Identity, Base):
    __tablename__ = 'tool_calls'
    resource_admitted_at: Mapped[datetime | None]=mapped_column(DateTime(timezone=True))
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    run_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    request_key: Mapped[str] = mapped_column(String(64))
    fingerprint: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(64))
    agent_key: Mapped[str] = mapped_column(String(64))
    arguments: Mapped[dict] = mapped_column(JSON)
    connector_snapshot: Mapped[dict | None] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(24))
    version: Mapped[int] = mapped_column(Integer, default=1)
    approved_by: Mapped[str | None] = mapped_column(ForeignKey('users.id'))
    approval_input_hash: Mapped[str | None] = mapped_column(String(64))
    error_code: Mapped[str | None] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (ForeignKeyConstraint(['run_id','workspace_id'],['runs.id','runs.workspace_id']),
        UniqueConstraint('id','workspace_id',name='tool_calls_event_scope'),
        UniqueConstraint('run_id','request_key',name='tool_calls_run_request_key'),
        CheckConstraint("status in ('pending','queued','running','completed','failed','rejected','cancelled','unknown','expired')"),)


class ToolAudit(Identity, Base):
    __tablename__ = 'tool_audits'
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    run_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), index=True)
    tool_call_id: Mapped[str | None] = mapped_column(ForeignKey('tool_calls.id'))
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    event: Mapped[str] = mapped_column(String(64))
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    __table_args__ = (ForeignKeyConstraint(['run_id','workspace_id'],['runs.id','runs.workspace_id']),)


class TelegramConnection(Identity, Base):
    """Credential-free namespace; staged storage never grants transport authority."""
    __tablename__ = 'telegram_connections'
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'))
    owner_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    kind: Mapped[str] = mapped_column(String(16), default='native')
    bot_user_id: Mapped[str | None] = mapped_column(String(24), unique=True)
    status: Mapped[str] = mapped_column(String(16), default='staged')
    version: Mapped[int] = mapped_column(Integer, default=1)
    __table_args__ = (UniqueConstraint('id','workspace_id'),
        CheckConstraint("kind IN ('legacy','native') AND status IN ('staged','revoked') AND version>=1"),
        CheckConstraint("(kind='legacy' OR bot_user_id IS NOT NULL) AND (bot_user_id IS NULL OR bot_user_id ~ '^[1-9][0-9]{0,15}$')"),
        Index('telegram_legacy_namespace_once','kind',unique=True,postgresql_where=text("kind='legacy'")))


class TelegramBotIdentity(Identity, Base):
    """Verified identity journal; never an activation or permission grant."""
    __tablename__='telegram_bot_identities'
    workspace_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    connection_id: Mapped[str]=mapped_column(Uuid(as_uuid=False),unique=True)
    owner_id: Mapped[str]=mapped_column(ForeignKey('users.id'))
    connection_version: Mapped[int]=mapped_column(Integer)
    bot_user_id: Mapped[str]=mapped_column(String(24),unique=True)
    request_key: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    content_hash: Mapped[str]=mapped_column(String(64))
    __table_args__=(ForeignKeyConstraint(['connection_id','workspace_id'],['telegram_connections.id','telegram_connections.workspace_id']),
        UniqueConstraint('workspace_id','owner_id','request_key'),
        CheckConstraint("connection_version>=1 AND bot_user_id ~ '^[1-9][0-9]{0,15}$' AND length(content_hash)=64",name='telegram_bot_identity_state'),)


class TelegramRuntimeProfile(Identity, Base):
    """Disabled durable credential generation, never transport authority."""
    __tablename__='telegram_runtime_profiles'
    workspace_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    connection_id: Mapped[str]=mapped_column(Uuid(as_uuid=False),unique=True)
    connection_version: Mapped[int]=mapped_column(Integer)
    generation: Mapped[int]=mapped_column(Integer,default=1)
    status: Mapped[str]=mapped_column(String(16),default='disabled')
    token_ciphertext: Mapped[str | None]=mapped_column(Text)
    next_offset: Mapped[int]=mapped_column(BigInteger,default=0)
    cooldown_until: Mapped[datetime | None]=mapped_column(DateTime(timezone=True))
    transport_mode: Mapped[str]=mapped_column(String(16),default='polling',server_default='polling')
    webhook_hash: Mapped[str | None]=mapped_column(String(64))
    cursor_epoch: Mapped[int]=mapped_column(Integer,default=0,server_default='0')
    cursor_touched_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,server_default=text('now()'))
    __table_args__=(ForeignKeyConstraint(['connection_id','workspace_id'],['telegram_connections.id','telegram_connections.workspace_id']),
        CheckConstraint("connection_version>=1 AND generation>=1 AND next_offset>=0 AND ((status IN ('disabled','enabled') AND token_ciphertext IS NOT NULL AND length(token_ciphertext) BETWEEN 1 AND 16384) OR (status='revoked' AND token_ciphertext IS NULL))",name='telegram_profile_state'),
        CheckConstraint("cursor_epoch>=0 AND transport_mode IN ('polling','webhook') AND (transport_mode='polling' AND webhook_hash IS NULL OR transport_mode='webhook' AND webhook_hash IS NOT NULL AND length(webhook_hash)=64)",name='telegram_transport_state'))


class TelegramRuntimeAudit(Identity, Base):
    __tablename__='telegram_runtime_audits'
    workspace_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    connection_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    actor_id: Mapped[str]=mapped_column(ForeignKey('users.id'))
    request_key: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    generation: Mapped[int]=mapped_column(Integer)
    action: Mapped[str]=mapped_column(String(16))
    content_hash: Mapped[str]=mapped_column(String(64))
    __table_args__=(ForeignKeyConstraint(['connection_id','workspace_id'],['telegram_connections.id','telegram_connections.workspace_id']),
        UniqueConstraint('connection_id','generation'),UniqueConstraint('workspace_id','actor_id','request_key'),
        CheckConstraint("length(content_hash)=64 AND ((generation=1 AND action='stored') OR (generation>1 AND action IN ('rotated','revoked','enabled','disabled')))",name='telegram_runtime_audit_state'),)


class TelegramRuntimeReceipt(Identity, Base):
    """Body-free quarantine evidence; not an admitted run or a replay queue."""
    __tablename__='telegram_runtime_receipts'
    workspace_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    connection_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    generation: Mapped[int]=mapped_column(Integer)
    update_id: Mapped[int]=mapped_column(BigInteger)
    cursor_epoch: Mapped[int]=mapped_column(Integer,default=0,server_default='0')
    content_hash: Mapped[str]=mapped_column(String(64))
    reason: Mapped[str]=mapped_column(String(16))
    inbound_id: Mapped[str | None]=mapped_column(Uuid(as_uuid=False))
    __table_args__=(ForeignKeyConstraint(['connection_id','workspace_id'],['telegram_connections.id','telegram_connections.workspace_id']),
        UniqueConstraint('connection_id','cursor_epoch','update_id'),
        ForeignKeyConstraint(['inbound_id','workspace_id'],['channel_inbounds.id','channel_inbounds.workspace_id']),
        CheckConstraint("generation>=1 AND update_id>=0 AND update_id<9223372036854775807 AND length(content_hash)=64 AND ((reason='inbound' AND inbound_id IS NOT NULL) OR (reason IN ('unsupported','unlinked','malformed','blocked') AND inbound_id IS NULL))",name='telegram_runtime_receipt_state'),)


class TelegramPairing(Identity, Base):
    """One-use hashed challenge, Telegram observation, then authenticated confirmation."""
    __tablename__='telegram_pairings'
    workspace_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    connection_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    user_id: Mapped[str]=mapped_column(ForeignKey('users.id'))
    generation: Mapped[int]=mapped_column(Integer)
    code_hash: Mapped[str]=mapped_column(String(64),unique=True)
    expected_user_id: Mapped[str]=mapped_column(String(24))
    observed_user_id: Mapped[str | None]=mapped_column(String(24))
    brain_id: Mapped[str | None]=mapped_column(Uuid(as_uuid=False))
    status: Mapped[str]=mapped_column(String(16),default='pending')
    expires_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    __table_args__=(ForeignKeyConstraint(['connection_id','workspace_id'],['telegram_connections.id','telegram_connections.workspace_id']),
        ForeignKeyConstraint(['brain_id','workspace_id'],['brains.id','brains.workspace_id']),
        CheckConstraint("generation>=1 AND length(code_hash)=64 AND expected_user_id ~ '^[1-9][0-9]{0,15}$' AND status IN ('pending','observed','confirmed','revoked')",name='telegram_pairing_state'))


class TelegramLegacyMapping(Identity, Base):
    __tablename__='telegram_legacy_mappings'
    workspace_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    connection_id: Mapped[str]=mapped_column(Uuid(as_uuid=False),unique=True)
    owner_id: Mapped[str]=mapped_column(ForeignKey('users.id'))
    request_key: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    preview_hash: Mapped[str]=mapped_column(String(64))
    content_hash: Mapped[str]=mapped_column(String(64))
    snapshot: Mapped[dict]=mapped_column(JSONB)
    generation: Mapped[int]=mapped_column(Integer,default=1)
    __table_args__=(UniqueConstraint('id','workspace_id'),UniqueConstraint('workspace_id','owner_id','request_key'),
        ForeignKeyConstraint(['connection_id','workspace_id'],['telegram_connections.id','telegram_connections.workspace_id']),
        CheckConstraint("generation=1 AND length(preview_hash)=64 AND length(content_hash)=64 AND jsonb_typeof(snapshot)='object'"))


class TelegramLegacyPeerMap(Identity, Base):
    __tablename__='telegram_legacy_peer_maps'
    workspace_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    mapping_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    source_peer_id: Mapped[str]=mapped_column(ForeignKey('telegram_peers.id'),unique=True)
    peer_id: Mapped[str]=mapped_column(ForeignKey('telegram_peers.id'),unique=True)
    source_binding_id: Mapped[str | None]=mapped_column(ForeignKey('channel_bindings.id'))
    binding_id: Mapped[str | None]=mapped_column(ForeignKey('channel_bindings.id'))
    __table_args__=(ForeignKeyConstraint(['mapping_id','workspace_id'],['telegram_legacy_mappings.id','telegram_legacy_mappings.workspace_id']),
        CheckConstraint('(source_binding_id IS NULL)=(binding_id IS NULL)'))


class TelegramLegacyMappingAudit(Identity, Base):
    __tablename__='telegram_legacy_mapping_audits'
    workspace_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    mapping_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    actor_id: Mapped[str]=mapped_column(ForeignKey('users.id'))
    request_key: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    content_hash: Mapped[str]=mapped_column(String(64))
    action: Mapped[str]=mapped_column(String(16))
    version: Mapped[int]=mapped_column(Integer)
    __table_args__=(ForeignKeyConstraint(['mapping_id','workspace_id'],['telegram_legacy_mappings.id','telegram_legacy_mappings.workspace_id']),
        UniqueConstraint('mapping_id','version'),UniqueConstraint('workspace_id','actor_id','request_key'),
        CheckConstraint("length(content_hash)=64 AND ((action='apply' AND version=1) OR (action='revoke' AND version=2))"))


class TelegramPeer(Identity, Base):
    __tablename__ = 'telegram_peers'
    connection_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    telegram_user_id: Mapped[str] = mapped_column(String(24))
    chat_id: Mapped[str] = mapped_column(String(24))
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'))
    session_id: Mapped[str | None] = mapped_column(ForeignKey('sessions.id'))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (ForeignKeyConstraint(['connection_id','workspace_id'],['telegram_connections.id','telegram_connections.workspace_id']),
        UniqueConstraint('connection_id','telegram_user_id'),UniqueConstraint('connection_id','chat_id'),
        Index('telegram_legacy_user_once','telegram_user_id',unique=True,postgresql_where=text('connection_id IS NULL')),
        Index('telegram_legacy_chat_once','chat_id',unique=True,postgresql_where=text('connection_id IS NULL')))


class TelegramUpdate(Identity, Base):
    __tablename__ = 'telegram_updates'
    connection_id: Mapped[str | None] = mapped_column(ForeignKey('telegram_connections.id'))
    update_id: Mapped[int] = mapped_column(BigInteger)
    peer_id: Mapped[str] = mapped_column(ForeignKey('telegram_peers.id'))
    run_id: Mapped[str | None] = mapped_column(ForeignKey('runs.id'), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint('connection_id','update_id'),
        Index('telegram_legacy_update_once','update_id',unique=True,postgresql_where=text('connection_id IS NULL')))


class TelegramDelivery(Identity, Base):
    __tablename__ = 'telegram_deliveries'
    peer_id: Mapped[str] = mapped_column(ForeignKey('telegram_peers.id'))
    connection_id: Mapped[str | None] = mapped_column(ForeignKey('telegram_connections.id'))
    dedup_key: Mapped[str] = mapped_column(String(100))
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default='queued')
    message_id: Mapped[str | None] = mapped_column(String(24))
    error_code: Mapped[str | None] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (CheckConstraint("status in ('queued','sending','sent','failed','unknown','cancelled')"),
        UniqueConstraint('connection_id','dedup_key'),
        Index('telegram_legacy_delivery_once','dedup_key',unique=True,postgresql_where=text('connection_id IS NULL')))


class AdsAppConfig(Base):
    __tablename__ = 'ads_app_configs'
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'),primary_key=True)
    provider: Mapped[str] = mapped_column(String(16),primary_key=True)
    mode: Mapped[str] = mapped_column(String(16))
    revision: Mapped[int] = mapped_column(Integer)
    credential_ciphertext: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=text('now()'))
    __table_args__=(CheckConstraint("provider IN ('meta','google') AND revision>=1 AND (mode='managed' AND credential_ciphertext IS NULL OR mode='byo' AND credential_ciphertext IS NOT NULL)",name='ads_app_config_state'),)


class AdsAppAudit(Identity, Base):
    __tablename__ = 'ads_app_audits'
    workspace_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    provider: Mapped[str] = mapped_column(String(16))
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    revision: Mapped[int] = mapped_column(Integer)
    mode: Mapped[str] = mapped_column(String(16))
    __table_args__=(ForeignKeyConstraint(['workspace_id','provider'],['ads_app_configs.workspace_id','ads_app_configs.provider']),
        UniqueConstraint('workspace_id','provider','revision'),CheckConstraint("revision>=1 AND mode IN ('managed','byo')",name='ads_app_audit_state'))


class MetaConnection(Identity, Base):
    __tablename__ = 'meta_connections'
    app_binding: Mapped[str | None] = mapped_column(String(64))
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    remote_user_id: Mapped[str | None] = mapped_column(String(64))
    token_ciphertext: Mapped[str | None] = mapped_column(Text)
    scopes: Mapped[list] = mapped_column(JSON, default=list)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), default='disconnected')
    version: Mapped[int] = mapped_column(Integer, default=1)
    __table_args__ = (UniqueConstraint('workspace_id','user_id'),)


class MetaOAuthState(Base):
    __tablename__ = 'meta_oauth_states'
    app_binding: Mapped[str | None] = mapped_column(String(64))
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    connection_id: Mapped[str] = mapped_column(ForeignKey('meta_connections.id'))
    browser_digest: Mapped[str] = mapped_column(String(64))
    connection_version: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used: Mapped[bool] = mapped_column(Boolean, default=False)


class MetaSyncJob(Identity, Base):
    __tablename__ = 'meta_sync_jobs'
    resource_admitted_at: Mapped[datetime | None]=mapped_column(DateTime(timezone=True))
    connection_id: Mapped[str] = mapped_column(ForeignKey('meta_connections.id'), index=True)
    connection_version: Mapped[int] = mapped_column(Integer)
    api_version: Mapped[str] = mapped_column(String(16))
    authority_pin: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))
    warehouse: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text('false'))
    granularity: Mapped[str] = mapped_column(String(8), default='daily', server_default='daily')
    request_key: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(16))
    account_id: Mapped[str | None] = mapped_column(String(64))
    since: Mapped[str | None] = mapped_column(String(10))
    until: Mapped[str | None] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20), default='queued')
    error_code: Mapped[str | None] = mapped_column(String(64))
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint('connection_id','request_key'),
        CheckConstraint("status in ('queued','running','completed','failed','cancelled')"),
        CheckConstraint("kind in ('accounts','historical')"),)


class MetaSnapshot(Identity, Base):
    __tablename__ = 'meta_snapshots'
    job_id: Mapped[str] = mapped_column(ForeignKey('meta_sync_jobs.id'), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    remote_key: Mapped[str] = mapped_column(String(180))
    payload: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint('job_id','kind','remote_key'),)


class GoogleAdsConnection(Identity, Base):
    __tablename__ = 'google_ads_connections'
    app_binding: Mapped[str | None] = mapped_column(String(64))
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    refresh_token_ciphertext: Mapped[str | None] = mapped_column(Text)
    scopes: Mapped[list] = mapped_column(JSON, default=list)
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), default='disconnected')
    version: Mapped[int] = mapped_column(Integer, default=1)
    __table_args__ = (UniqueConstraint('workspace_id','user_id'),CheckConstraint("status in ('disconnected','connected','expired')"))


class GoogleAdsOAuthState(Base):
    __tablename__ = 'google_ads_oauth_states'
    app_binding: Mapped[str | None] = mapped_column(String(64))
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    connection_id: Mapped[str] = mapped_column(ForeignKey('google_ads_connections.id'))
    browser_digest: Mapped[str] = mapped_column(String(64))
    connection_version: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used: Mapped[bool] = mapped_column(Boolean, default=False)


class GoogleAdsSyncJob(Identity, Base):
    __tablename__ = 'google_ads_sync_jobs'
    resource_admitted_at: Mapped[datetime | None]=mapped_column(DateTime(timezone=True))
    connection_id: Mapped[str] = mapped_column(ForeignKey('google_ads_connections.id'), index=True)
    connection_version: Mapped[int] = mapped_column(Integer)
    api_version: Mapped[str] = mapped_column(String(16))
    authority_pin: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))
    request_key: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(16))
    account_id: Mapped[str | None] = mapped_column(String(32))
    since: Mapped[str | None] = mapped_column(String(10))
    until: Mapped[str | None] = mapped_column(String(10))
    granularity: Mapped[str] = mapped_column(String(8), default='daily')
    status: Mapped[str] = mapped_column(String(20), default='queued')
    error_code: Mapped[str | None] = mapped_column(String(64))
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint('connection_id','request_key'),
        CheckConstraint("status in ('queued','running','completed','failed','cancelled')"),
        CheckConstraint("kind in ('accounts','historical')"),CheckConstraint("granularity in ('daily','hourly')"))


class AdEntity(Identity, Base):
    __tablename__ = 'ad_entities'
    connection_id: Mapped[str | None] = mapped_column(ForeignKey('meta_connections.id'))
    google_connection_id: Mapped[str | None] = mapped_column(ForeignKey('google_ads_connections.id'))
    connection_version: Mapped[int] = mapped_column(Integer)
    platform: Mapped[str] = mapped_column(String(16), default='meta')
    account_id: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(16))
    remote_id: Mapped[str] = mapped_column(String(64))
    parent_id: Mapped[str | None] = mapped_column(String(64))
    creative_id: Mapped[str | None] = mapped_column(String(64))
    name: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(String(64))
    objective: Mapped[str | None] = mapped_column(String(64))
    currency: Mapped[str] = mapped_column(String(3))
    timezone: Mapped[str] = mapped_column(String(80))
    source_job_id: Mapped[str | None] = mapped_column(ForeignKey('meta_sync_jobs.id'))
    google_source_job_id: Mapped[str | None] = mapped_column(ForeignKey('google_ads_sync_jobs.id'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint('connection_id','connection_version','account_id','kind','remote_id'),
        UniqueConstraint('google_connection_id','connection_version','account_id','kind','remote_id'),
        CheckConstraint("platform in ('meta','google')"),CheckConstraint("kind in ('account','campaign','adset','ad','creative')"),
        CheckConstraint("(platform='meta' and connection_id is not null and google_connection_id is null and source_job_id is not null and google_source_job_id is null) or (platform='google' and connection_id is null and google_connection_id is not null and source_job_id is null and google_source_job_id is not null)"),)


class AdMetric(Identity, Base):
    __tablename__ = 'ad_metrics'
    connection_id: Mapped[str | None] = mapped_column(ForeignKey('meta_connections.id'))
    google_connection_id: Mapped[str | None] = mapped_column(ForeignKey('google_ads_connections.id'))
    connection_version: Mapped[int] = mapped_column(Integer)
    platform: Mapped[str] = mapped_column(String(16), default='meta')
    account_id: Mapped[str] = mapped_column(String(64))
    level: Mapped[str] = mapped_column(String(16))
    entity_id: Mapped[str] = mapped_column(String(64))
    campaign_id: Mapped[str | None] = mapped_column(String(64))
    adset_id: Mapped[str | None] = mapped_column(String(64))
    day: Mapped[date] = mapped_column(Date)
    hour: Mapped[int] = mapped_column(Integer, default=-1)
    granularity: Mapped[str] = mapped_column(String(8))
    currency: Mapped[str] = mapped_column(String(3))
    timezone: Mapped[str] = mapped_column(String(80))
    attribution: Mapped[str] = mapped_column(String(80))
    spend: Mapped[Decimal | None] = mapped_column(Numeric(24,6))
    impressions: Mapped[int | None] = mapped_column(BigInteger)
    reach: Mapped[int | None] = mapped_column(BigInteger)
    clicks: Mapped[int | None] = mapped_column(BigInteger)
    link_clicks: Mapped[int | None] = mapped_column(BigInteger)
    frequency: Mapped[Decimal | None] = mapped_column(Numeric(24,6))
    ctr: Mapped[Decimal | None] = mapped_column(Numeric(24,6))
    cpc: Mapped[Decimal | None] = mapped_column(Numeric(24,6))
    cpm: Mapped[Decimal | None] = mapped_column(Numeric(24,6))
    leads: Mapped[Decimal | None] = mapped_column(Numeric(24,6))
    add_to_cart: Mapped[Decimal | None] = mapped_column(Numeric(24,6))
    checkout: Mapped[Decimal | None] = mapped_column(Numeric(24,6))
    purchase: Mapped[Decimal | None] = mapped_column(Numeric(24,6))
    revenue: Mapped[Decimal | None] = mapped_column(Numeric(24,6))
    conversions: Mapped[Decimal | None] = mapped_column(Numeric(24,6))
    conversion_value: Mapped[Decimal | None] = mapped_column(Numeric(24,6))
    cpl: Mapped[Decimal | None] = mapped_column(Numeric(24,6))
    cpa: Mapped[Decimal | None] = mapped_column(Numeric(24,6))
    roas: Mapped[Decimal | None] = mapped_column(Numeric(24,6))
    source_job_id: Mapped[str | None] = mapped_column(ForeignKey('meta_sync_jobs.id'))
    google_source_job_id: Mapped[str | None] = mapped_column(ForeignKey('google_ads_sync_jobs.id'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint('connection_id','connection_version','account_id','level','entity_id','day','hour','granularity','attribution'),
        UniqueConstraint('google_connection_id','connection_version','account_id','level','entity_id','day','hour','granularity','attribution'),
        CheckConstraint("platform in ('meta','google')"),CheckConstraint("level in ('campaign','adset','ad')"),
        CheckConstraint("(platform='meta' and connection_id is not null and google_connection_id is null and source_job_id is not null and google_source_job_id is null) or (platform='google' and connection_id is null and google_connection_id is not null and source_job_id is null and google_source_job_id is not null)"),
        CheckConstraint("(granularity = 'daily' and hour = -1) or (granularity = 'hourly' and hour between 0 and 23)"),
        Index('ad_metrics_scope_date','connection_id','connection_version','account_id','granularity','level','day'),
        Index('ad_metrics_google_scope_date','google_connection_id','connection_version','account_id','granularity','level','day'),)


class AdSyncSchedule(Identity, Base):
    __tablename__ = 'ad_sync_schedules'
    connection_id: Mapped[str] = mapped_column(ForeignKey('meta_connections.id'))
    connection_version: Mapped[int] = mapped_column(Integer)
    account_id: Mapped[str] = mapped_column(String(64))
    granularity: Mapped[str] = mapped_column(String(8))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    interval_minutes: Mapped[int] = mapped_column(Integer)
    lookback_days: Mapped[int] = mapped_column(Integer)
    next_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint('connection_id','account_id','granularity'),
        CheckConstraint('interval_minutes >= 15 and interval_minutes <= 10080'),
        CheckConstraint('lookback_days >= 1 and lookback_days <= 31'),
        CheckConstraint("granularity in ('daily','hourly')"),)


class AdReport(Identity, Base):
    __tablename__ = 'ad_reports'
    connection_id: Mapped[str] = mapped_column(ForeignKey('meta_connections.id'), index=True)
    connection_version: Mapped[int] = mapped_column(Integer)
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    account_id: Mapped[str] = mapped_column(String(64))
    request_key: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(8))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(String(3))
    timezone: Mapped[str] = mapped_column(String(80))
    attribution: Mapped[str] = mapped_column(String(80))
    spend: Mapped[Decimal | None] = mapped_column(Numeric(24,6))
    revenue: Mapped[Decimal | None] = mapped_column(Numeric(24,6))
    purchases: Mapped[Decimal | None] = mapped_column(Numeric(24,6))
    leads: Mapped[Decimal | None] = mapped_column(Numeric(24,6))
    impressions: Mapped[int | None] = mapped_column(BigInteger)
    clicks: Mapped[int | None] = mapped_column(BigInteger)
    roas: Mapped[Decimal | None] = mapped_column(Numeric(24,6))
    cpa: Mapped[Decimal | None] = mapped_column(Numeric(24,6))
    comparison: Mapped[dict] = mapped_column(JSON, default=dict)
    campaigns: Mapped[list] = mapped_column(JSON, default=list)
    coverage_days: Mapped[int] = mapped_column(Integer)
    expected_days: Mapped[int] = mapped_column(Integer)
    data_through: Mapped[date | None] = mapped_column(Date)
    source_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint('connection_id','request_key'),
        CheckConstraint("kind in ('daily','weekly')"),
        CheckConstraint('period_end >= period_start'),
        Index('ad_reports_scope_period','connection_id','connection_version','account_id','kind','period_end'),)


class AdReportDelivery(Identity, Base):
    __tablename__ = 'ad_report_deliveries'
    report_id: Mapped[str] = mapped_column(ForeignKey('ad_reports.id'), index=True)
    peer_id: Mapped[str] = mapped_column(ForeignKey('telegram_peers.id'))
    dedup_prefix: Mapped[str] = mapped_column(String(100), unique=True)
    __table_args__ = (UniqueConstraint('report_id','peer_id'),)


class AdReportSchedule(Identity, Base):
    __tablename__ = 'ad_report_schedules'
    connection_id: Mapped[str] = mapped_column(ForeignKey('meta_connections.id'))
    connection_version: Mapped[int] = mapped_column(Integer)
    account_id: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(8))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    delivery_hour: Mapped[int] = mapped_column(Integer, default=8)
    weekday: Mapped[int | None] = mapped_column(Integer)
    telegram: Mapped[bool] = mapped_column(Boolean, default=True)
    telegram_binding_id: Mapped[str | None]=mapped_column(ForeignKey('channel_bindings.id'))
    telegram_binding_version: Mapped[int | None]=mapped_column(Integer)
    next_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint('connection_id','account_id','kind'),
        CheckConstraint("kind in ('daily','weekly')"),
        CheckConstraint('delivery_hour between 0 and 23'),
        CheckConstraint("(kind='daily' and weekday is null) or (kind='weekly' and weekday between 0 and 6)"),)


class AdTarget(Identity, Base):
    __tablename__ = 'ad_targets'
    connection_id: Mapped[str] = mapped_column(ForeignKey('meta_connections.id'))
    connection_version: Mapped[int] = mapped_column(Integer)
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    account_id: Mapped[str] = mapped_column(String(64))
    target_cpa: Mapped[Decimal | None] = mapped_column(Numeric(24,6))
    target_roas: Mapped[Decimal | None] = mapped_column(Numeric(24,6))
    minimum_spend: Mapped[Decimal] = mapped_column(Numeric(24,6), default=0)
    minimum_impressions: Mapped[int] = mapped_column(BigInteger, default=1000)
    minimum_clicks: Mapped[int] = mapped_column(BigInteger, default=20)
    minimum_conversions: Mapped[int] = mapped_column(Integer, default=3)
    minimum_run_days: Mapped[int] = mapped_column(Integer, default=3)
    freshness_minutes: Mapped[int] = mapped_column(Integer, default=180)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint('connection_id','account_id'),
        CheckConstraint('target_cpa is null or target_cpa > 0'),
        CheckConstraint('target_roas is null or target_roas > 0'),
        CheckConstraint('minimum_spend >= 0 and minimum_impressions >= 0 and minimum_clicks >= 0'),
        CheckConstraint('minimum_conversions >= 0 and minimum_run_days between 1 and 30'),
        CheckConstraint('freshness_minutes between 15 and 10080'),)


class AdRule(Identity, Base):
    __tablename__ = 'ads_rules'
    connection_id: Mapped[str] = mapped_column(ForeignKey('meta_connections.id'))
    connection_version: Mapped[int] = mapped_column(Integer)
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    account_id: Mapped[str] = mapped_column(String(64))
    brand_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    platform: Mapped[str] = mapped_column(String(16), default='meta')
    code: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(120))
    conditions_json: Mapped[dict] = mapped_column(JSON)
    action_json: Mapped[dict] = mapped_column(JSON)
    mode: Mapped[str] = mapped_column(String(16), default='advisor')
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint('connection_id','account_id','code'),
        CheckConstraint("platform in ('meta')"),CheckConstraint("mode in ('advisor')"),)


class AdIntelligenceRun(Identity, Base):
    __tablename__ = 'ad_intelligence_runs'
    connection_id: Mapped[str] = mapped_column(ForeignKey('meta_connections.id'), index=True)
    connection_version: Mapped[int] = mapped_column(Integer)
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    account_id: Mapped[str] = mapped_column(String(64))
    request_key: Mapped[str] = mapped_column(String(100))
    granularity: Mapped[str] = mapped_column(String(8))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    hour: Mapped[int | None] = mapped_column(Integer)
    analyst_version: Mapped[str] = mapped_column(String(32), default='performance-analyst-v1')
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    source_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint('connection_id','request_key'),
        UniqueConstraint('id','workspace_id',name='ad_intelligence_event_scope'),
        CheckConstraint("granularity in ('daily','hourly')"),
        CheckConstraint("(granularity='daily' and hour is null) or (granularity='hourly' and hour between 0 and 23)"),)


class AdAnomaly(Identity, Base):
    __tablename__ = 'ad_anomalies'
    connection_id: Mapped[str] = mapped_column(ForeignKey('meta_connections.id'))
    connection_version: Mapped[int] = mapped_column(Integer)
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey('ad_intelligence_runs.id'))
    account_id: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(16))
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
    current_value: Mapped[Decimal | None] = mapped_column(Numeric(24,6))
    baseline_value: Mapped[Decimal | None] = mapped_column(Numeric(24,6))
    deviation_pct: Mapped[Decimal | None] = mapped_column(Numeric(24,6))
    evidence: Mapped[dict] = mapped_column(JSON)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (CheckConstraint("severity in ('info','notice','warning','critical')"),
        Index('ad_anomalies_scope','connection_id','connection_version','account_id','resolved','last_seen'),)


class AdRecommendation(Identity, Base):
    __tablename__ = 'ad_recommendations'
    connection_id: Mapped[str] = mapped_column(ForeignKey('meta_connections.id'))
    connection_version: Mapped[int] = mapped_column(Integer)
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey('ad_intelligence_runs.id'))
    account_id: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[str] = mapped_column(String(64))
    type: Mapped[str] = mapped_column(String(64))
    confidence: Mapped[Decimal] = mapped_column(Numeric(5,4))
    impact: Mapped[dict] = mapped_column(JSON)
    reason_codes: Mapped[list] = mapped_column(JSON)
    explanation: Mapped[str] = mapped_column(Text)
    proposed_action: Mapped[dict] = mapped_column(JSON)
    source: Mapped[dict] = mapped_column(JSON)
    data_freshness_seconds: Mapped[int] = mapped_column(Integer)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(16), default='active')
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (CheckConstraint('confidence >= 0 and confidence <= 1'),
        CheckConstraint("status in ('active','dismissed','resolved')"),
        Index('ad_recommendations_scope','connection_id','connection_version','account_id','status','last_seen'),)


class CreativeAsset(Identity, Base):
    __tablename__ = 'creative_assets'
    connection_id: Mapped[str] = mapped_column(ForeignKey('meta_connections.id'), index=True)
    connection_version: Mapped[int] = mapped_column(Integer)
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    account_id: Mapped[str] = mapped_column(String(64))
    creative_id: Mapped[str] = mapped_column(String(64))
    name: Mapped[str | None] = mapped_column(Text)
    source_job_id: Mapped[str] = mapped_column(ForeignKey('meta_sync_jobs.id'))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint('connection_id','connection_version','account_id','creative_id'),)


class CreativeMetadata(Identity, Base):
    __tablename__ = 'creative_metadata'
    asset_id: Mapped[str] = mapped_column(ForeignKey('creative_assets.id'), unique=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    brand_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    product: Mapped[str | None] = mapped_column(String(160))
    market: Mapped[str | None] = mapped_column(String(80))
    language: Mapped[str | None] = mapped_column(String(32))
    format: Mapped[str | None] = mapped_column(String(64))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    hook: Mapped[str | None] = mapped_column(Text)
    angle: Mapped[str | None] = mapped_column(Text)
    offer: Mapped[str | None] = mapped_column(Text)
    cta: Mapped[str | None] = mapped_column(String(160))
    creator: Mapped[str | None] = mapped_column(String(160))
    landing_page: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(16), default='manual')
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_by: Mapped[str] = mapped_column(ForeignKey('users.id'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (ForeignKeyConstraint(['brand_id','workspace_id'],['brands.id','brands.workspace_id']),
        CheckConstraint("source in ('manual','imported')"),
        CheckConstraint('duration_seconds is null or duration_seconds between 1 and 86400'),)


class CreativeAnalysisRun(Identity, Base):
    __tablename__ = 'creative_analysis_runs'
    connection_id: Mapped[str] = mapped_column(ForeignKey('meta_connections.id'), index=True)
    connection_version: Mapped[int] = mapped_column(Integer)
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    account_id: Mapped[str] = mapped_column(String(64))
    request_key: Mapped[str] = mapped_column(String(100))
    as_of: Mapped[date] = mapped_column(Date)
    current_days: Mapped[int] = mapped_column(Integer)
    baseline_days: Mapped[int] = mapped_column(Integer)
    configuration: Mapped[dict] = mapped_column(JSON)
    analyst_version: Mapped[str] = mapped_column(String(32), default='creative-analyst-v1')
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    source_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint('connection_id','request_key'),
        CheckConstraint('current_days between 2 and 14 and baseline_days between 2 and 28'),)


class CreativePerformance(Identity, Base):
    __tablename__ = 'creative_performance'
    run_id: Mapped[str] = mapped_column(ForeignKey('creative_analysis_runs.id'), index=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey('creative_assets.id'), index=True)
    sample_window: Mapped[str] = mapped_column(String(16))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(String(3))
    timezone: Mapped[str] = mapped_column(String(80))
    spend: Mapped[Decimal] = mapped_column(Numeric(24,6), default=0)
    impressions: Mapped[int] = mapped_column(BigInteger, default=0)
    clicks: Mapped[int] = mapped_column(BigInteger, default=0)
    purchases: Mapped[Decimal] = mapped_column(Numeric(24,6), default=0)
    revenue: Mapped[Decimal] = mapped_column(Numeric(24,6), default=0)
    ctr: Mapped[Decimal | None] = mapped_column(Numeric(24,6))
    cpm: Mapped[Decimal | None] = mapped_column(Numeric(24,6))
    cpa: Mapped[Decimal | None] = mapped_column(Numeric(24,6))
    roas: Mapped[Decimal | None] = mapped_column(Numeric(24,6))
    frequency: Mapped[Decimal | None] = mapped_column(Numeric(24,6))
    ad_count: Mapped[int] = mapped_column(Integer)
    coverage_days: Mapped[int] = mapped_column(Integer)
    __table_args__ = (UniqueConstraint('run_id','asset_id','sample_window'),
        CheckConstraint("sample_window in ('current','baseline')"), CheckConstraint('period_end >= period_start'),)


class CreativeFeature(Identity, Base):
    __tablename__ = 'creative_features'
    run_id: Mapped[str] = mapped_column(ForeignKey('creative_analysis_runs.id'), index=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey('creative_assets.id'), index=True)
    fatigue_status: Mapped[str] = mapped_column(String(16))
    fatigue_score: Mapped[Decimal] = mapped_column(Numeric(5,4))
    confidence: Mapped[Decimal] = mapped_column(Numeric(5,4))
    age_days: Mapped[int] = mapped_column(Integer)
    signals: Mapped[dict] = mapped_column(JSON)
    strategy_brief: Mapped[dict] = mapped_column(JSON, default=dict)
    __table_args__ = (UniqueConstraint('run_id','asset_id'),
        CheckConstraint("fatigue_status in ('healthy','watch','fatigued','insufficient')"),
        CheckConstraint('fatigue_score between 0 and 1 and confidence between 0 and 1'),)


class CreativeLearning(Identity, Base):
    __tablename__ = 'creative_learnings'
    connection_id: Mapped[str] = mapped_column(ForeignKey('meta_connections.id'), index=True)
    connection_version: Mapped[int] = mapped_column(Integer)
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    account_id: Mapped[str] = mapped_column(String(64))
    latest_run_id: Mapped[str] = mapped_column(ForeignKey('creative_analysis_runs.id'))
    dimension: Mapped[str] = mapped_column(String(32))
    value: Mapped[str] = mapped_column(Text)
    statement: Mapped[str] = mapped_column(Text)
    confidence: Mapped[Decimal] = mapped_column(Numeric(5,4))
    evidence: Mapped[dict] = mapped_column(JSON)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(16), default='active')
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (CheckConstraint("dimension in ('hook','angle','format','duration','market')"),
        CheckConstraint("status in ('active','resolved')"), CheckConstraint('confidence between 0 and 1'),)


class AttributionSource(Identity, Base):
    __tablename__ = 'attribution_sources'
    connection_id: Mapped[str] = mapped_column(ForeignKey('meta_connections.id'), index=True)
    connection_version: Mapped[int] = mapped_column(Integer)
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    account_id: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(120))
    currency: Mapped[str] = mapped_column(String(3))
    timezone: Mapped[str] = mapped_column(String(80))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_by: Mapped[str] = mapped_column(ForeignKey('users.id'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint('connection_id','account_id','kind','name'),
        CheckConstraint("kind in ('ga4','crm','orders')"),)


class AnalyticsEvent(Identity, Base):
    __tablename__ = 'analytics_events'
    source_id: Mapped[str] = mapped_column(ForeignKey('attribution_sources.id'), index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    external_id: Mapped[str] = mapped_column(String(180))
    fingerprint: Mapped[str] = mapped_column(String(64))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    event_name: Mapped[str] = mapped_column(String(32))
    visitor_ref_hash: Mapped[str | None] = mapped_column(String(64))
    session_ref_hash: Mapped[str | None] = mapped_column(String(64))
    campaign_id: Mapped[str | None] = mapped_column(String(64))
    adset_id: Mapped[str | None] = mapped_column(String(64))
    ad_id: Mapped[str | None] = mapped_column(String(64))
    utm_source: Mapped[str | None] = mapped_column(String(120))
    utm_medium: Mapped[str | None] = mapped_column(String(120))
    utm_campaign: Mapped[str | None] = mapped_column(String(180))
    value: Mapped[Decimal | None] = mapped_column(Numeric(24,6))
    currency: Mapped[str | None] = mapped_column(String(3))
    __table_args__ = (UniqueConstraint('source_id','external_id'),
        CheckConstraint("event_name in ('session','bounce','scroll','cta_click','form_start','form_submit','checkout','purchase')"),
        CheckConstraint('value is null or value >= 0'),)


class CrmLead(Identity, Base):
    __tablename__ = 'crm_leads'
    source_id: Mapped[str] = mapped_column(ForeignKey('attribution_sources.id'), index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    external_id: Mapped[str] = mapped_column(String(180))
    fingerprint: Mapped[str] = mapped_column(String(64))
    customer_ref_hash: Mapped[str | None] = mapped_column(String(64))
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    stage: Mapped[str] = mapped_column(String(16))
    stage_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    campaign_id: Mapped[str | None] = mapped_column(String(64))
    adset_id: Mapped[str | None] = mapped_column(String(64))
    ad_id: Mapped[str | None] = mapped_column(String(64))
    utm_source: Mapped[str | None] = mapped_column(String(120))
    utm_medium: Mapped[str | None] = mapped_column(String(120))
    utm_campaign: Mapped[str | None] = mapped_column(String(180))
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint('source_id','external_id'),
        CheckConstraint("stage in ('lead','qualified','appointment','sale','lost')"),)


class CrmStageEvent(Identity, Base):
    __tablename__ = 'crm_stage_events'
    source_id: Mapped[str] = mapped_column(ForeignKey('attribution_sources.id'), index=True)
    lead_id: Mapped[str] = mapped_column(ForeignKey('crm_leads.id'), index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    external_id: Mapped[str] = mapped_column(String(180))
    fingerprint: Mapped[str] = mapped_column(String(64))
    stage: Mapped[str] = mapped_column(String(16))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    __table_args__ = (UniqueConstraint('source_id','external_id'),
        CheckConstraint("stage in ('lead','qualified','appointment','sale','lost')"),)


class BusinessOrder(Identity, Base):
    __tablename__ = 'business_orders'
    source_id: Mapped[str] = mapped_column(ForeignKey('attribution_sources.id'), index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    external_id: Mapped[str] = mapped_column(String(180))
    fingerprint: Mapped[str] = mapped_column(String(64))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(16))
    revenue: Mapped[Decimal] = mapped_column(Numeric(24,6))
    currency: Mapped[str] = mapped_column(String(3))
    customer_ref_hash: Mapped[str | None] = mapped_column(String(64))
    lead_external_id: Mapped[str | None] = mapped_column(String(180))
    campaign_id: Mapped[str | None] = mapped_column(String(64))
    adset_id: Mapped[str | None] = mapped_column(String(64))
    ad_id: Mapped[str | None] = mapped_column(String(64))
    attribution_method: Mapped[str] = mapped_column(String(24))
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint('source_id','external_id'),
        CheckConstraint("status in ('pending','paid','refunded','cancelled')"),
        CheckConstraint("attribution_method in ('campaign_id','lead_link','utm','unattributed')"),
        CheckConstraint('revenue >= 0'),)


class AttributionRun(Identity, Base):
    __tablename__ = 'attribution_runs'
    connection_id: Mapped[str] = mapped_column(ForeignKey('meta_connections.id'), index=True)
    connection_version: Mapped[int] = mapped_column(Integer)
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    account_id: Mapped[str] = mapped_column(String(64))
    request_key: Mapped[str] = mapped_column(String(100))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    discrepancy_threshold_pct: Mapped[Decimal] = mapped_column(Numeric(7,3))
    analyst_version: Mapped[str] = mapped_column(String(32), default='attribution-analyst-v1')
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    source_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint('connection_id','request_key'),CheckConstraint('period_end >= period_start'),
        CheckConstraint('discrepancy_threshold_pct between 1 and 100'),)


class AttributionMetric(Identity, Base):
    __tablename__ = 'attribution_metrics'
    run_id: Mapped[str] = mapped_column(ForeignKey('attribution_runs.id'), index=True)
    campaign_id: Mapped[str] = mapped_column(String(64))
    campaign_name: Mapped[str | None] = mapped_column(Text)
    currency: Mapped[str] = mapped_column(String(3))
    spend: Mapped[Decimal] = mapped_column(Numeric(24,6), default=0)
    platform_purchases: Mapped[Decimal] = mapped_column(Numeric(24,6), default=0)
    platform_revenue: Mapped[Decimal] = mapped_column(Numeric(24,6), default=0)
    analytics_sessions: Mapped[int] = mapped_column(BigInteger, default=0)
    analytics_form_submits: Mapped[int] = mapped_column(BigInteger, default=0)
    analytics_purchases: Mapped[int] = mapped_column(BigInteger, default=0)
    leads: Mapped[int] = mapped_column(BigInteger, default=0)
    qualified_leads: Mapped[int] = mapped_column(BigInteger, default=0)
    appointments: Mapped[int] = mapped_column(BigInteger, default=0)
    sales: Mapped[int] = mapped_column(BigInteger, default=0)
    actual_orders: Mapped[int] = mapped_column(BigInteger, default=0)
    actual_revenue: Mapped[Decimal] = mapped_column(Numeric(24,6), default=0)
    landing_cvr: Mapped[Decimal | None] = mapped_column(Numeric(12,6))
    cpl: Mapped[Decimal | None] = mapped_column(Numeric(24,6))
    cost_qualified_lead: Mapped[Decimal | None] = mapped_column(Numeric(24,6))
    cost_appointment: Mapped[Decimal | None] = mapped_column(Numeric(24,6))
    cac: Mapped[Decimal | None] = mapped_column(Numeric(24,6))
    revenue_per_lead: Mapped[Decimal | None] = mapped_column(Numeric(24,6))
    purchase_discrepancy_pct: Mapped[Decimal | None] = mapped_column(Numeric(24,6))
    revenue_discrepancy_pct: Mapped[Decimal | None] = mapped_column(Numeric(24,6))
    tracking_status: Mapped[str] = mapped_column(String(16))
    evidence: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint('run_id','campaign_id'),
        CheckConstraint("tracking_status in ('healthy','watch','unhealthy','insufficient')"),)


class TrackingAlert(Identity, Base):
    __tablename__ = 'tracking_alerts'
    connection_id: Mapped[str] = mapped_column(ForeignKey('meta_connections.id'), index=True)
    connection_version: Mapped[int] = mapped_column(Integer)
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey('attribution_runs.id'))
    account_id: Mapped[str] = mapped_column(String(64))
    campaign_id: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(16))
    discrepancy_pct: Mapped[Decimal | None] = mapped_column(Numeric(24,6))
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
    evidence: Mapped[dict] = mapped_column(JSON)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (CheckConstraint("severity in ('warning','critical')"),)


class AdsAutopilotPolicy(Identity, Base):
    __tablename__ = 'ads_autopilot_policies'
    connection_id: Mapped[str] = mapped_column(ForeignKey('meta_connections.id'))
    connection_version: Mapped[int] = mapped_column(Integer)
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    account_id: Mapped[str] = mapped_column(String(64))
    mode: Mapped[str] = mapped_column(String(16), default='observer')
    halted: Mapped[bool] = mapped_column(Boolean, default=True)
    pause_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    resume_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    budget_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    max_budget_change_pct: Mapped[int] = mapped_column(Integer, default=10)
    max_daily_budget_minor_units: Mapped[int | None] = mapped_column(BigInteger)
    minimum_impressions: Mapped[int] = mapped_column(BigInteger, default=3000)
    minimum_conversions: Mapped[int] = mapped_column(Integer, default=3)
    minimum_confidence: Mapped[Decimal] = mapped_column(Numeric(5,4), default=Decimal('.8'))
    freshness_minutes: Mapped[int] = mapped_column(Integer, default=60)
    quiet_hours_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    quiet_start: Mapped[time] = mapped_column(Time, default=lambda:time(23,0))
    quiet_end: Mapped[time] = mapped_column(Time, default=lambda:time(7,0))
    max_actions_per_day: Mapped[int] = mapped_column(Integer, default=3)
    emergency_frozen: Mapped[bool] = mapped_column(Boolean, default=False)
    freeze_reason: Mapped[str | None] = mapped_column(String(120))
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_by: Mapped[str] = mapped_column(ForeignKey('users.id'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint('workspace_id','account_id'),
        CheckConstraint("mode in ('observer','advisor','copilot','autopilot')"),
        CheckConstraint('max_budget_change_pct between 1 and 20'),
        CheckConstraint('max_daily_budget_minor_units is null or max_daily_budget_minor_units > 0'),
        CheckConstraint('minimum_impressions >= 0 and minimum_conversions >= 0'),
        CheckConstraint('minimum_confidence >= 0 and minimum_confidence <= 1'),
        CheckConstraint('freshness_minutes between 15 and 1440'),
        CheckConstraint('max_actions_per_day between 1 and 100'),)


class AdsPolicyAudit(Identity, Base):
    __tablename__ = 'ads_policy_audits'
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    policy_id: Mapped[str] = mapped_column(ForeignKey('ads_autopilot_policies.id'), index=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    event: Mapped[str] = mapped_column(String(64))
    policy_version: Mapped[int] = mapped_column(Integer)
    data: Mapped[dict] = mapped_column(JSON, default=dict)


class AdAction(Identity, Base):
    __tablename__ = 'ads_actions'
    connection_id: Mapped[str] = mapped_column(ForeignKey('meta_connections.id'), index=True)
    connection_version: Mapped[int] = mapped_column(Integer)
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    recommendation_id: Mapped[str | None] = mapped_column(ForeignKey('ad_recommendations.id'))
    platform: Mapped[str] = mapped_column(String(16), default='meta')
    account_id: Mapped[str] = mapped_column(String(64))
    resource_type: Mapped[str] = mapped_column(String(16))
    resource_id: Mapped[str] = mapped_column(String(64))
    action_type: Mapped[str] = mapped_column(String(24))
    request_key: Mapped[str] = mapped_column(String(64))
    payload_hash: Mapped[str] = mapped_column(String(64))
    before_state: Mapped[dict] = mapped_column(JSON)
    proposed_state: Mapped[dict] = mapped_column(JSON)
    after_state: Mapped[dict] = mapped_column(JSON, default=dict)
    compensating_action: Mapped[dict] = mapped_column(JSON, default=dict)
    reason: Mapped[str] = mapped_column(Text)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5,4))
    source_agent: Mapped[str] = mapped_column(String(64), default='user')
    approval_status: Mapped[str] = mapped_column(String(24), default='pending')
    execution_status: Mapped[str] = mapped_column(String(24), default='pending')
    dry_run: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    approval_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    decision_channel: Mapped[str | None] = mapped_column(String(16))
    policy_id: Mapped[str | None] = mapped_column(ForeignKey('ads_autopilot_policies.id'))
    policy_version: Mapped[int | None] = mapped_column(Integer)
    policy_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    approved_by: Mapped[str | None] = mapped_column(ForeignKey('users.id'))
    approval_input_hash: Mapped[str | None] = mapped_column(String(64))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_24h: Mapped[dict] = mapped_column(JSON, default=dict)
    result_72h: Mapped[dict] = mapped_column(JSON, default=dict)
    result_7d: Mapped[dict] = mapped_column(JSON, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint('connection_id','request_key'),
        UniqueConstraint('id','workspace_id',name='ads_actions_event_scope'),
        CheckConstraint("platform in ('meta')"),CheckConstraint("resource_type in ('campaign','adset','ad')"),
        CheckConstraint("action_type in ('pause','resume','update_budget')"),
        CheckConstraint("approval_status in ('pending','approved','rejected','expired')"),
        CheckConstraint("execution_status in ('pending','queued','executing','simulated','succeeded','failed','unknown','stale','cancelled')"),
        CheckConstraint("decision_channel is null or decision_channel in ('ui','telegram','autopilot')"),
        CheckConstraint('confidence is null or (confidence >= 0 and confidence <= 1)'),
        Index('ads_actions_resource','connection_id','connection_version','resource_type','resource_id','created_at'),
        Index('ads_actions_approval_inbox','workspace_id','approval_status','approval_expires_at','created_at'),)


class AdActionAudit(Identity, Base):
    __tablename__ = 'ads_action_audits'
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    action_id: Mapped[str] = mapped_column(ForeignKey('ads_actions.id'), index=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    event: Mapped[str] = mapped_column(String(64))
    action_version: Mapped[int] = mapped_column(Integer)
    data: Mapped[dict] = mapped_column(JSON, default=dict)


class OutcomeObservation(Identity, Base):
    __tablename__='outcome_observations'
    workspace_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    action_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    actor_id: Mapped[str]=mapped_column(ForeignKey('users.id'))
    request_key: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    request_hash: Mapped[str]=mapped_column(String(64))
    source_hash: Mapped[str]=mapped_column(String(64))
    observed_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    snapshot: Mapped[dict]=mapped_column(JSON)
    __table_args__=(ForeignKeyConstraint(['action_id','workspace_id'],['ads_actions.id','ads_actions.workspace_id']),
        UniqueConstraint('action_id','actor_id','request_key'),
        CheckConstraint('length(request_hash)=64 AND length(source_hash)=64'),)


class AutomationWorkflow(Identity, Base):
    __tablename__ = 'automation_workflows'
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    request_key: Mapped[str] = mapped_column(String(64))
    request_fingerprint: Mapped[str] = mapped_column(String(64))
    temporal_workflow_id: Mapped[str] = mapped_column(String(120), unique=True)
    temporal_run_id: Mapped[str | None] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(24), default='starting')
    approval_status: Mapped[str] = mapped_column(String(16), default='not_required')
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(64))
    wait_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint('workspace_id','request_key'),
        CheckConstraint("kind in ('approval_wait','follow_up')"),
        CheckConstraint("status in ('starting','running','waiting_approval','waiting_timer','completed','failed','cancelled')"),
        CheckConstraint("approval_status in ('not_required','pending','approved','rejected')"),)


class AutomationOutbox(Identity, Base):
    __tablename__ = 'automation_outbox'
    workflow_id: Mapped[str] = mapped_column(ForeignKey('automation_workflows.id'), index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    dedupe_key: Mapped[str] = mapped_column(String(180), unique=True)
    operation: Mapped[str] = mapped_column(String(16))
    signal_name: Mapped[str | None] = mapped_column(String(32))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default='pending')
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        CheckConstraint("operation in ('start','signal')"),
        CheckConstraint("status in ('pending','processing','delivered','dead')"),
        CheckConstraint('attempts >= 0'),
    )


class AutomationWorkflowAudit(Identity, Base):
    __tablename__ = 'automation_workflow_audits'
    workflow_id: Mapped[str] = mapped_column(ForeignKey('automation_workflows.id'), index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    event: Mapped[str] = mapped_column(String(48))
    workflow_version: Mapped[int] = mapped_column(Integer)
    data: Mapped[dict] = mapped_column(JSON, default=dict)


class VoiceInteraction(Identity, Base):
    __tablename__ = 'voice_interactions'
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    session_id: Mapped[str | None] = mapped_column(ForeignKey('sessions.id'))
    kind: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16))
    provider: Mapped[str] = mapped_column(String(32))
    input_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    output_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    language: Mapped[str | None] = mapped_column(String(16))
    interrupted: Mapped[bool] = mapped_column(Boolean, default=False)
    error_code: Mapped[str | None] = mapped_column(String(64))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (CheckConstraint("kind in ('stt','tts')"),CheckConstraint("status in ('running','completed','failed','interrupted')"),
        CheckConstraint('input_bytes >= 0 and output_bytes >= 0 and duration_ms >= 0'),)


class Project(Identity, Base):
    __tablename__ = 'projects'
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default='')
    status: Mapped[str] = mapped_column(String(20), default='active')
    owner_id: Mapped[str | None] = mapped_column(ForeignKey('users.id'))
    created_by: Mapped[str] = mapped_column(ForeignKey('users.id'))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint('id', 'workspace_id'),
        CheckConstraint("status in ('active','on_hold','completed','archived')"),
    )


class Goal(Identity, Base):
    __tablename__ = 'goals'
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    project_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default='')
    success_criteria: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default='draft')
    owner_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    created_by: Mapped[str] = mapped_column(ForeignKey('users.id'))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint('id', 'workspace_id'),
        ForeignKeyConstraint(['project_id', 'workspace_id'], ['projects.id', 'projects.workspace_id']),
        CheckConstraint("status in ('draft','active','completed','failed','cancelled')"),
    )


class Task(Identity, Base):
    __tablename__ = 'tasks'
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    project_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), index=True)
    goal_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), index=True)
    parent_task_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default='')
    status: Mapped[str] = mapped_column(String(20), default='todo')
    kind: Mapped[str] = mapped_column(String(16), default='human')
    priority: Mapped[str] = mapped_column(String(16), default='medium')
    assignee_type: Mapped[str] = mapped_column(String(16), default='unassigned')
    assignee_id: Mapped[str | None] = mapped_column(String(80))
    progress: Mapped[int] = mapped_column(Integer, default=0)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(16), default='user')
    run_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    skill_id: Mapped[str | None] = mapped_column(String(100))
    success_criteria: Mapped[list] = mapped_column(JSON, default=list)
    input_references: Mapped[list] = mapped_column(JSON, default=list)
    budget: Mapped[dict] = mapped_column(JSON, default=dict)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    result_reference: Mapped[dict] = mapped_column(JSON, default=dict)
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    dependencies: Mapped[list] = mapped_column(JSON, default=list)
    files: Mapped[list] = mapped_column(JSON, default=list)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[str] = mapped_column(ForeignKey('users.id'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint('id', 'workspace_id'),
        ForeignKeyConstraint(['project_id', 'workspace_id'], ['projects.id', 'projects.workspace_id']),
        ForeignKeyConstraint(['goal_id', 'workspace_id'], ['goals.id', 'goals.workspace_id']),
        ForeignKeyConstraint(['parent_task_id', 'workspace_id'], ['tasks.id', 'tasks.workspace_id']),
        ForeignKeyConstraint(['run_id', 'workspace_id'], ['runs.id', 'runs.workspace_id']),
        CheckConstraint("status in ('draft','ready','running','waiting_approval','blocked','completed','failed','cancelled')"),
        CheckConstraint("kind in ('human','ai','agent')"),
        CheckConstraint("priority in ('low','medium','high','critical')"),
        CheckConstraint("assignee_type in ('user','agent','unassigned')"),
        CheckConstraint("source in ('user','pao','automation')"),
        CheckConstraint('progress between 0 and 100'),
    )


class TaskDependency(Identity, Base):
    __tablename__ = 'task_dependencies'
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    task_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), index=True)
    depends_on_task_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey('users.id'))
    __table_args__ = (
        UniqueConstraint('task_id', 'depends_on_task_id'),
        ForeignKeyConstraint(['task_id', 'workspace_id'], ['tasks.id', 'tasks.workspace_id']),
        ForeignKeyConstraint(['depends_on_task_id', 'workspace_id'], ['tasks.id', 'tasks.workspace_id']),
        CheckConstraint('task_id <> depends_on_task_id'),
    )


class TaskAttempt(Identity, Base):
    __tablename__ = 'task_attempts'
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    task_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), index=True)
    run_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    request_key: Mapped[str] = mapped_column(String(64))
    input_fingerprint: Mapped[str] = mapped_column(String(64))
    skill_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    skill_artifact: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    attempt_no: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default='running')
    input: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    error_code: Mapped[str | None] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        UniqueConstraint('id','workspace_id',name='task_attempt_scope_unique'),
        UniqueConstraint('task_id', 'attempt_no'),
        UniqueConstraint('task_id', 'request_key'),
        ForeignKeyConstraint(['task_id', 'workspace_id'], ['tasks.id', 'tasks.workspace_id']),
        ForeignKeyConstraint(['run_id', 'workspace_id'], ['runs.id', 'runs.workspace_id']),
        CheckConstraint("status in ('running','completed','failed','cancelled')"),
        CheckConstraint('attempt_no > 0'),
    )


class TaskComment(Identity, Base):
    __tablename__ = 'task_comments'
    task_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    body: Mapped[str] = mapped_column(Text)
    __table_args__ = (ForeignKeyConstraint(['task_id', 'workspace_id'], ['tasks.id', 'tasks.workspace_id']),)


class TaskActivity(Identity, Base):
    __tablename__ = 'task_activity'
    task_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), index=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey('users.id'))
    event: Mapped[str] = mapped_column(String(48))
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    __table_args__ = (ForeignKeyConstraint(['task_id', 'workspace_id'], ['tasks.id', 'tasks.workspace_id']),)


class StudioDefinition(Identity, Base):
    __tablename__ = 'studio_definitions'
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'),index=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    kind: Mapped[str] = mapped_column(String(12))
    slug: Mapped[str] = mapped_column(String(60))
    name: Mapped[str] = mapped_column(String(120))
    revision: Mapped[int] = mapped_column(Integer,default=1,server_default=text('1'))
    seed: Mapped[bool] = mapped_column(Boolean,default=False,server_default=text('false'))
    published_version_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint('id','workspace_id'),UniqueConstraint('workspace_id','kind','slug'),
        CheckConstraint("kind in ('agents','skills','workflows')",name='studio_kind'),
        ForeignKeyConstraint(['published_version_id','id','workspace_id'],['studio_versions.id','studio_versions.definition_id','studio_versions.workspace_id'],
            name='studio_published_scope',use_alter=True))


class StudioVersion(Identity, Base):
    __tablename__ = 'studio_versions'
    workspace_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    definition_id: Mapped[str] = mapped_column(Uuid(as_uuid=False),index=True)
    author_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    ordinal: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16),default='draft')
    __table_args__=(ForeignKeyConstraint(['definition_id','workspace_id'],['studio_definitions.id','studio_definitions.workspace_id']),
        UniqueConstraint('id','definition_id','workspace_id'),UniqueConstraint('definition_id','ordinal'),
        CheckConstraint("status in ('draft','validated','reviewed','published','deprecated')",name='studio_version_status'))


class StudioEvent(Identity, Base):
    __tablename__ = 'studio_events'
    workspace_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    definition_id: Mapped[str] = mapped_column(Uuid(as_uuid=False),index=True)
    version_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    actor_id: Mapped[str | None] = mapped_column(ForeignKey('users.id'))
    action: Mapped[str] = mapped_column(String(32))
    data: Mapped[dict] = mapped_column(JSON,default=dict)
    __table_args__=(ForeignKeyConstraint(['definition_id','workspace_id'],['studio_definitions.id','studio_definitions.workspace_id']),
        ForeignKeyConstraint(['version_id','definition_id','workspace_id'],['studio_versions.id','studio_versions.definition_id','studio_versions.workspace_id']))


class StudioExecution(Identity, Base):
    __tablename__='studio_executions'
    workspace_id: Mapped[str]=mapped_column(Uuid(as_uuid=False),index=True)
    definition_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    plan_id: Mapped[str]=mapped_column(ForeignKey('studio_events.id'),unique=True)
    actor_id: Mapped[str]=mapped_column(ForeignKey('users.id'))
    temporal_id: Mapped[str]=mapped_column(String(120),unique=True)
    snapshot_hash: Mapped[str]=mapped_column(String(64))
    command: Mapped[dict]=mapped_column(JSON)
    status: Mapped[str]=mapped_column(String(24),default='starting')
    version: Mapped[int]=mapped_column(Integer,default=1)
    sequence: Mapped[int]=mapped_column(Integer,default=0)
    state: Mapped[dict]=mapped_column(JSON,default=dict)
    cancel_requested: Mapped[bool]=mapped_column(Boolean,default=False)
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    __table_args__=(UniqueConstraint('id','workspace_id'),
        ForeignKeyConstraint(['definition_id','workspace_id'],['studio_definitions.id','studio_definitions.workspace_id']),
        CheckConstraint("status in ('starting','waiting_approval','waiting_timer','running','step_completed','completed','cancelled','manual_review')",name='studio_execution_status'),
        CheckConstraint('version>=1 AND sequence>=0 AND length(snapshot_hash)=64',name='studio_execution_version'),)


class StudioCommand(Identity, Base):
    __tablename__='studio_commands'
    workspace_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    execution_id: Mapped[str]=mapped_column(Uuid(as_uuid=False),index=True)
    actor_id: Mapped[str]=mapped_column(ForeignKey('users.id'))
    request_key: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    ordinal: Mapped[int]=mapped_column(Integer)
    operation: Mapped[str]=mapped_column(String(16))
    payload: Mapped[dict]=mapped_column(JSON)
    content_hash: Mapped[str]=mapped_column(String(64))
    status: Mapped[str]=mapped_column(String(16),default='pending')
    attempts: Mapped[int]=mapped_column(Integer,default=0)
    available_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,server_default=func.now())
    lease_token: Mapped[str|None]=mapped_column(Uuid(as_uuid=False))
    lease_until: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    error_code: Mapped[str|None]=mapped_column(String(64))
    delivered_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    __table_args__=(ForeignKeyConstraint(['execution_id','workspace_id'],['studio_executions.id','studio_executions.workspace_id']),
        UniqueConstraint('execution_id','request_key'),UniqueConstraint('execution_id','ordinal'),
        CheckConstraint("operation in ('start','decision','cancel') AND status in ('pending','processing','delivered','dead') AND attempts>=0 AND ordinal>=1 AND length(content_hash)=64",name='studio_command_profile'),
        Index('studio_command_dispatch','status','available_at','lease_until'),)


class GoalExecution(Identity, Base):
    __tablename__='goal_executions'
    workspace_id: Mapped[str]=mapped_column(Uuid(as_uuid=False),index=True)
    goal_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    initial_plan_id: Mapped[str]=mapped_column(ForeignKey('studio_events.id'),unique=True)
    actor_id: Mapped[str]=mapped_column(ForeignKey('users.id'))
    temporal_id: Mapped[str]=mapped_column(String(120),unique=True)
    envelope: Mapped[dict]=mapped_column(JSON)
    goal_snapshot: Mapped[dict]=mapped_column(JSON)
    initial_proposal: Mapped[dict]=mapped_column(JSON)
    admission_hash: Mapped[str]=mapped_column(String(64))
    status: Mapped[str]=mapped_column(String(24),default='starting')
    version: Mapped[int]=mapped_column(Integer,default=1)
    sequence: Mapped[int]=mapped_column(Integer,default=0)
    state: Mapped[dict]=mapped_column(JSON,default=dict)
    reserved_cost_microusd: Mapped[int]=mapped_column(BigInteger,default=0)
    cancel_requested: Mapped[bool]=mapped_column(Boolean,default=False)
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    __table_args__=(UniqueConstraint('id','workspace_id'),
        ForeignKeyConstraint(['goal_id','workspace_id'],['goals.id','goals.workspace_id']),
        CheckConstraint("status in ('starting','waiting_approval','waiting_replan','running','completed','cancelled','budget_exhausted','deadline_exceeded','manual_review')",name='goal_execution_status'),
        CheckConstraint('version>=1 AND sequence>=0 AND reserved_cost_microusd>=0 AND reserved_cost_microusd<=1000000000 AND length(admission_hash)=64',name='goal_execution_bounds'),
        Index('goal_execution_active_owner','goal_id',unique=True,postgresql_where=text("status NOT IN ('completed','cancelled','budget_exhausted','deadline_exceeded','manual_review') OR reserved_cost_microusd>0")),)


class GoalCommand(Identity, Base):
    __tablename__='goal_commands'
    workspace_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    execution_id: Mapped[str]=mapped_column(Uuid(as_uuid=False),index=True)
    actor_id: Mapped[str]=mapped_column(ForeignKey('users.id'))
    request_key: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    ordinal: Mapped[int]=mapped_column(Integer)
    operation: Mapped[str]=mapped_column(String(16))
    payload: Mapped[dict]=mapped_column(JSON)
    content_hash: Mapped[str]=mapped_column(String(64))
    status: Mapped[str]=mapped_column(String(16),default='pending')
    attempts: Mapped[int]=mapped_column(Integer,default=0)
    available_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now,server_default=func.now())
    lease_token: Mapped[str|None]=mapped_column(Uuid(as_uuid=False))
    lease_until: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    error_code: Mapped[str|None]=mapped_column(String(64))
    delivered_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    __table_args__=(ForeignKeyConstraint(['execution_id','workspace_id'],['goal_executions.id','goal_executions.workspace_id']),
        UniqueConstraint('execution_id','request_key'),UniqueConstraint('execution_id','ordinal'),
        CheckConstraint("operation in ('start','proposal','decision','cancel') AND status in ('pending','processing','delivered','dead') AND attempts>=0 AND ordinal>=1 AND length(content_hash)=64",name='goal_command_profile'),
        Index('goal_command_dispatch','status','available_at','lease_until'),)


class GoalEvent(Identity, Base):
    __tablename__='goal_events'
    workspace_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    execution_id: Mapped[str]=mapped_column(Uuid(as_uuid=False),index=True)
    actor_id: Mapped[str]=mapped_column(ForeignKey('users.id'))
    action: Mapped[str]=mapped_column(String(32))
    data: Mapped[dict]=mapped_column(JSON)
    content_hash: Mapped[str]=mapped_column(String(64))
    __table_args__=(ForeignKeyConstraint(['execution_id','workspace_id'],['goal_executions.id','goal_executions.workspace_id']),
        CheckConstraint('length(content_hash)=64',name='goal_event_hash'),)


class StudioSchedule(Identity, Base):
    __tablename__='studio_schedules'
    workspace_id: Mapped[str]=mapped_column(ForeignKey('workspaces.id'),index=True)
    actor_id: Mapped[str]=mapped_column(ForeignKey('users.id'))
    version: Mapped[int]=mapped_column(Integer,default=1)
    spec: Mapped[dict]=mapped_column(JSON)
    spec_hash: Mapped[str]=mapped_column(String(64))
    status: Mapped[str]=mapped_column(String(24),default='disabled')
    cursor_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    next_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    error_code: Mapped[str|None]=mapped_column(String(64))
    __table_args__=(UniqueConstraint('id','workspace_id'),
        CheckConstraint("version>=1 AND length(spec_hash)=64 AND status IN ('disabled','enabled','completed','manual_review','archived')",name='studio_schedule_state'),
        Index('studio_schedule_due','status','next_at'),)


class StudioScheduleEvent(Identity, Base):
    __tablename__='studio_schedule_events'
    schedule_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    workspace_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    actor_id: Mapped[str]=mapped_column(ForeignKey('users.id'))
    action: Mapped[str]=mapped_column(String(24))
    revision: Mapped[int]=mapped_column(Integer)
    data: Mapped[dict]=mapped_column(JSON)
    content_hash: Mapped[str]=mapped_column(String(64))
    __table_args__=(ForeignKeyConstraint(['schedule_id','workspace_id'],['studio_schedules.id','studio_schedules.workspace_id']),
        UniqueConstraint('schedule_id','revision'),
        CheckConstraint('length(content_hash)=64',name='studio_schedule_event_hash'),)


class StudioScheduleSlot(Identity, Base):
    __tablename__='studio_schedule_slots'
    schedule_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    workspace_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    slot_key: Mapped[str]=mapped_column(String(40))
    spec_hash: Mapped[str]=mapped_column(String(64))
    execution_id: Mapped[str]=mapped_column(Uuid(as_uuid=False),unique=True)
    __table_args__=(ForeignKeyConstraint(['schedule_id','workspace_id'],['studio_schedules.id','studio_schedules.workspace_id']),
        ForeignKeyConstraint(['execution_id','workspace_id'],['studio_executions.id','studio_executions.workspace_id']),
        UniqueConstraint('schedule_id','slot_key'),CheckConstraint('length(spec_hash)=64',name='studio_schedule_slot_hash'),)


class GoalScheduleSlot(Identity, Base):
    __tablename__='goal_schedule_slots'
    schedule_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    workspace_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    slot_key: Mapped[str]=mapped_column(String(40))
    spec_hash: Mapped[str]=mapped_column(String(64))
    execution_id: Mapped[str]=mapped_column(Uuid(as_uuid=False),unique=True)
    __table_args__=(ForeignKeyConstraint(['schedule_id','workspace_id'],['studio_schedules.id','studio_schedules.workspace_id']),
        ForeignKeyConstraint(['execution_id','workspace_id'],['goal_executions.id','goal_executions.workspace_id']),
        UniqueConstraint('schedule_id','slot_key'),CheckConstraint('length(spec_hash)=64',name='goal_schedule_slot_hash'),)


class TenantConnectionReference(Identity, Base):
    __tablename__ = 'tenant_connection_references'
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'))
    kind: Mapped[str] = mapped_column(String(16))
    source_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    provider: Mapped[str] = mapped_column(String(24))
    manager_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    source_version: Mapped[int | None] = mapped_column(Integer)
    source_stamp: Mapped[str] = mapped_column(String(64))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default='staged')
    generation: Mapped[int] = mapped_column(Integer,default=1,server_default='1')
    supersedes_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    __table_args__ = (
        UniqueConstraint('id', 'workspace_id'), UniqueConstraint('workspace_id','kind','source_id','generation',name='tenant_reference_generation_identity'),
        ForeignKeyConstraint(['supersedes_id','workspace_id'],['tenant_connection_references.id','tenant_connection_references.workspace_id'],name='tenant_reference_generation_parent'),
        CheckConstraint("(generation=1 AND supersedes_id IS NULL) OR (generation>1 AND supersedes_id IS NOT NULL)",name='tenant_reference_generation_state'),
        CheckConstraint("kind IN ('model','cli_model','mcp','meta_ads','google_ads') AND status IN ('staged','revoked') AND revision>=1 AND length(source_stamp)=64 AND (source_version IS NULL OR source_version>=1)", name='tenant_connection_reference_state'),)


class TenantConnectionGrant(Identity, Base):
    __tablename__ = 'tenant_connection_grants'
    workspace_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    reference_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    reference_revision: Mapped[int] = mapped_column(Integer)
    creator_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    grantee_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    brand_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    account_id: Mapped[str | None] = mapped_column(String(64))
    permission: Mapped[str] = mapped_column(String(16), default='read_only')
    request_key: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    fingerprint: Mapped[str] = mapped_column(String(64))
    ttl_minutes: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default='staged')
    __table_args__ = (
        UniqueConstraint('id', 'workspace_id'), UniqueConstraint('workspace_id', 'creator_id', 'request_key'),
        ForeignKeyConstraint(['reference_id', 'workspace_id'], ['tenant_connection_references.id', 'tenant_connection_references.workspace_id']),
        ForeignKeyConstraint(['brand_id', 'workspace_id'], ['brands.id', 'brands.workspace_id']),
        CheckConstraint("permission='read_only' AND status IN ('staged','revoked') AND revision>=1 AND reference_revision>=1 AND ttl_minutes BETWEEN 1 AND 43200 AND length(fingerprint)=64", name='tenant_connection_grant_state'),)


class ModelGrantActivation(Identity, Base):
    __tablename__ = 'model_grant_activations'
    workspace_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    grant_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), unique=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    reference_revision: Mapped[int] = mapped_column(Integer)
    grant_revision: Mapped[int] = mapped_column(Integer)
    source_stamp: Mapped[str] = mapped_column(String(64))
    capability: Mapped[str] = mapped_column(String(24), default='model_inference')
    request_key: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    fingerprint: Mapped[str] = mapped_column(String(64))
    __table_args__ = (
        UniqueConstraint('workspace_id', 'actor_id', 'request_key'),
        ForeignKeyConstraint(['grant_id', 'workspace_id'], ['tenant_connection_grants.id', 'tenant_connection_grants.workspace_id']),
        CheckConstraint("capability='model_inference' AND reference_revision>=1 AND grant_revision>=1 AND length(source_stamp)=64 AND length(fingerprint)=64", name='model_grant_activation_scope'),)


class ConnectionReadActivation(Identity, Base):
    __tablename__ = 'connection_read_activations'
    workspace_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    grant_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), unique=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    kind: Mapped[str] = mapped_column(String(16))
    reference_revision: Mapped[int] = mapped_column(Integer)
    grant_revision: Mapped[int] = mapped_column(Integer)
    source_stamp: Mapped[str] = mapped_column(String(64))
    capability: Mapped[str] = mapped_column(String(24))
    request_key: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    fingerprint: Mapped[str] = mapped_column(String(64))
    __table_args__ = (
        UniqueConstraint('workspace_id', 'actor_id', 'request_key'),
        ForeignKeyConstraint(['grant_id', 'workspace_id'], ['tenant_connection_grants.id', 'tenant_connection_grants.workspace_id']),
        CheckConstraint("((kind='mcp' AND capability='mcp_read') OR (kind IN ('meta_ads','google_ads') AND capability='ads_read')) AND reference_revision>=1 AND grant_revision>=1 AND length(source_stamp)=64 AND length(fingerprint)=64", name='connection_read_activation_scope'),)


class TenantConnectionAudit(Identity, Base):
    __tablename__ = 'tenant_connection_audits'
    workspace_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    reference_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    grant_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    action: Mapped[str] = mapped_column(String(32))
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    __table_args__ = (
        ForeignKeyConstraint(['reference_id', 'workspace_id'], ['tenant_connection_references.id', 'tenant_connection_references.workspace_id']),
        ForeignKeyConstraint(['grant_id', 'workspace_id'], ['tenant_connection_grants.id', 'tenant_connection_grants.workspace_id']),
        CheckConstraint("action IN ('reference_staged','grant_staged','grant_revoked','reference_revoked')", name='tenant_connection_audit_action'),)


class ConnectorConnection(Identity, Base):
    __tablename__='connector_connections'
    workspace_id: Mapped[str]=mapped_column(ForeignKey('workspaces.id'),index=True)
    owner_id: Mapped[str]=mapped_column(ForeignKey('users.id'))
    brain_id: Mapped[str|None]=mapped_column(ForeignKey('brains.id'))
    endpoint: Mapped[str]=mapped_column(String(1024))
    status: Mapped[str]=mapped_column(String(16),default='draft')
    version: Mapped[int]=mapped_column(Integer,default=1)
    manifest: Mapped[dict]=mapped_column(JSON,default=dict)
    manifest_hash: Mapped[str|None]=mapped_column(String(64))
    permissions: Mapped[dict]=mapped_column(JSON,default=dict)
    failures: Mapped[int]=mapped_column(Integer,default=0)
    circuit_until: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    __table_args__=(UniqueConstraint('id','workspace_id'),CheckConstraint("status in ('draft','connected','revoked')",name='connector_status'),)


class ConnectorSecret(Identity, Base):
    __tablename__='connector_secrets'
    workspace_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    connection_id: Mapped[str]=mapped_column(Uuid(as_uuid=False),unique=True)
    ciphertext: Mapped[str|None]=mapped_column(Text)
    __table_args__=(ForeignKeyConstraint(['connection_id','workspace_id'],['connector_connections.id','connector_connections.workspace_id']),)


class ConnectorEvent(Identity, Base):
    __tablename__='connector_events'
    workspace_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    connection_id: Mapped[str]=mapped_column(Uuid(as_uuid=False),index=True)
    actor_id: Mapped[str]=mapped_column(ForeignKey('users.id'))
    action: Mapped[str]=mapped_column(String(32))
    data: Mapped[dict]=mapped_column(JSON,default=dict)
    __table_args__=(ForeignKeyConstraint(['connection_id','workspace_id'],['connector_connections.id','connector_connections.workspace_id']),)


class BusinessEvent(Identity, Base):
    __tablename__ = 'business_events'
    workspace_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), index=True)
    event_type: Mapped[str] = mapped_column(String(64))
    schema_version: Mapped[int] = mapped_column(Integer)
    aggregate_type: Mapped[str] = mapped_column(String(16))
    aggregate_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    aggregate_version: Mapped[int] = mapped_column(Integer)
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    correlation_id: Mapped[str] = mapped_column(Uuid(as_uuid=False))
    causation_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    payload_reference: Mapped[dict] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(64))
    task_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    tool_call_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    ad_action_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    analysis_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    __table_args__ = (
        UniqueConstraint('id', 'workspace_id'),
        UniqueConstraint('workspace_id', 'event_type', 'aggregate_id', 'aggregate_version'),
        ForeignKeyConstraint(['task_id','workspace_id'], ['tasks.id','tasks.workspace_id'],name='business_event_task_scope'),
        ForeignKeyConstraint(['tool_call_id','workspace_id'], ['tool_calls.id','tool_calls.workspace_id'],name='business_event_tool_scope'),
        ForeignKeyConstraint(['ad_action_id','workspace_id'], ['ads_actions.id','ads_actions.workspace_id'],name='business_event_action_scope'),
        ForeignKeyConstraint(['analysis_id','workspace_id'], ['ad_intelligence_runs.id','ad_intelligence_runs.workspace_id'],name='business_event_analysis_scope'),
        CheckConstraint("schema_version=1 AND ((event_type='task.completed' AND aggregate_type='task') OR (event_type='approval.requested' AND aggregate_type in ('task','tool','ads_action')) OR (event_type='ads.analysis.completed' AND aggregate_type='ads_analysis'))", name='business_event_profile'),
        CheckConstraint("num_nonnulls(task_id,tool_call_id,ad_action_id,analysis_id)=1 AND ((aggregate_type='task' AND task_id IS NOT NULL AND task_id=aggregate_id) OR (aggregate_type='tool' AND tool_call_id IS NOT NULL AND tool_call_id=aggregate_id) OR (aggregate_type='ads_action' AND ad_action_id IS NOT NULL AND ad_action_id=aggregate_id) OR (aggregate_type='ads_analysis' AND analysis_id IS NOT NULL AND analysis_id=aggregate_id))",name='business_event_target'),
        CheckConstraint('aggregate_version >= 1 AND length(content_hash)=64', name='business_event_version_hash'),
    )


class BusinessOutbox(Identity, Base):
    __tablename__ = 'business_outbox'
    workspace_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), index=True)
    event_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), unique=True)
    status: Mapped[str] = mapped_column(String(16), default='pending')
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lease_token: Mapped[str | None] = mapped_column(Uuid(as_uuid=False))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, server_default=func.now())
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(64))
    __table_args__ = (
        ForeignKeyConstraint(['event_id', 'workspace_id'], ['business_events.id', 'business_events.workspace_id']),
        CheckConstraint("status in ('pending','processing','delivered','dead_letter') AND attempts >= 0", name='business_outbox_state'),
        Index('business_outbox_dispatch', 'status', 'available_at', 'lease_until'),
    )


class BusinessReceipt(Identity, Base):
    __tablename__ = 'business_receipts'
    workspace_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), index=True)
    event_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), unique=True)
    consumer: Mapped[str] = mapped_column(String(64), default='internal.audit.v1')
    content_hash: Mapped[str] = mapped_column(String(64))
    __table_args__ = (
        ForeignKeyConstraint(['event_id', 'workspace_id'], ['business_events.id', 'business_events.workspace_id']),
        CheckConstraint("consumer='internal.audit.v1' AND length(content_hash)=64", name='business_receipt_profile'),
    )


class ChannelBinding(Identity, Base):
    __tablename__='channel_bindings'
    workspace_id: Mapped[str]=mapped_column(ForeignKey('workspaces.id'))
    connection_id: Mapped[str | None]=mapped_column(Uuid(as_uuid=False))
    actor_id: Mapped[str]=mapped_column(ForeignKey('users.id'))
    channel: Mapped[str]=mapped_column(String(16))
    identity_hash: Mapped[str]=mapped_column(String(64))
    peer_id: Mapped[str | None]=mapped_column(ForeignKey('telegram_peers.id'),unique=True)
    brain_id: Mapped[str | None]=mapped_column(Uuid(as_uuid=False))
    session_id: Mapped[str | None]=mapped_column(Uuid(as_uuid=False),unique=True)
    kind: Mapped[str]=mapped_column(String(16))
    mode: Mapped[str]=mapped_column(String(16),default='quiet')
    enabled: Mapped[bool]=mapped_column(Boolean,default=True)
    outbound_confirmed: Mapped[bool]=mapped_column(Boolean,default=False)
    reports_enabled: Mapped[bool]=mapped_column(Boolean,default=False,server_default=text('false'))
    retention_days: Mapped[int]=mapped_column(Integer,default=7)
    version: Mapped[int]=mapped_column(Integer,default=1)
    __table_args__=(UniqueConstraint('id','workspace_id'),UniqueConstraint('channel','identity_hash'),
        ForeignKeyConstraint(['connection_id','workspace_id'],['telegram_connections.id','telegram_connections.workspace_id']),
        CheckConstraint("connection_id IS NULL OR channel='telegram'"),
        ForeignKeyConstraint(['brain_id','workspace_id'],['brains.id','brains.workspace_id']),
        ForeignKeyConstraint(['session_id','workspace_id'],['sessions.id','sessions.workspace_id']),
        CheckConstraint("channel IN ('local','telegram') AND kind IN ('personal','customer') AND mode IN ('auto','human','quiet') AND retention_days BETWEEN 1 AND 30 AND version>=1"))


class ChannelInbound(Identity, Base):
    __tablename__='channel_inbounds'
    workspace_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    connection_id: Mapped[str | None]=mapped_column(ForeignKey('telegram_connections.id'))
    telegram_context: Mapped[dict | None]=mapped_column(JSONB(none_as_null=True))
    binding_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    external_key: Mapped[str]=mapped_column(String(64))
    content_hash: Mapped[str]=mapped_column(String(64))
    body: Mapped[str | None]=mapped_column(Text)
    status: Mapped[str]=mapped_column(String(24))
    run_id: Mapped[str | None]=mapped_column(ForeignKey('runs.id'),unique=True)
    purged_at: Mapped[datetime | None]=mapped_column(DateTime(timezone=True))
    __table_args__=(UniqueConstraint('id','workspace_id'),ForeignKeyConstraint(['binding_id','workspace_id'],['channel_bindings.id','channel_bindings.workspace_id']),
        UniqueConstraint('binding_id','external_key'),CheckConstraint("length(content_hash)=64 AND status IN ('accepted','quiet','busy','command','blocked')"))


class ChannelOutbox(Identity, Base):
    __tablename__='channel_outbox'
    workspace_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    connection_id: Mapped[str | None]=mapped_column(ForeignKey('telegram_connections.id'))
    telegram_context: Mapped[dict | None]=mapped_column(JSONB(none_as_null=True))
    binding_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    request_key: Mapped[str]=mapped_column(String(80))
    content_hash: Mapped[str]=mapped_column(String(64))
    body: Mapped[str | None]=mapped_column(Text)
    kind: Mapped[str]=mapped_column(String(16))
    status: Mapped[str]=mapped_column(String(16),default='queued')
    attempts: Mapped[int]=mapped_column(Integer,default=0)
    available_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    remote_id: Mapped[str | None]=mapped_column(String(64))
    error_code: Mapped[str | None]=mapped_column(String(64))
    __table_args__=(ForeignKeyConstraint(['binding_id','workspace_id'],['channel_bindings.id','channel_bindings.workspace_id']),
        UniqueConstraint('binding_id','request_key'),CheckConstraint("kind IN ('auto','manual') AND status IN ('queued','sending','sent','failed','unknown','cancelled') AND attempts BETWEEN 0 AND 3 AND length(content_hash)=64"))


class ChannelAudit(Identity, Base):
    __tablename__='channel_audits'
    workspace_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    connection_id: Mapped[str | None]=mapped_column(ForeignKey('telegram_connections.id'))
    binding_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    actor_id: Mapped[str]=mapped_column(ForeignKey('users.id'))
    request_key: Mapped[str]=mapped_column(String(80))
    content_hash: Mapped[str]=mapped_column(String(64))
    data: Mapped[dict]=mapped_column(JSON)
    __table_args__=(ForeignKeyConstraint(['binding_id','workspace_id'],['channel_bindings.id','channel_bindings.workspace_id']),
        UniqueConstraint('binding_id','request_key'))


class VoiceTurn(Identity, Base):
    __tablename__='voice_turns'
    workspace_id: Mapped[str]=mapped_column(ForeignKey('workspaces.id'))
    session_id: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    user_id: Mapped[str]=mapped_column(ForeignKey('users.id'))
    request_key: Mapped[str]=mapped_column(Uuid(as_uuid=False))
    status: Mapped[str]=mapped_column(String(16),default='created')
    transcript: Mapped[str | None]=mapped_column(Text)
    audio_hash: Mapped[str | None]=mapped_column(String(64))
    language: Mapped[str | None]=mapped_column(String(16))
    duration_ms: Mapped[int | None]=mapped_column(Integer)
    run_id: Mapped[str | None]=mapped_column(ForeignKey('runs.id'),unique=True)
    error_code: Mapped[str | None]=mapped_column(String(64))
    version: Mapped[int]=mapped_column(Integer,default=1)
    __table_args__=(UniqueConstraint('user_id','request_key'),
        ForeignKeyConstraint(['session_id','workspace_id'],['sessions.id','sessions.workspace_id']),
        CheckConstraint("status IN ('created','transcribing','ready','submitted','cancelled','failed') AND version>=1"))


# Register bounded business planning tables after shared Base/Identity definitions.
from .modules.business_planning.models import (BusinessProfile, BusinessProfileVersion,
                                               MonthlyPlan, MonthlyPlanVersion,
                                               BusinessPlanReview, BusinessPlanAdmission, BusinessPlanTask,
                                               BusinessRoutingVersion)
from .modules.business_planning.operations_models import (BusinessJob, BusinessPlanEvent, BusinessBudget,
    BusinessAction, BusinessBudgetEntry)
from .modules.connections.enterprise_models import EnterpriseAIPolicy, EnterpriseAIRevision
from .modules.cli_connections.personal_models import PersonalCliPolicy, PersonalCliRevision
from .modules.installation_ai.models import InstallationAIResource, InstallationAIRevision
