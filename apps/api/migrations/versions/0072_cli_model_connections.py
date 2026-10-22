"""CLI metadata + dispatch extension; no auth values or historical repinning."""
from alembic import op
import sqlalchemy as sa

revision = '0072'
down_revision = '0071'
branch_labels = depends_on = None


def reference_state(kinds):
    return (f"kind IN ({kinds}) AND status IN ('staged','revoked') AND revision>=1 AND "
            "length(source_stamp)=64 AND (source_version IS NULL OR source_version>=1)")


CLI_BRANCH = "        WHEN 'cli_model' THEN SELECT id INTO found_id FROM cli_model_connections WHERE id=NEW.source_id AND workspace_id=NEW.workspace_id AND owner_id=NEW.manager_id AND provider=NEW.provider AND NEW.provider='codex_cli' FOR KEY SHARE;\n"
PERSONAL = "           (ref_kind='cli_model' AND NEW.grantee_id<>NEW.creator_id) OR\n"


def guards(up):
    connection = op.get_bind()
    for name in ('pao_tenant_connection_reference_guard', 'pao_tenant_connection_grant_guard', 'pao_model_grant_activation_guard'):
        original = connection.scalar(sa.text('SELECT pg_get_functiondef(CAST(:name AS regprocedure))'),
                                     {'name': 'public.' + name + '()'})
        if name == 'pao_model_grant_activation_guard':
            old, new = "r.kind='model'", "r.kind IN ('model','cli_model')"
        elif name.endswith('reference_guard'):
            old, new = "        WHEN 'mcp'", CLI_BRANCH + "        WHEN 'mcp'"
        else:
            old = "           (ref_kind IN ('model','mcp') AND NEW.account_id IS NOT NULL) OR\n"
            new = "           (ref_kind IN ('model','cli_model','mcp') AND NEW.account_id IS NOT NULL) OR\n" + PERSONAL
        if not up:
            old, new = new, old
        if original.count(old) != 1:
            raise RuntimeError('Existing immutable connection guard differs; stop schema rollout')
        op.execute(original.replace(old, new, 1))


