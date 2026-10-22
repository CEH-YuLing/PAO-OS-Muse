"""Pin queued Knowledge embeddings; explicit rebuild intent, no legacy backfill."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
revision='0058'
down_revision='0057'
branch_labels=depends_on=None

def upgrade():
    op.add_column('knowledge_index_jobs',sa.Column('embedding_engine',JSONB(),nullable=True))
    op.add_column('knowledge_index_jobs',sa.Column('embedding_generation',sa.Integer(),server_default=sa.text('0'),nullable=False))
    op.add_column('knowledge_chunks',sa.Column('embedding_binding',sa.String(64),nullable=True))
    op.create_check_constraint('knowledge_embedding_binding_valid','knowledge_chunks',"embedding_binding IS NULL OR embedding_binding ~ '^[0-9a-f]{64}$'")
    op.create_check_constraint('knowledge_index_embedding_pin_valid','knowledge_index_jobs',
        "embedding_generation>=0 AND (embedding_engine IS NULL OR (jsonb_typeof(embedding_engine)='object' AND embedding_engine->>'version'='1' AND embedding_engine->>'model'=embedding_model AND jsonb_typeof(embedding_engine->'url')='string'))")
    op.execute("""CREATE FUNCTION pao_knowledge_embedding_pin_guard() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF TG_OP='DELETE' THEN RAISE EXCEPTION 'knowledge_embedding_history_immutable'; END IF;
        IF (NEW.id,NEW.created_at,NEW.workspace_id,NEW.brain_id,NEW.version_id,NEW.chunker_version,NEW.embedding_model)
          IS DISTINCT FROM (OLD.id,OLD.created_at,OLD.workspace_id,OLD.brain_id,OLD.version_id,OLD.chunker_version,OLD.embedding_model)
          THEN RAISE EXCEPTION 'knowledge_embedding_identity_immutable'; END IF;
        IF NEW.embedding_generation=OLD.embedding_generation THEN
          IF (NEW.embedding_engine,NEW.actor_id) IS DISTINCT FROM (OLD.embedding_engine,OLD.actor_id)
            THEN RAISE EXCEPTION 'knowledge_embedding_pin_immutable'; END IF;
        ELSIF NEW.embedding_generation<>OLD.embedding_generation+1 OR OLD.status='running'
          OR NEW.status<>'queued' OR NEW.attempts<>0 OR NEW.claim_id IS NOT NULL OR NEW.locked_at IS NOT NULL
          THEN RAISE EXCEPTION 'knowledge_embedding_rebuild_required';
        END IF;
        RETURN NEW;
      END $$""")
    op.execute('CREATE TRIGGER knowledge_embedding_pin_immutable BEFORE UPDATE OR DELETE ON knowledge_index_jobs '
               'FOR EACH ROW EXECUTE FUNCTION pao_knowledge_embedding_pin_guard()')

def downgrade():
    if op.get_bind().scalar(sa.text('SELECT count(*) FROM knowledge_index_jobs WHERE embedding_engine IS NOT NULL OR embedding_generation<>0')) or op.get_bind().scalar(
        sa.text('SELECT count(*) FROM knowledge_chunks WHERE embedding_binding IS NOT NULL')):
        raise RuntimeError('Downgrade refused: Knowledge embedding pins must be preserved')
    op.execute('DROP TRIGGER knowledge_embedding_pin_immutable ON knowledge_index_jobs')
    op.execute('DROP FUNCTION pao_knowledge_embedding_pin_guard()')
    op.drop_constraint('knowledge_index_embedding_pin_valid','knowledge_index_jobs',type_='check')
    op.drop_constraint('knowledge_embedding_binding_valid','knowledge_chunks',type_='check')
    op.drop_column('knowledge_chunks','embedding_binding')
    op.drop_column('knowledge_index_jobs','embedding_generation')
    op.drop_column('knowledge_index_jobs','embedding_engine')
