"""Append generations; no credential/history rewrite or implicit consent."""
import ast
from pathlib import Path
from alembic import op
import sqlalchemy as sa

revision='0053'
down_revision='0052'
branch_labels=depends_on=None


def original_guard():
    # Reuse the exact immutable baseline body for an exact-schema downgrade.
    tree=ast.parse(Path(__file__).with_name('0049_tenant_connection_grants.py').read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if isinstance(node,ast.Call) and node.args and isinstance(node.args[0],ast.Constant):
            value=node.args[0].value
            if isinstance(value,str) and value.startswith('CREATE FUNCTION pao_tenant_connection_reference_guard()'):
                return value.replace('CREATE FUNCTION','CREATE OR REPLACE FUNCTION',1)
    raise RuntimeError('Immutable baseline reference guard missing')


def upgrade():
    table='tenant_connection_references'
    op.add_column(table,sa.Column('generation',sa.Integer(),nullable=False,server_default='1'))
    op.add_column(table,sa.Column('supersedes_id',sa.Uuid(as_uuid=False),nullable=True))
    op.drop_constraint('tenant_connection_references_workspace_id_kind_source_id_key',table,type_='unique')
    op.create_unique_constraint('tenant_reference_generation_identity',table,['workspace_id','kind','source_id','generation'])
    op.create_foreign_key('tenant_reference_generation_parent',table,table,
        ['supersedes_id','workspace_id'],['id','workspace_id'])
    op.create_check_constraint('tenant_reference_generation_state',table,
        "(generation=1 AND supersedes_id IS NULL) OR (generation>1 AND supersedes_id IS NOT NULL)")
    guard=original_guard().replace('NEW.source_version,NEW.source_stamp)',
        'NEW.source_version,NEW.source_stamp,NEW.generation,NEW.supersedes_id)').replace(
        'OLD.source_version,OLD.source_stamp)','OLD.source_version,OLD.source_stamp,OLD.generation,OLD.supersedes_id)')
    guard=guard.replace('      CASE NEW.kind',"""      IF NEW.generation=1 THEN
        IF NEW.supersedes_id IS NOT NULL OR EXISTS (SELECT 1 FROM tenant_connection_references
          WHERE workspace_id=NEW.workspace_id AND kind=NEW.kind AND source_id=NEW.source_id)
        THEN RAISE EXCEPTION 'tenant_reference_generation_invalid'; END IF;
      ELSE
        IF NOT EXISTS (SELECT 1 FROM tenant_connection_references r WHERE r.id=NEW.supersedes_id
          AND r.workspace_id=NEW.workspace_id AND r.kind=NEW.kind AND r.source_id=NEW.source_id
          AND r.manager_id=NEW.manager_id AND r.provider=NEW.provider AND r.status='revoked'
          AND r.generation=NEW.generation-1)
          OR EXISTS (SELECT 1 FROM tenant_connection_references r WHERE r.workspace_id=NEW.workspace_id
            AND r.kind=NEW.kind AND r.source_id=NEW.source_id AND (r.status<>'revoked' OR r.generation>=NEW.generation))
        THEN RAISE EXCEPTION 'tenant_reference_generation_invalid'; END IF;
      END IF;
      CASE NEW.kind""")
    op.execute(guard)


def downgrade():
    # Never destroy append-only history to make a downgrade green.
    if op.get_bind().scalar(sa.text('SELECT count(*) FROM tenant_connection_references WHERE generation>1')):
        raise RuntimeError('Downgrade refused: connection generation history must be preserved')
    op.execute(original_guard())
    table='tenant_connection_references'
    op.drop_constraint('tenant_reference_generation_parent',table,type_='foreignkey')
    op.drop_constraint('tenant_reference_generation_state',table,type_='check')
    op.drop_constraint('tenant_reference_generation_identity',table,type_='unique')
    op.drop_column(table,'supersedes_id');op.drop_column(table,'generation')
    op.create_unique_constraint('tenant_connection_references_workspace_id_kind_source_id_key',table,['workspace_id','kind','source_id'])
