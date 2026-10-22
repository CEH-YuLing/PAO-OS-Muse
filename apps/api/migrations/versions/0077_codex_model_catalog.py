"""Admit own-profile catalog models without changing the profile default.

0076 is reserved by an unpromoted shared-CLI candidate. This reviewed native
branch advances directly from0075 and does not install that candidate.
"""
from alembic import op
import sqlalchemy as sa

revision='0077'
down_revision='0075'
branch_labels=depends_on=None

def upgrade():
    op.execute("""CREATE OR REPLACE FUNCTION pao_cli_dispatch_guard() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF TG_OP='DELETE' THEN RAISE EXCEPTION 'cli_dispatch_delete_denied'; END IF;
        IF TG_OP='INSERT' THEN
          IF NEW.status<>'dispatched' OR NOT EXISTS (
            SELECT 1 FROM llm_attempts a JOIN cli_model_connections c ON c.id=NEW.connection_id AND c.workspace_id=a.workspace_id
            WHERE a.id=NEW.attempt_id AND a.workspace_id=NEW.workspace_id AND a.provider='codex_cli'
              AND a.user_id=c.owner_id AND a.status='started'
              AND (a.model=c.model OR EXISTS (
                SELECT 1 FROM runs r JOIN sessions s ON s.id=r.session_id AND s.workspace_id=r.workspace_id
                JOIN personal_cli_revisions cat ON cat.workspace_id=r.workspace_id AND cat.actor_id=s.user_id
                WHERE r.id=a.run_id AND r.workspace_id=a.workspace_id AND s.id=a.session_id AND s.user_id=a.user_id
                  AND r.status='running' AND NOT r.cancel_requested AND c.status='connected' AND c.setup_operation_id IS NULL
                  AND r.engine_snapshot->>'provider'='codex_cli' AND r.engine_snapshot->>'model'=a.model
                  AND r.engine_snapshot->>'connection_id'=c.id::text
                  AND r.engine_snapshot->'connection_authority'->>'mode'='personal_cli'
                  AND r.engine_snapshot->'connection_authority'->>'actor_id'=a.user_id::text
                  AND r.engine_snapshot->'connection_authority'->>'workspace_id'=a.workspace_id::text
                  AND r.engine_snapshot->'connection_authority'->>'source_id'=c.id::text
                  AND r.engine_snapshot->'cli_pin'->>'model'=a.model
                  AND r.engine_snapshot->'cli_model_catalog'->>'version'='codex-personal-model-catalog-v1'
                  AND r.engine_snapshot->'cli_model_catalog'->>'record_id'=cat.id::text
                  AND r.engine_snapshot->'cli_model_catalog'->>'revision'=cat.revision::text
                  AND r.engine_snapshot->'cli_model_catalog'->>'sha256'=cat.fingerprint
                  AND cat.content->>'version'='codex-personal-model-catalog-v1'
                  AND cat.content->'source_pin'->>'connection_id'=c.id::text
                  AND cat.content->'source_pin'->>'actor_id'=a.user_id::text
                  AND cat.content->'source_pin'->>'workspace_id'=a.workspace_id::text
                  AND cat.content->'source_pin'->>'source_version'=c.version::text
                  AND cat.content->'source_pin'->>'model'=c.model
                  AND cat.content->'source_pin'->>'profile_id'=c.profile_id::text
                  AND cat.content->'source_pin'->>'device_id'=c.device_id::text
                  AND cat.content->'source_pin'->>'binary_sha256'=c.binary_sha256
                  AND cat.content->'source_pin'->>'runtime_image_id'=c.runtime_image_id
                  AND (cat.content->'source_pin'->>'auth_checked_at')::timestamptz=c.auth_checked_at
                  AND (r.engine_snapshot->'cli_pin')::jsonb-'model'=(cat.content->'source_pin')::jsonb-'model'
                  AND EXISTS(SELECT 1 FROM jsonb_array_elements((cat.content->'models')::jsonb) m WHERE m->>'model'=a.model)
              ))) THEN RAISE EXCEPTION 'cli_dispatch_native_attempt_required'; END IF;
          RETURN NEW;
        END IF;
        IF (NEW.id,NEW.created_at,NEW.workspace_id,NEW.connection_id,NEW.attempt_id)
          IS DISTINCT FROM (OLD.id,OLD.created_at,OLD.workspace_id,OLD.connection_id,OLD.attempt_id)
          OR OLD.status<>'dispatched' OR NEW.status NOT IN ('completed','failed','cancelled','unknown')
          OR NEW.finished_at IS NULL OR NEW.finished_at<OLD.created_at
        THEN RAISE EXCEPTION 'cli_dispatch_history_immutable'; END IF;
        RETURN NEW;
      END $$""")

def downgrade():
    if op.get_bind().scalar(sa.text("SELECT EXISTS(SELECT 1 FROM cli_model_dispatches d JOIN llm_attempts a ON a.id=d.attempt_id JOIN runs r ON r.id=a.run_id WHERE r.engine_snapshot->'cli_model_catalog' IS NOT NULL)")):
        raise RuntimeError('Preserve populated multi-model dispatch history; use a reviewed recovery instead')
    op.execute("""CREATE OR REPLACE FUNCTION pao_cli_dispatch_guard() RETURNS trigger LANGUAGE plpgsql AS $$
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
