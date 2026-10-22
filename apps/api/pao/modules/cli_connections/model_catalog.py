"""Own-profile model metadata in the existing append-only setup journal.

Discovery is explicit and never activates inference or changes policy revision.
Each selection pins an immutable catalog record, separate from profile identity.
"""
from uuid import uuid4
from sqlalchemy import select, func
from ...models import PersonalCliRevision
from ..engines.contract import EngineFailure
from ..engines.service import digest
from ..installation_ai.catalog import normalize

VERSION = 'codex-personal-model-catalog-v1'


async def next_revision(db, wid, uid):
    # All writers hold the native Workspace row lock before allocating a number.
    return 1 + (await db.scalar(select(func.max(PersonalCliRevision.revision)).where(
        PersonalCliRevision.workspace_id == wid, PersonalCliRevision.actor_id == uid)) or 0)


async def latest(db, wid, uid, source_pin):
    row = await db.scalar(select(PersonalCliRevision).where(
        PersonalCliRevision.workspace_id == wid, PersonalCliRevision.actor_id == uid,
        PersonalCliRevision.content['version'].as_string() == VERSION,
        PersonalCliRevision.content['source_pin']['connection_id'].as_string() == source_pin['connection_id']
    ).order_by(PersonalCliRevision.revision.desc()).limit(1))
    return row if row and row.content.get('source_pin') == source_pin else None


async def capture(db, wid, uid, source_pin, choices):
    rows = normalize(choices)
    current = await latest(db, wid, uid, source_pin)
    if current and current.content['models'] == rows:
        return current
    content = {'version': VERSION, 'source_pin': source_pin, 'models': rows}
    row = PersonalCliRevision(workspace_id=wid, actor_id=uid,
        revision=await next_revision(db,wid,uid), content=content,
        request_key=str(uuid4()), fingerprint=digest(content))
    db.add(row)
    await db.flush()
    return row


def evidence(row):
    return {'version': VERSION, 'record_id': row.id, 'revision': row.revision,
            'sha256': digest(row.content)}


async def select_model(db, wid, uid, source_pin, model):
    row = await latest(db,wid,uid,source_pin)
    if not row or model not in {v['model'] for v in row.content['models']}:
        raise EngineFailure('cli_model_not_in_catalog')
    return evidence(row)


async def check(db, wid, uid, source_pin, value):
    selected = value.get('cli_model_catalog')
    if not isinstance(selected,dict) or selected.get('version') != VERSION:
        raise EngineFailure('cli_model_catalog_changed')
    row = await db.scalar(select(PersonalCliRevision).where(
        PersonalCliRevision.id == selected.get('record_id'),
        PersonalCliRevision.workspace_id == wid, PersonalCliRevision.actor_id == uid))
    if (not row or evidence(row) != selected or row.content.get('version') != VERSION
            or row.content.get('source_pin') != source_pin
            or value.get('model') not in {v['model'] for v in row.content.get('models',[])}
            or value.get('cli_pin') != {**source_pin,'model':value.get('model')}
            or value.get('reasoning_effort') is not None):
        raise EngineFailure('cli_model_catalog_changed')


async def public_catalog(db, wid, uid, source_pin):
    from ..installation_ai.modalities import metadata
    row = await latest(db,wid,uid,source_pin)
    if not row:
        return None
    # The installed Docker worker accepts model/prompt, not effort overrides.
    # Preserve upstream effort metadata in the journal without offering a no-op.
    return {'models':[v['model'] for v in row.content['models']],
        'model_details':[{'model':v['model'],'display_name':v['display_name'],
                         'reasoning_efforts':[],'default_effort':None,
                         'model_capabilities':metadata('codex_cli',v['model'])} for v in row.content['models']],
        'catalog_evidence':{'revision':row.revision,'sha256':digest(row.content['models']),
                            'scope':'caller_owned_cli','availability':'catalog_only'},
        'reasoning_control':'adapter_default'}
