"""Native read job caps; retain existing queues/authority and legacy rows."""
from alembic import op
import sqlalchemy as sa

revision='0055'
down_revision='0054'
branch_labels=depends_on=None
TABLES=('tool_calls','meta_sync_jobs','google_ads_sync_jobs')


def upgrade():
    op.create_table('tenant_read_policies',
        sa.Column('workspace_id',sa.Uuid(as_uuid=False),sa.ForeignKey('workspaces.id'),primary_key=True),
        sa.Column('version',sa.Integer(),nullable=False),
        sa.Column('daily_read_jobs',sa.Integer(),nullable=False),
        sa.Column('queued_read_jobs',sa.Integer(),nullable=False),
        sa.Column('concurrent_reads',sa.Integer(),nullable=False),
        sa.Column('updated_by',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
        sa.CheckConstraint('version>=1 AND daily_read_jobs BETWEEN 1 AND 10000 '
            'AND queued_read_jobs BETWEEN 1 AND 100 AND concurrent_reads BETWEEN 1 AND 8',name='tenant_read_policy_bounds'))
    for table in TABLES:op.add_column(table,sa.Column('resource_admitted_at',sa.DateTime(timezone=True)))
    op.execute("""CREATE FUNCTION pao_read_resource_usage(wid uuid)
      RETURNS TABLE(daily_jobs bigint,queued_jobs bigint,running_jobs bigint) LANGUAGE sql AS $$
      SELECT count(*) FILTER (WHERE stamp >= (date_trunc('day',statement_timestamp() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC')),
        count(*) FILTER (WHERE status='queued'),count(*) FILTER (WHERE status='running') FROM (
        SELECT coalesce(resource_admitted_at,created_at) stamp,status FROM tool_calls WHERE workspace_id=wid
          AND (name LIKE 'mcp.%' OR (connector_snapshot IS NOT NULL AND json_typeof(connector_snapshot)<>'null'))
        UNION ALL SELECT coalesce(j.resource_admitted_at,j.created_at),j.status FROM meta_sync_jobs j
          JOIN meta_connections c ON c.id=j.connection_id WHERE c.workspace_id=wid
        UNION ALL SELECT coalesce(j.resource_admitted_at,j.created_at),j.status FROM google_ads_sync_jobs j
          JOIN google_ads_connections c ON c.id=j.connection_id WHERE c.workspace_id=wid) reads;
      $$""")
    op.execute("""CREATE FUNCTION pao_read_resource_guard() RETURNS trigger LANGUAGE plpgsql AS $$
      DECLARE wid uuid; admitted timestamptz; daily_limit int:=500; queue_limit int:=20; active_limit int:=2;
        u record; old_state text; needs_admission boolean;
      BEGIN
        IF TG_OP='DELETE' THEN
          IF OLD.resource_admitted_at IS NOT NULL THEN RAISE EXCEPTION 'tenant_read_resource_history_immutable'; END IF;
          RETURN OLD;
        END IF;
        IF TG_TABLE_NAME='tool_calls' THEN
          IF NEW.name NOT LIKE 'mcp.%' AND (NEW.connector_snapshot IS NULL OR json_typeof(NEW.connector_snapshot)='null')
            AND (TG_OP='INSERT' OR OLD.resource_admitted_at IS NULL) THEN RETURN NEW; END IF;
        END IF;
        IF TG_OP='UPDATE' THEN
          IF NEW.resource_admitted_at IS DISTINCT FROM OLD.resource_admitted_at OR
            (OLD.resource_admitted_at IS NOT NULL AND (NEW.id,NEW.created_at,NEW.request_key) IS DISTINCT FROM
              (OLD.id,OLD.created_at,OLD.request_key))
          THEN RAISE EXCEPTION 'tenant_read_resource_history_immutable'; END IF;
          IF TG_TABLE_NAME='tool_calls' THEN
            IF OLD.resource_admitted_at IS NOT NULL AND (NEW.workspace_id,NEW.run_id,NEW.user_id,NEW.name) IS DISTINCT FROM
              (OLD.workspace_id,OLD.run_id,OLD.user_id,OLD.name) THEN RAISE EXCEPTION 'tenant_read_resource_history_immutable'; END IF;
          ELSE
            IF OLD.resource_admitted_at IS NOT NULL AND NEW.connection_id IS DISTINCT FROM OLD.connection_id
            THEN RAISE EXCEPTION 'tenant_read_resource_history_immutable'; END IF;
          END IF;
          IF NEW.status='queued' AND OLD.status NOT IN ('pending','queued') AND OLD.resource_admitted_at IS NOT NULL
          THEN RAISE EXCEPTION 'tenant_read_resource_replay_denied'; END IF;
          IF NEW.status<>'running' OR OLD.status='running' THEN RETURN NEW; END IF;
          IF OLD.status<>'queued' THEN RAISE EXCEPTION 'tenant_read_resource_replay_denied'; END IF;
        END IF;
        IF TG_TABLE_NAME='tool_calls' THEN
          IF NEW.name NOT LIKE 'mcp.%' AND (NEW.connector_snapshot IS NULL OR json_typeof(NEW.connector_snapshot)='null') THEN RETURN NEW; END IF;
          wid:=NEW.workspace_id;
        ELSIF TG_TABLE_NAME='meta_sync_jobs' THEN
          SELECT workspace_id INTO wid FROM meta_connections WHERE id=NEW.connection_id;
        ELSE
          SELECT workspace_id INTO wid FROM google_ads_connections WHERE id=NEW.connection_id;
        END IF;
        IF wid IS NULL THEN RAISE EXCEPTION 'tenant_read_resource_scope_missing'; END IF;
        PERFORM id FROM workspaces WHERE id=wid FOR KEY SHARE;
        PERFORM pg_advisory_xact_lock(hashtextextended('pao-read-resource-v1:'||wid::text,0));
        SELECT daily_read_jobs,queued_read_jobs,concurrent_reads INTO daily_limit,queue_limit,active_limit
          FROM tenant_read_policies WHERE workspace_id=wid;
        daily_limit:=coalesce(daily_limit,500);queue_limit:=coalesce(queue_limit,20);active_limit:=coalesce(active_limit,2);
        SELECT * INTO u FROM pao_read_resource_usage(wid);
        IF TG_OP='INSERT' THEN
          IF u.daily_jobs>=daily_limit THEN RAISE EXCEPTION 'tenant_read_daily_jobs_exhausted'; END IF;
          IF NEW.status='queued' AND u.queued_jobs>=queue_limit THEN RAISE EXCEPTION 'tenant_read_queue_exhausted'; END IF;
          NEW.resource_admitted_at:=clock_timestamp();
        END IF;
        IF NEW.status='running' AND u.running_jobs>=active_limit THEN RAISE EXCEPTION 'tenant_read_concurrency_exhausted'; END IF;
        RETURN NEW;
      END $$""")
    for table in TABLES:
        op.execute(f'CREATE TRIGGER tenant_read_resource_guard BEFORE INSERT OR UPDATE OR DELETE ON {table} '
            'FOR EACH ROW EXECUTE FUNCTION pao_read_resource_guard()')


def downgrade():
    db=op.get_bind()
    if db.scalar(sa.text('SELECT count(*) FROM tenant_read_policies')) or any(
        db.scalar(sa.text(f'SELECT count(*) FROM {table} WHERE resource_admitted_at IS NOT NULL')) for table in TABLES):
        raise RuntimeError('Downgrade refused: tenant read resource history must be preserved')
    for table in TABLES:op.execute(f'DROP TRIGGER tenant_read_resource_guard ON {table}')
    op.execute('DROP FUNCTION pao_read_resource_guard()');op.execute('DROP FUNCTION pao_read_resource_usage(uuid)')
    for table in TABLES:op.drop_column(table,'resource_admitted_at')
    op.drop_table('tenant_read_policies')
