"""Explicit model inference consent; B1 staged history remains unchanged."""
from alembic import op
import sqlalchemy as sa

revision = '0050'
down_revision = '0049'
branch_labels = depends_on = None


def upgrade():
    op.create_table('model_grant_activations',
        sa.Column('id', sa.Uuid(as_uuid=False), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('workspace_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('grant_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('actor_id', sa.Uuid(as_uuid=False), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('reference_revision', sa.Integer(), nullable=False),
        sa.Column('grant_revision', sa.Integer(), nullable=False),
        sa.Column('source_stamp', sa.String(64), nullable=False),
        sa.Column('capability', sa.String(24), nullable=False),
        sa.Column('request_key', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('fingerprint', sa.String(64), nullable=False),
        sa.UniqueConstraint('grant_id'),
        sa.UniqueConstraint('workspace_id', 'actor_id', 'request_key'),
        sa.ForeignKeyConstraint(['grant_id', 'workspace_id'], ['tenant_connection_grants.id', 'tenant_connection_grants.workspace_id']),
        sa.CheckConstraint("capability='model_inference' AND reference_revision>=1 AND grant_revision>=1 AND length(source_stamp)=64 AND length(fingerprint)=64", name='model_grant_activation_scope'))
    op.execute("""CREATE FUNCTION pao_model_grant_activation_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP<>'INSERT' THEN RAISE EXCEPTION 'model_grant_activation_immutable'; END IF;
      IF NOT EXISTS (SELECT 1 FROM tenant_connection_grants g
        JOIN tenant_connection_references r ON r.id=g.reference_id AND r.workspace_id=g.workspace_id
        JOIN workspace_members m ON m.workspace_id=r.workspace_id AND m.user_id=r.manager_id
        JOIN users u ON u.id=m.user_id
        JOIN workspace_members gm ON gm.workspace_id=g.workspace_id AND gm.user_id=g.grantee_id
        JOIN users gu ON gu.id=gm.user_id
        WHERE g.id=NEW.grant_id AND g.workspace_id=NEW.workspace_id AND g.status='staged'
        AND g.revision=NEW.grant_revision AND g.expires_at>clock_timestamp()
        AND r.status='staged' AND r.kind='model' AND r.manager_id=NEW.actor_id
        AND r.revision=NEW.reference_revision AND g.reference_revision=r.revision
        AND r.source_stamp=NEW.source_stamp AND m.role IN ('owner','admin') AND u.active
        AND gm.role IN ('owner','admin','operator','analyst') AND gu.active)
      THEN RAISE EXCEPTION 'model_grant_activation_scope_invalid'; END IF;
      RETURN NEW;
    END $$""")
    op.execute('CREATE TRIGGER model_grant_activation_guard BEFORE INSERT OR UPDATE OR DELETE ON model_grant_activations FOR EACH ROW EXECUTE FUNCTION pao_model_grant_activation_guard()')


def downgrade():
    op.drop_table('model_grant_activations')
    op.execute('DROP FUNCTION pao_model_grant_activation_guard()')
