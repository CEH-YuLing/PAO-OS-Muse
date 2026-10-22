"""Bounded immutable text/Markdown source bytes with recoverable trash."""
from alembic import op
import sqlalchemy as sa
revision='0026'
down_revision='0025'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('brain_files',
        sa.Column('id',sa.Uuid(as_uuid=False),primary_key=True),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('brain_id',sa.Uuid(as_uuid=False),nullable=False),
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),nullable=False),
        sa.Column('created_by',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('name',sa.String(160),nullable=False),sa.Column('mime',sa.String(32),nullable=False),
        sa.Column('size',sa.Integer(),nullable=False),sa.Column('sha256',sa.String(64),nullable=False),
        sa.Column('content',sa.LargeBinary(),nullable=False),
        sa.Column('revision',sa.Integer(),nullable=False,server_default=sa.text('1')),
        sa.Column('trashed_at',sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(['brain_id','workspace_id'],['brains.id','brains.workspace_id'],name='brain_files_brain_workspace_fk'),
        sa.CheckConstraint("mime in ('text/plain','text/markdown')",name='brain_files_mime_valid'),
        sa.CheckConstraint('size >= 0 AND size <= 1048576 AND octet_length(content) = size',name='brain_files_size_valid'),
        sa.CheckConstraint('revision >= 1',name='brain_files_revision_positive'))
    op.create_index('ix_brain_files_brain_id','brain_files',['brain_id'])
    op.execute("""CREATE FUNCTION brain_file_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN IF NEW.content IS DISTINCT FROM OLD.content OR NEW.sha256 IS DISTINCT FROM OLD.sha256
        OR NEW.size IS DISTINCT FROM OLD.size OR NEW.mime IS DISTINCT FROM OLD.mime
        OR NEW.name IS DISTINCT FROM OLD.name OR NEW.brain_id IS DISTINCT FROM OLD.brain_id
        OR NEW.workspace_id IS DISTINCT FROM OLD.workspace_id THEN
        RAISE EXCEPTION 'brain_source_immutable'; END IF; RETURN NEW; END $$""")
    op.execute('CREATE TRIGGER brain_file_immutable BEFORE UPDATE ON brain_files FOR EACH ROW EXECUTE FUNCTION brain_file_immutable()')

def downgrade():
    op.drop_table('brain_files')
    op.execute('DROP FUNCTION brain_file_immutable()')
