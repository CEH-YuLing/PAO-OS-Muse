"""Scoped in-app inbox receipts and delivery state; no outbound transport."""
from alembic import op
import sqlalchemy as sa
revision='0040'
down_revision='0039'
branch_labels=depends_on=None


def columns():
    return [sa.Column('id',sa.Uuid(as_uuid=False),primary_key=True),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),sa.ForeignKey('workspaces.id'),nullable=False),
        sa.Column('user_id',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('source_id',sa.Uuid(as_uuid=False),nullable=False),
        sa.Column('source_hash',sa.String(64),nullable=False)]


def upgrade():
    op.create_table('result_inbox_receipts',*columns(),
        sa.ForeignKeyConstraint(['source_id','workspace_id'],['studio_executions.id','studio_executions.workspace_id']),
        sa.Column('read_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('ack_at',sa.DateTime(timezone=True)),
        sa.UniqueConstraint('workspace_id','user_id','source_id','source_hash'),
        sa.CheckConstraint('length(source_hash)=64'))
    op.create_table('result_deliveries',*columns(),
        sa.ForeignKeyConstraint(['source_id','workspace_id'],['studio_executions.id','studio_executions.workspace_id']),
        sa.Column('destination',sa.String(24),nullable=False),
        sa.Column('status',sa.String(16),nullable=False),sa.Column('error_code',sa.String(64)),
        sa.Column('delivered_at',sa.DateTime(timezone=True)),
        sa.UniqueConstraint('workspace_id','user_id','source_id','source_hash','destination'),
        sa.CheckConstraint("destination='in_app' AND status IN ('pending','delivered','failed') AND length(source_hash)=64"))


def downgrade():
    op.drop_table('result_deliveries');op.drop_table('result_inbox_receipts')
