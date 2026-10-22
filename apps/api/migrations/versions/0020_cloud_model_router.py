"""cloud model router connections

Revision ID: 0020
Revises: 0019
"""
from alembic import op
import sqlalchemy as sa

revision = '0020'
down_revision = '0019'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('model_provider_connections',
        sa.Column('workspace_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('provider', sa.String(24), nullable=False),
        sa.Column('api_key_ciphertext', sa.Text(), nullable=False),
        sa.Column('model', sa.String(160), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=False),
        sa.Column('model_count', sa.Integer(), nullable=False),
        sa.Column('last_checked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.String(80), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("provider in ('openai','anthropic','gemini','openrouter')"),
        sa.CheckConstraint("status in ('connected','error')"),
        sa.CheckConstraint('model_count >= 0'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('workspace_id', 'provider'))
    op.create_index(op.f('ix_model_provider_connections_workspace_id'),
                    'model_provider_connections', ['workspace_id'])
    op.create_index('one_default_model_provider_per_workspace',
                    'model_provider_connections', ['workspace_id'], unique=True,
                    postgresql_where=sa.text('is_default'))


def downgrade():
    op.drop_index('one_default_model_provider_per_workspace', table_name='model_provider_connections')
    op.drop_index(op.f('ix_model_provider_connections_workspace_id'), table_name='model_provider_connections')
    op.drop_table('model_provider_connections')
