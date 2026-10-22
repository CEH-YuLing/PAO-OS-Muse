"""Goal result receipts and bounded recoverable in-app delivery. No transport."""
from alembic import op
import sqlalchemy as sa
revision='0044'
down_revision='0043'
branch_labels=depends_on=None

def common():
    return [sa.Column('id',sa.Uuid(as_uuid=False),primary_key=True),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),sa.ForeignKey('workspaces.id'),nullable=False),
        sa.Column('user_id',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('source_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('source_hash',sa.String(64),nullable=False)]

def recovery():
    return [sa.Column('requested_by',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id')),
        sa.Column('attempts',sa.Integer(),nullable=False,server_default='0'),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now())]

def upgrade():
    for column in recovery():op.add_column('result_deliveries',column)
    op.execute('UPDATE result_deliveries d SET requested_by=e.actor_id,updated_at=d.created_at FROM studio_executions e WHERE e.id=d.source_id')
    op.create_table('goal_result_receipts',*common(),
        sa.Column('read_at',sa.DateTime(timezone=True),nullable=False),sa.Column('ack_at',sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(['source_id','workspace_id'],['goal_executions.id','goal_executions.workspace_id']),
        sa.UniqueConstraint('workspace_id','user_id','source_id','source_hash'),sa.CheckConstraint('length(source_hash)=64'))
    op.create_table('goal_result_deliveries',*common(),*recovery(),
        sa.Column('destination',sa.String(24),nullable=False),sa.Column('status',sa.String(16),nullable=False),
        sa.Column('error_code',sa.String(64)),sa.Column('delivered_at',sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(['source_id','workspace_id'],['goal_executions.id','goal_executions.workspace_id']),
        sa.UniqueConstraint('workspace_id','user_id','source_id','source_hash','destination'),
        sa.CheckConstraint("destination='in_app' AND status IN ('pending','delivered','failed') AND length(source_hash)=64 AND attempts>=0 AND attempts<=5"))

def downgrade():
    op.drop_table('goal_result_deliveries');op.drop_table('goal_result_receipts')
    for name in ('updated_at','attempts','requested_by'):op.drop_column('result_deliveries',name)
