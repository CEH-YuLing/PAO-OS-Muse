"""S5 immutable job receipts, control/review/report evidence and simulated money."""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from alembic import op

revision = '0069'
down_revision = '0068'
branch_labels = depends_on = None


def identity():
    return [sa.Column('id',sa.Uuid(),primary_key=True),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('workspace_id',sa.Uuid(),sa.ForeignKey('workspaces.id'),nullable=False)]


def request():
    return [sa.Column('actor_id',sa.Uuid(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('request_key',sa.String(36),nullable=False),sa.Column('fingerprint',sa.String(64),nullable=False)]


def upgrade():
    op.create_table('business_jobs',*identity(),*request(),
        sa.Column('plan_task_id',sa.Uuid(),sa.ForeignKey('business_plan_tasks.id'),nullable=False,unique=True),
        sa.Column('run_id',sa.Uuid(),sa.ForeignKey('runs.id'),nullable=False,unique=True),
        sa.Column('attempt_id',sa.Uuid(),sa.ForeignKey('task_attempts.id'),nullable=False,unique=True),
        sa.Column('selection',JSONB(),nullable=False),sa.Column('selection_hash',sa.String(64),nullable=False),
        sa.UniqueConstraint('id','workspace_id'),sa.UniqueConstraint('workspace_id','actor_id','request_key'),
        sa.ForeignKeyConstraint(['run_id','workspace_id'],['runs.id','runs.workspace_id']),
        sa.ForeignKeyConstraint(['attempt_id','workspace_id'],['task_attempts.id','task_attempts.workspace_id']),
        sa.CheckConstraint('length(fingerprint)=64 AND length(selection_hash)=64',name='business_job_hash'))
    op.create_table('business_plan_events',*identity(),*request(),
        sa.Column('subject_kind',sa.String(16),nullable=False),sa.Column('subject_id',sa.Uuid(),nullable=False),
        sa.Column('action',sa.String(32),nullable=False),sa.Column('data',JSONB(),nullable=False),
        sa.Column('content_hash',sa.String(64),nullable=False),sa.UniqueConstraint('workspace_id','request_key'),
        sa.CheckConstraint("subject_kind IN ('job','action','budget','control','schedule','report') AND length(content_hash)=64 AND length(fingerprint)=64",name='business_event_value'))
    op.create_table('business_budgets',*identity(),*request(),
        sa.Column('plan_version_id',sa.Uuid(),sa.ForeignKey('monthly_plan_versions.id'),nullable=False),
        sa.Column('account_id',sa.String(80),nullable=False),sa.Column('campaign_id',sa.String(80),nullable=False),
        sa.Column('currency',sa.String(3),nullable=False),sa.Column('cap_minor',sa.BigInteger(),nullable=False),
        sa.Column('headroom_minor',sa.BigInteger(),nullable=False),sa.Column('opening_spent_minor',sa.BigInteger(),nullable=False),
        sa.Column('observed_at',sa.DateTime(timezone=True),nullable=False),sa.Column('max_age_seconds',sa.Integer(),nullable=False),
        sa.UniqueConstraint('id','workspace_id'),sa.UniqueConstraint('workspace_id','request_key'),
        sa.UniqueConstraint('workspace_id','plan_version_id','account_id','campaign_id','currency'),
        sa.CheckConstraint('cap_minor>0 AND headroom_minor>=0 AND opening_spent_minor>=0 AND headroom_minor+opening_spent_minor<=cap_minor AND max_age_seconds BETWEEN 60 AND 86400',name='business_budget_values'))
    op.create_table('business_actions',*identity(),*request(),
        sa.Column('job_id',sa.Uuid(),sa.ForeignKey('business_jobs.id'),nullable=False),
        sa.Column('budget_id',sa.Uuid(),sa.ForeignKey('business_budgets.id'),nullable=False),
        sa.Column('kind',sa.String(24),nullable=False),sa.Column('amount_minor',sa.BigInteger(),nullable=False),
        sa.Column('artifact_hash',sa.String(64),nullable=False),sa.UniqueConstraint('id','workspace_id'),
        sa.UniqueConstraint('workspace_id','request_key'),
        sa.ForeignKeyConstraint(['job_id','workspace_id'],['business_jobs.id','business_jobs.workspace_id']),
        sa.ForeignKeyConstraint(['budget_id','workspace_id'],['business_budgets.id','business_budgets.workspace_id']),
        sa.CheckConstraint("kind IN ('mock_publish','mock_ads_budget') AND amount_minor>0 AND length(artifact_hash)=64",name='business_action_values'))
    op.create_table('business_budget_entries',*identity(),
        sa.Column('budget_id',sa.Uuid(),sa.ForeignKey('business_budgets.id'),nullable=False),
        sa.Column('action_id',sa.Uuid(),sa.ForeignKey('business_actions.id'),nullable=False),
        sa.Column('kind',sa.String(16),nullable=False),sa.Column('amount_minor',sa.BigInteger(),nullable=False),
        sa.UniqueConstraint('action_id','kind'),
        sa.ForeignKeyConstraint(['budget_id','workspace_id'],['business_budgets.id','business_budgets.workspace_id']),
        sa.ForeignKeyConstraint(['action_id','workspace_id'],['business_actions.id','business_actions.workspace_id']),
        sa.CheckConstraint("kind IN ('reserved','spent','released') AND amount_minor>0",name='business_budget_entry_values'))
    op.execute('''CREATE FUNCTION pao_business_ops_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE available bigint; total bigint;
    BEGIN
      IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'business_operations_immutable'; END IF;
      IF TG_TABLE_NAME='business_jobs' THEN
        IF NOT EXISTS(SELECT 1 FROM business_plan_tasks p JOIN tasks t ON t.id=p.task_id
          JOIN task_attempts a ON a.task_id=t.id JOIN runs r ON r.id=a.run_id
          WHERE p.id=NEW.plan_task_id AND p.workspace_id=NEW.workspace_id AND a.id=NEW.attempt_id
          AND r.id=NEW.run_id AND r.workspace_id=NEW.workspace_id AND t.workspace_id=NEW.workspace_id)
        THEN RAISE EXCEPTION 'business_job_scope'; END IF;
      ELSIF TG_TABLE_NAME='business_budgets' THEN
        IF NOT EXISTS(SELECT 1 FROM monthly_plan_versions WHERE id=NEW.plan_version_id AND workspace_id=NEW.workspace_id)
        THEN RAISE EXCEPTION 'business_budget_scope'; END IF;
      ELSIF TG_TABLE_NAME='business_budget_entries' THEN
        PERFORM 1 FROM business_budgets WHERE id=NEW.budget_id FOR UPDATE;
        IF NOT EXISTS(SELECT 1 FROM business_actions WHERE id=NEW.action_id AND workspace_id=NEW.workspace_id
          AND budget_id=NEW.budget_id AND amount_minor=NEW.amount_minor) THEN RAISE EXCEPTION 'business_money_scope'; END IF;
        IF NEW.kind='reserved' THEN
          SELECT cap_minor-headroom_minor-opening_spent_minor INTO available FROM business_budgets WHERE id=NEW.budget_id;
          SELECT coalesce(sum(CASE WHEN kind='reserved' THEN amount_minor WHEN kind='released' THEN -amount_minor ELSE 0 END),0)
            INTO total FROM business_budget_entries WHERE budget_id=NEW.budget_id;
          IF total+NEW.amount_minor>available THEN RAISE EXCEPTION 'business_budget_exhausted'; END IF;
        ELSE
          IF NOT EXISTS(SELECT 1 FROM business_budget_entries WHERE action_id=NEW.action_id AND kind='reserved')
            OR EXISTS(SELECT 1 FROM business_budget_entries WHERE action_id=NEW.action_id AND kind IN ('spent','released'))
          THEN RAISE EXCEPTION 'business_money_settlement_conflict'; END IF;
        END IF;
      END IF;
      RETURN NEW;
    END $$''')
    for table in ('business_jobs','business_plan_events','business_budgets','business_actions','business_budget_entries'):
        op.execute(f'CREATE TRIGGER {table}_immutable BEFORE INSERT OR UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION pao_business_ops_guard()')


def downgrade():
    if any(op.get_bind().scalar(sa.text(f'SELECT EXISTS(SELECT 1 FROM {name})')) for name in
        ('business_jobs','business_plan_events','business_budgets','business_actions','business_budget_entries')):
        raise RuntimeError('Populated business operations cannot be discarded')
    for table in ('business_budget_entries','business_actions','business_budgets','business_plan_events','business_jobs'):op.drop_table(table)
    op.execute('DROP FUNCTION pao_business_ops_guard()')
