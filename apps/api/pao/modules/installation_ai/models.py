from sqlalchemy import String,Integer,JSON,ForeignKey,CheckConstraint,UniqueConstraint,Index,text
from sqlalchemy.orm import Mapped,mapped_column
from ...models import Base,Identity


class InstallationAIResource(Identity,Base):
    __tablename__='installation_ai_resources'
    provider:Mapped[str]=mapped_column(String(32),unique=True)
    owner_id:Mapped[str]=mapped_column(ForeignKey('users.id'))
    source_workspace_id:Mapped[str]=mapped_column(ForeignKey('workspaces.id'))
    source_id:Mapped[str]=mapped_column(String(36))
    source_kind:Mapped[str]=mapped_column(String(16))
    revision:Mapped[int]=mapped_column(Integer,default=1)
    enabled:Mapped[bool]=mapped_column(default=False)
    is_default:Mapped[bool]=mapped_column(default=False)
    source_stamp:Mapped[str]=mapped_column(String(64))
    catalog:Mapped[list]=mapped_column(JSON,default=list)
    default_model:Mapped[str]=mapped_column(String(120))
    __table_args__=(CheckConstraint("revision>=1 AND source_kind IN ('api','cli') AND length(source_stamp)=64",name='installation_ai_resource_state'),
                   Index('installation_ai_one_default','is_default',unique=True,postgresql_where=text('is_default AND enabled')))


class InstallationAIRevision(Identity,Base):
    __tablename__='installation_ai_revisions'
    resource_id:Mapped[str]=mapped_column(ForeignKey('installation_ai_resources.id'))
    actor_id:Mapped[str]=mapped_column(ForeignKey('users.id'))
    revision:Mapped[int]=mapped_column(Integer)
    request_key:Mapped[str]=mapped_column(String(36),unique=True)
    fingerprint:Mapped[str]=mapped_column(String(64))
    content:Mapped[dict]=mapped_column(JSON)
    __table_args__=(UniqueConstraint('resource_id','revision'),)
