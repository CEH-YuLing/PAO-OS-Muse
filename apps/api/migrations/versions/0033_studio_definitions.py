"""P4 immutable definitions, audited publication, durable run pins."""
from alembic import op
import sqlalchemy as sa
revision='0033'
down_revision='0032'
branch_labels=None
depends_on=None
def identity():return [sa.Column('id',sa.Uuid(as_uuid=False),primary_key=True),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False)]
def upgrade():
    op.add_column('runs',sa.Column('studio_snapshot',sa.JSON()))
    op.create_table('studio_definitions',*identity(),sa.Column('workspace_id',sa.Uuid(as_uuid=False),sa.ForeignKey('workspaces.id'),nullable=False),
        sa.Column('owner_id',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),sa.Column('kind',sa.String(12),nullable=False),
        sa.Column('slug',sa.String(60),nullable=False),sa.Column('name',sa.String(120),nullable=False),sa.Column('revision',sa.Integer(),nullable=False,server_default='1'),
        sa.Column('seed',sa.Boolean(),nullable=False,server_default='false'),sa.Column('published_version_id',sa.Uuid(as_uuid=False)),sa.Column('archived_at',sa.DateTime(timezone=True)),
        sa.UniqueConstraint('id','workspace_id'),sa.UniqueConstraint('workspace_id','kind','slug'),sa.CheckConstraint("kind in ('agents','skills','workflows')",name='studio_kind'))
    op.create_index('ix_studio_definitions_workspace_id','studio_definitions',['workspace_id'])
    op.create_table('studio_versions',*identity(),sa.Column('workspace_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('definition_id',sa.Uuid(as_uuid=False),nullable=False),
        sa.Column('author_id',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),sa.Column('ordinal',sa.Integer(),nullable=False),
        sa.Column('payload',sa.JSON(),nullable=False),sa.Column('content_hash',sa.String(64),nullable=False),sa.Column('status',sa.String(16),nullable=False),
        sa.ForeignKeyConstraint(['definition_id','workspace_id'],['studio_definitions.id','studio_definitions.workspace_id']),
        sa.UniqueConstraint('id','definition_id','workspace_id'),sa.UniqueConstraint('definition_id','ordinal'),
        sa.CheckConstraint("status in ('draft','validated','reviewed','published','deprecated')",name='studio_version_status'))
    op.create_index('ix_studio_versions_definition_id','studio_versions',['definition_id'])
    op.create_foreign_key('studio_published_scope','studio_definitions','studio_versions',['published_version_id','id','workspace_id'],['id','definition_id','workspace_id'])
    op.create_table('studio_events',*identity(),sa.Column('workspace_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('definition_id',sa.Uuid(as_uuid=False),nullable=False),
        sa.Column('version_id',sa.Uuid(as_uuid=False)),sa.Column('actor_id',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id')),
        sa.Column('action',sa.String(32),nullable=False),sa.Column('data',sa.JSON(),nullable=False),
        sa.ForeignKeyConstraint(['definition_id','workspace_id'],['studio_definitions.id','studio_definitions.workspace_id']),
        sa.ForeignKeyConstraint(['version_id','definition_id','workspace_id'],['studio_versions.id','studio_versions.definition_id','studio_versions.workspace_id']))
    op.create_index('ix_studio_events_definition_id','studio_events',['definition_id'])
    op.execute("""CREATE FUNCTION pao_studio_version_immutable() RETURNS trigger AS $$ BEGIN
      IF TG_OP='DELETE' THEN RAISE EXCEPTION 'studio_version_immutable'; END IF;
      IF OLD.payload::jsonb IS DISTINCT FROM NEW.payload::jsonb OR OLD.content_hash<>NEW.content_hash
        OR OLD.definition_id<>NEW.definition_id OR OLD.workspace_id<>NEW.workspace_id OR OLD.author_id<>NEW.author_id OR OLD.ordinal<>NEW.ordinal
      THEN RAISE EXCEPTION 'studio_version_immutable'; END IF; RETURN NEW; END; $$ LANGUAGE plpgsql""")
    op.execute('CREATE TRIGGER studio_version_immutable BEFORE UPDATE OR DELETE ON studio_versions FOR EACH ROW EXECUTE FUNCTION pao_studio_version_immutable()')
    op.execute("""CREATE FUNCTION pao_studio_audit_immutable() RETURNS trigger AS $$ BEGIN RAISE EXCEPTION 'studio_audit_immutable'; END; $$ LANGUAGE plpgsql""")
    op.execute('CREATE TRIGGER studio_audit_immutable BEFORE UPDATE OR DELETE ON studio_events FOR EACH ROW EXECUTE FUNCTION pao_studio_audit_immutable()')
    op.execute("""CREATE FUNCTION pao_studio_pin_immutable() RETURNS trigger AS $$ BEGIN
      IF OLD.studio_snapshot IS NOT NULL AND OLD.studio_snapshot::jsonb IS DISTINCT FROM NEW.studio_snapshot::jsonb
      THEN RAISE EXCEPTION 'studio_pin_immutable'; END IF; RETURN NEW; END; $$ LANGUAGE plpgsql""")
    op.execute('CREATE TRIGGER studio_pin_immutable BEFORE UPDATE ON runs FOR EACH ROW EXECUTE FUNCTION pao_studio_pin_immutable()')
def downgrade():
    op.execute('DROP TRIGGER studio_pin_immutable ON runs');op.execute('DROP FUNCTION pao_studio_pin_immutable()')
    op.execute('DROP TRIGGER studio_audit_immutable ON studio_events');op.execute('DROP FUNCTION pao_studio_audit_immutable()')
    op.execute('DROP TRIGGER studio_version_immutable ON studio_versions');op.execute('DROP FUNCTION pao_studio_version_immutable()')
    op.drop_table('studio_events');op.drop_constraint('studio_published_scope','studio_definitions',type_='foreignkey')
    op.drop_table('studio_versions');op.drop_table('studio_definitions');op.drop_column('runs','studio_snapshot')
