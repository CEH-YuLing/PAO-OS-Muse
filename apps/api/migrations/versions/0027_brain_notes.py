"""Versioned notes; metadata trash does not destroy immutable content history."""
from alembic import op
import sqlalchemy as sa
revision='0027'
down_revision='0026'
branch_labels=None
depends_on=None
def upgrade():
    op.create_table('brain_notes',
        sa.Column('id',sa.Uuid(as_uuid=False),primary_key=True),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('brain_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('workspace_id',sa.Uuid(as_uuid=False),nullable=False),
        sa.Column('title',sa.String(120),nullable=False),sa.Column('revision',sa.Integer(),nullable=False,server_default=sa.text('1')),
        sa.Column('content_version',sa.Integer(),nullable=False,server_default=sa.text('1')),sa.Column('trashed_at',sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(['brain_id','workspace_id'],['brains.id','brains.workspace_id'],name='brain_notes_brain_workspace_fk'),
        sa.CheckConstraint('revision >= 1 AND content_version >= 1',name='brain_notes_versions_positive'))
    op.create_index('ix_brain_notes_brain_id','brain_notes',['brain_id'])
    op.create_table('brain_note_versions',sa.Column('note_id',sa.Uuid(as_uuid=False),sa.ForeignKey('brain_notes.id'),primary_key=True),
        sa.Column('version',sa.Integer(),primary_key=True),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('created_by',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),sa.Column('content',sa.Text(),nullable=False),
        sa.Column('sha256',sa.String(64),nullable=False),sa.Column('size',sa.Integer(),nullable=False),
        sa.CheckConstraint('version >= 1 AND size >= 0 AND size <= 262144 AND octet_length(content) = size',name='brain_note_version_valid'))
    op.execute("""CREATE FUNCTION brain_note_version_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN IF NEW IS DISTINCT FROM OLD THEN RAISE EXCEPTION 'brain_note_version_immutable'; END IF; RETURN NEW; END $$""")
    op.execute('CREATE TRIGGER brain_note_version_immutable BEFORE UPDATE ON brain_note_versions FOR EACH ROW EXECUTE FUNCTION brain_note_version_immutable()')
def downgrade():
    op.drop_table('brain_note_versions');op.drop_table('brain_notes')
    op.execute('DROP FUNCTION brain_note_version_immutable()')
