"""M4.4 scoped event sources and frozen approval execution inputs."""
from alembic import op
import sqlalchemy as sa

revision = '0037'
down_revision = '0036'
branch_labels = depends_on = None
SOURCES = [('task_id', 'tasks', 'business_event_task_scope'),
           ('tool_call_id', 'tool_calls', 'business_event_tool_scope'),
           ('ad_action_id', 'ads_actions', 'business_event_action_scope'),
           ('analysis_id', 'ad_intelligence_runs', 'business_event_analysis_scope')]
UNIQUES = [('tool_calls','tool_calls_event_scope'), ('ads_actions','ads_actions_event_scope'),
           ('ad_intelligence_runs','ad_intelligence_event_scope')]


def immutable():
    op.execute('CREATE TRIGGER business_event_immutable BEFORE UPDATE OR DELETE ON business_events FOR EACH ROW EXECUTE FUNCTION pao_business_event_immutable()')


def upgrade():
    op.execute('DROP TRIGGER business_event_immutable ON business_events')
    for column, table, name in SOURCES:
        op.add_column('business_events', sa.Column(column, sa.Uuid(as_uuid=False)))
    op.execute('UPDATE business_events SET task_id=aggregate_id')
    # The original unnamed FK is resolved from inspected metadata, not guessed.
    for fk in sa.inspect(op.get_bind()).get_foreign_keys('business_events'):
        if fk['constrained_columns'] == ['aggregate_id', 'workspace_id']:
            op.drop_constraint(fk['name'], 'business_events', type_='foreignkey')
    for table, name in UNIQUES: op.create_unique_constraint(name, table, ['id','workspace_id'])
    for column, table, name in SOURCES:
        op.create_foreign_key(name, 'business_events', table, [column,'workspace_id'], ['id','workspace_id'])
    op.drop_constraint('business_event_profile','business_events',type_='check')
    op.create_check_constraint('business_event_profile','business_events', "schema_version=1 AND ((event_type='task.completed' AND aggregate_type='task') OR (event_type='approval.requested' AND aggregate_type in ('task','tool','ads_action')) OR (event_type='ads.analysis.completed' AND aggregate_type='ads_analysis'))")
    op.create_check_constraint('business_event_target','business_events', "num_nonnulls(task_id,tool_call_id,ad_action_id,analysis_id)=1 AND ((aggregate_type='task' AND task_id IS NOT NULL AND task_id=aggregate_id) OR (aggregate_type='tool' AND tool_call_id IS NOT NULL AND tool_call_id=aggregate_id) OR (aggregate_type='ads_action' AND ad_action_id IS NOT NULL AND ad_action_id=aggregate_id) OR (aggregate_type='ads_analysis' AND analysis_id IS NOT NULL AND analysis_id=aggregate_id))")
    for table in ('tool_calls','ads_actions'): op.add_column(table,sa.Column('approval_input_hash',sa.String(64)))
    immutable()


def downgrade():
    # Refuse a lossy downgrade if events from the new profiles exist.
    op.execute("DO $$ BEGIN IF EXISTS(SELECT 1 FROM business_events WHERE event_type<>'task.completed') THEN RAISE EXCEPTION 'new_event_profiles_require_backup'; END IF; END $$")
    op.execute('DROP TRIGGER business_event_immutable ON business_events')
    for table in ('tool_calls','ads_actions'): op.drop_column(table,'approval_input_hash')
    op.drop_constraint('business_event_target','business_events',type_='check')
    op.drop_constraint('business_event_profile','business_events',type_='check')
    op.create_check_constraint('business_event_profile','business_events', "event_type='task.completed' AND aggregate_type='task' AND schema_version=1")
    for column, table, name in SOURCES:
        op.drop_constraint(name,'business_events',type_='foreignkey'); op.drop_column('business_events',column)
    op.create_foreign_key('business_events_aggregate_id_workspace_id_fkey','business_events','tasks',['aggregate_id','workspace_id'],['id','workspace_id'])
    for table, name in UNIQUES: op.drop_constraint(name,table,type_='unique')
    immutable()
