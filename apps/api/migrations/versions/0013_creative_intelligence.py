"""creative_intelligence"""
from alembic import op
import sqlalchemy as sa

revision='0013'
down_revision='0012'
branch_labels=None
depends_on=None

ID=lambda:sa.Column('id',sa.Uuid(as_uuid=False),primary_key=True)
CREATED=lambda:sa.Column('created_at',sa.DateTime(timezone=True),nullable=False)

def upgrade():
    op.create_table('creative_assets',
        sa.Column('connection_id',sa.Uuid(as_uuid=False),sa.ForeignKey('meta_connections.id'),nullable=False),sa.Column('connection_version',sa.Integer(),nullable=False),
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),sa.ForeignKey('workspaces.id'),nullable=False),sa.Column('account_id',sa.String(64),nullable=False),
        sa.Column('creative_id',sa.String(64),nullable=False),sa.Column('name',sa.Text()),sa.Column('source_job_id',sa.Uuid(as_uuid=False),sa.ForeignKey('meta_sync_jobs.id'),nullable=False),
        sa.Column('first_seen_at',sa.DateTime(timezone=True),nullable=False),sa.Column('last_seen_at',sa.DateTime(timezone=True),nullable=False),ID(),CREATED(),
        sa.UniqueConstraint('connection_id','connection_version','account_id','creative_id'))
    op.create_index('ix_creative_assets_connection_id','creative_assets',['connection_id']);op.create_index('ix_creative_assets_workspace_id','creative_assets',['workspace_id'])
    op.create_table('creative_metadata',sa.Column('asset_id',sa.Uuid(as_uuid=False),sa.ForeignKey('creative_assets.id'),nullable=False,unique=True),
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),sa.ForeignKey('workspaces.id'),nullable=False),sa.Column('brand_id',sa.Uuid(as_uuid=False)),
        sa.Column('product',sa.String(160)),sa.Column('market',sa.String(80)),sa.Column('language',sa.String(32)),sa.Column('format',sa.String(64)),sa.Column('duration_seconds',sa.Integer()),
        sa.Column('hook',sa.Text()),sa.Column('angle',sa.Text()),sa.Column('offer',sa.Text()),sa.Column('cta',sa.String(160)),sa.Column('creator',sa.String(160)),sa.Column('landing_page',sa.Text()),
        sa.Column('source',sa.String(16),nullable=False),sa.Column('version',sa.Integer(),nullable=False),sa.Column('updated_by',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),ID(),CREATED(),sa.ForeignKeyConstraint(['brand_id','workspace_id'],['brands.id','brands.workspace_id']),
        sa.CheckConstraint("source in ('manual','imported')"),sa.CheckConstraint('duration_seconds is null or duration_seconds between 1 and 86400'))
    op.create_index('ix_creative_metadata_workspace_id','creative_metadata',['workspace_id'])
    op.create_table('creative_analysis_runs',sa.Column('connection_id',sa.Uuid(as_uuid=False),sa.ForeignKey('meta_connections.id'),nullable=False),sa.Column('connection_version',sa.Integer(),nullable=False),
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),sa.ForeignKey('workspaces.id'),nullable=False),sa.Column('user_id',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('account_id',sa.String(64),nullable=False),sa.Column('request_key',sa.String(100),nullable=False),sa.Column('as_of',sa.Date(),nullable=False),
        sa.Column('current_days',sa.Integer(),nullable=False),sa.Column('baseline_days',sa.Integer(),nullable=False),sa.Column('configuration',sa.JSON(),nullable=False),
        sa.Column('analyst_version',sa.String(32),nullable=False),sa.Column('summary',sa.JSON(),nullable=False),sa.Column('source_updated_at',sa.DateTime(timezone=True),nullable=False),ID(),CREATED(),
        sa.UniqueConstraint('connection_id','request_key'),sa.CheckConstraint('current_days between 2 and 14 and baseline_days between 2 and 28'))
    op.create_index('ix_creative_analysis_runs_connection_id','creative_analysis_runs',['connection_id']);op.create_index('ix_creative_analysis_runs_workspace_id','creative_analysis_runs',['workspace_id'])
    op.create_table('creative_performance',sa.Column('run_id',sa.Uuid(as_uuid=False),sa.ForeignKey('creative_analysis_runs.id'),nullable=False),sa.Column('asset_id',sa.Uuid(as_uuid=False),sa.ForeignKey('creative_assets.id'),nullable=False),
        sa.Column('sample_window',sa.String(16),nullable=False),sa.Column('period_start',sa.Date(),nullable=False),sa.Column('period_end',sa.Date(),nullable=False),sa.Column('currency',sa.String(3),nullable=False),sa.Column('timezone',sa.String(80),nullable=False),
        sa.Column('spend',sa.Numeric(24,6),nullable=False),sa.Column('impressions',sa.BigInteger(),nullable=False),sa.Column('clicks',sa.BigInteger(),nullable=False),sa.Column('purchases',sa.Numeric(24,6),nullable=False),sa.Column('revenue',sa.Numeric(24,6),nullable=False),
        sa.Column('ctr',sa.Numeric(24,6)),sa.Column('cpm',sa.Numeric(24,6)),sa.Column('cpa',sa.Numeric(24,6)),sa.Column('roas',sa.Numeric(24,6)),sa.Column('frequency',sa.Numeric(24,6)),
        sa.Column('ad_count',sa.Integer(),nullable=False),sa.Column('coverage_days',sa.Integer(),nullable=False),ID(),CREATED(),sa.UniqueConstraint('run_id','asset_id','sample_window'),sa.CheckConstraint("sample_window in ('current','baseline')"),sa.CheckConstraint('period_end >= period_start'))
    op.create_index('ix_creative_performance_run_id','creative_performance',['run_id']);op.create_index('ix_creative_performance_asset_id','creative_performance',['asset_id'])
    op.create_table('creative_features',sa.Column('run_id',sa.Uuid(as_uuid=False),sa.ForeignKey('creative_analysis_runs.id'),nullable=False),sa.Column('asset_id',sa.Uuid(as_uuid=False),sa.ForeignKey('creative_assets.id'),nullable=False),
        sa.Column('fatigue_status',sa.String(16),nullable=False),sa.Column('fatigue_score',sa.Numeric(5,4),nullable=False),sa.Column('confidence',sa.Numeric(5,4),nullable=False),sa.Column('age_days',sa.Integer(),nullable=False),
        sa.Column('signals',sa.JSON(),nullable=False),sa.Column('strategy_brief',sa.JSON(),nullable=False),ID(),CREATED(),sa.UniqueConstraint('run_id','asset_id'),sa.CheckConstraint("fatigue_status in ('healthy','watch','fatigued','insufficient')"),sa.CheckConstraint('fatigue_score between 0 and 1 and confidence between 0 and 1'))
    op.create_index('ix_creative_features_run_id','creative_features',['run_id']);op.create_index('ix_creative_features_asset_id','creative_features',['asset_id'])
    op.create_table('creative_learnings',sa.Column('connection_id',sa.Uuid(as_uuid=False),sa.ForeignKey('meta_connections.id'),nullable=False),sa.Column('connection_version',sa.Integer(),nullable=False),
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),sa.ForeignKey('workspaces.id'),nullable=False),sa.Column('account_id',sa.String(64),nullable=False),sa.Column('latest_run_id',sa.Uuid(as_uuid=False),sa.ForeignKey('creative_analysis_runs.id'),nullable=False),
        sa.Column('dimension',sa.String(32),nullable=False),sa.Column('value',sa.Text(),nullable=False),sa.Column('statement',sa.Text(),nullable=False),sa.Column('confidence',sa.Numeric(5,4),nullable=False),sa.Column('evidence',sa.JSON(),nullable=False),
        sa.Column('fingerprint',sa.String(64),nullable=False,unique=True),sa.Column('status',sa.String(16),nullable=False),sa.Column('first_seen_at',sa.DateTime(timezone=True),nullable=False),sa.Column('last_seen_at',sa.DateTime(timezone=True),nullable=False),ID(),CREATED(),
        sa.CheckConstraint("dimension in ('hook','angle','format','duration','market')"),sa.CheckConstraint("status in ('active','resolved')"),sa.CheckConstraint('confidence between 0 and 1'))
    op.create_index('ix_creative_learnings_connection_id','creative_learnings',['connection_id']);op.create_index('ix_creative_learnings_workspace_id','creative_learnings',['workspace_id'])

def downgrade():
    for table,indexes in [('creative_learnings',['ix_creative_learnings_workspace_id','ix_creative_learnings_connection_id']),('creative_features',['ix_creative_features_asset_id','ix_creative_features_run_id']),('creative_performance',['ix_creative_performance_asset_id','ix_creative_performance_run_id']),('creative_analysis_runs',['ix_creative_analysis_runs_workspace_id','ix_creative_analysis_runs_connection_id']),('creative_metadata',['ix_creative_metadata_workspace_id']),('creative_assets',['ix_creative_assets_workspace_id','ix_creative_assets_connection_id'])]:
        for index in indexes:op.drop_index(index,table_name=table)
        op.drop_table(table)
