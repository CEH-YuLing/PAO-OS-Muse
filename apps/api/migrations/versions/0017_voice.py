"""voice

Revision ID: 0017
Revises: 0016
"""
from alembic import op
import sqlalchemy as sa
revision='0017';down_revision='0016';branch_labels=None;depends_on=None
def upgrade():
    op.create_table('voice_interactions',sa.Column('workspace_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('user_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('session_id',sa.Uuid(as_uuid=False),nullable=True),sa.Column('kind',sa.String(16),nullable=False),sa.Column('status',sa.String(16),nullable=False),sa.Column('provider',sa.String(32),nullable=False),sa.Column('input_bytes',sa.BigInteger(),nullable=False),sa.Column('output_bytes',sa.BigInteger(),nullable=False),sa.Column('duration_ms',sa.Integer(),nullable=False),sa.Column('language',sa.String(16),nullable=True),sa.Column('interrupted',sa.Boolean(),nullable=False),sa.Column('error_code',sa.String(64),nullable=True),sa.Column('completed_at',sa.DateTime(timezone=True),nullable=True),sa.Column('id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.CheckConstraint('input_bytes >= 0 and output_bytes >= 0 and duration_ms >= 0'),sa.CheckConstraint("kind in ('stt','tts')"),sa.CheckConstraint("status in ('running','completed','failed','interrupted')"),sa.ForeignKeyConstraint(['session_id'],['sessions.id']),sa.ForeignKeyConstraint(['user_id'],['users.id']),sa.ForeignKeyConstraint(['workspace_id'],['workspaces.id']),sa.PrimaryKeyConstraint('id'))
    op.create_index(op.f('ix_voice_interactions_workspace_id'),'voice_interactions',['workspace_id'])
def downgrade():
    op.drop_index(op.f('ix_voice_interactions_workspace_id'),table_name='voice_interactions');op.drop_table('voice_interactions')
