"""Pinned fixed-Echo schedules, immutable audit/slot ledger."""
from alembic import op
import sqlalchemy as sa
revision='0042'
down_revision='0041'
branch_labels=depends_on=None

def identity():
    return [sa.Column('id',sa.Uuid(as_uuid=False),primary_key=True),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False)]

def upgrade():
    op.create_table('studio_schedules',*identity(),
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),sa.ForeignKey('workspaces.id'),nullable=False),
        sa.Column('actor_id',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('version',sa.Integer(),nullable=False),sa.Column('spec',sa.JSON(),nullable=False),
        sa.Column('spec_hash',sa.String(64),nullable=False),sa.Column('status',sa.String(24),nullable=False),
        sa.Column('cursor_at',sa.DateTime(timezone=True),nullable=False),sa.Column('next_at',sa.DateTime(timezone=True)),
        sa.Column('error_code',sa.String(64)),sa.UniqueConstraint('id','workspace_id'),
        sa.CheckConstraint("version>=1 AND length(spec_hash)=64 AND status IN ('disabled','enabled','completed','manual_review','archived')",name='studio_schedule_state'))
    op.create_index('ix_studio_schedules_workspace_id','studio_schedules',['workspace_id'])
    op.create_index('studio_schedule_due','studio_schedules',['status','next_at'])
    op.create_table('studio_schedule_events',*identity(),
        sa.Column('schedule_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('workspace_id',sa.Uuid(as_uuid=False),nullable=False),
        sa.Column('actor_id',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('action',sa.String(24),nullable=False),sa.Column('revision',sa.Integer(),nullable=False),sa.Column('data',sa.JSON(),nullable=False),
        sa.Column('content_hash',sa.String(64),nullable=False),
        sa.ForeignKeyConstraint(['schedule_id','workspace_id'],['studio_schedules.id','studio_schedules.workspace_id']),
        sa.UniqueConstraint('schedule_id','revision'),
        sa.CheckConstraint('length(content_hash)=64',name='studio_schedule_event_hash'))
    op.create_table('studio_schedule_slots',*identity(),
        sa.Column('schedule_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('workspace_id',sa.Uuid(as_uuid=False),nullable=False),
        sa.Column('slot_key',sa.String(40),nullable=False),sa.Column('spec_hash',sa.String(64),nullable=False),
        sa.Column('execution_id',sa.Uuid(as_uuid=False),nullable=False,unique=True),
        sa.ForeignKeyConstraint(['schedule_id','workspace_id'],['studio_schedules.id','studio_schedules.workspace_id']),
        sa.ForeignKeyConstraint(['execution_id','workspace_id'],['studio_executions.id','studio_executions.workspace_id']),
        sa.UniqueConstraint('schedule_id','slot_key'),sa.CheckConstraint('length(spec_hash)=64',name='studio_schedule_slot_hash'))
    op.execute("""CREATE FUNCTION studio_schedule_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP='DELETE' OR TG_TABLE_NAME<>'studio_schedules' THEN RAISE EXCEPTION 'schedule evidence immutable'; END IF;
      IF ROW(NEW.id,NEW.created_at,NEW.workspace_id,NEW.actor_id) IS DISTINCT FROM ROW(OLD.id,OLD.created_at,OLD.workspace_id,OLD.actor_id)
      THEN RAISE EXCEPTION 'schedule identity immutable'; END IF; RETURN NEW;
    END $$""")
    for name in ('studio_schedules','studio_schedule_events','studio_schedule_slots'):
        op.execute(f'CREATE TRIGGER {name}_immutable BEFORE UPDATE OR DELETE ON {name} FOR EACH ROW EXECUTE FUNCTION studio_schedule_immutable()')

def downgrade():
    for name in ('studio_schedule_slots','studio_schedule_events','studio_schedules'):op.drop_table(name)
    op.execute('DROP FUNCTION studio_schedule_immutable()')
