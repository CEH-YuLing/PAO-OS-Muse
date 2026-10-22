"""Explicit storage-only legacy mapping journal; permanent no-fallback barrier."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision='0060'
down_revision='0059'
branch_labels=depends_on=None
TABLES=('telegram_legacy_mappings','telegram_legacy_peer_maps','telegram_legacy_mapping_audits')

def columns():
    return [sa.Column('id',sa.Uuid(as_uuid=False),primary_key=True),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('workspace_id',sa.Uuid(as_uuid=False),nullable=False)]

def upgrade():
    op.create_table(TABLES[0],*columns(),sa.Column('connection_id',sa.Uuid(as_uuid=False),nullable=False,unique=True),
        sa.Column('owner_id',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),sa.Column('request_key',sa.Uuid(as_uuid=False),nullable=False),
        sa.Column('preview_hash',sa.String(64),nullable=False),sa.Column('content_hash',sa.String(64),nullable=False),sa.Column('snapshot',JSONB(),nullable=False),sa.Column('generation',sa.Integer(),nullable=False),
        sa.UniqueConstraint('id','workspace_id'),sa.UniqueConstraint('workspace_id','owner_id','request_key'),
        sa.ForeignKeyConstraint(['connection_id','workspace_id'],['telegram_connections.id','telegram_connections.workspace_id']),
        sa.CheckConstraint("generation=1 AND length(preview_hash)=64 AND length(content_hash)=64 AND jsonb_typeof(snapshot)='object'"))
    op.create_table(TABLES[1],*columns(),sa.Column('mapping_id',sa.Uuid(as_uuid=False),nullable=False),
        sa.Column('source_peer_id',sa.Uuid(as_uuid=False),sa.ForeignKey('telegram_peers.id'),nullable=False,unique=True),
        sa.Column('peer_id',sa.Uuid(as_uuid=False),sa.ForeignKey('telegram_peers.id'),nullable=False,unique=True),
        sa.Column('source_binding_id',sa.Uuid(as_uuid=False),sa.ForeignKey('channel_bindings.id')),sa.Column('binding_id',sa.Uuid(as_uuid=False),sa.ForeignKey('channel_bindings.id')),
        sa.ForeignKeyConstraint(['mapping_id','workspace_id'],['telegram_legacy_mappings.id','telegram_legacy_mappings.workspace_id']),
        sa.CheckConstraint('(source_binding_id IS NULL)=(binding_id IS NULL)'))
    op.create_table(TABLES[2],*columns(),sa.Column('mapping_id',sa.Uuid(as_uuid=False),nullable=False),
        sa.Column('actor_id',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),sa.Column('request_key',sa.Uuid(as_uuid=False),nullable=False),
        sa.Column('content_hash',sa.String(64),nullable=False),sa.Column('action',sa.String(16),nullable=False),sa.Column('version',sa.Integer(),nullable=False),
        sa.ForeignKeyConstraint(['mapping_id','workspace_id'],['telegram_legacy_mappings.id','telegram_legacy_mappings.workspace_id']),
        sa.UniqueConstraint('mapping_id','version'),sa.UniqueConstraint('workspace_id','actor_id','request_key'),
        sa.CheckConstraint("length(content_hash)=64 AND ((action='apply' AND version=1) OR (action='revoke' AND version=2))"))
    op.execute("CREATE FUNCTION pao_telegram_mapping_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'telegram_mapping_journal_immutable'; END $$")
    for table in TABLES:op.execute(f'CREATE TRIGGER telegram_mapping_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION pao_telegram_mapping_immutable()')
    op.execute("""CREATE FUNCTION pao_telegram_mapping_header_guard() RETURNS trigger LANGUAGE plpgsql AS $$
      DECLARE connection telegram_connections%ROWTYPE; parent telegram_legacy_mappings%ROWTYPE;
      BEGIN
        IF TG_TABLE_NAME='telegram_legacy_mappings' THEN
          SELECT * INTO connection FROM telegram_connections WHERE id=NEW.connection_id;
          IF connection.kind IS DISTINCT FROM 'legacy' OR connection.status IS DISTINCT FROM 'staged' OR connection.version IS DISTINCT FROM 1
            OR (connection.workspace_id,connection.owner_id) IS DISTINCT FROM (NEW.workspace_id,NEW.owner_id)
            THEN RAISE EXCEPTION 'telegram_mapping_connection_mismatch'; END IF;
        ELSE
          SELECT * INTO parent FROM telegram_legacy_mappings WHERE id=NEW.mapping_id;
          SELECT * INTO connection FROM telegram_connections WHERE id=parent.connection_id;
          IF parent.workspace_id IS DISTINCT FROM NEW.workspace_id OR connection.version IS DISTINCT FROM NEW.version
            OR (NEW.action='apply' AND (connection.status<>'staged' OR NEW.actor_id<>parent.owner_id OR NEW.request_key<>parent.request_key OR NEW.content_hash<>parent.content_hash))
            OR (NEW.action='revoke' AND connection.status<>'revoked')
            THEN RAISE EXCEPTION 'telegram_mapping_audit_mismatch'; END IF;
        END IF;
        RETURN NEW;
      END $$""")
    for table in (TABLES[0],TABLES[2]):op.execute(f'CREATE TRIGGER telegram_mapping_header_guard BEFORE INSERT ON {table} FOR EACH ROW EXECUTE FUNCTION pao_telegram_mapping_header_guard()')
    op.execute("""CREATE FUNCTION pao_telegram_mapping_link_guard() RETURNS trigger LANGUAGE plpgsql AS $$
      DECLARE source telegram_peers%ROWTYPE; target telegram_peers%ROWTYPE; parent telegram_legacy_mappings%ROWTYPE;
        source_binding channel_bindings%ROWTYPE; target_binding channel_bindings%ROWTYPE;
      BEGIN
        SELECT * INTO parent FROM telegram_legacy_mappings WHERE id=NEW.mapping_id;
        SELECT * INTO source FROM telegram_peers WHERE id=NEW.source_peer_id;
        SELECT * INTO target FROM telegram_peers WHERE id=NEW.peer_id;
        IF parent.id IS NULL OR source.id IS NULL OR target.id IS NULL OR source.connection_id IS NOT NULL
          OR (target.connection_id,target.workspace_id,source.workspace_id,NEW.workspace_id) IS DISTINCT FROM
             (parent.connection_id,parent.workspace_id,parent.workspace_id,parent.workspace_id)
          OR (source.user_id,source.telegram_user_id,source.chat_id) IS DISTINCT FROM (target.user_id,target.telegram_user_id,target.chat_id)
          OR target.enabled OR target.session_id IS NOT NULL
          THEN RAISE EXCEPTION 'telegram_mapping_peer_scope_mismatch'; END IF;
        IF NEW.binding_id IS NOT NULL THEN
          SELECT * INTO source_binding FROM channel_bindings WHERE id=NEW.source_binding_id;
          SELECT * INTO target_binding FROM channel_bindings WHERE id=NEW.binding_id;
          IF source_binding.id IS NULL OR target_binding.id IS NULL OR source_binding.peer_id<>source.id OR target_binding.peer_id<>target.id
            OR source_binding.connection_id IS NOT NULL OR target_binding.connection_id IS DISTINCT FROM parent.connection_id
            OR source_binding.channel<>'telegram' OR target_binding.channel<>'telegram'
            OR (source_binding.workspace_id,source_binding.actor_id,source_binding.kind) IS DISTINCT FROM
               (target_binding.workspace_id,target_binding.actor_id,target_binding.kind)
            OR target_binding.enabled OR target_binding.outbound_confirmed OR target_binding.mode<>'quiet'
            OR target_binding.session_id IS NOT NULL OR target_binding.brain_id IS NOT NULL
            THEN RAISE EXCEPTION 'telegram_mapping_binding_scope_mismatch'; END IF;
        END IF;
        RETURN NEW;
      END $$""")
    op.execute('CREATE TRIGGER telegram_mapping_link_guard BEFORE INSERT ON telegram_legacy_peer_maps FOR EACH ROW EXECUTE FUNCTION pao_telegram_mapping_link_guard()')
    op.execute("""CREATE FUNCTION pao_telegram_legacy_barrier() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF NEW.connection_id IS NULL AND EXISTS(SELECT 1 FROM telegram_connections WHERE kind='legacy') THEN
          IF TG_TABLE_NAME IN ('telegram_peers','telegram_updates','telegram_deliveries') THEN
            RAISE EXCEPTION 'telegram_legacy_mapping_barrier';
          ELSIF TG_TABLE_NAME='channel_bindings' THEN
            IF NEW.channel='telegram' THEN RAISE EXCEPTION 'telegram_legacy_mapping_barrier'; END IF;
          ELSIF EXISTS(SELECT 1 FROM channel_bindings WHERE id=NEW.binding_id AND channel='telegram') THEN
            RAISE EXCEPTION 'telegram_legacy_mapping_barrier';
          END IF;
        END IF;
        RETURN NEW;
      END $$""")
    for table in ('telegram_peers','telegram_updates','telegram_deliveries','channel_bindings','channel_inbounds','channel_outbox'):
        op.execute(f'CREATE TRIGGER telegram_legacy_mapping_barrier BEFORE INSERT ON {table} FOR EACH ROW EXECUTE FUNCTION pao_telegram_legacy_barrier()')
    op.execute("""CREATE FUNCTION pao_telegram_legacy_source_guard() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF EXISTS(SELECT 1 FROM telegram_legacy_peer_maps WHERE source_peer_id=OLD.id) AND
          (NEW.workspace_id,NEW.user_id,NEW.telegram_user_id,NEW.chat_id,NEW.session_id) IS DISTINCT FROM
          (OLD.workspace_id,OLD.user_id,OLD.telegram_user_id,OLD.chat_id,OLD.session_id)
          THEN RAISE EXCEPTION 'telegram_mapping_source_immutable'; END IF;
        RETURN NEW;
      END $$""")
    op.execute('CREATE TRIGGER telegram_legacy_source_guard BEFORE UPDATE ON telegram_peers FOR EACH ROW EXECUTE FUNCTION pao_telegram_legacy_source_guard()')

def downgrade():
    if any(op.get_bind().scalar(sa.text(f'SELECT count(*) FROM {table}')) for table in TABLES):
        raise RuntimeError('Downgrade refused: Telegram legacy mapping history must be preserved')
    op.execute('DROP TRIGGER telegram_legacy_source_guard ON telegram_peers');op.execute('DROP FUNCTION pao_telegram_legacy_source_guard()')
    for table in ('telegram_peers','telegram_updates','telegram_deliveries','channel_bindings','channel_inbounds','channel_outbox'):
        op.execute(f'DROP TRIGGER telegram_legacy_mapping_barrier ON {table}')
    op.execute('DROP FUNCTION pao_telegram_legacy_barrier()')
    for table in reversed(TABLES):op.drop_table(table)
    op.execute('DROP FUNCTION pao_telegram_mapping_link_guard()');op.execute('DROP FUNCTION pao_telegram_mapping_immutable()');op.execute('DROP FUNCTION IF EXISTS pao_telegram_mapping_header_guard()')