def upgrade():
    op.create_table('cli_model_connections',
        sa.Column('id', sa.Uuid(), primary_key=True), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('workspace_id', sa.Uuid(), sa.ForeignKey('workspaces.id'), nullable=False),
        sa.Column('owner_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('provider', sa.String(24), nullable=False), sa.Column('device_id', sa.Uuid(), nullable=False),
        sa.Column('profile_id', sa.Uuid(), unique=True, nullable=False), sa.Column('model', sa.String(120), nullable=False),
        sa.Column('request_key', sa.Uuid(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False), sa.Column('status', sa.String(16), nullable=False),
        sa.Column('binary_sha256', sa.String(64)), sa.Column('binary_version', sa.String(64)),
        sa.Column('runtime_image_id', sa.String(71)),
        sa.Column('auth_checked_at', sa.DateTime(timezone=True)), sa.UniqueConstraint('id', 'workspace_id'),
        sa.Column('setup_operation_id', sa.Uuid()),
        sa.UniqueConstraint('workspace_id','owner_id','request_key'),
        sa.CheckConstraint("provider='codex_cli' AND version>=1 AND status IN ('pending','connected','disconnected','error') "
            "AND (status<>'connected' OR (binary_sha256 IS NOT NULL AND binary_sha256 ~ '^[0-9a-f]{64}$' "
            "AND binary_version IS NOT NULL AND runtime_image_id IS NOT NULL AND runtime_image_id ~ '^sha256:[0-9a-f]{64}$' AND auth_checked_at IS NOT NULL))",
            name='cli_model_connection_state'))
    op.create_index('ix_cli_model_connections_workspace_id', 'cli_model_connections', ['workspace_id'])
    op.create_table('cli_model_dispatches',
        sa.Column('id', sa.Uuid(), primary_key=True), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('workspace_id', sa.Uuid(), nullable=False), sa.Column('connection_id', sa.Uuid(), nullable=False),
        sa.Column('attempt_id', sa.Uuid(), unique=True, nullable=False), sa.Column('status', sa.String(16), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(['connection_id','workspace_id'], ['cli_model_connections.id','cli_model_connections.workspace_id']),
        sa.ForeignKeyConstraint(['attempt_id','workspace_id'], ['llm_attempts.id','llm_attempts.workspace_id']),
        sa.CheckConstraint("status IN ('dispatched','completed','failed','cancelled','unknown') AND "
            "((status='dispatched' AND finished_at IS NULL) OR (status<>'dispatched' AND finished_at IS NOT NULL))", name='cli_model_dispatch_state'))
    op.create_index('cli_one_unresolved_dispatch', 'cli_model_dispatches', ['connection_id'], unique=True,
                    postgresql_where=sa.text("status IN ('dispatched','unknown')"))
    op.execute("""CREATE FUNCTION pao_cli_dispatch_guard() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF TG_OP='DELETE' THEN RAISE EXCEPTION 'cli_dispatch_delete_denied'; END IF;
        IF TG_OP='INSERT' THEN
          IF NEW.status<>'dispatched' OR NOT EXISTS (
            SELECT 1 FROM llm_attempts a JOIN cli_model_connections c ON c.id=NEW.connection_id AND c.workspace_id=a.workspace_id
            WHERE a.id=NEW.attempt_id AND a.workspace_id=NEW.workspace_id AND a.provider='codex_cli'
              AND a.model=c.model AND a.user_id=c.owner_id AND a.status='started')
          THEN RAISE EXCEPTION 'cli_dispatch_native_attempt_required'; END IF;
          RETURN NEW;
        END IF;
        IF (NEW.id,NEW.created_at,NEW.workspace_id,NEW.connection_id,NEW.attempt_id)
          IS DISTINCT FROM (OLD.id,OLD.created_at,OLD.workspace_id,OLD.connection_id,OLD.attempt_id)
          OR OLD.status<>'dispatched' OR NEW.status NOT IN ('completed','failed','cancelled','unknown')
          OR NEW.finished_at IS NULL OR NEW.finished_at<OLD.created_at
        THEN RAISE EXCEPTION 'cli_dispatch_history_immutable'; END IF;
        RETURN NEW;
      END $$""")
    op.execute('CREATE TRIGGER cli_dispatch_guard BEFORE INSERT OR UPDATE OR DELETE ON cli_model_dispatches FOR EACH ROW EXECUTE FUNCTION pao_cli_dispatch_guard()')
    op.drop_constraint('tenant_connection_reference_state', 'tenant_connection_references', type_='check')
    op.create_check_constraint('tenant_connection_reference_state', 'tenant_connection_references',
                               reference_state("'model','cli_model','mcp','meta_ads','google_ads'"))
    guards(True)


def downgrade():
    connection = op.get_bind()
    if (connection.scalar(sa.text('SELECT EXISTS(SELECT 1 FROM cli_model_connections)'))
            or connection.scalar(sa.text('SELECT EXISTS(SELECT 1 FROM cli_model_dispatches)'))
            or connection.scalar(sa.text("SELECT EXISTS(SELECT 1 FROM tenant_connection_references WHERE kind='cli_model')"))):
        raise RuntimeError('Populated CLI identity/dispatch history cannot be discarded')
    guards(False)
    op.drop_constraint('tenant_connection_reference_state', 'tenant_connection_references', type_='check')
    op.create_check_constraint('tenant_connection_reference_state', 'tenant_connection_references',
                               reference_state("'model','mcp','meta_ads','google_ads'"))
    op.drop_table('cli_model_dispatches')
    op.execute('DROP FUNCTION pao_cli_dispatch_guard()')
    op.drop_table('cli_model_connections')
