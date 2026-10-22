"""S5 versioned profiles and monthly draft plans; no execution authority."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision='0066'
down_revision='0065'
branch_labels=depends_on=None


def upgrade():
    def identity():return [sa.Column('id',sa.Uuid(as_uuid=False),primary_key=True),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False)]
    op.create_table('business_profiles',*identity(),
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),sa.ForeignKey('workspaces.id'),nullable=False),
        sa.Column('brand_id',sa.Uuid(as_uuid=False),sa.ForeignKey('brands.id')),
        sa.Column('scope_key',sa.String(40),nullable=False),sa.Column('revision',sa.Integer(),nullable=False),
        sa.UniqueConstraint('id','workspace_id'),sa.UniqueConstraint('workspace_id','scope_key'),
        sa.CheckConstraint("revision>=1 AND scope_key=coalesce(brand_id::text,'enterprise')",name='business_profile_scope'))
    op.create_table('business_profile_versions',*identity(),
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),sa.ForeignKey('workspaces.id'),nullable=False),
        sa.Column('profile_id',sa.Uuid(as_uuid=False),sa.ForeignKey('business_profiles.id'),nullable=False),
        sa.Column('revision',sa.Integer(),nullable=False),sa.Column('request_key',sa.String(36),nullable=False),
        sa.Column('actor_id',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('content',JSONB(),nullable=False),sa.Column('content_hash',sa.String(64),nullable=False),
        sa.ForeignKeyConstraint(['profile_id','workspace_id'],['business_profiles.id','business_profiles.workspace_id']),
        sa.UniqueConstraint('profile_id','revision'),sa.UniqueConstraint('profile_id','workspace_id','revision'),sa.UniqueConstraint('profile_id','request_key'),sa.UniqueConstraint('id','workspace_id'),
        sa.CheckConstraint('revision>=1 AND length(content_hash)=64',name='business_profile_version_value'))
    op.create_table('monthly_plans',*identity(),
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),sa.ForeignKey('workspaces.id'),nullable=False),
        sa.Column('profile_id',sa.Uuid(as_uuid=False),sa.ForeignKey('business_profiles.id'),nullable=False),
        sa.Column('revision',sa.Integer(),nullable=False),sa.UniqueConstraint('id','workspace_id'),
        sa.ForeignKeyConstraint(['profile_id','workspace_id'],['business_profiles.id','business_profiles.workspace_id']),
        sa.CheckConstraint('revision>=1',name='monthly_plan_revision'))
    op.create_table('monthly_plan_versions',*identity(),
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),sa.ForeignKey('workspaces.id'),nullable=False),
        sa.Column('plan_id',sa.Uuid(as_uuid=False),sa.ForeignKey('monthly_plans.id'),nullable=False),
        sa.Column('profile_version_id',sa.Uuid(as_uuid=False),sa.ForeignKey('business_profile_versions.id'),nullable=False),
        sa.Column('revision',sa.Integer(),nullable=False),sa.Column('request_key',sa.String(36),nullable=False),
        sa.Column('actor_id',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('content',JSONB(),nullable=False),sa.Column('content_hash',sa.String(64),nullable=False),
        sa.ForeignKeyConstraint(['plan_id','workspace_id'],['monthly_plans.id','monthly_plans.workspace_id']),
        sa.ForeignKeyConstraint(['profile_version_id','workspace_id'],['business_profile_versions.id','business_profile_versions.workspace_id']),
        sa.UniqueConstraint('plan_id','revision'),sa.UniqueConstraint('plan_id','workspace_id','revision'),sa.UniqueConstraint('plan_id','request_key'),
        sa.CheckConstraint('revision>=1 AND length(content_hash)=64',name='monthly_plan_version_value'))
    op.create_foreign_key('business_profile_head','business_profiles','business_profile_versions',['id','workspace_id','revision'],['profile_id','workspace_id','revision'],deferrable=True,initially='DEFERRED')
    op.create_foreign_key('monthly_plan_head','monthly_plans','monthly_plan_versions',['id','workspace_id','revision'],['plan_id','workspace_id','revision'],deferrable=True,initially='DEFERRED')
    op.execute('''CREATE FUNCTION pao_business_planning_guard() RETURNS trigger LANGUAGE plpgsql AS $$
      DECLARE expected_workspace uuid; expected_profile uuid;
      BEGIN
        IF TG_OP='DELETE' THEN RAISE EXCEPTION 'business_planning_history_immutable'; END IF;
        IF TG_TABLE_NAME IN ('business_profile_versions','monthly_plan_versions') AND TG_OP='UPDATE' THEN RAISE EXCEPTION 'business_planning_history_immutable'; END IF;
        IF TG_TABLE_NAME='business_profiles' THEN
          IF NEW.brand_id IS NOT NULL THEN
            SELECT workspace_id INTO expected_workspace FROM brands WHERE id=NEW.brand_id;
            IF expected_workspace IS DISTINCT FROM NEW.workspace_id THEN RAISE EXCEPTION 'business_profile_brand_scope'; END IF;
          END IF;
          IF TG_OP='UPDATE' AND ((NEW.id,NEW.workspace_id,NEW.brand_id,NEW.scope_key,NEW.created_at) IS DISTINCT FROM (OLD.id,OLD.workspace_id,OLD.brand_id,OLD.scope_key,OLD.created_at) OR NEW.revision<>OLD.revision+1) THEN RAISE EXCEPTION 'business_profile_identity_immutable'; END IF;
        ELSIF TG_TABLE_NAME='monthly_plans' AND TG_OP='UPDATE' THEN
          IF (NEW.id,NEW.workspace_id,NEW.profile_id,NEW.created_at) IS DISTINCT FROM (OLD.id,OLD.workspace_id,OLD.profile_id,OLD.created_at) OR NEW.revision<>OLD.revision+1 THEN RAISE EXCEPTION 'monthly_plan_identity_immutable'; END IF;
        ELSIF TG_TABLE_NAME='monthly_plan_versions' AND TG_OP='INSERT' THEN
          SELECT profile_id INTO expected_profile FROM monthly_plans WHERE id=NEW.plan_id;
          IF NOT EXISTS(SELECT 1 FROM business_profile_versions WHERE id=NEW.profile_version_id AND profile_id=expected_profile AND workspace_id=NEW.workspace_id) THEN RAISE EXCEPTION 'monthly_plan_profile_pin'; END IF;
        END IF;
        RETURN NEW;
      END $$''')
    for table in ('business_profiles','business_profile_versions','monthly_plans','monthly_plan_versions'):
        op.execute(f'CREATE TRIGGER {table}_guard BEFORE INSERT OR UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION pao_business_planning_guard()')


def downgrade():
    if op.get_bind().scalar(sa.text('SELECT EXISTS(SELECT 1 FROM business_profiles) OR EXISTS(SELECT 1 FROM monthly_plans)')):
        raise RuntimeError('Populated business planning history cannot be discarded; restore an approved checkpoint')
    op.drop_constraint('monthly_plan_head','monthly_plans',type_='foreignkey')
    op.drop_constraint('business_profile_head','business_profiles',type_='foreignkey')
    for table in ('monthly_plan_versions','monthly_plans','business_profile_versions','business_profiles'):op.drop_table(table)
    op.execute('DROP FUNCTION pao_business_planning_guard()')
