"""Invite-only accounts, revocable sessions and non-destructive data requests."""
from alembic import op
import sqlalchemy as sa

revision = '0071'
down_revision = '0070'
branch_labels = depends_on = None


def identity():
    return [sa.Column('id', sa.Uuid(), primary_key=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False)]


def upgrade():
    op.add_column('users', sa.Column('auth_version', sa.Integer(), server_default='0', nullable=False))
    op.add_column('workspaces', sa.Column('lifecycle_version', sa.Integer(), server_default='1', nullable=False))
    op.create_table('workspace_invitations', *identity(),
        sa.Column('workspace_id', sa.Uuid(), sa.ForeignKey('workspaces.id'), nullable=False),
        sa.Column('creator_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('email', sa.String(254), nullable=False), sa.Column('role', sa.String(20), nullable=False),
        sa.Column('code_hash', sa.String(64), unique=True, nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('accepted_by', sa.Uuid(), sa.ForeignKey('users.id')),
        sa.CheckConstraint("role IN ('admin','operator','analyst','viewer') AND status IN ('pending','accepted','revoked')", name='workspace_invitation_state'))
    op.create_index('ix_workspace_invitations_workspace_id', 'workspace_invitations', ['workspace_id'])
    op.create_table('login_sessions', *identity(),
        sa.Column('user_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('token_hash', sa.String(64), unique=True, nullable=False),
        sa.Column('auth_version', sa.Integer(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked', sa.Boolean(), nullable=False))
    op.create_index('ix_login_sessions_user_id', 'login_sessions', ['user_id'])
    op.create_table('lifecycle_audits', *identity(),
        sa.Column('workspace_id', sa.Uuid(), sa.ForeignKey('workspaces.id')),
        sa.Column('actor_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('action', sa.String(48), nullable=False), sa.Column('subject_id', sa.Uuid(), nullable=False),
        sa.Column('details', sa.JSON(), nullable=False))
    op.create_index('ix_lifecycle_audits_workspace_id', 'lifecycle_audits', ['workspace_id'])
    op.execute("""CREATE FUNCTION pao_lifecycle_audit_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'lifecycle_audit_immutable'; END $$""")
    op.execute('CREATE TRIGGER lifecycle_audit_immutable BEFORE UPDATE OR DELETE ON lifecycle_audits FOR EACH ROW EXECUTE FUNCTION pao_lifecycle_audit_immutable()')
    op.create_table('data_lifecycle_requests', *identity(),
        sa.Column('workspace_id', sa.Uuid(), sa.ForeignKey('workspaces.id'), nullable=False),
        sa.Column('actor_id', sa.Uuid(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('kind', sa.String(16), nullable=False), sa.Column('status', sa.String(16), nullable=False),
        sa.Column('scope_hash', sa.String(64), nullable=False), sa.Column('summary', sa.JSON(), nullable=False),
        sa.Column('payload', sa.LargeBinary()), sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("kind IN ('export','deletion') AND status IN ('ready','preview','requested','confirmed')", name='data_lifecycle_request_state'))
    op.create_index('ix_data_lifecycle_requests_workspace_id', 'data_lifecycle_requests', ['workspace_id'])


def downgrade():
    connection = op.get_bind()
    if any(connection.scalar(sa.text(f'SELECT EXISTS(SELECT 1 FROM {table})')) for table in
           ('workspace_invitations','login_sessions','lifecycle_audits','data_lifecycle_requests')):
        raise RuntimeError('Populated lifecycle history cannot be discarded')
    op.drop_table('data_lifecycle_requests')
    op.drop_table('lifecycle_audits')
    op.execute('DROP FUNCTION pao_lifecycle_audit_immutable()')
    op.drop_table('login_sessions')
    op.drop_table('workspace_invitations')
    op.drop_column('workspaces', 'lifecycle_version')
    op.drop_column('users', 'auth_version')
