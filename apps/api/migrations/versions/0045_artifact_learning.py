"""Human-reviewed, data-only extractive artifact learning with immutable provenance."""
from alembic import op
import sqlalchemy as sa
revision='0045'
down_revision='0044'
branch_labels=depends_on=None
def identity():return [sa.Column('id',sa.Uuid(as_uuid=False),primary_key=True),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False)]
def upgrade():
    op.create_table('artifact_learning_proposals',*identity(),
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('brain_id',sa.Uuid(as_uuid=False),nullable=False),
        sa.Column('actor_id',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),sa.Column('source_id',sa.Uuid(as_uuid=False),nullable=False),
        sa.Column('source_hash',sa.String(64),nullable=False),sa.Column('candidate',sa.Text(),nullable=False),
        sa.Column('fingerprint',sa.String(64),nullable=False),sa.Column('derivation',sa.String(32),nullable=False),sa.Column('segments',sa.JSON(),nullable=False),
        sa.Column('status',sa.String(16),nullable=False),sa.Column('note_id',sa.Uuid(as_uuid=False),sa.ForeignKey('brain_notes.id')),
        sa.ForeignKeyConstraint(['brain_id','workspace_id'],['brains.id','brains.workspace_id']),
        sa.ForeignKeyConstraint(['source_id','brain_id','workspace_id'],['brain_files.id','brain_files.brain_id','brain_files.workspace_id']),
        sa.UniqueConstraint('brain_id','actor_id','fingerprint'),
        sa.CheckConstraint("status IN ('pending','promoted','reverted','rejected') AND derivation IN ('quote','extractive_summary_v1') AND length(source_hash)=64 AND length(fingerprint)=64"))
    op.create_table('artifact_learning_audits',*identity(),sa.Column('proposal_id',sa.Uuid(as_uuid=False),sa.ForeignKey('artifact_learning_proposals.id'),nullable=False),
        sa.Column('actor_id',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),sa.Column('action',sa.String(16),nullable=False),sa.Column('data',sa.JSON(),nullable=False))
    op.execute("""CREATE FUNCTION artifact_learning_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP='DELETE' OR TG_TABLE_NAME='artifact_learning_audits' THEN RAISE EXCEPTION 'learning evidence immutable'; END IF;
      IF ROW(NEW.id,NEW.created_at,NEW.workspace_id,NEW.brain_id,NEW.actor_id,NEW.source_id,NEW.source_hash,NEW.candidate,NEW.fingerprint,NEW.derivation,NEW.segments::text)
        IS DISTINCT FROM ROW(OLD.id,OLD.created_at,OLD.workspace_id,OLD.brain_id,OLD.actor_id,OLD.source_id,OLD.source_hash,OLD.candidate,OLD.fingerprint,OLD.derivation,OLD.segments::text)
      THEN RAISE EXCEPTION 'learning proposal immutable'; END IF; RETURN NEW;
    END $$""")
    for table in ('artifact_learning_proposals','artifact_learning_audits'):
        op.execute(f'CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION artifact_learning_immutable()')
def downgrade():
    op.drop_table('artifact_learning_audits');op.drop_table('artifact_learning_proposals');op.execute('DROP FUNCTION artifact_learning_immutable()')
