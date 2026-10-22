"""Standalone embeddings share SME model caps; no synthetic Run/LLM attempt."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision='0057'
down_revision='0056'
branch_labels=depends_on=None

BASE="policy_version >= 0 AND status IN ('active','released','expired') AND "
TAIL=("expires_at>created_at AND expires_at<=created_at+interval '5 minutes' AND "
      "((status='active' AND released_at IS NULL) OR (status<>'active' AND released_at IS NOT NULL))")
OLD=BASE+("((kind='llm' AND attempt_id IS NOT NULL AND reserved_tokens=0) OR "
          "(kind='management_probe' AND attempt_id IS NULL AND reserved_tokens=96)) AND ")+TAIL
NEW=BASE+("((kind='llm' AND attempt_id IS NOT NULL AND reserved_tokens=0 AND embedding_pin IS NULL) OR "
          "(kind='management_probe' AND attempt_id IS NULL AND reserved_tokens=96 AND embedding_pin IS NULL) OR "
          "(kind='embedding' AND attempt_id IS NULL AND reserved_tokens BETWEEN 1 AND 8192 AND embedding_pin IS NOT NULL)) AND ")+TAIL

def guard(embedding=False):
    new=',NEW.embedding_pin' if embedding else ''
    old=',OLD.embedding_pin' if embedding else ''
    op.execute(f"""CREATE OR REPLACE FUNCTION pao_tenant_model_lease_guard() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF TG_OP='DELETE' THEN RAISE EXCEPTION 'tenant_model_lease_history_immutable'; END IF;
        IF (NEW.id,NEW.created_at,NEW.workspace_id,NEW.actor_id,NEW.kind,NEW.request_key,
            NEW.attempt_id,NEW.policy_version,NEW.reserved_tokens,NEW.expires_at{new}) IS DISTINCT FROM
           (OLD.id,OLD.created_at,OLD.workspace_id,OLD.actor_id,OLD.kind,OLD.request_key,
            OLD.attempt_id,OLD.policy_version,OLD.reserved_tokens,OLD.expires_at{old})
           OR OLD.status<>'active' OR NEW.status NOT IN ('released','expired')
        THEN RAISE EXCEPTION 'tenant_model_lease_history_immutable'; END IF;
        RETURN NEW;
      END $$""")

def upgrade():
    op.add_column('tenant_model_leases',sa.Column('embedding_pin',JSONB(),nullable=True))
    op.drop_constraint('tenant_model_lease_state','tenant_model_leases',type_='check')
    op.create_check_constraint('tenant_model_lease_state','tenant_model_leases',NEW)
    guard(True)

def downgrade():
    if op.get_bind().scalar(sa.text("SELECT count(*) FROM tenant_model_leases WHERE kind='embedding' OR embedding_pin IS NOT NULL")):
        raise RuntimeError('Downgrade refused: embedding history must be preserved')
    guard(False)
    op.drop_constraint('tenant_model_lease_state','tenant_model_leases',type_='check')
    op.create_check_constraint('tenant_model_lease_state','tenant_model_leases',OLD)
    op.drop_column('tenant_model_leases','embedding_pin')
