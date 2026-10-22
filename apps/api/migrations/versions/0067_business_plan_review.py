"""S5 owner review and immutable native Goal/Task admission, not execution."""
from alembic import op
import sqlalchemy as sa

revision='0067'
down_revision='0066'
branch_labels=depends_on=None


def upgrade():
    def identity():return [sa.Column('id',sa.Uuid(as_uuid=False),primary_key=True),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False)]
    op.create_table('business_plan_reviews',*identity(),
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),sa.ForeignKey('workspaces.id'),nullable=False),
        sa.Column('plan_version_id',sa.Uuid(as_uuid=False),sa.ForeignKey('monthly_plan_versions.id'),nullable=False,unique=True),
        sa.Column('actor_id',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('decision',sa.String(16),nullable=False),sa.Column('source_hash',sa.String(64),nullable=False),
        sa.Column('request_key',sa.String(36),nullable=False),sa.Column('fingerprint',sa.String(64),nullable=False),
        sa.Column('self_review',sa.Boolean(),nullable=False),sa.Column('acknowledge_missing',sa.Boolean(),nullable=False),
        sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('id','workspace_id'),sa.UniqueConstraint('workspace_id','actor_id','request_key'),
        sa.CheckConstraint("decision IN ('approve','reject') AND length(source_hash)=64 AND length(fingerprint)=64",name='business_review_value'))
    op.create_table('business_plan_admissions',*identity(),
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),sa.ForeignKey('workspaces.id'),nullable=False),
        sa.Column('plan_version_id',sa.Uuid(as_uuid=False),sa.ForeignKey('monthly_plan_versions.id'),nullable=False,unique=True),
        sa.Column('review_id',sa.Uuid(as_uuid=False),sa.ForeignKey('business_plan_reviews.id'),nullable=False,unique=True),
        sa.Column('project_id',sa.Uuid(as_uuid=False),sa.ForeignKey('projects.id'),nullable=False,unique=True),
        sa.Column('goal_id',sa.Uuid(as_uuid=False),sa.ForeignKey('goals.id'),nullable=False,unique=True),
        sa.Column('actor_id',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('request_key',sa.String(36),nullable=False),sa.Column('fingerprint',sa.String(64),nullable=False),
        sa.UniqueConstraint('id','workspace_id'),sa.UniqueConstraint('workspace_id','actor_id','request_key'),
        sa.ForeignKeyConstraint(['review_id','workspace_id'],['business_plan_reviews.id','business_plan_reviews.workspace_id']),
        sa.ForeignKeyConstraint(['project_id','workspace_id'],['projects.id','projects.workspace_id']),
        sa.ForeignKeyConstraint(['goal_id','workspace_id'],['goals.id','goals.workspace_id']),
        sa.CheckConstraint('length(fingerprint)=64',name='business_admission_value'))
    op.create_table('business_plan_tasks',*identity(),
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),sa.ForeignKey('workspaces.id'),nullable=False),
        sa.Column('admission_id',sa.Uuid(as_uuid=False),sa.ForeignKey('business_plan_admissions.id'),nullable=False),
        sa.Column('task_id',sa.Uuid(as_uuid=False),sa.ForeignKey('tasks.id'),nullable=False,unique=True),
        sa.Column('item_key',sa.String(40),nullable=False),sa.Column('task_hash',sa.String(64),nullable=False),
        sa.ForeignKeyConstraint(['admission_id','workspace_id'],['business_plan_admissions.id','business_plan_admissions.workspace_id']),
        sa.ForeignKeyConstraint(['task_id','workspace_id'],['tasks.id','tasks.workspace_id']),
        sa.UniqueConstraint('admission_id','item_key'),sa.CheckConstraint('length(task_hash)=64',name='business_task_value'))
    op.execute('''CREATE FUNCTION pao_business_review_guard() RETURNS trigger LANGUAGE plpgsql AS $$
      DECLARE target_plan uuid;
      BEGIN
        IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'business_review_history_immutable'; END IF;
        IF TG_TABLE_NAME='business_plan_reviews' THEN
          IF NOT EXISTS(SELECT 1 FROM monthly_plan_versions WHERE id=NEW.plan_version_id AND workspace_id=NEW.workspace_id AND content_hash=NEW.source_hash) THEN RAISE EXCEPTION 'business_review_plan_scope'; END IF;
        ELSIF TG_TABLE_NAME='business_plan_admissions' THEN
          IF NOT EXISTS(SELECT 1 FROM business_plan_reviews WHERE id=NEW.review_id AND workspace_id=NEW.workspace_id AND plan_version_id=NEW.plan_version_id AND decision='approve') THEN RAISE EXCEPTION 'business_admission_review_scope'; END IF;
        ELSE
          IF NOT EXISTS(SELECT 1 FROM business_plan_admissions a JOIN tasks t ON t.id=NEW.task_id WHERE a.id=NEW.admission_id AND a.workspace_id=NEW.workspace_id AND t.workspace_id=NEW.workspace_id AND t.goal_id=a.goal_id AND t.project_id=a.project_id) THEN RAISE EXCEPTION 'business_task_parent_scope'; END IF;
        END IF;
        RETURN NEW;
      END $$''')
    for table in ('business_plan_reviews','business_plan_admissions','business_plan_tasks'):
        op.execute(f'CREATE TRIGGER {table}_guard BEFORE INSERT OR UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION pao_business_review_guard()')


def downgrade():
    if op.get_bind().scalar(sa.text('SELECT EXISTS(SELECT 1 FROM business_plan_reviews) OR EXISTS(SELECT 1 FROM business_plan_admissions)')):
        raise RuntimeError('Populated business review history cannot be discarded')
    for table in ('business_plan_tasks','business_plan_admissions','business_plan_reviews'):op.drop_table(table)
    op.execute('DROP FUNCTION pao_business_review_guard()')
