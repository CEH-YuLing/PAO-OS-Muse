"""Explicit self-use consent; no credentials, expiring grants or shared profiles."""
from sqlalchemy import ForeignKey,Integer,JSON,String,UniqueConstraint,CheckConstraint
from sqlalchemy.orm import Mapped,mapped_column
from ...models import Base,Identity

class PersonalCliPolicy(Identity,Base):
    __tablename__='personal_cli_policies'
    workspace_id:Mapped[str]=mapped_column(ForeignKey('workspaces.id'))
    actor_id:Mapped[str]=mapped_column(ForeignKey('users.id'))
    revision:Mapped[int]=mapped_column(Integer)
    content:Mapped[dict]=mapped_column(JSON)
    __table_args__=(UniqueConstraint('workspace_id','actor_id'),CheckConstraint('revision>=1'))

class PersonalCliRevision(Identity,Base):
    __tablename__='personal_cli_revisions'
    workspace_id:Mapped[str]=mapped_column(ForeignKey('workspaces.id'))
    actor_id:Mapped[str]=mapped_column(ForeignKey('users.id'))
    revision:Mapped[int]=mapped_column(Integer)
    content:Mapped[dict]=mapped_column(JSON)
    request_key:Mapped[str]=mapped_column(String(36))
    fingerprint:Mapped[str]=mapped_column(String(64))
    __table_args__=(UniqueConstraint('workspace_id','actor_id','revision'),
        UniqueConstraint('workspace_id','actor_id','request_key'),CheckConstraint('revision>=1 AND length(fingerprint)=64'))
