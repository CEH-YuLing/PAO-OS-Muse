"""M4.1 immutable task-completion envelope + scoped pending outbox, no delivery."""
from alembic import op
import sqlalchemy as sa
revision='0035'
down_revision='0034'
branch_labels=None
depends_on=None

def identity():
    return [sa.Column('id',sa.Uuid(as_uuid=False),primary_key=True),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False)]

def upgrade():
    op.create_table('business_events',*identity(),
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),nullable=False),
        sa.Column('event_type',sa.String(64),nullable=False),sa.Column('schema_version',sa.Integer(),nullable=False),
        sa.Column('aggregate_type',sa.String(16),nullable=False),sa.Column('aggregate_id',sa.Uuid(as_uuid=False),nullable=False),
        sa.Column('aggregate_version',sa.Integer(),nullable=False),
        sa.Column('actor_id',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('occurred_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('correlation_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('causation_id',sa.Uuid(as_uuid=False)),
        sa.Column('payload_reference',sa.JSON(),nullable=False),sa.Column('content_hash',sa.String(64),nullable=False),
        sa.UniqueConstraint('id','workspace_id'),
        sa.UniqueConstraint('workspace_id','event_type','aggregate_id','aggregate_version'),
        sa.ForeignKeyConstraint(['aggregate_id','workspace_id'],['tasks.id','tasks.workspace_id']),
        sa.CheckConstraint("event_type='task.completed' AND aggregate_type='task' AND schema_version=1",name='business_event_profile'),
        sa.CheckConstraint('aggregate_version >= 1 AND length(content_hash)=64',name='business_event_version_hash'))
    op.create_index('ix_business_events_workspace_id','business_events',['workspace_id'])
    op.create_table('business_outbox',*identity(),
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),nullable=False),
        sa.Column('event_id',sa.Uuid(as_uuid=False),nullable=False,unique=True),
        sa.Column('status',sa.String(16),nullable=False),sa.Column('attempts',sa.Integer(),nullable=False),
        sa.ForeignKeyConstraint(['event_id','workspace_id'],['business_events.id','business_events.workspace_id']),
        sa.CheckConstraint("status in ('pending','processing','delivered','dead_letter') AND attempts >= 0",name='business_outbox_state'))
    op.create_index('ix_business_outbox_workspace_id','business_outbox',['workspace_id'])
    op.execute("CREATE FUNCTION pao_business_event_immutable() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'business_event_immutable'; END; $$ LANGUAGE plpgsql")
    op.execute('CREATE TRIGGER business_event_immutable BEFORE UPDATE OR DELETE ON business_events FOR EACH ROW EXECUTE FUNCTION pao_business_event_immutable()')
    op.execute("""CREATE FUNCTION pao_business_outbox_scope() RETURNS trigger AS $$ BEGIN
        IF OLD.id<>NEW.id OR OLD.workspace_id<>NEW.workspace_id OR OLD.event_id<>NEW.event_id OR OLD.created_at<>NEW.created_at
        THEN RAISE EXCEPTION 'business_outbox_scope_immutable'; END IF; RETURN NEW; END; $$ LANGUAGE plpgsql""")
    op.execute('CREATE TRIGGER business_outbox_scope BEFORE UPDATE ON business_outbox FOR EACH ROW EXECUTE FUNCTION pao_business_outbox_scope()')

def downgrade():
    op.execute('DROP TRIGGER business_outbox_scope ON business_outbox');op.execute('DROP FUNCTION pao_business_outbox_scope()')
    op.execute('DROP TRIGGER business_event_immutable ON business_events');op.execute('DROP FUNCTION pao_business_event_immutable()')
    op.drop_table('business_outbox');op.drop_table('business_events')
