"""Actor-scoped expiring dry-run plans; confirmation is atomic and revision pinned."""
from alembic import op
import sqlalchemy as sa
revision='0028'
down_revision='0027'
branch_labels=None
depends_on=None
def upgrade():
    op.create_table('brain_import_plans',
        sa.Column('id',sa.Uuid(as_uuid=False),primary_key=True),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('brain_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('workspace_id',sa.Uuid(as_uuid=False),nullable=False),
        sa.Column('actor_id',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),sa.Column('brain_revision',sa.Integer(),nullable=False),
        sa.Column('archive',sa.LargeBinary(),nullable=False),sa.Column('sha256',sa.String(64),nullable=False),
        sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),sa.Column('consumed_at',sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(['brain_id','workspace_id'],['brains.id','brains.workspace_id'],name='brain_import_plans_brain_workspace_fk'),
        sa.CheckConstraint('brain_revision >= 1 AND octet_length(archive) <= 12582912',name='brain_import_plan_valid'))
    op.create_index('ix_brain_import_plans_brain_id','brain_import_plans',['brain_id'])
    op.create_index('ix_brain_import_plans_actor_id','brain_import_plans',['actor_id'])
def downgrade():op.drop_table('brain_import_plans')
