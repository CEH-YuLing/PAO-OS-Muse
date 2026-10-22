"""Append-only, secret-free SME routing configuration. No execution tables."""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision = '0068'
down_revision = '0067'
branch_labels = depends_on = None


def upgrade():
    op.create_table('business_routing_versions',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('workspace_id', sa.Uuid(), sa.ForeignKey('workspaces.id'), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('actor_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('request_key', sa.String(36), nullable=False),
        sa.Column('content', postgresql.JSONB(), nullable=False),
        sa.Column('content_hash', sa.String(64), nullable=False),
        sa.UniqueConstraint('workspace_id', 'revision'), sa.UniqueConstraint('workspace_id', 'request_key'),
        sa.CheckConstraint('revision>=1 AND length(content_hash)=64', name='business_routing_value'))
    op.execute('''CREATE FUNCTION pao_business_routing_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'business_routing_history_immutable'; END IF;
      PERFORM 1 FROM workspaces WHERE id=NEW.workspace_id FOR UPDATE;
      IF NEW.revision<>(SELECT coalesce(max(revision),0)+1 FROM business_routing_versions WHERE workspace_id=NEW.workspace_id)
      THEN RAISE EXCEPTION 'business_routing_revision_conflict'; END IF;
      RETURN NEW;
    END $$''')
    op.execute('''CREATE TRIGGER business_routing_guard BEFORE INSERT OR UPDATE OR DELETE
        ON business_routing_versions FOR EACH ROW EXECUTE FUNCTION pao_business_routing_guard()''')


def downgrade():
    if op.get_bind().scalar(sa.text('SELECT EXISTS(SELECT 1 FROM business_routing_versions)')):
        raise RuntimeError('Populated business routing history cannot be discarded')
    op.drop_table('business_routing_versions')
    op.execute('DROP FUNCTION pao_business_routing_guard()')
