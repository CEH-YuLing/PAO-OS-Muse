"""Staged tenant references/grants. No credential copy or automatic mapping."""
from alembic import op
import sqlalchemy as sa

revision = '0049'
down_revision = '0048'
branch_labels = depends_on = None


def identity():
    return [sa.Column('id', sa.Uuid(as_uuid=False), primary_key=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False)]


def upgrade():
    op.create_table('tenant_connection_references', *identity(),
        sa.Column('workspace_id', sa.Uuid(as_uuid=False), sa.ForeignKey('workspaces.id'), nullable=False),
        sa.Column('kind', sa.String(16), nullable=False), sa.Column('source_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('provider', sa.String(24), nullable=False),
        sa.Column('manager_id', sa.Uuid(as_uuid=False), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('source_version', sa.Integer()), sa.Column('source_stamp', sa.String(64), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False), sa.Column('status', sa.String(16), nullable=False),
        sa.UniqueConstraint('id', 'workspace_id'), sa.UniqueConstraint('workspace_id', 'kind', 'source_id'),
        sa.CheckConstraint("kind IN ('model','mcp','meta_ads','google_ads') AND status IN ('staged','revoked') AND revision>=1 AND length(source_stamp)=64 AND (source_version IS NULL OR source_version>=1)", name='tenant_connection_reference_state'))
    op.create_table('tenant_connection_grants', *identity(),
        sa.Column('workspace_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('reference_id', sa.Uuid(as_uuid=False), nullable=False), sa.Column('reference_revision', sa.Integer(), nullable=False),
        sa.Column('creator_id', sa.Uuid(as_uuid=False), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('grantee_id', sa.Uuid(as_uuid=False), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('brand_id', sa.Uuid(as_uuid=False)), sa.Column('account_id', sa.String(64)),
        sa.Column('permission', sa.String(16), nullable=False), sa.Column('request_key', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('fingerprint', sa.String(64), nullable=False), sa.Column('ttl_minutes', sa.Integer(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False), sa.Column('status', sa.String(16), nullable=False),
        sa.UniqueConstraint('id', 'workspace_id'), sa.UniqueConstraint('workspace_id', 'creator_id', 'request_key'),
        sa.ForeignKeyConstraint(['reference_id', 'workspace_id'], ['tenant_connection_references.id', 'tenant_connection_references.workspace_id']),
        sa.ForeignKeyConstraint(['brand_id', 'workspace_id'], ['brands.id', 'brands.workspace_id']),
        sa.CheckConstraint("permission='read_only' AND status IN ('staged','revoked') AND revision>=1 AND reference_revision>=1 AND ttl_minutes BETWEEN 1 AND 43200 AND length(fingerprint)=64", name='tenant_connection_grant_state'))
    op.create_table('tenant_connection_audits', *identity(),
        sa.Column('workspace_id', sa.Uuid(as_uuid=False), nullable=False), sa.Column('reference_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('grant_id', sa.Uuid(as_uuid=False)), sa.Column('actor_id', sa.Uuid(as_uuid=False), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('action', sa.String(32), nullable=False), sa.Column('data', sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(['reference_id', 'workspace_id'], ['tenant_connection_references.id', 'tenant_connection_references.workspace_id']),
        sa.ForeignKeyConstraint(['grant_id', 'workspace_id'], ['tenant_connection_grants.id', 'tenant_connection_grants.workspace_id']),
        sa.CheckConstraint("action IN ('reference_staged','grant_staged','grant_revoked','reference_revoked')", name='tenant_connection_audit_action'))
    # No polymorphic FK that would delete a tombstone on native disconnect. Validate
    # source tenant on INSERT; preserve identity on native delete and fail closed.
    op.execute("""CREATE FUNCTION pao_tenant_connection_reference_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE found_id uuid;
    BEGIN
      IF TG_OP='DELETE' THEN RAISE EXCEPTION 'tenant_reference_delete_denied'; END IF;
      IF TG_OP='UPDATE' THEN
        IF (NEW.id,NEW.created_at,NEW.workspace_id,NEW.kind,NEW.source_id,NEW.provider,NEW.manager_id,NEW.source_version,NEW.source_stamp)
           IS DISTINCT FROM (OLD.id,OLD.created_at,OLD.workspace_id,OLD.kind,OLD.source_id,OLD.provider,OLD.manager_id,OLD.source_version,OLD.source_stamp)
           OR OLD.status<>'staged' OR NEW.status<>'revoked' OR NEW.revision<>OLD.revision+1
        THEN RAISE EXCEPTION 'tenant_reference_immutable'; END IF;
        RETURN NEW;
      END IF;
      CASE NEW.kind
        WHEN 'model' THEN SELECT id INTO found_id FROM model_provider_connections WHERE id=NEW.source_id AND workspace_id=NEW.workspace_id AND provider=NEW.provider FOR KEY SHARE;
        WHEN 'mcp' THEN SELECT id INTO found_id FROM connector_connections WHERE id=NEW.source_id AND workspace_id=NEW.workspace_id AND owner_id=NEW.manager_id AND NEW.provider='mcp' FOR KEY SHARE;
        WHEN 'meta_ads' THEN SELECT id INTO found_id FROM meta_connections WHERE id=NEW.source_id AND workspace_id=NEW.workspace_id AND user_id=NEW.manager_id AND NEW.provider='meta_ads' FOR KEY SHARE;
        WHEN 'google_ads' THEN SELECT id INTO found_id FROM google_ads_connections WHERE id=NEW.source_id AND workspace_id=NEW.workspace_id AND user_id=NEW.manager_id AND NEW.provider='google_ads' FOR KEY SHARE;
        ELSE RAISE EXCEPTION 'tenant_reference_kind_invalid';
      END CASE;
      IF found_id IS NULL OR NEW.status<>'staged' OR NEW.revision<>1 THEN RAISE EXCEPTION 'tenant_reference_source_invalid'; END IF;
      IF NOT EXISTS (SELECT 1 FROM workspace_members m JOIN users u ON u.id=m.user_id WHERE m.workspace_id=NEW.workspace_id AND m.user_id=NEW.manager_id AND m.role IN ('owner','admin') AND u.active)
      THEN RAISE EXCEPTION 'tenant_reference_manager_invalid'; END IF;
      RETURN NEW;
    END $$""")
    op.execute('CREATE TRIGGER tenant_connection_reference_guard BEFORE INSERT OR UPDATE OR DELETE ON tenant_connection_references FOR EACH ROW EXECUTE FUNCTION pao_tenant_connection_reference_guard()')
    op.execute("""CREATE FUNCTION pao_tenant_connection_grant_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE ref_kind text;
    BEGIN
      IF TG_OP='INSERT' THEN
        SELECT kind INTO ref_kind FROM tenant_connection_references WHERE id=NEW.reference_id AND workspace_id=NEW.workspace_id AND manager_id=NEW.creator_id AND revision=NEW.reference_revision AND status='staged' FOR KEY SHARE;
        IF ref_kind IS NULL OR NEW.revision<>1 OR NEW.status<>'staged' OR NEW.expires_at<=NEW.created_at OR
           (ref_kind IN ('model','mcp') AND NEW.account_id IS NOT NULL) OR
           (ref_kind IN ('meta_ads','google_ads') AND NEW.account_id IS NULL) OR
           NOT EXISTS (SELECT 1 FROM workspace_members m JOIN users u ON u.id=m.user_id WHERE m.workspace_id=NEW.workspace_id AND m.user_id=NEW.grantee_id AND m.role IN ('owner','admin','operator','analyst') AND u.active)
        THEN RAISE EXCEPTION 'tenant_grant_scope_invalid'; END IF;
        RETURN NEW;
      END IF;
      IF TG_OP='DELETE' THEN RAISE EXCEPTION 'tenant_grant_delete_denied'; END IF;
      IF (NEW.id,NEW.created_at,NEW.workspace_id,NEW.reference_id,NEW.reference_revision,NEW.creator_id,NEW.grantee_id,NEW.brand_id,NEW.account_id,NEW.permission,NEW.request_key,NEW.fingerprint,NEW.ttl_minutes,NEW.expires_at)
        IS DISTINCT FROM (OLD.id,OLD.created_at,OLD.workspace_id,OLD.reference_id,OLD.reference_revision,OLD.creator_id,OLD.grantee_id,OLD.brand_id,OLD.account_id,OLD.permission,OLD.request_key,OLD.fingerprint,OLD.ttl_minutes,OLD.expires_at)
        OR OLD.status<>'staged' OR NEW.status<>'revoked' OR NEW.revision<>OLD.revision+1
      THEN RAISE EXCEPTION 'tenant_grant_immutable'; END IF;
      RETURN NEW;
    END $$""")
    op.execute('CREATE TRIGGER tenant_connection_grant_guard BEFORE INSERT OR UPDATE OR DELETE ON tenant_connection_grants FOR EACH ROW EXECUTE FUNCTION pao_tenant_connection_grant_guard()')
    op.execute("CREATE FUNCTION pao_tenant_connection_audit_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'tenant_connection_audit_immutable'; END $$")
    op.execute('CREATE TRIGGER tenant_connection_audit_guard BEFORE UPDATE OR DELETE ON tenant_connection_audits FOR EACH ROW EXECUTE FUNCTION pao_tenant_connection_audit_guard()')


def downgrade():
    for table in ('tenant_connection_audits', 'tenant_connection_grants', 'tenant_connection_references'):
        op.drop_table(table)
    for name in ('audit', 'grant', 'reference'):
        op.execute(f'DROP FUNCTION pao_tenant_connection_{name}_guard()')
