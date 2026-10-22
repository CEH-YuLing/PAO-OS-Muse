"""Archive terminal skill attempt results without re-executing old code."""
from alembic import op
import sqlalchemy as sa

revision = '0024'
down_revision = '0023'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('task_attempts', sa.Column('skill_artifact', sa.JSON(), nullable=True))


def downgrade():
    op.drop_column('task_attempts', 'skill_artifact')
