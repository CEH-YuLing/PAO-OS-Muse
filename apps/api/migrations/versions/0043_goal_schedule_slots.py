"""Additive scheduled Goal admission evidence; shared schedule projection/owner."""
from alembic import op
import sqlalchemy as sa
revision='0043'
down_revision='0042'
branch_labels=depends_on=None

def upgrade():
    op.create_table('goal_schedule_slots',
        sa.Column('id',sa.Uuid(as_uuid=False),primary_key=True),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('schedule_id',sa.Uuid(as_uuid=False),nullable=False),
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),nullable=False),
        sa.Column('slot_key',sa.String(40),nullable=False),
        sa.Column('spec_hash',sa.String(64),nullable=False),
        sa.Column('execution_id',sa.Uuid(as_uuid=False),nullable=False,unique=True),
        sa.ForeignKeyConstraint(['schedule_id','workspace_id'],['studio_schedules.id','studio_schedules.workspace_id']),
        sa.ForeignKeyConstraint(['execution_id','workspace_id'],['goal_executions.id','goal_executions.workspace_id']),
        sa.UniqueConstraint('schedule_id','slot_key'),
        sa.CheckConstraint('length(spec_hash)=64',name='goal_schedule_slot_hash'))
    op.execute('CREATE TRIGGER goal_schedule_slots_immutable BEFORE UPDATE OR DELETE ON goal_schedule_slots FOR EACH ROW EXECUTE FUNCTION studio_schedule_immutable()')

def downgrade():op.drop_table('goal_schedule_slots')
