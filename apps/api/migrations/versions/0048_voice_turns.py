"""Scoped voice-turn ledger; no raw audio persistence or new Run executor."""
from alembic import op
import sqlalchemy as sa
revision='0048'
down_revision='0047'
branch_labels=depends_on=None

def upgrade():
    op.create_table('voice_turns',sa.Column('id',sa.Uuid(as_uuid=False),primary_key=True),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),sa.ForeignKey('workspaces.id'),nullable=False),sa.Column('session_id',sa.Uuid(as_uuid=False),nullable=False),
        sa.Column('user_id',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),sa.Column('request_key',sa.Uuid(as_uuid=False),nullable=False),
        sa.Column('status',sa.String(16),nullable=False),sa.Column('transcript',sa.Text()),sa.Column('audio_hash',sa.String(64)),sa.Column('language',sa.String(16)),
        sa.Column('duration_ms',sa.Integer()),sa.Column('run_id',sa.Uuid(as_uuid=False),sa.ForeignKey('runs.id'),unique=True),sa.Column('error_code',sa.String(64)),sa.Column('version',sa.Integer(),nullable=False),
        sa.UniqueConstraint('user_id','request_key'),sa.ForeignKeyConstraint(['session_id','workspace_id'],['sessions.id','sessions.workspace_id']),
        sa.CheckConstraint("status IN ('created','transcribing','ready','submitted','cancelled','failed') AND version>=1"))
    op.execute("""CREATE FUNCTION voice_turn_identity() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN IF (NEW.id,NEW.workspace_id,NEW.session_id,NEW.user_id,NEW.request_key,NEW.audio_hash)
      IS DISTINCT FROM (OLD.id,OLD.workspace_id,OLD.session_id,OLD.user_id,OLD.request_key,OLD.audio_hash)
      AND NOT (NEW.id=OLD.id AND NEW.workspace_id=OLD.workspace_id AND NEW.session_id=OLD.session_id AND NEW.user_id=OLD.user_id AND NEW.request_key=OLD.request_key AND OLD.audio_hash IS NULL)
    THEN RAISE EXCEPTION 'voice identity immutable'; END IF; RETURN NEW; END $$""")
    op.execute('CREATE TRIGGER voice_turn_identity BEFORE UPDATE ON voice_turns FOR EACH ROW EXECUTE FUNCTION voice_turn_identity()')

def downgrade():
    op.drop_table('voice_turns');op.execute('DROP FUNCTION voice_turn_identity()')
