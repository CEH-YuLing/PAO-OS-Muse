"""Immutable verified bot identity across native/legacy, no history repinning."""
from alembic import op
import sqlalchemy as sa

revision='0062'
down_revision='0061'
branch_labels=depends_on=None


def profile_guard_sql():
    # Exact0061 body for a schema-equivalent downgrade, kept as a versioned
    # constant here. No historical migration edits or table recreation.
    return """CREATE OR REPLACE FUNCTION pao_telegram_profile_guard() RETURNS trigger LANGUAGE plpgsql AS $$
      DECLARE connection telegram_connections%ROWTYPE;
      BEGIN
        IF TG_OP='DELETE' THEN RAISE EXCEPTION 'telegram_runtime_history_immutable'; END IF;
        SELECT * INTO connection FROM telegram_connections WHERE id=NEW.connection_id FOR SHARE;
        IF connection.id IS NULL OR connection.kind<>'native' OR connection.status<>'staged'
          OR (NEW.workspace_id,NEW.connection_version) IS DISTINCT FROM (connection.workspace_id,connection.version)
          THEN RAISE EXCEPTION 'telegram_runtime_profile_scope'; END IF;
        IF TG_OP='INSERT' THEN
          IF NEW.generation<>1 OR NEW.status<>'disabled' OR NEW.next_offset<>0
            THEN RAISE EXCEPTION 'telegram_runtime_profile_initial'; END IF;
        ELSE
          IF (NEW.id,NEW.created_at,NEW.workspace_id,NEW.connection_id,NEW.connection_version)
            IS DISTINCT FROM (OLD.id,OLD.created_at,OLD.workspace_id,OLD.connection_id,OLD.connection_version)
            OR OLD.status='revoked' OR NEW.next_offset<OLD.next_offset
            THEN RAISE EXCEPTION 'telegram_runtime_profile_transition'; END IF;
          IF (NEW.token_ciphertext,NEW.status) IS DISTINCT FROM (OLD.token_ciphertext,OLD.status) THEN
            IF NEW.generation<>OLD.generation+1 OR NEW.next_offset<>OLD.next_offset
              THEN RAISE EXCEPTION 'telegram_runtime_profile_generation'; END IF;
          ELSIF NEW.generation<>OLD.generation THEN RAISE EXCEPTION 'telegram_runtime_profile_generation'; END IF;
        END IF;
        RETURN NEW;
      END $$"""


def upgrade():
    op.create_table('telegram_bot_identities',
        sa.Column('id',sa.Uuid(as_uuid=False),primary_key=True),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),nullable=False),
        sa.Column('connection_id',sa.Uuid(as_uuid=False),nullable=False,unique=True),
        sa.Column('owner_id',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('connection_version',sa.Integer(),nullable=False),
        sa.Column('bot_user_id',sa.String(24),nullable=False,unique=True),
        sa.Column('request_key',sa.Uuid(as_uuid=False),nullable=False),sa.Column('content_hash',sa.String(64),nullable=False),
        sa.ForeignKeyConstraint(['connection_id','workspace_id'],['telegram_connections.id','telegram_connections.workspace_id']),
        sa.UniqueConstraint('workspace_id','owner_id','request_key'),
        sa.CheckConstraint("connection_version>=1 AND bot_user_id ~ '^[1-9][0-9]{0,15}$' AND length(content_hash)=64",name='telegram_bot_identity_state'))
    op.execute("""CREATE FUNCTION pao_telegram_bot_identity_guard() RETURNS trigger LANGUAGE plpgsql AS $$
      DECLARE connection telegram_connections%ROWTYPE;
      BEGIN
        IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'telegram_bot_identity_immutable'; END IF;
        PERFORM pg_advisory_xact_lock(hashtextextended('pao-telegram-bot-v1:'||NEW.bot_user_id,0));
        SELECT * INTO connection FROM telegram_connections WHERE id=NEW.connection_id FOR SHARE;
        IF connection.id IS NULL OR connection.status<>'staged' OR
          (connection.workspace_id,connection.owner_id,connection.version) IS DISTINCT FROM
          (NEW.workspace_id,NEW.owner_id,NEW.connection_version) OR
          NOT EXISTS(SELECT 1 FROM workspace_members m JOIN users u ON u.id=m.user_id
            WHERE m.workspace_id=NEW.workspace_id AND m.user_id=NEW.owner_id AND m.role IN ('owner','admin') AND u.active)
          THEN RAISE EXCEPTION 'telegram_bot_identity_scope'; END IF;
        IF (connection.kind='native' AND connection.bot_user_id IS DISTINCT FROM NEW.bot_user_id) OR
          (connection.kind='legacy' AND (connection.bot_user_id IS NOT NULL OR NOT EXISTS(
            SELECT 1 FROM telegram_legacy_mappings WHERE connection_id=NEW.connection_id
            AND workspace_id=NEW.workspace_id AND owner_id=NEW.owner_id)))
          THEN RAISE EXCEPTION 'telegram_bot_identity_namespace'; END IF;
        IF EXISTS(SELECT 1 FROM telegram_connections WHERE bot_user_id=NEW.bot_user_id AND id<>NEW.connection_id)
          THEN RAISE EXCEPTION 'telegram_bot_identity_claimed'; END IF;
        RETURN NEW;
      END $$""")
    op.execute('CREATE TRIGGER telegram_bot_identity_guard BEFORE INSERT OR UPDATE OR DELETE ON telegram_bot_identities FOR EACH ROW EXECUTE FUNCTION pao_telegram_bot_identity_guard()')
    op.execute("""CREATE FUNCTION pao_telegram_bot_identity_reservation() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF NEW.bot_user_id IS NOT NULL THEN
          PERFORM pg_advisory_xact_lock(hashtextextended('pao-telegram-bot-v1:'||NEW.bot_user_id,0));
          IF EXISTS(SELECT 1 FROM telegram_bot_identities WHERE bot_user_id=NEW.bot_user_id AND connection_id<>NEW.id)
            THEN RAISE EXCEPTION 'telegram_bot_identity_claimed'; END IF;
        END IF;
        RETURN NEW;
      END $$""")
    op.execute('CREATE TRIGGER telegram_bot_identity_reservation BEFORE INSERT ON telegram_connections FOR EACH ROW EXECUTE FUNCTION pao_telegram_bot_identity_reservation()')
    legacy="""(connection.kind<>'native' AND NOT (connection.kind='legacy' AND connection.bot_user_id IS NULL AND EXISTS(
            SELECT 1 FROM telegram_bot_identities i JOIN telegram_legacy_mappings m ON m.connection_id=i.connection_id
            WHERE i.connection_id=connection.id AND i.workspace_id=connection.workspace_id AND i.owner_id=connection.owner_id
            AND i.connection_version=connection.version AND m.workspace_id=i.workspace_id AND m.owner_id=i.owner_id)))"""
    op.execute(profile_guard_sql().replace("connection.kind<>'native'",legacy,1))


def downgrade():
    if op.get_bind().scalar(sa.text('SELECT count(*) FROM telegram_bot_identities')):
        raise RuntimeError('Downgrade refused: Telegram bot identity history must be preserved')
    op.execute(profile_guard_sql())
    op.execute('DROP TRIGGER telegram_bot_identity_reservation ON telegram_connections')
    op.drop_table('telegram_bot_identities')
    op.execute('DROP FUNCTION pao_telegram_bot_identity_reservation()')
    op.execute('DROP FUNCTION pao_telegram_bot_identity_guard()')
