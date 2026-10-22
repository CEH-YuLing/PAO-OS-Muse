"""Credential-free Telegram namespaces; retain unmapped legacy history verbatim."""
from alembic import op
import sqlalchemy as sa

revision='0059'
down_revision='0058'
branch_labels=depends_on=None
CHILDREN=('telegram_updates','telegram_deliveries','channel_inbounds','channel_outbox','channel_audits')


def upgrade():
    op.create_table('telegram_connections',
        sa.Column('id',sa.Uuid(as_uuid=False),primary_key=True),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),sa.ForeignKey('workspaces.id'),nullable=False),
        sa.Column('owner_id',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('kind',sa.String(16),nullable=False),sa.Column('bot_user_id',sa.String(24),unique=True),
        sa.Column('status',sa.String(16),nullable=False),sa.Column('version',sa.Integer(),nullable=False),
        sa.UniqueConstraint('id','workspace_id'),
        sa.CheckConstraint("kind IN ('legacy','native') AND status IN ('staged','revoked') AND version>=1"),
        sa.CheckConstraint("(kind='legacy' OR bot_user_id IS NOT NULL) AND (bot_user_id IS NULL OR bot_user_id ~ '^[1-9][0-9]{0,15}$')"))
    op.create_index('telegram_legacy_namespace_once','telegram_connections',['kind'],unique=True,postgresql_where=sa.text("kind='legacy'"))
    for table in ('telegram_peers','channel_bindings'):
        op.add_column(table,sa.Column('connection_id',sa.Uuid(as_uuid=False)))
        op.create_foreign_key(table+'_connection_scope',table,'telegram_connections',['connection_id','workspace_id'],['id','workspace_id'])
    op.create_check_constraint('channel_connection_kind','channel_bindings',"connection_id IS NULL OR channel='telegram'")
    for table in CHILDREN:
        op.add_column(table,sa.Column('connection_id',sa.Uuid(as_uuid=False),sa.ForeignKey('telegram_connections.id')))
    for field,legacy in (('telegram_user_id','user'),('chat_id','chat')):
        op.drop_constraint('telegram_peers_'+field+'_key','telegram_peers',type_='unique')
        op.create_unique_constraint('telegram_peers_connection_id_'+field+'_key','telegram_peers',['connection_id',field])
        op.create_index('telegram_legacy_'+legacy+'_once','telegram_peers',[field],unique=True,postgresql_where=sa.text('connection_id IS NULL'))
    # Internal UUID replaces global update_id PK, without changing any old field.
    # No extension or bot/token-derived ID, and no inferred connection backfill.
    op.add_column('telegram_updates',sa.Column('id',sa.Uuid(as_uuid=False)))
    op.execute("UPDATE telegram_updates SET id=md5('pao-legacy-telegram-update:'||update_id::text)::uuid")
    op.alter_column('telegram_updates','id',nullable=False)
    op.drop_constraint('telegram_updates_pkey','telegram_updates',type_='primary')
    op.create_primary_key('telegram_updates_pkey','telegram_updates',['id'])
    op.create_unique_constraint('telegram_updates_connection_id_update_id_key','telegram_updates',['connection_id','update_id'])
    op.create_index('telegram_legacy_update_once','telegram_updates',['update_id'],unique=True,postgresql_where=sa.text('connection_id IS NULL'))
    op.drop_constraint('telegram_deliveries_dedup_key_key','telegram_deliveries',type_='unique')
    op.create_unique_constraint('telegram_deliveries_connection_id_dedup_key_key','telegram_deliveries',['connection_id','dedup_key'])
    op.create_index('telegram_legacy_delivery_once','telegram_deliveries',['dedup_key'],unique=True,postgresql_where=sa.text('connection_id IS NULL'))
    op.execute("""CREATE FUNCTION pao_telegram_connection_guard() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF TG_OP='DELETE' THEN RAISE EXCEPTION 'telegram_connection_history_immutable'; END IF;
        IF (NEW.id,NEW.created_at,NEW.workspace_id,NEW.owner_id,NEW.kind,NEW.bot_user_id)
          IS DISTINCT FROM (OLD.id,OLD.created_at,OLD.workspace_id,OLD.owner_id,OLD.kind,OLD.bot_user_id)
          THEN RAISE EXCEPTION 'telegram_connection_identity_immutable'; END IF;
        IF NEW.status IS DISTINCT FROM OLD.status OR NEW.version IS DISTINCT FROM OLD.version THEN
          IF OLD.status='revoked' OR NEW.status<>'revoked' OR NEW.version<>OLD.version+1
            THEN RAISE EXCEPTION 'telegram_connection_transition_invalid'; END IF;
        END IF;
        RETURN NEW;
      END $$""")
    op.execute('CREATE TRIGGER telegram_connection_immutable BEFORE UPDATE OR DELETE ON telegram_connections FOR EACH ROW EXECUTE FUNCTION pao_telegram_connection_guard()')
    op.execute("""CREATE FUNCTION pao_telegram_namespace_parent() RETURNS trigger LANGUAGE plpgsql AS $$
      DECLARE expected uuid; BEGIN
        IF TG_OP='UPDATE' AND NEW.connection_id IS DISTINCT FROM OLD.connection_id
          THEN RAISE EXCEPTION 'telegram_namespace_history_immutable'; END IF;
        IF TG_TABLE_NAME='telegram_peers' THEN
          IF TG_OP='UPDATE' AND OLD.connection_id IS NOT NULL AND
            (NEW.workspace_id,NEW.user_id,NEW.telegram_user_id,NEW.chat_id) IS DISTINCT FROM
            (OLD.workspace_id,OLD.user_id,OLD.telegram_user_id,OLD.chat_id)
            THEN RAISE EXCEPTION 'telegram_peer_identity_immutable'; END IF;
        ELSIF NEW.channel='telegram' THEN
          SELECT connection_id INTO expected FROM telegram_peers WHERE id=NEW.peer_id AND workspace_id=NEW.workspace_id AND user_id=NEW.actor_id;
          IF NOT FOUND OR NEW.connection_id IS DISTINCT FROM expected
            THEN RAISE EXCEPTION 'telegram_binding_namespace_mismatch'; END IF;
        END IF;
        RETURN NEW;
      END $$""")
    for table in ('telegram_peers','channel_bindings'):
        op.execute(f'CREATE TRIGGER telegram_namespace_parent BEFORE INSERT OR UPDATE ON {table} FOR EACH ROW EXECUTE FUNCTION pao_telegram_namespace_parent()')
    op.execute("""CREATE FUNCTION pao_telegram_namespace_child() RETURNS trigger LANGUAGE plpgsql AS $$
      DECLARE expected uuid; BEGIN
        IF TG_OP='UPDATE' AND NEW.connection_id IS DISTINCT FROM OLD.connection_id
          THEN RAISE EXCEPTION 'telegram_namespace_history_immutable'; END IF;
        IF TG_TABLE_NAME IN ('telegram_updates','telegram_deliveries') THEN
          SELECT connection_id INTO expected FROM telegram_peers WHERE id=NEW.peer_id;
        ELSE
          SELECT connection_id INTO expected FROM channel_bindings WHERE id=NEW.binding_id;
        END IF;
        IF NOT FOUND OR NEW.connection_id IS DISTINCT FROM expected
          THEN RAISE EXCEPTION 'telegram_receipt_namespace_mismatch'; END IF;
        RETURN NEW;
      END $$""")
    for table in CHILDREN:
        op.execute(f'CREATE TRIGGER telegram_namespace_child BEFORE INSERT OR UPDATE ON {table} FOR EACH ROW EXECUTE FUNCTION pao_telegram_namespace_child()')


