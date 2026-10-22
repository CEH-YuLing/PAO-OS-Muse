"""Opt-in Codex self-use defaults. No cache, grants or old run repinning."""
from alembic import op
import sqlalchemy as sa
revision='0074'
down_revision='0073'
branch_labels=depends_on=None
def upgrade():
    common=lambda:[sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('workspace_id',sa.Uuid(),sa.ForeignKey('workspaces.id'),nullable=False),
        sa.Column('actor_id',sa.Uuid(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('revision',sa.Integer(),nullable=False),sa.Column('content',sa.JSON(),nullable=False)]
    op.create_table('personal_cli_policies',*common(),sa.UniqueConstraint('workspace_id','actor_id'),sa.CheckConstraint('revision>=1'))
    op.create_table('personal_cli_revisions',*common(),sa.Column('request_key',sa.String(36),nullable=False),sa.Column('fingerprint',sa.String(64),nullable=False),
        sa.UniqueConstraint('workspace_id','actor_id','revision'),sa.UniqueConstraint('workspace_id','actor_id','request_key'),sa.CheckConstraint('revision>=1 AND length(fingerprint)=64'))
    op.execute("CREATE FUNCTION pao_personal_cli_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'personal_cli_history_immutable'; END $$")
    op.execute('CREATE TRIGGER personal_cli_history_guard BEFORE UPDATE OR DELETE ON personal_cli_revisions FOR EACH ROW EXECUTE FUNCTION pao_personal_cli_history_guard()')
def downgrade():
    if op.get_bind().scalar(sa.text('SELECT EXISTS(SELECT 1 FROM personal_cli_revisions)')):
        raise RuntimeError('Preserve populated personal CLI consent history')
    op.drop_table('personal_cli_revisions');op.execute('DROP FUNCTION pao_personal_cli_history_guard()');op.drop_table('personal_cli_policies')
