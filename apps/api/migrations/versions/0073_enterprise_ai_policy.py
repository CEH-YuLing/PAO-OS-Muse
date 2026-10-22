"""Opt-in enterprise inference inheritance, preserving every personal CLI profile."""
from alembic import op
import sqlalchemy as sa

revision = '0073'
down_revision = '0072'
branch_labels = depends_on = None


def upgrade():
    op.create_table('enterprise_ai_policies',
        sa.Column('id', sa.Uuid(), primary_key=True), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('workspace_id', sa.Uuid(), sa.ForeignKey('workspaces.id'), nullable=False, unique=True),
        sa.Column('revision', sa.Integer(), nullable=False), sa.Column('content', sa.JSON(), nullable=False),
        sa.CheckConstraint('revision>=1'))
    op.create_table('enterprise_ai_revisions',
        sa.Column('id', sa.Uuid(), primary_key=True), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('workspace_id', sa.Uuid(), sa.ForeignKey('workspaces.id'), nullable=False),
        sa.Column('actor_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False), sa.Column('content', sa.JSON(), nullable=False),
        sa.Column('request_key', sa.String(36), nullable=False), sa.Column('fingerprint', sa.String(64), nullable=False),
        sa.UniqueConstraint('workspace_id', 'revision'), sa.UniqueConstraint('workspace_id', 'actor_id', 'request_key'),
        sa.CheckConstraint('revision>=1 AND length(fingerprint)=64'))
    op.execute("""CREATE FUNCTION pao_enterprise_ai_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN RAISE EXCEPTION 'enterprise_ai_history_immutable'; END $$""")
    op.execute('CREATE TRIGGER enterprise_ai_history_guard BEFORE UPDATE OR DELETE ON enterprise_ai_revisions FOR EACH ROW EXECUTE FUNCTION pao_enterprise_ai_history_guard()')


def downgrade():
    if op.get_bind().scalar(sa.text('SELECT EXISTS(SELECT 1 FROM enterprise_ai_revisions)')):
        raise RuntimeError('Preserve populated enterprise AI consent history')
    op.drop_table('enterprise_ai_revisions')
    op.execute('DROP FUNCTION pao_enterprise_ai_history_guard()')
    op.drop_table('enterprise_ai_policies')
