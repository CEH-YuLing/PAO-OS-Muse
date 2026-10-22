"""Enterprise-owned inference policy; never credentials or per-user grants."""
from sqlalchemy import ForeignKey, Integer, JSON, String, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from ...models import Base, Identity


class EnterpriseAIPolicy(Identity, Base):
    __tablename__ = 'enterprise_ai_policies'
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'), unique=True)
    revision: Mapped[int] = mapped_column(Integer)
    content: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (CheckConstraint('revision>=1'),)


class EnterpriseAIRevision(Identity, Base):
    __tablename__ = 'enterprise_ai_revisions'
    workspace_id: Mapped[str] = mapped_column(ForeignKey('workspaces.id'))
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    revision: Mapped[int] = mapped_column(Integer)
    request_key: Mapped[str] = mapped_column(String(36))
    fingerprint: Mapped[str] = mapped_column(String(64))
    content: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint('workspace_id', 'revision'),
                     UniqueConstraint('workspace_id', 'actor_id', 'request_key'),
                     CheckConstraint('revision>=1 AND length(fingerprint)=64'))
