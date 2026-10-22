"""M4.2 leased durable delivery and scoped internal consumer receipts."""
from alembic import op
import sqlalchemy as sa

revision = '0036'
down_revision = '0035'
branch_labels = depends_on = None


def upgrade():
    for column in (
        sa.Column('lease_token', sa.Uuid(as_uuid=False)),
        sa.Column('lease_until', sa.DateTime(timezone=True)),
        sa.Column('available_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('delivered_at', sa.DateTime(timezone=True)),
        sa.Column('error_code', sa.String(64)),
    ):
        op.add_column('business_outbox', column)
    op.create_index('business_outbox_dispatch', 'business_outbox', ['status', 'available_at', 'lease_until'])
    op.create_table('business_receipts',
        sa.Column('id', sa.Uuid(as_uuid=False), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('workspace_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('event_id', sa.Uuid(as_uuid=False), nullable=False, unique=True),
        sa.Column('consumer', sa.String(64), nullable=False),
        sa.Column('content_hash', sa.String(64), nullable=False),
        sa.ForeignKeyConstraint(['event_id', 'workspace_id'], ['business_events.id', 'business_events.workspace_id']),
        sa.CheckConstraint("consumer='internal.audit.v1' AND length(content_hash)=64", name='business_receipt_profile'))
    op.create_index('ix_business_receipts_workspace_id', 'business_receipts', ['workspace_id'])


def downgrade():
    op.drop_table('business_receipts')
    op.drop_index('business_outbox_dispatch', table_name='business_outbox')
    for name in ('error_code', 'delivered_at', 'available_at', 'lease_until', 'lease_token'):
        op.drop_column('business_outbox', name)
