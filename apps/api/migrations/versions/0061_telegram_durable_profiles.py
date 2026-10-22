"""Disabled runtime profiles, append-only generations and quarantine/cursor.

No backfill, activation, bot identity repinning or change to legacy history.
"""
from alembic import op
import sqlalchemy as sa

revision='0061'
down_revision='0060'
branch_labels=depends_on=None
TABLES=('telegram_runtime_profiles','telegram_runtime_audits','telegram_runtime_receipts')


def columns():
    return [sa.Column('id',sa.Uuid(as_uuid=False),primary_key=True),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),nullable=False),
        sa.Column('connection_id',sa.Uuid(as_uuid=False),nullable=False)]


def scope():
    return sa.ForeignKeyConstraint(['connection_id','workspace_id'],['telegram_connections.id','telegram_connections.workspace_id'])


def upgrade():
    op.create_table(TABLES[0],*columns(),
        sa.Column('connection_version',sa.Integer(),nullable=False),
        sa.Column('generation',sa.Integer(),nullable=False),sa.Column('status',sa.String(16),nullable=False),
        sa.Column('token_ciphertext',sa.Text()),sa.Column('next_offset',sa.BigInteger(),nullable=False),
        sa.UniqueConstraint('connection_id'),scope(),
        sa.CheckConstraint("connection_version>=1 AND generation>=1 AND next_offset>=0 AND ((status='disabled' AND token_ciphertext IS NOT NULL AND length(token_ciphertext) BETWEEN 1 AND 16384) OR (status='revoked' AND token_ciphertext IS NULL))",name='telegram_profile_state'))
    op.create_table(TABLES[1],*columns(),
        sa.Column('actor_id',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('request_key',sa.Uuid(as_uuid=False),nullable=False),
        sa.Column('generation',sa.Integer(),nullable=False),sa.Column('action',sa.String(16),nullable=False),
        sa.Column('content_hash',sa.String(64),nullable=False),scope(),
        sa.UniqueConstraint('connection_id','generation'),sa.UniqueConstraint('workspace_id','actor_id','request_key'),
        sa.CheckConstraint("length(content_hash)=64 AND ((generation=1 AND action='stored') OR (generation>1 AND action IN ('rotated','revoked')))",name='telegram_runtime_audit_state'))
    op.create_table(TABLES[2],*columns(),
        sa.Column('generation',sa.Integer(),nullable=False),sa.Column('update_id',sa.BigInteger(),nullable=False),
        sa.Column('content_hash',sa.String(64),nullable=False),sa.Column('reason',sa.String(16),nullable=False),scope(),
        sa.UniqueConstraint('connection_id','update_id'),
        sa.CheckConstraint("generation>=1 AND update_id>=0 AND update_id<9223372036854775807 AND length(content_hash)=64 AND reason IN ('unsupported','unlinked','malformed')",name='telegram_runtime_receipt_state'))
    op.execute("""CREATE FUNCTION pao_telegram_runtime_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN RAISE EXCEPTION 'telegram_runtime_history_immutable'; END $$""")
    for table in TABLES[1:]:
        op.execute(f'CREATE TRIGGER telegram_runtime_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION pao_telegram_runtime_immutable()')
    op.execute("""CREATE FUNCTION pao_telegram_profile_guard() RETURNS trigger LANGUAGE plpgsql AS $$
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
      END $$""")
    op.execute('CREATE TRIGGER telegram_profile_guard BEFORE INSERT OR UPDATE OR DELETE ON telegram_runtime_profiles FOR EACH ROW EXECUTE FUNCTION pao_telegram_profile_guard()')
    op.execute("""CREATE FUNCTION pao_telegram_runtime_evidence_guard() RETURNS trigger LANGUAGE plpgsql AS $$
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
    for table in TABLES[1:]:
        op.execute(f'CREATE TRIGGER telegram_runtime_evidence_guard BEFORE INSERT ON {table} FOR EACH ROW EXECUTE FUNCTION pao_telegram_runtime_evidence_guard()')
    op.execute("""CREATE FUNCTION pao_telegram_profile_audit_required() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF NOT EXISTS(SELECT 1 FROM telegram_runtime_audits WHERE connection_id=NEW.connection_id
            AND workspace_id=NEW.workspace_id AND generation=NEW.generation)
          THEN RAISE EXCEPTION 'telegram_runtime_audit_required'; END IF;
        IF TG_OP='UPDATE' AND NEW.next_offset>OLD.next_offset AND NOT EXISTS(
            SELECT 1 FROM telegram_runtime_receipts WHERE connection_id=NEW.connection_id
            AND workspace_id=NEW.workspace_id AND generation=NEW.generation AND update_id=NEW.next_offset-1)
          THEN RAISE EXCEPTION 'telegram_runtime_cursor_receipt_required'; END IF;
        RETURN NEW;
      END $$""")
    op.execute('CREATE CONSTRAINT TRIGGER telegram_profile_audit_required AFTER INSERT OR UPDATE ON telegram_runtime_profiles DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION pao_telegram_profile_audit_required()')


def downgrade():
    if any(op.get_bind().scalar(sa.text(f'SELECT count(*) FROM {table}')) for table in TABLES):
        raise RuntimeError('Downgrade refused: Telegram runtime history must be preserved')
    for table in reversed(TABLES):op.drop_table(table)
    for name in ('pao_telegram_profile_audit_required','pao_telegram_runtime_evidence_guard','pao_telegram_profile_guard','pao_telegram_runtime_immutable'):
        op.execute(f'DROP FUNCTION {name}()')
