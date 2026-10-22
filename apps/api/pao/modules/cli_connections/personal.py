"""Self-only authority, consented at setup and rechecked natively per call."""
from sqlalchemy import select
from ...models import PersonalCliPolicy,Workspace,User,Brand
from ..engines.contract import EngineFailure
from ..engines.service import digest
from ..connections.enterprise_ai import actor
from . import service
VERSION='ea21-personal-cli-v1'

async def policy(db,wid,uid):
    return await db.scalar(select(PersonalCliPolicy).where(PersonalCliPolicy.workspace_id==wid,
        PersonalCliPolicy.actor_id==uid).execution_options(populate_existing=True))

async def principal_state(db,wid,uid):
    epoch=await db.scalar(select(Workspace.lifecycle_version).where(Workspace.id==wid).with_for_update(read=True,key_share=True))
    member=await actor(db,wid,uid,managing=True)
    version=await db.scalar(select(User.auth_version).where(User.id==uid))
    return epoch,version,member.role

async def pin(db,wid,uid,brand=None,connection=None):
    epoch,auth,role=await principal_state(db,wid,uid)
    if brand and not await db.scalar(select(Brand.id).where(Brand.id==brand,Brand.workspace_id==wid)):
        raise EngineFailure('personal_cli_access_denied')
    row=await policy(db,wid,uid)
    if not row or row.content.get('enabled') is not True or row.content.get('version')!=VERSION:
        raise EngineFailure('personal_cli_not_enabled')
    content=row.content;source_pin=content.get('source_pin')
    if (content.get('membership_epoch')!=epoch or content.get('auth_version')!=auth or not isinstance(source_pin,dict)
            or connection is not None and source_pin.get('connection_id')!=connection):
        raise EngineFailure('personal_cli_setup_changed')
    source=await service.source(db,wid,uid,source_pin.get('connection_id'))
    if service.pin(source)!=source_pin:raise EngineFailure('personal_cli_setup_changed')
    return {'version':VERSION,'mode':'personal_cli','source_kind':'cli_model','workspace_id':wid,
        'actor_id':uid,'actor_role':role,'brand_id':brand,'membership_epoch':epoch,'auth_version':auth,
        'policy_id':row.id,'policy_revision':row.revision,'source_id':source.id,
        'source_stamp':digest(source_pin),'capability':'model_inference'}

async def config(db,wid,uid,brand=None,connection=None,model=None):
    authority=await pin(db,wid,uid,brand,connection)
    row=await policy(db,wid,uid);selected=dict(row.content['source_pin'])
    value={'provider':'codex_cli','model':selected['model'],'connection_id':authority['source_id'],
        'connection_authority':authority,'cli_pin':selected}
    if model is not None and model != selected['model']:
        from .model_catalog import select_model
        value['cli_model_catalog']=await select_model(db,wid,uid,selected,model)
        value['model']=model
        value['cli_pin']={**selected,'model':model}
    return value

async def default_config(db,wid,uid,brand=None):
    row=await policy(db,wid,uid)
    if row and row.content.get('enabled') is True and row.content.get('make_default') is True:
        return await config(db,wid,uid,brand)  # Invalid default never silently falls back.
    return None

async def check(db,run,chat,value):
    selected=value.get('connection_authority')
    brand=(run.brain_context or {}).get('brand_id') if run.brain_id else chat.brand_id
    current=await pin(db,run.workspace_id,chat.user_id,brand,value.get('connection_id'))
    if current!=selected or value.get('provider')!='codex_cli':raise EngineFailure('personal_cli_setup_changed')
    if run.brain_id:
        from ..brains.context import check_run_brain
        await check_run_brain(db,run,chat)
