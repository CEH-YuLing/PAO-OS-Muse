"""Bounded multi-agent execution while retaining legacy Chief runs."""
from alembic import op
import sqlalchemy as sa

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('runs', sa.Column('execution_plan', sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    op.drop_constraint('agent_runs_run_id_key', 'agent_runs', type_='unique')
    op.add_column('agent_runs', sa.Column('step_index', sa.Integer(), nullable=False, server_default=sa.text('0')))
    op.add_column('agent_runs', sa.Column('task', sa.Text(), nullable=False, server_default=sa.text("''")))
    op.add_column('agent_runs', sa.Column('output', sa.Text(), nullable=False, server_default=sa.text("''")))
    op.add_column('agent_runs', sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True))
    op.create_unique_constraint('agent_runs_run_step_key', 'agent_runs', ['run_id', 'step_index'])


def downgrade():
    if op.get_bind().scalar(sa.text('SELECT EXISTS(SELECT run_id FROM agent_runs GROUP BY run_id HAVING count(*) > 1)')):
        raise RuntimeError('Multi-agent history exists; export/restore a pre-Phase-4 backup instead of discarding steps')
    op.drop_constraint('agent_runs_run_step_key', 'agent_runs', type_='unique')
    for name in ('finished_at', 'output', 'task', 'step_index'):
        op.drop_column('agent_runs', name)
    op.create_unique_constraint('agent_runs_run_id_key', 'agent_runs', ['run_id'])
    op.drop_column('runs', 'execution_plan')
