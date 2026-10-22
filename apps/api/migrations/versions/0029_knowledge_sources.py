"""Add source provenance and durable text ingestion. No legacy data backfill."""
from alembic import op
import sqlalchemy as sa
revision='0029'
down_revision='0028'
branch_labels=None
depends_on=None

def identity():
    return [sa.Column('id',sa.Uuid(as_uuid=False),primary_key=True),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False)]

def scope():
    return [sa.Column('brain_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('workspace_id',sa.Uuid(as_uuid=False),nullable=False)]

def upgrade():
    for table in ('brain_files','brain_notes'):
        op.create_unique_constraint(table+'_origin_scope_unique',table,['id','brain_id','workspace_id'])
    op.create_table('knowledge_sources',*identity(),*scope(),
        sa.Column('file_id',sa.Uuid(as_uuid=False)),sa.Column('note_id',sa.Uuid(as_uuid=False)),
        sa.Column('created_by',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('title',sa.String(160),nullable=False),
        sa.Column('current_version',sa.Integer(),nullable=False,server_default='1'),
        sa.Column('revision',sa.Integer(),nullable=False,server_default='1'),sa.Column('archived_at',sa.DateTime(timezone=True)),
        sa.UniqueConstraint('id','brain_id','workspace_id',name='knowledge_sources_scope_unique'),
        sa.UniqueConstraint('brain_id','file_id',name='knowledge_sources_file_unique'),
        sa.UniqueConstraint('brain_id','note_id',name='knowledge_sources_note_unique'),
        sa.ForeignKeyConstraint(['brain_id','workspace_id'],['brains.id','brains.workspace_id'],name='knowledge_sources_brain_fk'),
        sa.ForeignKeyConstraint(['file_id','brain_id','workspace_id'],['brain_files.id','brain_files.brain_id','brain_files.workspace_id'],name='knowledge_sources_file_scope_fk'),
        sa.ForeignKeyConstraint(['note_id','brain_id','workspace_id'],['brain_notes.id','brain_notes.brain_id','brain_notes.workspace_id'],name='knowledge_sources_note_scope_fk'),
        sa.CheckConstraint('(file_id IS NULL) <> (note_id IS NULL)',name='knowledge_sources_one_origin'),
        sa.CheckConstraint('current_version >= 1 AND revision >= 1',name='knowledge_sources_versions_positive'))
    op.create_index('ix_knowledge_sources_brain_id','knowledge_sources',['brain_id'])
    op.create_table('knowledge_versions',*identity(),*scope(),
        sa.Column('source_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('number',sa.Integer(),nullable=False),
        sa.Column('origin_version',sa.Integer(),nullable=False),sa.Column('source_sha256',sa.String(64),nullable=False),
        sa.Column('source_size',sa.Integer(),nullable=False),sa.Column('title',sa.String(160),nullable=False),
        sa.Column('created_by',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),
        sa.UniqueConstraint('id','brain_id','workspace_id',name='knowledge_versions_scope_unique'),
        sa.UniqueConstraint('source_id','number',name='knowledge_versions_number_unique'),
        sa.UniqueConstraint('source_id','source_sha256',name='knowledge_versions_content_unique'),
        sa.ForeignKeyConstraint(['source_id','brain_id','workspace_id'],['knowledge_sources.id','knowledge_sources.brain_id','knowledge_sources.workspace_id'],name='knowledge_versions_source_scope_fk'),
        sa.CheckConstraint('number >= 1 AND origin_version >= 1 AND source_size >= 0 AND source_size <= 1048576 AND length(source_sha256)=64',name='knowledge_versions_valid'))
    op.create_index('ix_knowledge_versions_source_id','knowledge_versions',['source_id'])
    op.create_table('knowledge_ingestion_jobs',*identity(),*scope(),
        sa.Column('version_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('actor_id',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('parser_version',sa.String(32),nullable=False),sa.Column('status',sa.String(16),nullable=False,server_default="queued"),
        sa.Column('attempts',sa.Integer(),nullable=False,server_default='0'),sa.Column('claim_id',sa.Uuid(as_uuid=False)),
        sa.Column('locked_at',sa.DateTime(timezone=True)),sa.Column('error_code',sa.String(64)),
        sa.Column('parsed_text',sa.Text()),sa.Column('parsed_sha256',sa.String(64)),sa.Column('line_count',sa.Integer()),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('version_id','parser_version',name='knowledge_ingestion_parser_unique'),
        sa.ForeignKeyConstraint(['version_id','brain_id','workspace_id'],['knowledge_versions.id','knowledge_versions.brain_id','knowledge_versions.workspace_id'],name='knowledge_ingestion_version_scope_fk'),
        sa.CheckConstraint("status in ('queued','running','completed','failed') AND attempts >= 0 AND attempts <= 3",name='knowledge_ingestion_status_valid'),
        sa.CheckConstraint("(status = 'completed' AND parsed_text IS NOT NULL AND parsed_sha256 IS NOT NULL AND line_count IS NOT NULL AND line_count >= 1 AND length(parsed_sha256)=64 AND octet_length(parsed_text) <= 1048576) OR (status <> 'completed' AND parsed_text IS NULL AND parsed_sha256 IS NULL AND line_count IS NULL)",name='knowledge_ingestion_output_valid'))
    op.create_index('ix_knowledge_ingestion_jobs_version_id','knowledge_ingestion_jobs',['version_id'])
    op.create_index('ix_knowledge_ingestion_jobs_brain_id','knowledge_ingestion_jobs',['brain_id'])
    op.execute("""CREATE FUNCTION knowledge_source_origin_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF (NEW.id,NEW.brain_id,NEW.workspace_id,NEW.file_id,NEW.note_id,NEW.created_by,NEW.created_at)
         IS DISTINCT FROM (OLD.id,OLD.brain_id,OLD.workspace_id,OLD.file_id,OLD.note_id,OLD.created_by,OLD.created_at)
      THEN RAISE EXCEPTION 'knowledge source origin is immutable'; END IF;
      RETURN NEW;
    END $$""")
    op.execute('CREATE TRIGGER knowledge_source_origin_immutable BEFORE UPDATE ON knowledge_sources FOR EACH ROW EXECUTE FUNCTION knowledge_source_origin_immutable()')
    op.execute("""CREATE FUNCTION knowledge_version_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'knowledge version is immutable'; END $$""")
    op.execute('CREATE TRIGGER knowledge_version_immutable BEFORE UPDATE ON knowledge_versions FOR EACH ROW EXECUTE FUNCTION knowledge_version_immutable()')
    op.execute("""CREATE FUNCTION knowledge_completed_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF OLD.status='completed' THEN RAISE EXCEPTION 'completed parse is immutable'; END IF;
      IF (NEW.id,NEW.version_id,NEW.brain_id,NEW.workspace_id,NEW.parser_version,NEW.created_at)
         IS DISTINCT FROM (OLD.id,OLD.version_id,OLD.brain_id,OLD.workspace_id,OLD.parser_version,OLD.created_at)
      THEN RAISE EXCEPTION 'ingestion identity is immutable'; END IF;
      RETURN NEW;
    END $$""")
    op.execute('CREATE TRIGGER knowledge_completed_immutable BEFORE UPDATE ON knowledge_ingestion_jobs FOR EACH ROW EXECUTE FUNCTION knowledge_completed_immutable()')

def downgrade():
    for table in ('knowledge_ingestion_jobs','knowledge_versions','knowledge_sources'):op.drop_table(table)
    for name in ('knowledge_completed_immutable','knowledge_version_immutable','knowledge_source_origin_immutable'):op.execute('DROP FUNCTION '+name+'()')
    for table in ('brain_files','brain_notes'):op.drop_constraint(table+'_origin_scope_unique',table,type_='unique')
