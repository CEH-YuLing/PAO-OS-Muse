"""advanced_automation

Revision ID: 0016
Revises: 0015
"""
from alembic import op
import sqlalchemy as sa
revision='0016';down_revision='0015';branch_labels=None;depends_on=None
def upgrade():
    op.create_table('automation_workflows',
      sa.Column('workspace_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('user_id',sa.Uuid(as_uuid=False),nullable=False),
      sa.Column('request_key',sa.String(64),nullable=False),sa.Column('temporal_workflow_id',sa.String(120),nullable=False),sa.Column('temporal_run_id',sa.String(120),nullable=True),
      sa.Column('kind',sa.String(24),nullable=False),sa.Column('status',sa.String(24),nullable=False),sa.Column('approval_status',sa.String(16),nullable=False),
      sa.Column('payload',sa.JSON(),nullable=False),sa.Column('result',sa.JSON(),nullable=False),sa.Column('error_code',sa.String(64),nullable=True),
      sa.Column('wait_until',sa.DateTime(timezone=True),nullable=True),sa.Column('version',sa.Integer(),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),sa.Column('completed_at',sa.DateTime(timezone=True),nullable=True),
      sa.Column('id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
      sa.CheckConstraint("approval_status in ('not_required','pending','approved','rejected')"),sa.CheckConstraint("kind in ('approval_wait','follow_up')"),
      sa.CheckConstraint("status in ('starting','running','waiting_approval','waiting_timer','completed','failed','cancelled')"),
      sa.ForeignKeyConstraint(['user_id'],['users.id']),sa.ForeignKeyConstraint(['workspace_id'],['workspaces.id']),sa.PrimaryKeyConstraint('id'),
      sa.UniqueConstraint('temporal_workflow_id'),sa.UniqueConstraint('workspace_id','request_key'))
    op.create_index(op.f('ix_automation_workflows_workspace_id'),'automation_workflows',['workspace_id'])
    op.create_table('automation_workflow_audits',
      sa.Column('workflow_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('workspace_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('actor_id',sa.Uuid(as_uuid=False),nullable=False),
      sa.Column('event',sa.String(48),nullable=False),sa.Column('workflow_version',sa.Integer(),nullable=False),sa.Column('data',sa.JSON(),nullable=False),
      sa.Column('id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
      sa.ForeignKeyConstraint(['actor_id'],['users.id']),sa.ForeignKeyConstraint(['workflow_id'],['automation_workflows.id']),sa.ForeignKeyConstraint(['workspace_id'],['workspaces.id']),sa.PrimaryKeyConstraint('id'))
    op.create_index(op.f('ix_automation_workflow_audits_workflow_id'),'automation_workflow_audits',['workflow_id']);op.create_index(op.f('ix_automation_workflow_audits_workspace_id'),'automation_workflow_audits',['workspace_id'])
def downgrade():
    op.drop_index(op.f('ix_automation_workflow_audits_workspace_id'),table_name='automation_workflow_audits');op.drop_index(op.f('ix_automation_workflow_audits_workflow_id'),table_name='automation_workflow_audits');op.drop_table('automation_workflow_audits');op.drop_index(op.f('ix_automation_workflows_workspace_id'),table_name='automation_workflows');op.drop_table('automation_workflows')
