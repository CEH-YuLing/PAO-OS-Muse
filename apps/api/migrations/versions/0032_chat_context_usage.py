"""P3 additive chat metadata, compaction versions and usage ledger."""
from alembic import op
import sqlalchemy as sa
revision='0032'
down_revision='0031'
branch_labels=None
depends_on=None

def identity():
    return [sa.Column('id',sa.Uuid(as_uuid=False),primary_key=True),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False)]
def upgrade():
    op.create_unique_constraint('task_attempt_scope_unique','task_attempts',['id','workspace_id'])
    op.add_column('sessions',sa.Column('chat_profile',sa.JSON(),nullable=True))
    op.add_column('sessions',sa.Column('chat_revision',sa.Integer(),nullable=False,server_default='1'))
    op.add_column('runs',sa.Column('parent_run_id',sa.Uuid(as_uuid=False),nullable=True))
    op.create_foreign_key('runs_retry_workspace_fk','runs','runs',['parent_run_id','workspace_id'],['id','workspace_id'])
    op.create_table('chat_compactions',*identity(),
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('session_id',sa.Uuid(as_uuid=False),nullable=False),
        sa.Column('user_id',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),sa.Column('brain_id',sa.Uuid(as_uuid=False)),
        sa.Column('revision',sa.Integer(),nullable=False),sa.Column('version',sa.String(32),nullable=False),
        sa.Column('source_hash',sa.String(64),nullable=False),sa.Column('message_ids',sa.JSON(),nullable=False),sa.Column('content',sa.Text(),nullable=False),
        sa.ForeignKeyConstraint(['session_id','workspace_id'],['sessions.id','sessions.workspace_id']),
        sa.UniqueConstraint('session_id','revision'),sa.CheckConstraint('revision >= 1',name='chat_compaction_revision_positive'))
    op.execute("""CREATE FUNCTION pao_compaction_immutable() RETURNS trigger AS $$ BEGIN
      RAISE EXCEPTION 'chat_compaction_immutable'; END; $$ LANGUAGE plpgsql""")
    op.execute('CREATE TRIGGER chat_compaction_immutable BEFORE UPDATE ON chat_compactions FOR EACH ROW EXECUTE FUNCTION pao_compaction_immutable()')
    op.create_table('llm_attempts',*identity(),
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('user_id',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('brain_id',sa.Uuid(as_uuid=False)),sa.Column('session_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('run_id',sa.Uuid(as_uuid=False),nullable=False),
        sa.Column('task_attempt_id',sa.Uuid(as_uuid=False)),sa.Column('request_key',sa.String(64),nullable=False),sa.Column('source',sa.String(32),nullable=False),
        sa.Column('provider',sa.String(24),nullable=False),sa.Column('model',sa.String(120),nullable=False),sa.Column('status',sa.String(16),nullable=False),
        sa.Column('usage_state',sa.String(16),nullable=False),sa.Column('estimated_input_tokens',sa.Integer(),nullable=False),
        sa.Column('reserved_output_tokens',sa.Integer(),nullable=False),sa.Column('estimated_output_tokens',sa.Integer()),
        sa.Column('input_tokens',sa.Integer()),sa.Column('output_tokens',sa.Integer()),sa.Column('cost_estimate',sa.Numeric(20,10)),
        sa.Column('pricing',sa.JSON()),sa.Column('trace',sa.JSON(),nullable=False),sa.Column('ttft_ms',sa.Integer()),sa.Column('elapsed_ms',sa.Integer()),
        sa.Column('finished_at',sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(['run_id','workspace_id'],['runs.id','runs.workspace_id']),
        sa.ForeignKeyConstraint(['session_id','workspace_id'],['sessions.id','sessions.workspace_id']),
        sa.ForeignKeyConstraint(['task_attempt_id','workspace_id'],['task_attempts.id','task_attempts.workspace_id']),sa.UniqueConstraint('run_id','request_key'),
        sa.CheckConstraint("status in ('started','completed','failed','cancelled')",name='llm_attempt_status'),
        sa.CheckConstraint("usage_state in ('unknown','reported','partial')",name='llm_attempt_usage_state'),
        sa.CheckConstraint('estimated_input_tokens >= 0 AND reserved_output_tokens >= 0',name='llm_attempt_reservation_positive'))
    for field in ('workspace_id','user_id','session_id','run_id'):op.create_index('ix_llm_attempts_'+field,'llm_attempts',[field])
    op.execute("CREATE INDEX chat_session_title_fts ON sessions USING gin(to_tsvector('simple',title))")
    op.execute("CREATE INDEX chat_message_content_fts ON messages USING gin(to_tsvector('simple',content))")
def downgrade():
    op.drop_index('chat_message_content_fts',table_name='messages');op.drop_index('chat_session_title_fts',table_name='sessions')
    op.drop_table('llm_attempts')
    op.drop_constraint('task_attempt_scope_unique','task_attempts',type_='unique')
    op.execute('DROP TRIGGER chat_compaction_immutable ON chat_compactions');op.execute('DROP FUNCTION pao_compaction_immutable()')
    op.drop_table('chat_compactions');op.drop_constraint('runs_retry_workspace_fk','runs',type_='foreignkey')
    op.drop_column('runs','parent_run_id');op.drop_column('sessions','chat_revision');op.drop_column('sessions','chat_profile')
