"""tasks and projects

Revision ID: 0018
Revises: 0017
"""
from alembic import op
import sqlalchemy as sa

revision = '0018'
down_revision = '0017'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('projects',
        sa.Column('workspace_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('name', sa.String(160), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('owner_id', sa.Uuid(as_uuid=False), nullable=True),
        sa.Column('created_by', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('due_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status in ('active','on_hold','completed','archived')"),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'), sa.UniqueConstraint('id', 'workspace_id'))
    op.create_index(op.f('ix_projects_workspace_id'), 'projects', ['workspace_id'])

    op.create_table('tasks',
        sa.Column('workspace_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('project_id', sa.Uuid(as_uuid=False), nullable=True),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('kind', sa.String(16), nullable=False),
        sa.Column('priority', sa.String(16), nullable=False),
        sa.Column('assignee_type', sa.String(16), nullable=False),
        sa.Column('assignee_id', sa.String(80), nullable=True),
        sa.Column('progress', sa.Integer(), nullable=False),
        sa.Column('due_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('source', sa.String(16), nullable=False),
        sa.Column('run_id', sa.Uuid(as_uuid=False), nullable=True),
        sa.Column('dependencies', sa.JSON(), nullable=False),
        sa.Column('files', sa.JSON(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('created_by', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status in ('backlog','todo','in_progress','review','done')"),
        sa.CheckConstraint("kind in ('human','ai','agent')"),
        sa.CheckConstraint("priority in ('low','medium','high','critical')"),
        sa.CheckConstraint("assignee_type in ('user','agent','unassigned')"),
        sa.CheckConstraint("source in ('user','pao','automation')"),
        sa.CheckConstraint('progress between 0 and 100'),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
        sa.ForeignKeyConstraint(['project_id', 'workspace_id'], ['projects.id', 'projects.workspace_id']),
        sa.ForeignKeyConstraint(['run_id', 'workspace_id'], ['runs.id', 'runs.workspace_id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'), sa.UniqueConstraint('id', 'workspace_id'))
    op.create_index(op.f('ix_tasks_workspace_id'), 'tasks', ['workspace_id'])
    op.create_index(op.f('ix_tasks_project_id'), 'tasks', ['project_id'])

    op.create_table('task_comments',
        sa.Column('task_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('workspace_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('author_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['task_id', 'workspace_id'], ['tasks.id', 'tasks.workspace_id']),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
        sa.ForeignKeyConstraint(['author_id'], ['users.id']), sa.PrimaryKeyConstraint('id'))
    op.create_index(op.f('ix_task_comments_task_id'), 'task_comments', ['task_id'])
    op.create_index(op.f('ix_task_comments_workspace_id'), 'task_comments', ['workspace_id'])

    op.create_table('task_activity',
        sa.Column('task_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('workspace_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('actor_id', sa.Uuid(as_uuid=False), nullable=True),
        sa.Column('event', sa.String(48), nullable=False),
        sa.Column('data', sa.JSON(), nullable=False),
        sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['task_id', 'workspace_id'], ['tasks.id', 'tasks.workspace_id']),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id']),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id']), sa.PrimaryKeyConstraint('id'))
    op.create_index(op.f('ix_task_activity_task_id'), 'task_activity', ['task_id'])
    op.create_index(op.f('ix_task_activity_workspace_id'), 'task_activity', ['workspace_id'])


def downgrade():
    op.drop_index(op.f('ix_task_activity_workspace_id'), table_name='task_activity')
    op.drop_index(op.f('ix_task_activity_task_id'), table_name='task_activity')
    op.drop_table('task_activity')
    op.drop_index(op.f('ix_task_comments_workspace_id'), table_name='task_comments')
    op.drop_index(op.f('ix_task_comments_task_id'), table_name='task_comments')
    op.drop_table('task_comments')
    op.drop_index(op.f('ix_tasks_project_id'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_workspace_id'), table_name='tasks')
    op.drop_table('tasks')
    op.drop_index(op.f('ix_projects_workspace_id'), table_name='projects')
    op.drop_table('projects')
