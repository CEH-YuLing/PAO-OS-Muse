"""meta_write"""
from alembic import op
import sqlalchemy as sa

revision='0010'
down_revision='0009'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('ads_actions',
        sa.Column('connection_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('connection_version',sa.Integer(),nullable=False),
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('user_id',sa.Uuid(as_uuid=False),nullable=False),
        sa.Column('recommendation_id',sa.Uuid(as_uuid=False)),sa.Column('platform',sa.String(16),nullable=False),
        sa.Column('account_id',sa.String(64),nullable=False),sa.Column('resource_type',sa.String(16),nullable=False),sa.Column('resource_id',sa.String(64),nullable=False),
        sa.Column('action_type',sa.String(24),nullable=False),sa.Column('request_key',sa.String(64),nullable=False),sa.Column('payload_hash',sa.String(64),nullable=False),
        sa.Column('before_state',sa.JSON(),nullable=False),sa.Column('proposed_state',sa.JSON(),nullable=False),sa.Column('after_state',sa.JSON(),nullable=False),
        sa.Column('compensating_action',sa.JSON(),nullable=False),sa.Column('reason',sa.Text(),nullable=False),sa.Column('confidence',sa.Numeric(5,4)),
        sa.Column('source_agent',sa.String(64),nullable=False),sa.Column('approval_status',sa.String(24),nullable=False),
        sa.Column('execution_status',sa.String(24),nullable=False),sa.Column('dry_run',sa.Boolean(),nullable=False),sa.Column('version',sa.Integer(),nullable=False),
        sa.Column('approved_by',sa.Uuid(as_uuid=False)),sa.Column('approved_at',sa.DateTime(timezone=True)),sa.Column('executed_at',sa.DateTime(timezone=True)),
        sa.Column('result_24h',sa.JSON(),nullable=False),sa.Column('result_72h',sa.JSON(),nullable=False),sa.Column('result_7d',sa.JSON(),nullable=False),
        sa.Column('error_code',sa.String(64)),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('id',sa.Uuid(as_uuid=False),primary_key=True),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.ForeignKeyConstraint(['connection_id'],['meta_connections.id']),sa.ForeignKeyConstraint(['workspace_id'],['workspaces.id']),
        sa.ForeignKeyConstraint(['user_id'],['users.id']),sa.ForeignKeyConstraint(['approved_by'],['users.id']),
        sa.ForeignKeyConstraint(['recommendation_id'],['ad_recommendations.id']),sa.UniqueConstraint('connection_id','request_key'),
        sa.CheckConstraint("platform in ('meta')"),sa.CheckConstraint("resource_type in ('campaign','adset','ad')"),
        sa.CheckConstraint("action_type in ('pause','resume','update_budget')"),sa.CheckConstraint("approval_status in ('copilot_pending','copilot_confirmed')"),
        sa.CheckConstraint("execution_status in ('pending','executing','simulated','succeeded','failed','unknown','stale')"),
        sa.CheckConstraint('confidence is null or (confidence >= 0 and confidence <= 1)'))
    op.create_index(op.f('ix_ads_actions_connection_id'),'ads_actions',['connection_id'])
    op.create_index(op.f('ix_ads_actions_workspace_id'),'ads_actions',['workspace_id'])
    op.create_index('ads_actions_resource','ads_actions',['connection_id','connection_version','resource_type','resource_id','created_at'])
    op.create_table('ads_action_audits',
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('action_id',sa.Uuid(as_uuid=False),nullable=False),
        sa.Column('actor_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('event',sa.String(64),nullable=False),
        sa.Column('action_version',sa.Integer(),nullable=False),sa.Column('data',sa.JSON(),nullable=False),
        sa.Column('id',sa.Uuid(as_uuid=False),primary_key=True),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'],['workspaces.id']),sa.ForeignKeyConstraint(['action_id'],['ads_actions.id']),
        sa.ForeignKeyConstraint(['actor_id'],['users.id']))
    op.create_index(op.f('ix_ads_action_audits_workspace_id'),'ads_action_audits',['workspace_id'])
    op.create_index(op.f('ix_ads_action_audits_action_id'),'ads_action_audits',['action_id'])


def downgrade():
    op.drop_index(op.f('ix_ads_action_audits_action_id'),table_name='ads_action_audits');op.drop_index(op.f('ix_ads_action_audits_workspace_id'),table_name='ads_action_audits');op.drop_table('ads_action_audits')
    op.drop_index('ads_actions_resource',table_name='ads_actions');op.drop_index(op.f('ix_ads_actions_workspace_id'),table_name='ads_actions');op.drop_index(op.f('ix_ads_actions_connection_id'),table_name='ads_actions');op.drop_table('ads_actions')
