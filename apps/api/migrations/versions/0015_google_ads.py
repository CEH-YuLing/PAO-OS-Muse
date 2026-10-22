"""google_ads

Revision ID: 0015
Revises: 0014
"""
from alembic import op
import sqlalchemy as sa
revision='0015';down_revision='0014';branch_labels=None;depends_on=None
def upgrade():
    op.create_table('google_ads_connections',
      sa.Column('workspace_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('user_id',sa.Uuid(as_uuid=False),nullable=False),
      sa.Column('refresh_token_ciphertext',sa.Text(),nullable=True),sa.Column('scopes',sa.JSON(),nullable=False),sa.Column('connected_at',sa.DateTime(timezone=True),nullable=True),
      sa.Column('status',sa.String(24),nullable=False),sa.Column('version',sa.Integer(),nullable=False),sa.Column('id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
      sa.CheckConstraint("status in ('disconnected','connected','expired')"),sa.ForeignKeyConstraint(['user_id'],['users.id']),sa.ForeignKeyConstraint(['workspace_id'],['workspaces.id']),sa.PrimaryKeyConstraint('id'),sa.UniqueConstraint('workspace_id','user_id'))
    op.create_index(op.f('ix_google_ads_connections_user_id'),'google_ads_connections',['user_id']);op.create_index(op.f('ix_google_ads_connections_workspace_id'),'google_ads_connections',['workspace_id'])
    op.create_table('google_ads_oauth_states',sa.Column('digest',sa.String(64),nullable=False),sa.Column('connection_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('browser_digest',sa.String(64),nullable=False),sa.Column('connection_version',sa.Integer(),nullable=False),sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),sa.Column('used',sa.Boolean(),nullable=False),sa.ForeignKeyConstraint(['connection_id'],['google_ads_connections.id']),sa.PrimaryKeyConstraint('digest'))
    op.create_table('google_ads_sync_jobs',sa.Column('connection_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('connection_version',sa.Integer(),nullable=False),sa.Column('api_version',sa.String(16),nullable=False),sa.Column('request_key',sa.String(64),nullable=False),sa.Column('kind',sa.String(16),nullable=False),sa.Column('account_id',sa.String(32),nullable=True),sa.Column('since',sa.String(10),nullable=True),sa.Column('until',sa.String(10),nullable=True),sa.Column('granularity',sa.String(8),nullable=False),sa.Column('status',sa.String(20),nullable=False),sa.Column('error_code',sa.String(64),nullable=True),sa.Column('row_count',sa.Integer(),nullable=False),sa.Column('attempts',sa.Integer(),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),sa.Column('id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.CheckConstraint("granularity in ('daily','hourly')"),sa.CheckConstraint("kind in ('accounts','historical')"),sa.CheckConstraint("status in ('queued','running','completed','failed','cancelled')"),sa.ForeignKeyConstraint(['connection_id'],['google_ads_connections.id']),sa.PrimaryKeyConstraint('id'),sa.UniqueConstraint('connection_id','request_key'))
    op.create_index(op.f('ix_google_ads_sync_jobs_connection_id'),'google_ads_sync_jobs',['connection_id'])
    for table in ('ad_entities','ad_metrics'):
        op.alter_column(table,'connection_id',existing_type=sa.Uuid(as_uuid=False),nullable=True);op.alter_column(table,'source_job_id',existing_type=sa.Uuid(as_uuid=False),nullable=True)
        op.add_column(table,sa.Column('google_connection_id',sa.Uuid(as_uuid=False),nullable=True));op.add_column(table,sa.Column('google_source_job_id',sa.Uuid(as_uuid=False),nullable=True))
        op.create_foreign_key(f'{table}_google_connection_fkey',table,'google_ads_connections',['google_connection_id'],['id']);op.create_foreign_key(f'{table}_google_source_job_fkey',table,'google_ads_sync_jobs',['google_source_job_id'],['id'])
        op.create_check_constraint(f'{table}_platform_check',table,"platform in ('meta','google')")
        op.create_check_constraint(f'{table}_platform_source_check',table,"(platform='meta' and connection_id is not null and google_connection_id is null and source_job_id is not null and google_source_job_id is null) or (platform='google' and connection_id is null and google_connection_id is not null and source_job_id is null and google_source_job_id is not null)")
    op.create_unique_constraint('ad_entities_google_scope_key','ad_entities',['google_connection_id','connection_version','account_id','kind','remote_id'])
    op.create_unique_constraint('ad_metrics_google_scope_key','ad_metrics',['google_connection_id','connection_version','account_id','level','entity_id','day','hour','granularity','attribution'])
    op.add_column('ad_metrics',sa.Column('conversions',sa.Numeric(24,6),nullable=True));op.add_column('ad_metrics',sa.Column('conversion_value',sa.Numeric(24,6),nullable=True))
    op.execute("UPDATE ad_metrics SET conversions=purchase, conversion_value=revenue WHERE platform='meta'")
    op.create_index('ad_metrics_google_scope_date','ad_metrics',['google_connection_id','connection_version','account_id','granularity','level','day'])
def downgrade():
    op.drop_index('ad_metrics_google_scope_date',table_name='ad_metrics');op.drop_column('ad_metrics','conversion_value');op.drop_column('ad_metrics','conversions')
    op.drop_constraint('ad_metrics_google_scope_key','ad_metrics',type_='unique');op.drop_constraint('ad_entities_google_scope_key','ad_entities',type_='unique')
    for table in ('ad_metrics','ad_entities'):
        op.drop_constraint(f'{table}_platform_source_check',table,type_='check');op.drop_constraint(f'{table}_platform_check',table,type_='check');op.drop_constraint(f'{table}_google_source_job_fkey',table,type_='foreignkey');op.drop_constraint(f'{table}_google_connection_fkey',table,type_='foreignkey');op.drop_column(table,'google_source_job_id');op.drop_column(table,'google_connection_id');op.alter_column(table,'source_job_id',existing_type=sa.Uuid(as_uuid=False),nullable=False);op.alter_column(table,'connection_id',existing_type=sa.Uuid(as_uuid=False),nullable=False)
    op.drop_index(op.f('ix_google_ads_sync_jobs_connection_id'),table_name='google_ads_sync_jobs');op.drop_table('google_ads_sync_jobs');op.drop_table('google_ads_oauth_states');op.drop_index(op.f('ix_google_ads_connections_workspace_id'),table_name='google_ads_connections');op.drop_index(op.f('ix_google_ads_connections_user_id'),table_name='google_ads_connections');op.drop_table('google_ads_connections')
