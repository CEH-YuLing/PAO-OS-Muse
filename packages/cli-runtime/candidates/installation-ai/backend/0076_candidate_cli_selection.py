"""Candidate ONLY: tenant-local attempt, installation-local CLI source.

Not in the installed Alembic tree. Requires the staged adapter; never remove the
native attempt FK, unique unresolved profile fence or immutable dispatch guard.
"""
from alembic import op
import sqlalchemy as sa

revision = '0076'
down_revision = '0075'
branch_labels = depends_on = None

GUARD = """CREATE OR REPLACE FUNCTION pao_cli_dispatch_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='DELETE' THEN RAISE EXCEPTION 'cli_dispatch_delete_denied'; END IF;
  IF TG_OP='INSERT' THEN
    IF NEW.status<>'dispatched' OR NOT EXISTS (
      SELECT 1 FROM llm_attempts a
      JOIN runs r ON r.id=a.run_id AND r.workspace_id=a.workspace_id
      JOIN cli_model_connections c ON c.id=NEW.connection_id
      WHERE a.id=NEW.attempt_id AND a.workspace_id=NEW.workspace_id
        AND a.provider='codex_cli' AND a.status='started'
        AND (
          (COALESCE(r.engine_snapshot->'connection_authority'->>'mode','')<>'installation_resource'
            AND c.workspace_id=a.workspace_id AND a.model=c.model AND a.user_id=c.owner_id)
          OR (
            r.status='running' AND NOT r.cancel_requested
            AND r.engine_snapshot->>'provider'='codex_cli'
            AND r.engine_snapshot->>'model'=a.model
            AND r.engine_snapshot->>'connection_id'=c.id::text
            AND r.engine_snapshot->'connection_authority'->>'mode'='installation_resource'
            AND r.engine_snapshot->'connection_authority'->>'workspace_id'=a.workspace_id::text
            AND r.engine_snapshot->'connection_authority'->>'actor_id'=a.user_id::text
            AND EXISTS (SELECT 1 FROM tenant_model_leases lease WHERE lease.attempt_id=a.id
              AND lease.workspace_id=a.workspace_id AND lease.actor_id=a.user_id
              AND lease.kind='llm' AND lease.status='active' AND lease.expires_at>now())
            AND c.status='connected' AND c.setup_operation_id IS NULL
            AND r.engine_snapshot->'cli_pin'->>'connection_id'=c.id::text
            AND r.engine_snapshot->'cli_pin'->>'workspace_id'=c.workspace_id::text
            AND r.engine_snapshot->'cli_pin'->>'actor_id'=c.owner_id::text
            AND r.engine_snapshot->'cli_pin'->>'profile_id'=c.profile_id::text
            AND r.engine_snapshot->'cli_pin'->>'device_id'=c.device_id::text
            AND r.engine_snapshot->'cli_pin'->>'source_version'=c.version::text
            AND r.engine_snapshot->'cli_pin'->>'model'=c.model
            AND r.engine_snapshot->'cli_pin'->>'binary_sha256'=c.binary_sha256
            AND r.engine_snapshot->'cli_pin'->>'binary_version'=c.binary_version
            AND r.engine_snapshot->'cli_pin'->>'runtime_image_id'=c.runtime_image_id
            AND (r.engine_snapshot->'cli_pin'->>'auth_checked_at')::timestamptz=c.auth_checked_at
            AND EXISTS (SELECT 1 FROM workspace_members custodian JOIN users custodian_user ON custodian_user.id=custodian.user_id
              WHERE custodian.workspace_id=c.workspace_id AND custodian.user_id=c.owner_id
                AND custodian.role IN ('owner','admin') AND custodian_user.active)
            AND EXISTS (
              SELECT 1 FROM installation_ai_resources x,
                jsonb_array_elements(x.catalog::jsonb) catalog_model
              WHERE x.id::text=r.engine_snapshot->'connection_authority'->>'resource_id'
                AND x.source_kind='cli' AND x.provider='codex_cli' AND x.enabled
                AND x.source_id=c.id::text AND x.source_workspace_id=c.workspace_id AND x.owner_id=c.owner_id
                AND x.revision::text=r.engine_snapshot->'connection_authority'->>'resource_revision'
                AND x.source_stamp=r.engine_snapshot->'connection_authority'->>'source_stamp'
                AND catalog_model->>'model'=a.model
                AND (r.engine_snapshot->>'reasoning_effort' IS NULL OR
                  COALESCE(catalog_model->'reasoning_efforts','[]'::jsonb) ? (r.engine_snapshot->>'reasoning_effort'))
            )
            AND EXISTS (
              SELECT 1 FROM sessions s JOIN workspace_members m ON m.workspace_id=s.workspace_id AND m.user_id=s.user_id
              JOIN users u ON u.id=s.user_id JOIN workspaces w ON w.id=m.workspace_id
              WHERE s.id=a.session_id AND s.id=r.session_id AND s.workspace_id=a.workspace_id AND s.user_id=a.user_id
                AND u.active AND u.auth_version::text=r.engine_snapshot->'connection_authority'->>'auth_version'
                AND w.lifecycle_version::text=r.engine_snapshot->'connection_authority'->>'membership_epoch'
                AND m.role=r.engine_snapshot->'connection_authority'->>'actor_role'
                AND m.role IN ('owner','admin','operator','analyst','viewer')
                AND (m.role<>'viewer' OR r.engine_snapshot->>'interaction_mode'='read_only_ai')
            )
          )
        )
    ) THEN RAISE EXCEPTION 'cli_dispatch_native_attempt_required'; END IF;
    RETURN NEW;
  END IF;
  IF (NEW.id,NEW.created_at,NEW.workspace_id,NEW.connection_id,NEW.attempt_id)
    IS DISTINCT FROM (OLD.id,OLD.created_at,OLD.workspace_id,OLD.connection_id,OLD.attempt_id)
    OR OLD.status<>'dispatched' OR NEW.status NOT IN ('completed','failed','cancelled','unknown')
    OR NEW.finished_at IS NULL OR NEW.finished_at<OLD.created_at
  THEN RAISE EXCEPTION 'cli_dispatch_history_immutable'; END IF;
  RETURN NEW;
END $$"""


