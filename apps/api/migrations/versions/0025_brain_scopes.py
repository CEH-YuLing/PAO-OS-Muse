"""Private Brain metadata; legacy facts and existing run history stay unchanged."""
from alembic import op
import sqlalchemy as sa

revision = '0025'
down_revision = '0024'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('brains',
        sa.Column('id', sa.Uuid(as_uuid=False), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('workspace_id', sa.Uuid(as_uuid=False), sa.ForeignKey('workspaces.id'), nullable=False),
        sa.Column('owner_id', sa.Uuid(as_uuid=False), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('brand_id', sa.Uuid(as_uuid=False)),
        sa.Column('name', sa.String(120), nullable=False),
        sa.Column('legacy_default', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('revision', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.Column('archived_at', sa.DateTime(timezone=True)),
        sa.UniqueConstraint('id', 'workspace_id'),
        sa.ForeignKeyConstraint(['brand_id','workspace_id'], ['brands.id','brands.workspace_id'], name='brains_brand_workspace_fk'),
        sa.CheckConstraint('revision >= 1', name='brains_revision_positive'))
    op.create_index('ix_brains_workspace_id','brains',['workspace_id'])
    op.create_index('ix_brains_owner_id','brains',['owner_id'])
    op.create_index('brains_legacy_scope_unique','brains',['workspace_id','owner_id','brand_id'], unique=True,
        postgresql_nulls_not_distinct=True, postgresql_where=sa.text('legacy_default'))
    op.create_table('brain_members',
        sa.Column('brain_id',sa.Uuid(as_uuid=False),primary_key=True),
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),nullable=False),
        sa.Column('user_id',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),primary_key=True),
        sa.Column('role',sa.String(16),nullable=False),
        sa.ForeignKeyConstraint(['brain_id','workspace_id'],['brains.id','brains.workspace_id'],name='brain_members_brain_workspace_fk'),
        sa.ForeignKeyConstraint(['workspace_id','user_id'],['workspace_members.workspace_id','workspace_members.user_id'],name='brain_members_workspace_member_fk'),
        sa.CheckConstraint("role in ('reader','editor')",name='brain_members_role_valid'))
    op.add_column('sessions',sa.Column('brain_id',sa.Uuid(as_uuid=False)))
    op.add_column('sessions',sa.Column('brain_version',sa.Integer(),server_default=sa.text('1'),nullable=False))
    op.create_foreign_key('sessions_brain_workspace_fk','sessions','brains',['brain_id','workspace_id'],['id','workspace_id'])
    op.add_column('runs',sa.Column('brain_id',sa.Uuid(as_uuid=False)))
    op.add_column('runs',sa.Column('brain_revision',sa.Integer()))
    op.add_column('runs',sa.Column('brain_context',sa.JSON()))
    op.create_foreign_key('runs_brain_workspace_fk','runs','brains',['brain_id','workspace_id'],['id','workspace_id'])
    op.execute("""INSERT INTO brains(id,created_at,workspace_id,owner_id,brand_id,name,legacy_default)
        SELECT gen_random_uuid(), CURRENT_TIMESTAMP, workspace_id, user_id, brand_id,
               'Legacy private memory', true FROM (
          SELECT workspace_id,user_id,NULL::uuid AS brand_id FROM workspace_members
          UNION SELECT workspace_id,user_id,brand_id FROM memories
          UNION SELECT workspace_id,user_id,brand_id FROM sessions
        ) scopes""")
    op.execute("""UPDATE sessions s SET brain_id=b.id FROM brains b
        WHERE b.legacy_default AND s.workspace_id=b.workspace_id AND s.user_id=b.owner_id
          AND s.brand_id IS NOT DISTINCT FROM b.brand_id""")


def downgrade():
    op.drop_constraint('runs_brain_workspace_fk','runs',type_='foreignkey')
    for name in ('brain_context','brain_revision','brain_id'):
        op.drop_column('runs',name)
    op.drop_constraint('sessions_brain_workspace_fk','sessions',type_='foreignkey')
    op.drop_column('sessions','brain_version')
    op.drop_column('sessions','brain_id')
    op.drop_table('brain_members')
    op.drop_table('brains')
