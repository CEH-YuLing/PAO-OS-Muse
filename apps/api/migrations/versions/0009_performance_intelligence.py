"""performance_intelligence"""
from alembic import op
import sqlalchemy as sa

revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('ad_targets',
        sa.Column('connection_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('connection_version',sa.Integer(),nullable=False),
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('account_id',sa.String(64),nullable=False),
        sa.Column('target_cpa',sa.Numeric(24,6)),sa.Column('target_roas',sa.Numeric(24,6)),
        sa.Column('minimum_spend',sa.Numeric(24,6),nullable=False),sa.Column('minimum_impressions',sa.BigInteger(),nullable=False),
        sa.Column('minimum_clicks',sa.BigInteger(),nullable=False),sa.Column('minimum_conversions',sa.Integer(),nullable=False),
        sa.Column('minimum_run_days',sa.Integer(),nullable=False),sa.Column('freshness_minutes',sa.Integer(),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),sa.Column('id',sa.Uuid(as_uuid=False),primary_key=True),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.ForeignKeyConstraint(['connection_id'],['meta_connections.id']),
        sa.ForeignKeyConstraint(['workspace_id'],['workspaces.id']),sa.UniqueConstraint('connection_id','account_id'),
        sa.CheckConstraint('target_cpa is null or target_cpa > 0'),sa.CheckConstraint('target_roas is null or target_roas > 0'),
        sa.CheckConstraint('minimum_spend >= 0 and minimum_impressions >= 0 and minimum_clicks >= 0'),
        sa.CheckConstraint('minimum_conversions >= 0 and minimum_run_days between 1 and 30'),sa.CheckConstraint('freshness_minutes between 15 and 10080'))
    op.create_index(op.f('ix_ad_targets_workspace_id'),'ad_targets',['workspace_id'])
    op.create_table('ads_rules',
        sa.Column('connection_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('connection_version',sa.Integer(),nullable=False),
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('account_id',sa.String(64),nullable=False),
        sa.Column('brand_id',sa.Uuid(as_uuid=False)),sa.Column('platform',sa.String(16),nullable=False),sa.Column('code',sa.String(64),nullable=False),
        sa.Column('name',sa.String(120),nullable=False),sa.Column('conditions_json',sa.JSON(),nullable=False),sa.Column('action_json',sa.JSON(),nullable=False),
        sa.Column('mode',sa.String(16),nullable=False),sa.Column('enabled',sa.Boolean(),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('id',sa.Uuid(as_uuid=False),primary_key=True),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.ForeignKeyConstraint(['connection_id'],['meta_connections.id']),sa.ForeignKeyConstraint(['workspace_id'],['workspaces.id']),
        sa.UniqueConstraint('connection_id','account_id','code'),sa.CheckConstraint("platform in ('meta')"),sa.CheckConstraint("mode in ('advisor')"))
    op.create_index(op.f('ix_ads_rules_workspace_id'),'ads_rules',['workspace_id'])
    op.create_table('ad_intelligence_runs',
        sa.Column('connection_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('connection_version',sa.Integer(),nullable=False),
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('user_id',sa.Uuid(as_uuid=False),nullable=False),
        sa.Column('account_id',sa.String(64),nullable=False),sa.Column('request_key',sa.String(100),nullable=False),
        sa.Column('granularity',sa.String(8),nullable=False),sa.Column('period_start',sa.Date(),nullable=False),sa.Column('period_end',sa.Date(),nullable=False),
        sa.Column('hour',sa.Integer()),sa.Column('analyst_version',sa.String(32),nullable=False),sa.Column('summary',sa.JSON(),nullable=False),
        sa.Column('source_updated_at',sa.DateTime(timezone=True),nullable=False),sa.Column('id',sa.Uuid(as_uuid=False),primary_key=True),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.ForeignKeyConstraint(['connection_id'],['meta_connections.id']),
        sa.ForeignKeyConstraint(['workspace_id'],['workspaces.id']),sa.ForeignKeyConstraint(['user_id'],['users.id']),
        sa.UniqueConstraint('connection_id','request_key'),sa.CheckConstraint("granularity in ('daily','hourly')"),
        sa.CheckConstraint("(granularity='daily' and hour is null) or (granularity='hourly' and hour between 0 and 23)"))
    op.create_index(op.f('ix_ad_intelligence_runs_connection_id'),'ad_intelligence_runs',['connection_id'])
    op.create_index(op.f('ix_ad_intelligence_runs_workspace_id'),'ad_intelligence_runs',['workspace_id'])
    op.create_table('ad_anomalies',
        sa.Column('connection_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('connection_version',sa.Integer(),nullable=False),
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('run_id',sa.Uuid(as_uuid=False),nullable=False),
        sa.Column('account_id',sa.String(64),nullable=False),sa.Column('resource_id',sa.String(64),nullable=False),
        sa.Column('kind',sa.String(64),nullable=False),sa.Column('severity',sa.String(16),nullable=False),sa.Column('fingerprint',sa.String(64),nullable=False,unique=True),
        sa.Column('current_value',sa.Numeric(24,6)),sa.Column('baseline_value',sa.Numeric(24,6)),sa.Column('deviation_pct',sa.Numeric(24,6)),
        sa.Column('evidence',sa.JSON(),nullable=False),sa.Column('first_seen',sa.DateTime(timezone=True),nullable=False),sa.Column('last_seen',sa.DateTime(timezone=True),nullable=False),
        sa.Column('acknowledged',sa.Boolean(),nullable=False),sa.Column('resolved',sa.Boolean(),nullable=False),
        sa.Column('id',sa.Uuid(as_uuid=False),primary_key=True),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.ForeignKeyConstraint(['connection_id'],['meta_connections.id']),sa.ForeignKeyConstraint(['workspace_id'],['workspaces.id']),
        sa.ForeignKeyConstraint(['run_id'],['ad_intelligence_runs.id']),sa.CheckConstraint("severity in ('info','notice','warning','critical')"))
    op.create_index('ad_anomalies_scope','ad_anomalies',['connection_id','connection_version','account_id','resolved','last_seen'])
    op.create_index(op.f('ix_ad_anomalies_workspace_id'),'ad_anomalies',['workspace_id'])
    op.create_table('ad_recommendations',
        sa.Column('connection_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('connection_version',sa.Integer(),nullable=False),
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('run_id',sa.Uuid(as_uuid=False),nullable=False),
        sa.Column('account_id',sa.String(64),nullable=False),sa.Column('resource_id',sa.String(64),nullable=False),sa.Column('type',sa.String(64),nullable=False),
        sa.Column('confidence',sa.Numeric(5,4),nullable=False),sa.Column('impact',sa.JSON(),nullable=False),sa.Column('reason_codes',sa.JSON(),nullable=False),
        sa.Column('explanation',sa.Text(),nullable=False),sa.Column('proposed_action',sa.JSON(),nullable=False),sa.Column('source',sa.JSON(),nullable=False),
        sa.Column('data_freshness_seconds',sa.Integer(),nullable=False),sa.Column('fingerprint',sa.String(64),nullable=False,unique=True),
        sa.Column('status',sa.String(16),nullable=False),sa.Column('first_seen',sa.DateTime(timezone=True),nullable=False),sa.Column('last_seen',sa.DateTime(timezone=True),nullable=False),
        sa.Column('id',sa.Uuid(as_uuid=False),primary_key=True),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.ForeignKeyConstraint(['connection_id'],['meta_connections.id']),sa.ForeignKeyConstraint(['workspace_id'],['workspaces.id']),
        sa.ForeignKeyConstraint(['run_id'],['ad_intelligence_runs.id']),sa.CheckConstraint('confidence >= 0 and confidence <= 1'),
        sa.CheckConstraint("status in ('active','dismissed','resolved')"))
    op.create_index('ad_recommendations_scope','ad_recommendations',['connection_id','connection_version','account_id','status','last_seen'])
    op.create_index(op.f('ix_ad_recommendations_workspace_id'),'ad_recommendations',['workspace_id'])


def downgrade():
    op.drop_index(op.f('ix_ad_recommendations_workspace_id'),table_name='ad_recommendations');op.drop_index('ad_recommendations_scope',table_name='ad_recommendations');op.drop_table('ad_recommendations')
    op.drop_index(op.f('ix_ad_anomalies_workspace_id'),table_name='ad_anomalies');op.drop_index('ad_anomalies_scope',table_name='ad_anomalies');op.drop_table('ad_anomalies')
    op.drop_index(op.f('ix_ad_intelligence_runs_workspace_id'),table_name='ad_intelligence_runs');op.drop_index(op.f('ix_ad_intelligence_runs_connection_id'),table_name='ad_intelligence_runs');op.drop_table('ad_intelligence_runs')
    op.drop_index(op.f('ix_ads_rules_workspace_id'),table_name='ads_rules');op.drop_table('ads_rules')
    op.drop_index(op.f('ix_ad_targets_workspace_id'),table_name='ad_targets');op.drop_table('ad_targets')
