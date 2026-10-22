"""S5 evidence parent and native actor fences; accepted tables unchanged."""
from alembic import op
from sqlalchemy import text
revision='0070'
down_revision='0069'
branch_labels=depends_on=None


def upgrade():
    op.execute('''CREATE FUNCTION pao_business_parent_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_TABLE_NAME='business_jobs' THEN
        IF NOT EXISTS(SELECT 1 FROM runs r JOIN sessions s ON s.id=r.session_id WHERE r.id=NEW.run_id
          AND s.workspace_id=NEW.workspace_id AND s.user_id=NEW.actor_id)
        THEN RAISE EXCEPTION 'business_job_actor_scope'; END IF;
      ELSIF TG_TABLE_NAME='business_actions' THEN
        IF NOT EXISTS(SELECT 1 FROM business_jobs j JOIN business_budgets b ON b.id=NEW.budget_id
          WHERE j.id=NEW.job_id AND j.workspace_id=NEW.workspace_id AND b.workspace_id=NEW.workspace_id
          AND j.selection->>'plan_version_id'=b.plan_version_id::text)
        THEN RAISE EXCEPTION 'business_action_plan_scope'; END IF;
      ELSE
        IF (NEW.subject_kind='control' AND NEW.subject_id<>NEW.workspace_id)
          OR (NEW.subject_kind='job' AND NOT EXISTS(SELECT 1 FROM business_jobs WHERE id=NEW.subject_id AND workspace_id=NEW.workspace_id))
          OR (NEW.subject_kind='action' AND NOT EXISTS(SELECT 1 FROM business_actions WHERE id=NEW.subject_id AND workspace_id=NEW.workspace_id))
          OR (NEW.subject_kind='budget' AND NOT EXISTS(SELECT 1 FROM business_budgets WHERE id=NEW.subject_id AND workspace_id=NEW.workspace_id))
          OR (NEW.subject_kind IN ('report','schedule') AND NOT EXISTS(SELECT 1 FROM monthly_plans WHERE id=NEW.subject_id AND workspace_id=NEW.workspace_id))
        THEN RAISE EXCEPTION 'business_event_parent_scope'; END IF;
      END IF;
      RETURN NEW;
    END $$''')
    for table in ('business_jobs','business_actions','business_plan_events'):
        op.execute(f'CREATE TRIGGER {table}_parent_scope BEFORE INSERT ON {table} FOR EACH ROW EXECUTE FUNCTION pao_business_parent_guard()')


def downgrade():
    if op.get_bind().scalar(text('SELECT EXISTS(SELECT 1 FROM business_jobs) OR EXISTS(SELECT 1 FROM business_plan_events)')):
        raise RuntimeError('Populated business operations cannot lose scope fences')
    for table in ('business_jobs','business_actions','business_plan_events'):
        op.execute(f'DROP TRIGGER {table}_parent_scope ON {table}')
    op.execute('DROP FUNCTION pao_business_parent_guard()')
