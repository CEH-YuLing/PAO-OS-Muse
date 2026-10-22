"""archive conversations

Revision ID: 0019
Revises: 0018
"""
from alembic import op
import sqlalchemy as sa

revision = '0019'
down_revision = '0018'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('sessions', sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_sessions_archived_at'), 'sessions', ['archived_at'])


def downgrade():
    op.drop_index(op.f('ix_sessions_archived_at'), table_name='sessions')
    op.drop_column('sessions', 'archived_at')
