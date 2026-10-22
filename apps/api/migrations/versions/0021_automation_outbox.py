"""durable automation outbox

Revision ID: 0021
Revises: 0020
"""
from alembic import op
import sqlalchemy as sa

revision = '0021'
down_revision = '0020'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('automation_workflows',
                  sa.Column('request_fingerprint', sa.String(64), nullable=True))
    op.execute("UPDATE automation_workflows SET request_fingerprint = repeat('0', 64) WHERE request_fingerprint IS NULL")
    op.alter_column('automation_workflows', 'request_fingerprint', nullable=False)
    op.create_table(
        'automation_outbox',
        sa.Column('workflow_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('workspace_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('dedupe_key', sa.String(180), nullable=False),
        sa.Column('operation', sa.String(16), nullable=False),
        sa.Column('signal_name', sa.String(32), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False),
        sa.Column('available_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('locked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.String(64), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("operation in ('start','signal')"),
        sa.CheckConstraint("status in ('pending','processing','delivered','dead')"),
        sa.CheckConstraint('attempts >= 0'),
        sa.ForeignKeyConstraint(['workflow_id'], ['automation_workflows.id']),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('dedupe_key'),
    )
    op.create_index(op.f('ix_automation_outbox_workflow_id'), 'automation_outbox', ['workflow_id'])
    op.create_index(op.f('ix_automation_outbox_workspace_id'), 'automation_outbox', ['workspace_id'])
    op.create_index(op.f('ix_automation_outbox_available_at'), 'automation_outbox', ['available_at'])


def downgrade():
    op.drop_index(op.f('ix_automation_outbox_available_at'), table_name='automation_outbox')
    op.drop_index(op.f('ix_automation_outbox_workspace_id'), table_name='automation_outbox')
    op.drop_index(op.f('ix_automation_outbox_workflow_id'), table_name='automation_outbox')
    op.drop_table('automation_outbox')
    op.drop_column('automation_workflows', 'request_fingerprint')
