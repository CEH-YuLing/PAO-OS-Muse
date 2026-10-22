"""Durable SME metadata admission; no auto policy, credentials or legacy stamps."""
from alembic import op
import sqlalchemy as sa

revision='0056'
down_revision='0055'
branch_labels=depends_on=None


def upgrade():
    op.create_table('tenant_metadata_policies',
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),sa.ForeignKey('workspaces.id'),primary_key=True),
        sa.Column('version',sa.Integer(),nullable=False),
        sa.Column('daily_metadata_requests',sa.Integer(),nullable=False),
        sa.Column('concurrent_metadata',sa.Integer(),nullable=False),
        sa.Column('updated_by',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
        sa.CheckConstraint('version>=1 AND daily_metadata_requests BETWEEN 1 AND 1000 '
            'AND concurrent_metadata BETWEEN 1 AND 8',name='tenant_metadata_policy_bounds'))
    op.create_table('tenant_metadata_leases',
        sa.Column('id',sa.Uuid(as_uuid=False),primary_key=True),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),sa.ForeignKey('workspaces.id'),nullable=False),
        sa.Column('actor_id',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('kind',sa.String(24),nullable=False),
        sa.Column('request_key',sa.Uuid(as_uuid=False),nullable=False),
        sa.Column('target_hash',sa.String(64),nullable=False),
        sa.Column('policy_version',sa.Integer(),nullable=False),
        sa.Column('status',sa.String(16),nullable=False),
        sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('released_at',sa.DateTime(timezone=True)),
        sa.UniqueConstraint('workspace_id','request_key'),
        sa.CheckConstraint("policy_version>=0 AND kind IN ('model_connect','model_catalogue','model_select','mcp_discovery') "
            "AND target_hash ~ '^[0-9a-f]{64}$' AND status IN ('active','released','expired') "
            "AND expires_at=created_at+interval '90 seconds' AND "
            "((status='active' AND released_at IS NULL) OR (status<>'active' AND released_at IS NOT NULL AND released_at>=created_at))",
            name='tenant_metadata_lease_state'))
    op.create_index('tenant_metadata_lease_usage','tenant_metadata_leases',['workspace_id','status','created_at'])
    op.execute("""CREATE FUNCTION pao_metadata_resource_guard() RETURNS trigger LANGUAGE plpgsql AS $$
      DECLARE daily_cap integer; concurrent_cap integer; ver integer; stamp timestamptz;
      BEGIN
        IF TG_OP='DELETE' THEN RAISE EXCEPTION 'tenant_metadata_history_immutable'; END IF;
        IF TG_OP='UPDATE' THEN
          IF (NEW.id,NEW.created_at,NEW.workspace_id,NEW.actor_id,NEW.kind,NEW.request_key,
              NEW.target_hash,NEW.policy_version,NEW.expires_at) IS DISTINCT FROM
             (OLD.id,OLD.created_at,OLD.workspace_id,OLD.actor_id,OLD.kind,OLD.request_key,
              OLD.target_hash,OLD.policy_version,OLD.expires_at)
             OR OLD.status<>'active' OR NEW.status NOT IN ('released','expired')
             OR (NEW.status='expired' AND OLD.expires_at>clock_timestamp())
          THEN RAISE EXCEPTION 'tenant_metadata_history_immutable'; END IF;
          NEW.released_at=clock_timestamp(); RETURN NEW;
        END IF;
        IF NEW.status<>'active' OR NEW.released_at IS NOT NULL
        THEN RAISE EXCEPTION 'tenant_metadata_admission_required'; END IF;
        PERFORM id FROM workspaces WHERE id=NEW.workspace_id FOR KEY SHARE;
        PERFORM pg_advisory_xact_lock(hashtextextended('pao-metadata-resource-v1:'||NEW.workspace_id::text,0));
        stamp=clock_timestamp();
        IF EXISTS(SELECT 1 FROM tenant_metadata_leases WHERE workspace_id=NEW.workspace_id AND request_key=NEW.request_key)
        THEN RAISE EXCEPTION 'tenant_metadata_replay_denied'; END IF;
        UPDATE tenant_metadata_leases SET status='expired',released_at=stamp
          WHERE workspace_id=NEW.workspace_id AND status='active' AND expires_at<=stamp;
        SELECT daily_metadata_requests,concurrent_metadata,version INTO daily_cap,concurrent_cap,ver
          FROM tenant_metadata_policies WHERE workspace_id=NEW.workspace_id;
        daily_cap=coalesce(daily_cap,100);concurrent_cap=coalesce(concurrent_cap,2);ver=coalesce(ver,0);
        IF (SELECT count(*) FROM tenant_metadata_leases WHERE workspace_id=NEW.workspace_id
            AND created_at>=date_trunc('day',stamp AT TIME ZONE 'UTC') AT TIME ZONE 'UTC')>=daily_cap
        THEN RAISE EXCEPTION 'tenant_metadata_daily_exhausted'; END IF;
        IF (SELECT count(*) FROM tenant_metadata_leases WHERE workspace_id=NEW.workspace_id AND status='active')>=concurrent_cap
        THEN RAISE EXCEPTION 'tenant_metadata_concurrency_exhausted'; END IF;
        NEW.created_at=stamp;NEW.expires_at=stamp+interval '90 seconds';NEW.policy_version=ver;
        RETURN NEW;
      END $$""")
    op.execute('CREATE TRIGGER tenant_metadata_resource_guard BEFORE INSERT OR UPDATE OR DELETE ON tenant_metadata_leases '
        'FOR EACH ROW EXECUTE FUNCTION pao_metadata_resource_guard()')


def downgrade():
    if op.get_bind().scalar(sa.text('SELECT count(*) FROM tenant_metadata_leases')) or op.get_bind().scalar(
        sa.text('SELECT count(*) FROM tenant_metadata_policies')):
        raise RuntimeError('Downgrade refused: tenant metadata history must be preserved')
    op.drop_table('tenant_metadata_leases')
    op.execute('DROP FUNCTION pao_metadata_resource_guard()')
    op.drop_table('tenant_metadata_policies')
