"""Pinned immutable local outcome observations; no external Ads writes."""
from alembic import op
import sqlalchemy as sa
revision='0046'
down_revision='0045'
branch_labels=depends_on=None
def upgrade():
    op.create_table('outcome_observations',sa.Column('id',sa.Uuid(as_uuid=False),primary_key=True),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('workspace_id',sa.Uuid(as_uuid=False),nullable=False),
        sa.Column('action_id',sa.Uuid(as_uuid=False),nullable=False),sa.Column('actor_id',sa.Uuid(as_uuid=False),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('request_key',sa.Uuid(as_uuid=False),nullable=False),sa.Column('request_hash',sa.String(64),nullable=False),
        sa.Column('source_hash',sa.String(64),nullable=False),sa.Column('observed_at',sa.DateTime(timezone=True),nullable=False),sa.Column('snapshot',sa.JSON(),nullable=False),
        sa.ForeignKeyConstraint(['action_id','workspace_id'],['ads_actions.id','ads_actions.workspace_id']),
        sa.UniqueConstraint('action_id','actor_id','request_key'),sa.CheckConstraint('length(request_hash)=64 AND length(source_hash)=64'))
    op.execute("""CREATE FUNCTION outcome_observation_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN RAISE EXCEPTION 'outcome observation immutable'; END $$""")
    op.execute('CREATE TRIGGER outcome_observation_immutable BEFORE UPDATE OR DELETE ON outcome_observations FOR EACH ROW EXECUTE FUNCTION outcome_observation_immutable()')
def downgrade():
    op.drop_table('outcome_observations');op.execute('DROP FUNCTION outcome_observation_immutable()')
