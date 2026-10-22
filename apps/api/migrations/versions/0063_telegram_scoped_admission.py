"""Explicit runtime consent, immutable channel pins and atomic scoped receipts.

No automatic activation/backfill, no public route, no worker rollout.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision='0063'
down_revision='0062'
branch_labels=depends_on=None
OLD_PROFILE="connection_version>=1 AND generation>=1 AND next_offset>=0 AND ((status='disabled' AND token_ciphertext IS NOT NULL AND length(token_ciphertext) BETWEEN 1 AND 16384) OR (status='revoked' AND token_ciphertext IS NULL))"
NEW_PROFILE=OLD_PROFILE.replace("status='disabled'","status IN ('disabled','enabled')")
OLD_AUDIT="length(content_hash)=64 AND ((generation=1 AND action='stored') OR (generation>1 AND action IN ('rotated','revoked')))"
NEW_AUDIT=OLD_AUDIT.replace("'rotated','revoked'","'rotated','revoked','enabled','disabled'")
OLD_RECEIPT="generation>=1 AND update_id>=0 AND update_id<9223372036854775807 AND length(content_hash)=64 AND reason IN ('unsupported','unlinked','malformed')"
NEW_RECEIPT="generation>=1 AND update_id>=0 AND update_id<9223372036854775807 AND length(content_hash)=64 AND ((reason='inbound' AND inbound_id IS NOT NULL) OR (reason IN ('unsupported','unlinked','malformed','blocked') AND inbound_id IS NULL))"


def constraints(new):
    for table,name,old,updated in (
        ('telegram_runtime_profiles','telegram_profile_state',OLD_PROFILE,NEW_PROFILE),
        ('telegram_runtime_audits','telegram_runtime_audit_state',OLD_AUDIT,NEW_AUDIT),
        ('telegram_runtime_receipts','telegram_runtime_receipt_state',OLD_RECEIPT,NEW_RECEIPT)):
        op.drop_constraint(name,table,type_='check');op.create_check_constraint(name,table,updated if new else old)


def upgrade():
    op.add_column('telegram_runtime_profiles',sa.Column('cooldown_until',sa.DateTime(timezone=True)))
    for table in ('channel_inbounds','channel_outbox'):
        op.add_column(table,sa.Column('telegram_context',JSONB(none_as_null=True)))
    op.create_unique_constraint('channel_inbounds_id_workspace_id_key','channel_inbounds',['id','workspace_id'])
    op.add_column('telegram_runtime_receipts',sa.Column('inbound_id',sa.Uuid(as_uuid=False)))
    op.create_foreign_key('telegram_receipt_inbound_scope','telegram_runtime_receipts','channel_inbounds',
        ['inbound_id','workspace_id'],['id','workspace_id'])
    constraints(True)
    op.execute("""CREATE FUNCTION pao_telegram_execution_pin() RETURNS trigger LANGUAGE plpgsql AS $$
      DECLARE ctx jsonb; binding channel_bindings%ROWTYPE; profile telegram_runtime_profiles%ROWTYPE;
      BEGIN
        IF TG_OP='UPDATE' THEN
          IF NEW.telegram_context IS DISTINCT FROM OLD.telegram_context
            THEN RAISE EXCEPTION 'telegram_execution_pin_immutable'; END IF;
          RETURN NEW;
        END IF;
        ctx=NEW.telegram_context;
        IF ctx IS NULL THEN RETURN NEW; END IF;
        SELECT * INTO binding FROM channel_bindings WHERE id=NEW.binding_id;
        SELECT * INTO profile FROM telegram_runtime_profiles WHERE connection_id=NEW.connection_id;
        IF NEW.connection_id IS NULL OR jsonb_typeof(ctx)<>'object' OR
          (ctx->>'connection_id',ctx->>'workspace_id',ctx->>'binding_id',ctx->>'actor_id',ctx->>'peer_id') IS DISTINCT FROM
          (NEW.connection_id::text,NEW.workspace_id::text,NEW.binding_id::text,binding.actor_id::text,binding.peer_id::text) OR
          jsonb_typeof(ctx->'generation') IS DISTINCT FROM 'number' OR
          jsonb_typeof(ctx->'binding_version') IS DISTINCT FROM 'number' OR
          (ctx->>'generation')::bigint IS DISTINCT FROM profile.generation OR
          (ctx->>'binding_version')::bigint IS DISTINCT FROM binding.version OR
          profile.status IS DISTINCT FROM 'enabled'
          THEN RAISE EXCEPTION 'telegram_execution_pin_scope'; END IF;
        RETURN NEW;
      END $$""")
    for table in ('channel_inbounds','channel_outbox'):
        op.execute(f'CREATE TRIGGER telegram_execution_pin BEFORE INSERT OR UPDATE ON {table} FOR EACH ROW EXECUTE FUNCTION pao_telegram_execution_pin()')
    op.execute("""CREATE FUNCTION pao_telegram_admission_receipt() RETURNS trigger LANGUAGE plpgsql AS $$
      DECLARE incoming channel_inbounds%ROWTYPE; profile telegram_runtime_profiles%ROWTYPE;
      BEGIN
        SELECT * INTO profile FROM telegram_runtime_profiles WHERE connection_id=NEW.connection_id;
        IF NEW.reason='inbound' THEN
          SELECT * INTO incoming FROM channel_inbounds WHERE id=NEW.inbound_id;
          IF incoming.id IS NULL OR profile.status IS DISTINCT FROM 'enabled' OR
            (incoming.workspace_id,incoming.connection_id) IS DISTINCT FROM (NEW.workspace_id,NEW.connection_id) OR
            (incoming.telegram_context->>'generation')::bigint IS DISTINCT FROM NEW.generation
            THEN RAISE EXCEPTION 'telegram_admission_receipt_scope'; END IF;
        END IF;
        RETURN NEW;
      END $$""")
    op.execute('CREATE TRIGGER telegram_admission_receipt BEFORE INSERT ON telegram_runtime_receipts FOR EACH ROW EXECUTE FUNCTION pao_telegram_admission_receipt()')
    # Existing immutable audit trigger still checks namespace/current generation.
    # It must accept receipts while explicitly enabled, not only while staged.
    op.execute("""CREATE OR REPLACE FUNCTION pao_telegram_runtime_evidence_guard() RETURNS trigger LANGUAGE plpgsql AS $$
      DECLARE profile telegram_runtime_profiles%ROWTYPE; connection telegram_connections%ROWTYPE;
      BEGIN
        SELECT * INTO profile FROM telegram_runtime_profiles WHERE connection_id=NEW.connection_id FOR SHARE;
        SELECT * INTO connection FROM telegram_connections WHERE id=NEW.connection_id;
        IF profile.id IS NULL OR profile.workspace_id IS DISTINCT FROM NEW.workspace_id OR profile.generation<>NEW.generation
          THEN RAISE EXCEPTION 'telegram_runtime_evidence_scope'; END IF;
        IF TG_TABLE_NAME='telegram_runtime_audits' THEN
          IF NEW.actor_id IS DISTINCT FROM connection.owner_id OR
            profile.status IS DISTINCT FROM (CASE NEW.action WHEN 'enabled' THEN 'enabled' WHEN 'revoked' THEN 'revoked' ELSE 'disabled' END)
            THEN RAISE EXCEPTION 'telegram_runtime_audit_scope'; END IF;
        ELSIF profile.status NOT IN ('disabled','enabled') THEN RAISE EXCEPTION 'telegram_runtime_receipt_revoked'; END IF;
        RETURN NEW;
      END $$""")
    op.execute("""CREATE FUNCTION pao_telegram_binding_version() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF NEW.connection_id IS NOT NULL THEN
          IF (NEW.actor_id,NEW.peer_id,NEW.brain_id,NEW.session_id,NEW.kind,NEW.mode,NEW.enabled,NEW.outbound_confirmed)
            IS DISTINCT FROM (OLD.actor_id,OLD.peer_id,OLD.brain_id,OLD.session_id,OLD.kind,OLD.mode,OLD.enabled,OLD.outbound_confirmed)
            THEN NEW.version=greatest(NEW.version,OLD.version+1); END IF;
          IF NEW.version<OLD.version THEN RAISE EXCEPTION 'telegram_binding_version_monotonic'; END IF;
        END IF;
        RETURN NEW;
      END $$""")
    op.execute('CREATE TRIGGER telegram_binding_version BEFORE UPDATE ON channel_bindings FOR EACH ROW EXECUTE FUNCTION pao_telegram_binding_version()')
    op.execute("""CREATE FUNCTION pao_telegram_authority_revoked() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF TG_TABLE_NAME='workspace_members' THEN
          IF TG_OP='UPDATE' AND NEW.role IS NOT DISTINCT FROM OLD.role THEN RETURN NULL; END IF;
          UPDATE channel_bindings b SET enabled=false,outbound_confirmed=false,version=version+1
            WHERE b.connection_id IS NOT NULL AND b.workspace_id=OLD.workspace_id AND
            (b.actor_id=OLD.user_id OR EXISTS(SELECT 1 FROM telegram_connections c WHERE c.id=b.connection_id AND c.owner_id=OLD.user_id));
        ELSIF TG_TABLE_NAME='users' THEN
          IF NEW.active OR NEW.active IS NOT DISTINCT FROM OLD.active THEN RETURN NULL; END IF;
          UPDATE channel_bindings b SET enabled=false,outbound_confirmed=false,version=version+1
            WHERE b.connection_id IS NOT NULL AND (b.actor_id=OLD.id OR EXISTS(SELECT 1 FROM telegram_connections c WHERE c.id=b.connection_id AND c.owner_id=OLD.id));
        ELSIF TG_TABLE_NAME='brain_members' THEN
          IF TG_OP='UPDATE' AND NEW.role IS NOT DISTINCT FROM OLD.role THEN RETURN NULL; END IF;
          UPDATE channel_bindings SET enabled=false,outbound_confirmed=false,version=version+1
            WHERE connection_id IS NOT NULL AND brain_id=OLD.brain_id AND actor_id=OLD.user_id;
        ELSIF TG_TABLE_NAME='telegram_peers' THEN
          IF NEW.enabled OR NEW.enabled IS NOT DISTINCT FROM OLD.enabled THEN RETURN NULL; END IF;
          UPDATE channel_bindings SET enabled=false,outbound_confirmed=false,version=version+1
            WHERE connection_id IS NOT NULL AND peer_id=OLD.id;
        ELSIF TG_TABLE_NAME='sessions' THEN
          IF (NEW.user_id,NEW.workspace_id,NEW.brain_id,NEW.memory_enabled,NEW.knowledge_enabled,NEW.knowledge_scope)
            IS NOT DISTINCT FROM (OLD.user_id,OLD.workspace_id,OLD.brain_id,OLD.memory_enabled,OLD.knowledge_enabled,OLD.knowledge_scope)
            THEN RETURN NULL; END IF;
          UPDATE channel_bindings SET enabled=false,outbound_confirmed=false,version=version+1
            WHERE connection_id IS NOT NULL AND session_id=OLD.id;
        END IF;
        RETURN NULL;
      END $$""")
    for table,event in (('workspace_members','UPDATE OF role OR DELETE'),('users','UPDATE OF active'),
        ('brain_members','UPDATE OF role OR DELETE'),('telegram_peers','UPDATE OF enabled'),
        ('sessions','UPDATE OF user_id,workspace_id,brain_id,memory_enabled,knowledge_enabled,knowledge_scope')):
        op.execute(f'CREATE TRIGGER telegram_authority_revoked AFTER {event} ON {table} FOR EACH ROW EXECUTE FUNCTION pao_telegram_authority_revoked()')


def downgrade():
    bind=op.get_bind()
    if (bind.scalar(sa.text("SELECT count(*) FROM telegram_runtime_audits WHERE action IN ('enabled','disabled')")) or
        bind.scalar(sa.text("SELECT count(*) FROM telegram_runtime_profiles WHERE status='enabled' OR cooldown_until IS NOT NULL")) or
        bind.scalar(sa.text("SELECT count(*) FROM telegram_runtime_receipts WHERE reason IN ('inbound','blocked')")) or
        any(bind.scalar(sa.text(f'SELECT count(*) FROM {table} WHERE telegram_context IS NOT NULL')) for table in ('channel_inbounds','channel_outbox'))):
        raise RuntimeError('Downgrade refused: Telegram scoped execution history must be preserved')
    for table in ('workspace_members','users','brain_members','telegram_peers','sessions'):
        op.execute(f'DROP TRIGGER IF EXISTS telegram_authority_revoked ON {table}')
    op.execute('DROP FUNCTION IF EXISTS pao_telegram_authority_revoked()')
    op.execute('DROP TRIGGER IF EXISTS telegram_binding_version ON channel_bindings')
    op.execute('DROP FUNCTION IF EXISTS pao_telegram_binding_version()')
    op.execute('DROP TRIGGER telegram_admission_receipt ON telegram_runtime_receipts')
    op.execute('DROP FUNCTION pao_telegram_admission_receipt()')
    for table in ('channel_inbounds','channel_outbox'):
        op.execute(f'DROP TRIGGER telegram_execution_pin ON {table}');op.drop_column(table,'telegram_context')
    op.execute('DROP FUNCTION pao_telegram_execution_pin()')
    op.drop_constraint('telegram_receipt_inbound_scope','telegram_runtime_receipts',type_='foreignkey')
    constraints(False)
    op.drop_column('telegram_runtime_receipts','inbound_id')
    op.drop_constraint('channel_inbounds_id_workspace_id_key','channel_inbounds',type_='unique')
    op.drop_column('telegram_runtime_profiles','cooldown_until')
    op.execute("""CREATE OR REPLACE FUNCTION pao_telegram_runtime_evidence_guard() RETURNS trigger LANGUAGE plpgsql AS $$
      DECLARE profile telegram_runtime_profiles%ROWTYPE; connection telegram_connections%ROWTYPE;
      BEGIN
        SELECT * INTO profile FROM telegram_runtime_profiles WHERE connection_id=NEW.connection_id FOR SHARE;
        SELECT * INTO connection FROM telegram_connections WHERE id=NEW.connection_id;
        IF profile.id IS NULL OR profile.workspace_id IS DISTINCT FROM NEW.workspace_id OR profile.generation<>NEW.generation
          THEN RAISE EXCEPTION 'telegram_runtime_evidence_scope'; END IF;
        IF TG_TABLE_NAME='telegram_runtime_audits' THEN
          IF NEW.actor_id IS DISTINCT FROM connection.owner_id OR
            ((NEW.action='revoked') IS DISTINCT FROM (profile.status='revoked'))
            THEN RAISE EXCEPTION 'telegram_runtime_audit_scope'; END IF;
        ELSIF profile.status<>'disabled' THEN RAISE EXCEPTION 'telegram_runtime_receipt_revoked'; END IF;
        RETURN NEW;
      END $$""")
