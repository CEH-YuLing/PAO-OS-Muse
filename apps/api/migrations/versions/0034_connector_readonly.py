"""P5 scoped connectors, separate encrypted secrets and immutable gateway pins."""
from alembic import op
import sqlalchemy as sa
revision='0034'
down_revision='0033'
branch_labels=None
depends_on=None
def identity():return [sa.Column('id',sa.Uuid(as_uuid=False),primary_key=True),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False)]
def upgrade():
    op.add_column('tool_calls',sa.Column('connector_snapshot',sa.JSON()))
    op.create_table('connector_connections',*identity(),
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),sa.ForeignKey('workspaces.id'),nullable=False),
        sa.Column('owner_id',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('brain_id',sa.Uuid(as_uuid=False),sa.ForeignKey('brains.id')),
        sa.Column('endpoint',sa.String(1024),nullable=False),sa.Column('status',sa.String(16),nullable=False),
        sa.Column('version',sa.Integer(),nullable=False),sa.Column('manifest',sa.JSON(),nullable=False),
        sa.Column('manifest_hash',sa.String(64)),sa.Column('permissions',sa.JSON(),nullable=False),
        sa.Column('failures',sa.Integer(),nullable=False),sa.Column('circuit_until',sa.DateTime(timezone=True)),
        sa.UniqueConstraint('id','workspace_id'),sa.CheckConstraint("status in ('draft','connected','revoked')",name='connector_status'))
    op.create_index('ix_connector_connections_workspace_id','connector_connections',['workspace_id'])
    op.create_table('connector_secrets',*identity(),sa.Column('workspace_id',sa.Uuid(as_uuid=False),nullable=False),
        sa.Column('connection_id',sa.Uuid(as_uuid=False),nullable=False,unique=True),sa.Column('ciphertext',sa.Text()),
        sa.ForeignKeyConstraint(['connection_id','workspace_id'],['connector_connections.id','connector_connections.workspace_id']))
    op.create_table('connector_events',*identity(),sa.Column('workspace_id',sa.Uuid(as_uuid=False),nullable=False),
        sa.Column('connection_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('actor_id',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('action',sa.String(32),nullable=False),sa.Column('data',sa.JSON(),nullable=False),
        sa.ForeignKeyConstraint(['connection_id','workspace_id'],['connector_connections.id','connector_connections.workspace_id']))
    op.create_index('ix_connector_events_connection_id','connector_events',['connection_id'])
    op.execute("CREATE FUNCTION pao_connector_audit_immutable() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'connector_audit_immutable'; END; $$ LANGUAGE plpgsql")
    op.execute('CREATE TRIGGER connector_audit_immutable BEFORE UPDATE OR DELETE ON connector_events FOR EACH ROW EXECUTE FUNCTION pao_connector_audit_immutable()')
    op.execute("""CREATE FUNCTION pao_connector_pin_immutable() RETURNS trigger AS $$ BEGIN
      IF OLD.connector_snapshot IS NOT NULL AND (OLD.connector_snapshot::jsonb IS DISTINCT FROM NEW.connector_snapshot::jsonb
        OR OLD.arguments::jsonb IS DISTINCT FROM NEW.arguments::jsonb OR OLD.name<>NEW.name OR OLD.run_id<>NEW.run_id OR OLD.workspace_id<>NEW.workspace_id OR OLD.user_id<>NEW.user_id)
      THEN RAISE EXCEPTION 'connector_pin_immutable'; END IF; RETURN NEW; END; $$ LANGUAGE plpgsql""")
    op.execute('CREATE TRIGGER connector_pin_immutable BEFORE UPDATE ON tool_calls FOR EACH ROW EXECUTE FUNCTION pao_connector_pin_immutable()')
def downgrade():
    op.execute('DROP TRIGGER connector_pin_immutable ON tool_calls');op.execute('DROP FUNCTION pao_connector_pin_immutable()')
    op.execute('DROP TRIGGER connector_audit_immutable ON connector_events');op.execute('DROP FUNCTION pao_connector_audit_immutable()')
    op.drop_table('connector_events');op.drop_table('connector_secrets');op.drop_table('connector_connections');op.drop_column('tool_calls','connector_snapshot')