def connection_fk():
    matches = [v for v in sa.inspect(op.get_bind()).get_foreign_keys('cli_model_dispatches')
        if v['referred_table'] == 'cli_model_connections']
    if len(matches) != 1 or not matches[0]['name']:
        raise RuntimeError('Unexpected CLI FK; stop candidate migration')
    return matches[0]


def upgrade():
    fk = connection_fk()
    if fk['constrained_columns'] != ['connection_id','workspace_id']:
        raise RuntimeError('Unexpected CLI FK shape')
    # Keep an exact preimage to restore, without importing old mutable source.
    original = op.get_bind().scalar(sa.text("SELECT pg_get_functiondef('pao_cli_dispatch_guard()'::regprocedure)"))
    if 'cli_dispatch_native_attempt_required' not in original or 'installation_resource' in original:
        raise RuntimeError('Unexpected dispatch guard')
    op.execute('CREATE TABLE candidate_cli_guard_preimage (definition text NOT NULL)')
    op.get_bind().execute(sa.text('INSERT INTO candidate_cli_guard_preimage VALUES (:v)'), {'v': original})
    op.drop_constraint(fk['name'], 'cli_model_dispatches', type_='foreignkey')
    op.create_foreign_key('cli_dispatch_installation_source_fk', 'cli_model_dispatches', 'cli_model_connections', ['connection_id'], ['id'])
    op.execute(GUARD)


def downgrade():
    # No candidate history can be coerced back into the personal-only shape.
    if op.get_bind().scalar(sa.text("""SELECT EXISTS(SELECT 1 FROM cli_model_dispatches d
        JOIN llm_attempts a ON a.id=d.attempt_id JOIN runs r ON r.id=a.run_id
        WHERE r.engine_snapshot->'connection_authority'->>'mode'='installation_resource')""")):
        raise RuntimeError('Populated shared CLI history cannot be downgraded')
    original = op.get_bind().scalar(sa.text('SELECT definition FROM candidate_cli_guard_preimage'))
    op.execute(original)
    op.drop_constraint(connection_fk()['name'], 'cli_model_dispatches', type_='foreignkey')
    op.create_foreign_key('cli_model_dispatches_connection_id_workspace_id_fkey', 'cli_model_dispatches',
        'cli_model_connections', ['connection_id','workspace_id'], ['id','workspace_id'])
    op.drop_table('candidate_cli_guard_preimage')
