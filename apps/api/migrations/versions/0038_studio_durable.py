"""P6.2B admission/projection/outbox; live dispatch remains disabled."""
from alembic import op
import sqlalchemy as sa

revision='0038'
down_revision='0037'
branch_labels=depends_on=None

def upgrade():
    op.create_table('studio_executions',
        sa.Column('id',sa.Uuid(as_uuid=False),primary_key=True),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('definition_id',sa.Uuid(as_uuid=False),nullable=False),
        sa.Column('plan_id',sa.Uuid(as_uuid=False),sa.ForeignKey('studio_events.id'),nullable=False,unique=True),
        sa.Column('actor_id',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('temporal_id',sa.String(120),nullable=False,unique=True),sa.Column('snapshot_hash',sa.String(64),nullable=False),
        sa.Column('command',sa.JSON(),nullable=False),sa.Column('status',sa.String(24),nullable=False),
        sa.Column('version',sa.Integer(),nullable=False),sa.Column('sequence',sa.Integer(),nullable=False),
        sa.Column('state',sa.JSON(),nullable=False),sa.Column('cancel_requested',sa.Boolean(),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint('id','workspace_id'),
        sa.ForeignKeyConstraint(['definition_id','workspace_id'],['studio_definitions.id','studio_definitions.workspace_id']),
        sa.CheckConstraint("status in ('starting','waiting_approval','waiting_timer','running','step_completed','completed','cancelled','manual_review')",name='studio_execution_status'),
        sa.CheckConstraint('version>=1 AND sequence>=0 AND length(snapshot_hash)=64',name='studio_execution_version'))
    op.create_index('ix_studio_executions_workspace_id','studio_executions',['workspace_id'])
    op.create_table('studio_commands',
        sa.Column('id',sa.Uuid(as_uuid=False),primary_key=True),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('execution_id',sa.Uuid(as_uuid=False),nullable=False),
        sa.Column('actor_id',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('request_key',sa.Uuid(as_uuid=False),nullable=False),sa.Column('ordinal',sa.Integer(),nullable=False),
        sa.Column('operation',sa.String(16),nullable=False),sa.Column('payload',sa.JSON(),nullable=False),
        sa.Column('content_hash',sa.String(64),nullable=False),sa.Column('status',sa.String(16),nullable=False),
        sa.Column('attempts',sa.Integer(),nullable=False),sa.Column('available_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.Column('lease_token',sa.Uuid(as_uuid=False)),sa.Column('lease_until',sa.DateTime(timezone=True)),
        sa.Column('error_code',sa.String(64)),sa.Column('delivered_at',sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(['execution_id','workspace_id'],['studio_executions.id','studio_executions.workspace_id']),
        sa.UniqueConstraint('execution_id','request_key'),sa.UniqueConstraint('execution_id','ordinal'),
        sa.CheckConstraint("operation in ('start','decision','cancel') AND status in ('pending','processing','delivered','dead') AND attempts>=0 AND ordinal>=1 AND length(content_hash)=64",name='studio_command_profile'))
    op.create_index('ix_studio_commands_execution_id','studio_commands',['execution_id'])
    op.create_index('studio_command_dispatch','studio_commands',['status','available_at','lease_until'])
    # Envelope/identity is immutable; only delivery/projection fields can change.
    op.execute("""CREATE FUNCTION studio_durable_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_TABLE_NAME='studio_executions' THEN
        IF ROW(NEW.id,NEW.workspace_id,NEW.definition_id,NEW.plan_id,NEW.actor_id,NEW.temporal_id,NEW.snapshot_hash,NEW.command::text,NEW.created_at)
          IS DISTINCT FROM ROW(OLD.id,OLD.workspace_id,OLD.definition_id,OLD.plan_id,OLD.actor_id,OLD.temporal_id,OLD.snapshot_hash,OLD.command::text,OLD.created_at)
          THEN RAISE EXCEPTION 'studio execution identity immutable'; END IF;
      ELSE
        IF ROW(NEW.id,NEW.workspace_id,NEW.execution_id,NEW.actor_id,NEW.request_key,NEW.ordinal,NEW.operation,NEW.payload::text,NEW.content_hash,NEW.created_at)
          IS DISTINCT FROM ROW(OLD.id,OLD.workspace_id,OLD.execution_id,OLD.actor_id,OLD.request_key,OLD.ordinal,OLD.operation,OLD.payload::text,OLD.content_hash,OLD.created_at)
          THEN RAISE EXCEPTION 'studio command immutable'; END IF;
      END IF; RETURN NEW;
    END $$""")
    for table in ('studio_executions','studio_commands'):
        op.execute(f'CREATE TRIGGER {table}_immutable BEFORE UPDATE ON {table} FOR EACH ROW EXECUTE FUNCTION studio_durable_immutable()')

def downgrade():
    op.drop_table('studio_commands');op.drop_table('studio_executions');op.execute('DROP FUNCTION studio_durable_immutable()')
