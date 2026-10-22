"""Channel identity, inbox/outbox and append-only control journal."""
from alembic import op
import sqlalchemy as sa
revision='0047'
down_revision='0046'
branch_labels=depends_on=None

def common():
    return [sa.Column('id',sa.Uuid(as_uuid=False),primary_key=True),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('workspace_id',sa.Uuid(as_uuid=False),nullable=False)]

def upgrade():
    op.add_column('runs',sa.Column('channel_context',sa.JSON(),nullable=True))
    op.create_table('channel_bindings',*common(),sa.Column('actor_id',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('channel',sa.String(16),nullable=False),sa.Column('identity_hash',sa.String(64),nullable=False),
        sa.Column('peer_id',sa.Uuid(as_uuid=False),sa.ForeignKey('telegram_peers.id'),unique=True),sa.Column('brain_id',sa.Uuid(as_uuid=False)),sa.Column('session_id',sa.Uuid(as_uuid=False),unique=True),
        sa.Column('kind',sa.String(16),nullable=False),sa.Column('mode',sa.String(16),nullable=False),sa.Column('enabled',sa.Boolean(),nullable=False),
        sa.Column('outbound_confirmed',sa.Boolean(),nullable=False),sa.Column('retention_days',sa.Integer(),nullable=False),sa.Column('version',sa.Integer(),nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'],['workspaces.id']),sa.UniqueConstraint('id','workspace_id'),sa.UniqueConstraint('channel','identity_hash'),
        sa.ForeignKeyConstraint(['brain_id','workspace_id'],['brains.id','brains.workspace_id']),sa.ForeignKeyConstraint(['session_id','workspace_id'],['sessions.id','sessions.workspace_id']),
        sa.CheckConstraint("channel IN ('local','telegram') AND kind IN ('personal','customer') AND mode IN ('auto','human','quiet') AND retention_days BETWEEN 1 AND 30 AND version>=1"))
    foreign=lambda:sa.ForeignKeyConstraint(['binding_id','workspace_id'],['channel_bindings.id','channel_bindings.workspace_id'])
    op.create_table('channel_inbounds',*common(),sa.Column('binding_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('external_key',sa.String(64),nullable=False),
        sa.Column('content_hash',sa.String(64),nullable=False),sa.Column('body',sa.Text()),sa.Column('status',sa.String(24),nullable=False),
        sa.Column('run_id',sa.Uuid(as_uuid=False),sa.ForeignKey('runs.id'),unique=True),sa.Column('purged_at',sa.DateTime(timezone=True)),foreign(),
        sa.UniqueConstraint('binding_id','external_key'),sa.CheckConstraint("length(content_hash)=64 AND status IN ('accepted','quiet','busy','command','blocked')"))
    op.create_table('channel_outbox',*common(),sa.Column('binding_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('request_key',sa.String(80),nullable=False),
        sa.Column('content_hash',sa.String(64),nullable=False),sa.Column('body',sa.Text()),sa.Column('kind',sa.String(16),nullable=False),sa.Column('status',sa.String(16),nullable=False),
        sa.Column('attempts',sa.Integer(),nullable=False),sa.Column('available_at',sa.DateTime(timezone=True),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('remote_id',sa.String(64)),sa.Column('error_code',sa.String(64)),foreign(),sa.UniqueConstraint('binding_id','request_key'),
        sa.CheckConstraint("kind IN ('auto','manual') AND status IN ('queued','sending','sent','failed','unknown','cancelled') AND attempts BETWEEN 0 AND 3 AND length(content_hash)=64"))
    op.create_table('channel_audits',*common(),sa.Column('binding_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('actor_id',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('request_key',sa.String(80),nullable=False),sa.Column('content_hash',sa.String(64),nullable=False),sa.Column('data',sa.JSON(),nullable=False),foreign(),sa.UniqueConstraint('binding_id','request_key'))
    op.execute("CREATE FUNCTION channel_audit_immutable() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'channel audit immutable'; END $$")
    op.execute('CREATE TRIGGER channel_audit_immutable BEFORE UPDATE OR DELETE ON channel_audits FOR EACH ROW EXECUTE FUNCTION channel_audit_immutable()')
    op.execute("""CREATE FUNCTION channel_identity_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN IF (NEW.id,NEW.workspace_id,NEW.actor_id,NEW.channel,NEW.identity_hash,NEW.peer_id,NEW.brain_id,NEW.kind,NEW.retention_days)
    IS DISTINCT FROM (OLD.id,OLD.workspace_id,OLD.actor_id,OLD.channel,OLD.identity_hash,OLD.peer_id,OLD.brain_id,OLD.kind,OLD.retention_days)
    THEN RAISE EXCEPTION 'channel identity immutable'; END IF; RETURN NEW; END $$""")
    op.execute('CREATE TRIGGER channel_identity_immutable BEFORE UPDATE ON channel_bindings FOR EACH ROW EXECUTE FUNCTION channel_identity_immutable()')

def downgrade():
    for name in ('channel_audits','channel_outbox','channel_inbounds','channel_bindings'):op.drop_table(name)
    op.execute('DROP FUNCTION channel_audit_immutable()');op.execute('DROP FUNCTION IF EXISTS channel_identity_immutable()');op.drop_column('runs','channel_context')
