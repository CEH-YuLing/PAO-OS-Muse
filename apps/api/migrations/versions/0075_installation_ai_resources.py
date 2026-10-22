"""Installation AI resource registry; never migrates credentials or old run pins."""
from alembic import op
import sqlalchemy as sa
revision='0075'
down_revision='0074'
branch_labels=depends_on=None

def upgrade():
    op.create_table('installation_ai_resources',
        sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('provider',sa.String(32),nullable=False,unique=True),
        sa.Column('owner_id',sa.Uuid(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('source_workspace_id',sa.Uuid(),sa.ForeignKey('workspaces.id'),nullable=False),
        sa.Column('source_id',sa.String(36),nullable=False),sa.Column('source_kind',sa.String(16),nullable=False),
        sa.Column('revision',sa.Integer(),nullable=False),sa.Column('enabled',sa.Boolean(),nullable=False),
        sa.Column('is_default',sa.Boolean(),nullable=False),sa.Column('source_stamp',sa.String(64),nullable=False),
        sa.Column('catalog',sa.JSON(),nullable=False),sa.Column('default_model',sa.String(120),nullable=False),
        sa.CheckConstraint("revision>=1 AND source_kind IN ('api','cli') AND length(source_stamp)=64",name='installation_ai_resource_state'))
    op.create_index('installation_ai_one_default','installation_ai_resources',['is_default'],unique=True,postgresql_where=sa.text('is_default AND enabled'))
    op.create_table('installation_ai_revisions',
        sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('resource_id',sa.Uuid(),sa.ForeignKey('installation_ai_resources.id'),nullable=False),
        sa.Column('actor_id',sa.Uuid(),sa.ForeignKey('users.id'),nullable=False),sa.Column('revision',sa.Integer(),nullable=False),
        sa.Column('request_key',sa.String(36),nullable=False,unique=True),sa.Column('fingerprint',sa.String(64),nullable=False),
        sa.Column('content',sa.JSON(),nullable=False),sa.UniqueConstraint('resource_id','revision'))
    op.execute("CREATE FUNCTION pao_installation_ai_history_guard() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'installation_ai_history_immutable'; END $$")
    op.execute('CREATE TRIGGER installation_ai_history_guard BEFORE UPDATE OR DELETE ON installation_ai_revisions FOR EACH ROW EXECUTE FUNCTION pao_installation_ai_history_guard()')

def downgrade():
    if op.get_bind().scalar(sa.text('SELECT EXISTS(SELECT 1 FROM installation_ai_revisions)')):
        raise RuntimeError('Preserve installation AI history; no destructive downgrade')
    op.drop_table('installation_ai_revisions');op.execute('DROP FUNCTION pao_installation_ai_history_guard()');op.drop_table('installation_ai_resources')
