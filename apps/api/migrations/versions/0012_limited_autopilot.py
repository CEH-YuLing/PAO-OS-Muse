"""limited_autopilot"""
from alembic import op
import sqlalchemy as sa

revision='0012'
down_revision='0011'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('ads_autopilot_policies',
        sa.Column('connection_id',sa.Uuid(as_uuid=False),sa.ForeignKey('meta_connections.id'),nullable=False),
        sa.Column('connection_version',sa.Integer(),nullable=False),
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),sa.ForeignKey('workspaces.id'),nullable=False),
        sa.Column('account_id',sa.String(64),nullable=False),
        sa.Column('mode',sa.String(16),nullable=False),sa.Column('halted',sa.Boolean(),nullable=False),
        sa.Column('pause_allowed',sa.Boolean(),nullable=False),sa.Column('resume_allowed',sa.Boolean(),nullable=False),
        sa.Column('budget_allowed',sa.Boolean(),nullable=False),sa.Column('max_budget_change_pct',sa.Integer(),nullable=False),
        sa.Column('max_daily_budget_minor_units',sa.BigInteger(),nullable=True),
        sa.Column('minimum_impressions',sa.BigInteger(),nullable=False),sa.Column('minimum_conversions',sa.Integer(),nullable=False),
        sa.Column('minimum_confidence',sa.Numeric(5,4),nullable=False),sa.Column('freshness_minutes',sa.Integer(),nullable=False),
        sa.Column('quiet_hours_enabled',sa.Boolean(),nullable=False),sa.Column('quiet_start',sa.Time(),nullable=False),
        sa.Column('quiet_end',sa.Time(),nullable=False),sa.Column('max_actions_per_day',sa.Integer(),nullable=False),
        sa.Column('emergency_frozen',sa.Boolean(),nullable=False),sa.Column('freeze_reason',sa.String(120),nullable=True),
        sa.Column('version',sa.Integer(),nullable=False),sa.Column('updated_by',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('id',sa.Uuid(as_uuid=False),primary_key=True),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('workspace_id','account_id'),
        sa.CheckConstraint("mode in ('observer','advisor','copilot','autopilot')"),
        sa.CheckConstraint('max_budget_change_pct between 1 and 20'),
        sa.CheckConstraint('max_daily_budget_minor_units is null or max_daily_budget_minor_units > 0'),
        sa.CheckConstraint('minimum_impressions >= 0 and minimum_conversions >= 0'),
        sa.CheckConstraint('minimum_confidence >= 0 and minimum_confidence <= 1'),
        sa.CheckConstraint('freshness_minutes between 15 and 1440'),sa.CheckConstraint('max_actions_per_day between 1 and 100'))
    op.create_index('ix_ads_autopilot_policies_workspace_id','ads_autopilot_policies',['workspace_id'])
    op.create_table('ads_policy_audits',
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),sa.ForeignKey('workspaces.id'),nullable=False),
        sa.Column('policy_id',sa.Uuid(as_uuid=False),sa.ForeignKey('ads_autopilot_policies.id'),nullable=False),
        sa.Column('actor_id',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('event',sa.String(64),nullable=False),sa.Column('policy_version',sa.Integer(),nullable=False),
        sa.Column('data',sa.JSON(),nullable=False),sa.Column('id',sa.Uuid(as_uuid=False),primary_key=True),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_ads_policy_audits_workspace_id','ads_policy_audits',['workspace_id'])
    op.create_index('ix_ads_policy_audits_policy_id','ads_policy_audits',['policy_id'])
    op.drop_constraint('ads_actions_decision_channel_check','ads_actions',type_='check')
    op.add_column('ads_actions',sa.Column('policy_id',sa.Uuid(as_uuid=False),sa.ForeignKey('ads_autopilot_policies.id'),nullable=True))
    op.add_column('ads_actions',sa.Column('policy_version',sa.Integer(),nullable=True))
    op.add_column('ads_actions',sa.Column('policy_snapshot',sa.JSON(),nullable=False,server_default=sa.text("'{}'::json")))
    op.create_check_constraint('ads_actions_decision_channel_check','ads_actions',
        "decision_channel is null or decision_channel in ('ui','telegram','autopilot')")


def downgrade():
    op.drop_constraint('ads_actions_decision_channel_check','ads_actions',type_='check')
    op.execute("update ads_actions set decision_channel='ui' where decision_channel='autopilot'")
    op.drop_column('ads_actions','policy_snapshot');op.drop_column('ads_actions','policy_version');op.drop_column('ads_actions','policy_id')
    op.create_check_constraint('ads_actions_decision_channel_check','ads_actions',
        "decision_channel is null or decision_channel in ('ui','telegram')")
    op.drop_index('ix_ads_policy_audits_policy_id',table_name='ads_policy_audits')
    op.drop_index('ix_ads_policy_audits_workspace_id',table_name='ads_policy_audits');op.drop_table('ads_policy_audits')
    op.drop_index('ix_ads_autopilot_policies_workspace_id',table_name='ads_autopilot_policies');op.drop_table('ads_autopilot_policies')
