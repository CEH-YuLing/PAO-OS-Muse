"""Additive Ads authority pins; existing jobs/consents remain untouched."""
from alembic import op
import sqlalchemy as sa

revision = '0052'
down_revision = '0051'
branch_labels = depends_on = None
SCOPE = "((kind='mcp' AND capability='mcp_read') OR (kind IN ('meta_ads','google_ads') AND capability='ads_read')) AND reference_revision>=1 AND grant_revision>=1 AND length(source_stamp)=64 AND length(fingerprint)=64"


def upgrade():
    op.drop_constraint('connection_read_activation_scope', 'connection_read_activations', type_='check')
    op.create_check_constraint('connection_read_activation_scope', 'connection_read_activations', SCOPE)
    op.execute("""CREATE FUNCTION pao_ads_authority_pin_guard() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP='UPDATE' AND NEW.authority_pin::text IS DISTINCT FROM OLD.authority_pin::text
      THEN RAISE EXCEPTION 'ads_authority_pin_immutable'; END IF;
      IF NEW.authority_pin IS NOT NULL AND (
        json_typeof(NEW.authority_pin)<>'object' OR NEW.kind<>'historical' OR
        NEW.authority_pin->>'source_id' IS DISTINCT FROM NEW.connection_id::text OR
        NEW.authority_pin->>'account_id' IS DISTINCT FROM NEW.account_id OR
        NEW.authority_pin->>'source_version' IS DISTINCT FROM NEW.connection_version::text OR
        NEW.authority_pin->>'capability' IS DISTINCT FROM 'ads_read' OR
        NEW.authority_pin->>'kind' IS DISTINCT FROM CASE WHEN TG_TABLE_NAME='meta_sync_jobs' THEN 'meta_ads' ELSE 'google_ads' END)
      THEN RAISE EXCEPTION 'ads_authority_pin_scope_invalid'; END IF;
      RETURN NEW;
    END $$""")
    for table in ('meta_sync_jobs', 'google_ads_sync_jobs'):
        op.add_column(table, sa.Column('authority_pin', sa.JSON(), nullable=True))
        op.execute(f'CREATE TRIGGER ads_authority_pin_guard BEFORE INSERT OR UPDATE ON {table} FOR EACH ROW EXECUTE FUNCTION pao_ads_authority_pin_guard()')


def downgrade():
    for table in ('meta_sync_jobs', 'google_ads_sync_jobs'):
        op.execute(f'DROP TRIGGER ads_authority_pin_guard ON {table}')
        op.drop_column(table, 'authority_pin')
    op.execute('DROP FUNCTION pao_ads_authority_pin_guard()')
    op.drop_constraint('connection_read_activation_scope', 'connection_read_activations', type_='check')
    op.create_check_constraint('connection_read_activation_scope', 'connection_read_activations',
        "kind='mcp' AND capability='mcp_read' AND reference_revision>=1 AND grant_revision>=1 AND length(source_stamp)=64 AND length(fingerprint)=64")
