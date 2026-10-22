"""Muse source in the existing installation registry, not another grants system."""
from uuid import UUID
from sqlalchemy import select
from ..engines.contract import EngineFailure
from ..engines.service import digest
from ..installation_ai.models import InstallationAIResource,InstallationAIRevision
from ..installation_ai import service
from . import muse_client as client

SOURCE_ID='44b1c517-8614-523c-8565-10a349cc6f21'
ADAPTER='muse-exec-text-v1'
MIN_CONTEXT=32768
MIN_RUN_BUDGET=65536
MIN_JOB_BUDGET=32768
NATIVE_INPUT_RESERVATION=16000


def stamp():
    value=client.read_state()
    if (not value.get('connected') or value.get('account_state')!='accountLogin'
            or value.get('binary_sha256')!=client.SHA or value.get('schema_fingerprint')!=client.SCHEMA
            or value.get('profile')!='pao_isolated' or value.get('execution_adapter')!=ADAPTER):
        raise EngineFailure('muse_source_unavailable')
    return digest({k:value.get(k) for k in ('revision','connected','account_state','binary_sha256',
        'schema_fingerprint','profile','execution_adapter','models')})


async def publish(db,uid,wid,key,disconnect=False):
    if not await service.manager(db,uid):raise EngineFailure('installation_ai_manager_revoked')
    await service.lock(db)
    row=await db.scalar(select(InstallationAIResource).where(InstallationAIResource.provider=='muse').with_for_update())
    old=await db.scalar(select(InstallationAIRevision).where(InstallationAIRevision.request_key==key))
    if old:
        if not row or old.actor_id!=uid or old.resource_id!=row.id:raise EngineFailure('installation_ai_request_conflict')
        return row
    if row and row.owner_id!=uid:raise EngineFailure('installation_ai_source_conflict')
    if disconnect:
        if row:
            row.enabled=row.is_default=False;row.revision+=1
            await service.record(db,row,uid,key,digest({'disconnect':row.revision}))
        return row
    value=client.read_state();source_stamp=stamp();catalog=value['models']
    if not catalog:raise EngineFailure('muse_source_unavailable')
    if not row:
        row=InstallationAIResource(provider='muse',owner_id=uid,source_workspace_id=wid,
            source_id=SOURCE_ID,source_kind='cli',revision=1,enabled=True,is_default=False,
            source_stamp=source_stamp,catalog=catalog,default_model=catalog[0]['model'])
        db.add(row);await db.flush()
    else:
        row.revision+=1;row.source_stamp=source_stamp;row.catalog=catalog;row.enabled=True
        if row.default_model not in {v['model'] for v in catalog}:row.default_model=catalog[0]['model']
    await service.record(db,row,uid,key,digest({'stamp':source_stamp,'revision':row.revision}),catalog_capture=True)
    return row


async def available(db,value):
    if value.get('execution_adapter')!=ADAPTER:return False
    row=await db.scalar(select(InstallationAIResource).where(InstallationAIResource.provider=='muse'))
    try:await service.ready(db,row);return True
    except EngineFailure:return False
