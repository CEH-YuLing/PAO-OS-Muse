"""goals and evidence-based task execution

Revision ID: 0022
Revises: 0021
"""
from alembic import op
import sqlalchemy as sa

revision = '0022'
down_revision = '0021'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'goals',
        sa.Column('workspace_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('project_id', sa.Uuid(as_uuid=False), nullable=True),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('success_criteria', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('owner_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('created_by', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('due_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status in ('draft','active','completed','failed','cancelled')"),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
        sa.ForeignKeyConstraint(['project_id', 'workspace_id'], ['projects.id', 'projects.workspace_id']),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'), sa.UniqueConstraint('id', 'workspace_id'),
    )
    op.create_index(op.f('ix_goals_workspace_id'), 'goals', ['workspace_id'])
    op.create_index(op.f('ix_goals_project_id'), 'goals', ['project_id'])

    op.drop_constraint('tasks_status_check', 'tasks', type_='check')
    op.execute("UPDATE tasks SET status=CASE status WHEN 'backlog' THEN 'draft' WHEN 'todo' THEN 'ready' WHEN 'in_progress' THEN 'running' WHEN 'review' THEN 'waiting_approval' WHEN 'done' THEN 'completed' ELSE status END")
    op.create_check_constraint('tasks_status_check', 'tasks',
        "status in ('draft','ready','running','waiting_approval','blocked','completed','failed','cancelled')")
    op.add_column('tasks', sa.Column('goal_id', sa.Uuid(as_uuid=False), nullable=True))
    op.add_column('tasks', sa.Column('parent_task_id', sa.Uuid(as_uuid=False), nullable=True))
    op.add_column('tasks', sa.Column('skill_id', sa.String(100), nullable=True))
    op.add_column('tasks', sa.Column('success_criteria', sa.JSON(), nullable=False, server_default='[]'))
    op.add_column('tasks', sa.Column('input_references', sa.JSON(), nullable=False, server_default='[]'))
    op.add_column('tasks', sa.Column('budget', sa.JSON(), nullable=False, server_default='{}'))
    op.add_column('tasks', sa.Column('evidence', sa.JSON(), nullable=False, server_default='[]'))
    op.add_column('tasks', sa.Column('result_reference', sa.JSON(), nullable=False, server_default='{}'))
    op.add_column('tasks', sa.Column('required', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_foreign_key('tasks_goal_workspace_fkey', 'tasks', 'goals',
                          ['goal_id', 'workspace_id'], ['id', 'workspace_id'])
    op.create_foreign_key('tasks_parent_workspace_fkey', 'tasks', 'tasks',
                          ['parent_task_id', 'workspace_id'], ['id', 'workspace_id'])
    op.create_index(op.f('ix_tasks_goal_id'), 'tasks', ['goal_id'])
    op.create_index(op.f('ix_tasks_parent_task_id'), 'tasks', ['parent_task_id'])

    op.create_table(
        'task_dependencies',
        sa.Column('workspace_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('task_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('depends_on_task_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('created_by', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('task_id <> depends_on_task_id'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
        sa.ForeignKeyConstraint(['task_id', 'workspace_id'], ['tasks.id', 'tasks.workspace_id']),
        sa.ForeignKeyConstraint(['depends_on_task_id', 'workspace_id'], ['tasks.id', 'tasks.workspace_id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'), sa.UniqueConstraint('task_id', 'depends_on_task_id'),
    )
    op.create_index(op.f('ix_task_dependencies_workspace_id'), 'task_dependencies', ['workspace_id'])
    op.create_index(op.f('ix_task_dependencies_task_id'), 'task_dependencies', ['task_id'])
    op.create_index(op.f('ix_task_dependencies_depends_on_task_id'), 'task_dependencies', ['depends_on_task_id'])
    op.execute("""
        INSERT INTO task_dependencies
          (id, created_at, workspace_id, task_id, depends_on_task_id, created_by)
        SELECT md5(t.id::text || ':' || dep.value)::uuid, t.created_at,
               t.workspace_id, t.id, dep.value::uuid, t.created_by
        FROM tasks t CROSS JOIN LATERAL json_array_elements_text(t.dependencies) dep(value)
        ON CONFLICT DO NOTHING
    """)

    op.create_table(
        'task_attempts',
        sa.Column('workspace_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('task_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('run_id', sa.Uuid(as_uuid=False), nullable=True),
        sa.Column('request_key', sa.String(64), nullable=False),
        sa.Column('input_fingerprint', sa.String(64), nullable=False),
        sa.Column('attempt_no', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(16), nullable=False),
        sa.Column('input', sa.JSON(), nullable=False),
        sa.Column('result', sa.JSON(), nullable=False),
        sa.Column('evidence', sa.JSON(), nullable=False),
        sa.Column('error_code', sa.String(64), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status in ('running','completed','failed','cancelled')"),
        sa.CheckConstraint('attempt_no > 0'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
        sa.ForeignKeyConstraint(['task_id', 'workspace_id'], ['tasks.id', 'tasks.workspace_id']),
        sa.ForeignKeyConstraint(['run_id', 'workspace_id'], ['runs.id', 'runs.workspace_id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('task_id', 'attempt_no'),
        sa.UniqueConstraint('task_id', 'request_key'),
    )
    op.create_index(op.f('ix_task_attempts_workspace_id'), 'task_attempts', ['workspace_id'])
    op.create_index(op.f('ix_task_attempts_task_id'), 'task_attempts', ['task_id'])


def downgrade():
    op.drop_index(op.f('ix_task_attempts_task_id'), table_name='task_attempts')
    op.drop_index(op.f('ix_task_attempts_workspace_id'), table_name='task_attempts')
    op.drop_table('task_attempts')
    op.drop_index(op.f('ix_task_dependencies_depends_on_task_id'), table_name='task_dependencies')
    op.drop_index(op.f('ix_task_dependencies_task_id'), table_name='task_dependencies')
    op.drop_index(op.f('ix_task_dependencies_workspace_id'), table_name='task_dependencies')
    op.drop_table('task_dependencies')
    op.drop_index(op.f('ix_tasks_parent_task_id'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_goal_id'), table_name='tasks')
    op.drop_constraint('tasks_parent_workspace_fkey', 'tasks', type_='foreignkey')
    op.drop_constraint('tasks_goal_workspace_fkey', 'tasks', type_='foreignkey')
    for column in ('required','result_reference','evidence','budget','input_references','success_criteria','skill_id','parent_task_id','goal_id'):
        op.drop_column('tasks', column)
    op.drop_constraint('tasks_status_check', 'tasks', type_='check')
    op.execute("UPDATE tasks SET status=CASE status WHEN 'draft' THEN 'backlog' WHEN 'ready' THEN 'todo' WHEN 'running' THEN 'in_progress' WHEN 'waiting_approval' THEN 'review' WHEN 'completed' THEN 'done' WHEN 'blocked' THEN 'todo' WHEN 'failed' THEN 'todo' WHEN 'cancelled' THEN 'backlog' ELSE status END")
    op.create_check_constraint('tasks_status_check', 'tasks',
        "status in ('backlog','todo','in_progress','review','done')")
    op.drop_index(op.f('ix_goals_project_id'), table_name='goals')
    op.drop_index(op.f('ix_goals_workspace_id'), table_name='goals')
    op.drop_table('goals')
