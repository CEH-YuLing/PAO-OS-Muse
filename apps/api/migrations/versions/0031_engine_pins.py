"""P3.1 session engine selection and immutable run snapshots (additive)."""
from alembic import op
import sqlalchemy as sa

revision = '0031'
down_revision = '0030'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('sessions', sa.Column('engine_config', sa.JSON(), nullable=True))
    op.add_column('sessions', sa.Column('engine_version', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('runs', sa.Column('engine_snapshot', sa.JSON(), nullable=True))
    op.execute("""CREATE FUNCTION pao_engine_snapshot_immutable() RETURNS trigger AS $$
    BEGIN
      IF OLD.engine_snapshot IS NOT NULL AND
         NEW.engine_snapshot::jsonb IS DISTINCT FROM OLD.engine_snapshot::jsonb THEN
        RAISE EXCEPTION 'engine_snapshot_immutable';
      END IF;
      RETURN NEW;
    END; $$ LANGUAGE plpgsql""")
    op.execute("""CREATE TRIGGER engine_snapshot_immutable BEFORE UPDATE OF engine_snapshot ON runs
      FOR EACH ROW EXECUTE FUNCTION pao_engine_snapshot_immutable()""")


def downgrade():
    op.execute('DROP TRIGGER engine_snapshot_immutable ON runs')
    op.execute('DROP FUNCTION pao_engine_snapshot_immutable()')
    op.drop_column('runs', 'engine_snapshot')
    op.drop_column('sessions', 'engine_version')
    op.drop_column('sessions', 'engine_config')
