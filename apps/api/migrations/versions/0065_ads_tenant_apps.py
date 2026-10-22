"""Explicit SME app selection with rotation revocation and OAuth config pins."""
from alembic import op
import sqlalchemy as sa

revision='0065'
down_revision='0064'
branch_labels=depends_on=None


def upgrade():
    for table in ('meta_connections','google_ads_connections','meta_oauth_states','google_ads_oauth_states'):
        op.add_column(table,sa.Column('app_binding',sa.String(64)))
    op.create_table('ads_app_configs',
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),sa.ForeignKey('workspaces.id'),primary_key=True),
        sa.Column('provider',sa.String(16),primary_key=True),sa.Column('mode',sa.String(16),nullable=False),
        sa.Column('revision',sa.Integer(),nullable=False),sa.Column('credential_ciphertext',sa.Text()),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False,server_default=sa.text('now()')),
        sa.CheckConstraint("provider IN ('meta','google') AND revision>=1 AND (mode='managed' AND credential_ciphertext IS NULL OR mode='byo' AND credential_ciphertext IS NOT NULL)",name='ads_app_config_state'))
    op.create_table('ads_app_audits',
        sa.Column('id',sa.Uuid(as_uuid=False),primary_key=True),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('provider',sa.String(16),nullable=False),
        sa.Column('actor_id',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('revision',sa.Integer(),nullable=False),sa.Column('mode',sa.String(16),nullable=False),
        sa.ForeignKeyConstraint(['workspace_id','provider'],['ads_app_configs.workspace_id','ads_app_configs.provider']),
        sa.UniqueConstraint('workspace_id','provider','revision'),
        sa.CheckConstraint("revision>=1 AND mode IN ('managed','byo')",name='ads_app_audit_state'))
    op.execute('''CREATE FUNCTION pao_ads_app_guard() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF TG_OP='DELETE' OR TG_TABLE_NAME='ads_app_audits' THEN RAISE EXCEPTION 'ads_app_history_immutable'; END IF;
        IF TG_OP='UPDATE' AND ((NEW.workspace_id,NEW.provider) IS DISTINCT FROM (OLD.workspace_id,OLD.provider) OR NEW.revision<>OLD.revision+1)
          THEN RAISE EXCEPTION 'ads_app_revision_immutable'; END IF;
        RETURN NEW;
      END $$''')
    op.execute('CREATE TRIGGER ads_app_config_guard BEFORE UPDATE OR DELETE ON ads_app_configs FOR EACH ROW EXECUTE FUNCTION pao_ads_app_guard()')
    op.execute('CREATE TRIGGER ads_app_audit_guard BEFORE UPDATE OR DELETE ON ads_app_audits FOR EACH ROW EXECUTE FUNCTION pao_ads_app_guard()')
    op.execute('''CREATE FUNCTION pao_ads_app_revoke() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF NEW.provider='meta' THEN
          UPDATE meta_connections SET version=version+1,status='disconnected',token_ciphertext=NULL,scopes='[]'::json,expires_at=NULL,remote_user_id=NULL,app_binding=NULL WHERE workspace_id=NEW.workspace_id;
          UPDATE meta_oauth_states SET used=true WHERE connection_id IN (SELECT id FROM meta_connections WHERE workspace_id=NEW.workspace_id);
          UPDATE meta_sync_jobs SET status='cancelled',updated_at=now() WHERE status IN ('queued','running') AND connection_id IN (SELECT id FROM meta_connections WHERE workspace_id=NEW.workspace_id);
        ELSE
          UPDATE google_ads_connections SET version=version+1,status='disconnected',refresh_token_ciphertext=NULL,scopes='[]'::json,app_binding=NULL WHERE workspace_id=NEW.workspace_id;
          UPDATE google_ads_oauth_states SET used=true WHERE connection_id IN (SELECT id FROM google_ads_connections WHERE workspace_id=NEW.workspace_id);
          UPDATE google_ads_sync_jobs SET status='cancelled',updated_at=now() WHERE status IN ('queued','running') AND connection_id IN (SELECT id FROM google_ads_connections WHERE workspace_id=NEW.workspace_id);
        END IF;
        RETURN NEW;
      END $$''')
    op.execute('CREATE TRIGGER ads_app_revoke AFTER INSERT OR UPDATE ON ads_app_configs FOR EACH ROW EXECUTE FUNCTION pao_ads_app_revoke()')


def downgrade():
    populated=op.get_bind().scalar(sa.text('SELECT EXISTS(SELECT 1 FROM ads_app_configs) OR EXISTS(SELECT 1 FROM ads_app_audits)'))
    for table in ('meta_connections','google_ads_connections','meta_oauth_states','google_ads_oauth_states'):
        populated=populated or op.get_bind().scalar(sa.text('SELECT EXISTS(SELECT 1 FROM '+table+' WHERE app_binding IS NOT NULL)'))
    if populated:raise RuntimeError('Populated S4 app history cannot be discarded; restore an approved checkpoint instead')
    op.execute('DROP TRIGGER ads_app_revoke ON ads_app_configs')
    op.execute('DROP TRIGGER ads_app_config_guard ON ads_app_configs')
    op.execute('DROP TRIGGER ads_app_audit_guard ON ads_app_audits')
    op.execute('DROP FUNCTION pao_ads_app_revoke()');op.execute('DROP FUNCTION pao_ads_app_guard()')
    op.drop_table('ads_app_audits');op.drop_table('ads_app_configs')
    for table in ('meta_connections','google_ads_connections','meta_oauth_states','google_ads_oauth_states'):op.drop_column(table,'app_binding')