def downgrade():
    bind=op.get_bind()
    if bind.scalar(sa.text('SELECT count(*) FROM telegram_connections')) or any(
        bind.scalar(sa.text(f'SELECT count(*) FROM {table} WHERE connection_id IS NOT NULL'))
        for table in ('telegram_peers','channel_bindings',*CHILDREN)):
        raise RuntimeError('Downgrade refused: Telegram connection history must be preserved')
    for table in CHILDREN:op.execute(f'DROP TRIGGER telegram_namespace_child ON {table}')
    for table in ('telegram_peers','channel_bindings'):op.execute(f'DROP TRIGGER telegram_namespace_parent ON {table}')
    op.execute('DROP TRIGGER telegram_connection_immutable ON telegram_connections')
    for name in ('pao_telegram_namespace_child','pao_telegram_namespace_parent','pao_telegram_connection_guard'):op.execute(f'DROP FUNCTION {name}()')
    for field,legacy in (('telegram_user_id','user'),('chat_id','chat')):
        op.drop_index('telegram_legacy_'+legacy+'_once',table_name='telegram_peers')
        op.drop_constraint('telegram_peers_connection_id_'+field+'_key','telegram_peers',type_='unique')
        op.create_unique_constraint('telegram_peers_'+field+'_key','telegram_peers',[field])
    op.drop_index('telegram_legacy_update_once',table_name='telegram_updates')
    op.drop_constraint('telegram_updates_connection_id_update_id_key','telegram_updates',type_='unique')
    op.drop_constraint('telegram_updates_pkey','telegram_updates',type_='primary')
    op.create_primary_key('telegram_updates_pkey','telegram_updates',['update_id'])
    op.drop_column('telegram_updates','id')
    op.drop_index('telegram_legacy_delivery_once',table_name='telegram_deliveries')
    op.drop_constraint('telegram_deliveries_connection_id_dedup_key_key','telegram_deliveries',type_='unique')
    op.create_unique_constraint('telegram_deliveries_dedup_key_key','telegram_deliveries',['dedup_key'])
    op.drop_constraint('channel_connection_kind','channel_bindings',type_='check')
    for table in CHILDREN:op.drop_column(table,'connection_id')
    for table in ('telegram_peers','channel_bindings'):
        op.drop_constraint(table+'_connection_scope',table,type_='foreignkey');op.drop_column(table,'connection_id')
    op.drop_table('telegram_connections')
