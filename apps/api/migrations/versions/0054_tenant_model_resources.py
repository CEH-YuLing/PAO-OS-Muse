"""Per-SME model resource policy; actual usage remains in LlmAttempt."""
from alembic import op
import sqlalchemy as sa

revision='0054'
down_revision='0053'
branch_labels=depends_on=None


def upgrade():
    op.create_unique_constraint('llm_attempt_workspace_identity','llm_attempts',['id','workspace_id'])
    op.create_table('tenant_resource_policies',
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),sa.ForeignKey('workspaces.id'),primary_key=True),
        sa.Column('version',sa.Integer(),nullable=False),
        sa.Column('daily_model_calls',sa.Integer(),nullable=False),
        sa.Column('daily_model_tokens',sa.Integer(),nullable=False),
        sa.Column('concurrent_models',sa.Integer(),nullable=False),
        sa.Column('updated_by',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
        sa.CheckConstraint('version >= 1 AND daily_model_calls BETWEEN 1 AND 10000 '
            'AND daily_model_tokens BETWEEN 1 AND 10000000 AND concurrent_models BETWEEN 1 AND 8',
            name='tenant_resource_policy_bounds'))
    op.create_table('tenant_model_leases',
        sa.Column('id',sa.Uuid(as_uuid=False),primary_key=True),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),sa.ForeignKey('workspaces.id'),nullable=False),
        sa.Column('actor_id',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('kind',sa.String(24),nullable=False),
        sa.Column('request_key',sa.String(64),nullable=False),
        sa.Column('attempt_id',sa.Uuid(as_uuid=False)),
        sa.Column('policy_version',sa.Integer(),nullable=False),
        sa.Column('reserved_tokens',sa.Integer(),nullable=False),
        sa.Column('status',sa.String(16),nullable=False),
        sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('released_at',sa.DateTime(timezone=True)),
        sa.UniqueConstraint('workspace_id','kind','request_key'),sa.UniqueConstraint('attempt_id'),
        sa.ForeignKeyConstraint(['attempt_id','workspace_id'],['llm_attempts.id','llm_attempts.workspace_id']),
        sa.CheckConstraint("policy_version >= 0 AND status IN ('active','released','expired') AND "
            "((kind='llm' AND attempt_id IS NOT NULL AND reserved_tokens=0) OR "
            "(kind='management_probe' AND attempt_id IS NULL AND reserved_tokens=96)) AND "
            "expires_at>created_at AND expires_at<=created_at+interval '5 minutes' AND "
            "((status='active' AND released_at IS NULL) OR (status<>'active' AND released_at IS NOT NULL))",
            name='tenant_model_lease_state'))
    op.create_index('tenant_model_lease_active','tenant_model_leases',['workspace_id','status','expires_at'])
    op.execute("""CREATE FUNCTION pao_tenant_model_lease_guard() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF TG_OP='DELETE' THEN RAISE EXCEPTION 'tenant_model_lease_history_immutable'; END IF;
        IF (NEW.id,NEW.created_at,NEW.workspace_id,NEW.actor_id,NEW.kind,NEW.request_key,
            NEW.attempt_id,NEW.policy_version,NEW.reserved_tokens,NEW.expires_at) IS DISTINCT FROM
           (OLD.id,OLD.created_at,OLD.workspace_id,OLD.actor_id,OLD.kind,OLD.request_key,
            OLD.attempt_id,OLD.policy_version,OLD.reserved_tokens,OLD.expires_at)
           OR OLD.status<>'active' OR NEW.status NOT IN ('released','expired')
        THEN RAISE EXCEPTION 'tenant_model_lease_history_immutable'; END IF;
        RETURN NEW;
      END $$""")
    op.execute('CREATE TRIGGER tenant_model_lease_immutable BEFORE UPDATE OR DELETE ON tenant_model_leases '
        'FOR EACH ROW EXECUTE FUNCTION pao_tenant_model_lease_guard()')


def downgrade():
    if op.get_bind().scalar(sa.text('SELECT count(*) FROM tenant_model_leases')) or op.get_bind().scalar(
        sa.text('SELECT count(*) FROM tenant_resource_policies')):
        raise RuntimeError('Downgrade refused: tenant resource history must be preserved')
    op.drop_table('tenant_model_leases')
    op.execute('DROP FUNCTION pao_tenant_model_lease_guard()')
    op.drop_table('tenant_resource_policies')
    op.drop_constraint('llm_attempt_workspace_identity','llm_attempts',type_='unique')
