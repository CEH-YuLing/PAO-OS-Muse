"""ads_approval"""
from alembic import op
import sqlalchemy as sa

revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint('ads_actions_approval_status_check', 'ads_actions', type_='check')
    op.drop_constraint('ads_actions_execution_status_check', 'ads_actions', type_='check')
    op.add_column('ads_actions', sa.Column('approval_expires_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('ads_actions', sa.Column('decision_channel', sa.String(16), nullable=True))
    op.execute("update ads_actions set approval_status=case when approval_status='copilot_confirmed' then 'approved' else 'pending' end")
    op.execute("update ads_actions set approval_expires_at=created_at + interval '24 hours'")
    op.alter_column('ads_actions', 'approval_expires_at', nullable=False)
    op.create_check_constraint('ads_actions_approval_status_check', 'ads_actions',
        "approval_status in ('pending','approved','rejected','expired')")
    op.create_check_constraint('ads_actions_execution_status_check', 'ads_actions',
        "execution_status in ('pending','queued','executing','simulated','succeeded','failed','unknown','stale','cancelled')")
    op.create_check_constraint('ads_actions_decision_channel_check', 'ads_actions',
        "decision_channel is null or decision_channel in ('ui','telegram')")
    op.create_index('ads_actions_approval_inbox', 'ads_actions',
        ['workspace_id', 'approval_status', 'approval_expires_at', 'created_at'])


def downgrade():
    op.drop_index('ads_actions_approval_inbox', table_name='ads_actions')
    op.drop_constraint('ads_actions_decision_channel_check', 'ads_actions', type_='check')
    op.drop_constraint('ads_actions_execution_status_check', 'ads_actions', type_='check')
    op.drop_constraint('ads_actions_approval_status_check', 'ads_actions', type_='check')
    op.execute("update ads_actions set approval_status=case when approval_status='approved' then 'copilot_confirmed' else 'copilot_pending' end")
    op.execute("update ads_actions set execution_status='failed' where execution_status in ('queued','cancelled')")
    op.drop_column('ads_actions', 'decision_channel')
    op.drop_column('ads_actions', 'approval_expires_at')
    op.create_check_constraint('ads_actions_approval_status_check', 'ads_actions',
        "approval_status in ('copilot_pending','copilot_confirmed')")
    op.create_check_constraint('ads_actions_execution_status_check', 'ads_actions',
        "execution_status in ('pending','executing','simulated','succeeded','failed','unknown','stale')")
