"""Pin reviewed skill contracts on task attempts.

Revision ID: 0023
Revises: 0022
"""
from alembic import op
import sqlalchemy as sa

revision = '0023'
down_revision = '0022'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('task_attempts', sa.Column('skill_snapshot', sa.JSON(), nullable=True))


def downgrade():
    op.drop_column('task_attempts', 'skill_snapshot')
