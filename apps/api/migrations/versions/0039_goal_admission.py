"""Goal admission ledger only; no live workflow registration."""
from alembic import op
import sqlalchemy as sa

revision='0039'
down_revision='0038'
branch_labels=depends_on=None


def identity():
    return [sa.Column('id',sa.Uuid(as_uuid=False),primary_key=True),
            sa.Column('created_at',sa.DateTime(timezone=True),nullable=False)]


def upgrade():
    op.create_table('goal_executions',*identity(),
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),nullable=False),
        sa.Column('goal_id',sa.Uuid(as_uuid=False),nullable=False),
        sa.Column('initial_plan_id',sa.Uuid(as_uuid=False),sa.ForeignKey('studio_events.id'),nullable=False,unique=True),
        sa.Column('actor_id',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('temporal_id',sa.String(120),nullable=False,unique=True),
        *[sa.Column(k,sa.JSON(),nullable=False) for k in ('envelope','goal_snapshot','initial_proposal','state')],
        sa.Column('admission_hash',sa.String(64),nullable=False),sa.Column('status',sa.String(24),nullable=False),
        sa.Column('version',sa.Integer(),nullable=False),sa.Column('sequence',sa.Integer(),nullable=False),
        sa.Column('reserved_cost_microusd',sa.BigInteger(),nullable=False),
        sa.Column('cancel_requested',sa.Boolean(),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('id','workspace_id'),
        sa.ForeignKeyConstraint(['goal_id','workspace_id'],['goals.id','goals.workspace_id']),
        sa.CheckConstraint("status in ('starting','waiting_approval','waiting_replan','running','completed','cancelled','budget_exhausted','deadline_exceeded','manual_review')",name='goal_execution_status'),
        sa.CheckConstraint('version>=1 AND sequence>=0 AND reserved_cost_microusd>=0 AND reserved_cost_microusd<=1000000000 AND length(admission_hash)=64',name='goal_execution_bounds'))
    op.create_index('ix_goal_executions_workspace_id','goal_executions',['workspace_id'])
    op.create_index('goal_execution_active_owner','goal_executions',['goal_id'],unique=True,
        postgresql_where=sa.text("status NOT IN ('completed','cancelled','budget_exhausted','deadline_exceeded','manual_review') OR reserved_cost_microusd>0"))
    op.create_table('goal_commands',*identity(),
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('execution_id',sa.Uuid(as_uuid=False),nullable=False),
        sa.Column('actor_id',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('request_key',sa.Uuid(as_uuid=False),nullable=False),sa.Column('ordinal',sa.Integer(),nullable=False),
        sa.Column('operation',sa.String(16),nullable=False),sa.Column('payload',sa.JSON(),nullable=False),
        sa.Column('content_hash',sa.String(64),nullable=False),sa.Column('status',sa.String(16),nullable=False),
        sa.Column('attempts',sa.Integer(),nullable=False),
        sa.Column('available_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),
        sa.Column('lease_token',sa.Uuid(as_uuid=False)),sa.Column('lease_until',sa.DateTime(timezone=True)),
        sa.Column('error_code',sa.String(64)),sa.Column('delivered_at',sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(['execution_id','workspace_id'],['goal_executions.id','goal_executions.workspace_id']),
        sa.UniqueConstraint('execution_id','request_key'),sa.UniqueConstraint('execution_id','ordinal'),
        sa.CheckConstraint("operation in ('start','proposal','decision','cancel') AND status in ('pending','processing','delivered','dead') AND attempts>=0 AND ordinal>=1 AND length(content_hash)=64",name='goal_command_profile'))
    op.create_index('ix_goal_commands_execution_id','goal_commands',['execution_id'])
    op.create_index('goal_command_dispatch','goal_commands',['status','available_at','lease_until'])
    op.create_table('goal_events',*identity(),
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('execution_id',sa.Uuid(as_uuid=False),nullable=False),
        sa.Column('actor_id',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('action',sa.String(32),nullable=False),sa.Column('data',sa.JSON(),nullable=False),sa.Column('content_hash',sa.String(64),nullable=False),
        sa.ForeignKeyConstraint(['execution_id','workspace_id'],['goal_executions.id','goal_executions.workspace_id']),
        sa.CheckConstraint('length(content_hash)=64',name='goal_event_hash'))
    op.create_index('ix_goal_events_execution_id','goal_events',['execution_id'])
    op.execute("""CREATE FUNCTION goal_ledger_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP='DELETE' THEN RAISE EXCEPTION 'goal ledger immutable'; END IF;
      IF TG_TABLE_NAME='goal_events' THEN RAISE EXCEPTION 'goal audit immutable';
      ELSIF TG_TABLE_NAME='goal_executions' THEN
        IF ROW(NEW.id,NEW.workspace_id,NEW.goal_id,NEW.initial_plan_id,NEW.actor_id,NEW.temporal_id,NEW.envelope::jsonb,NEW.goal_snapshot::jsonb,NEW.initial_proposal::jsonb,NEW.admission_hash,NEW.created_at)
          IS DISTINCT FROM ROW(OLD.id,OLD.workspace_id,OLD.goal_id,OLD.initial_plan_id,OLD.actor_id,OLD.temporal_id,OLD.envelope::jsonb,OLD.goal_snapshot::jsonb,OLD.initial_proposal::jsonb,OLD.admission_hash,OLD.created_at)
        THEN RAISE EXCEPTION 'goal execution identity immutable'; END IF;
      ELSE
        IF ROW(NEW.id,NEW.workspace_id,NEW.execution_id,NEW.actor_id,NEW.request_key,NEW.ordinal,NEW.operation,NEW.payload::jsonb,NEW.content_hash,NEW.created_at)
          IS DISTINCT FROM ROW(OLD.id,OLD.workspace_id,OLD.execution_id,OLD.actor_id,OLD.request_key,OLD.ordinal,OLD.operation,OLD.payload::jsonb,OLD.content_hash,OLD.created_at)
        THEN RAISE EXCEPTION 'goal command immutable'; END IF;
      END IF; RETURN NEW;
    END $$""")
    for table in ('goal_executions','goal_commands','goal_events'):
        op.execute(f'CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION goal_ledger_immutable()')


def downgrade():
    op.drop_table('goal_events');op.drop_table('goal_commands');op.drop_table('goal_executions')
    op.execute('DROP FUNCTION goal_ledger_immutable()')
