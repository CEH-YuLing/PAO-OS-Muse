"""Short-lived auth ceremonies, not a model/job runner. DB fence survives restart."""
import asyncio
from dataclasses import dataclass,field
import time
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from ...auth import check_session
from ...db import Session
from ...models import CliModelConnection,now
from . import runtime
from .login_transport import LoginTransport

MAX_SECONDS=600


@dataclass(repr=False)
class Ceremony:
    operation:str
    workspace:str
    actor:str
    connection:str
    session:str
    original_version:int
    version:int
    who:object=field(repr=False)
    pin:dict=field(repr=False)
    config:dict=field(repr=False)
    state:str='starting'
    code:str|None=field(default=None,repr=False)
    url:str|None=None
    created:float=field(default_factory=time.monotonic)
    task:object=None
    transport:object=None

    def view(self,who):
        same=who.token_hash==self.session
        return {'operation_id':self.operation,'connection_id':self.connection,'version':self.version,
            'status':self.state if same else 'another_session',
            'verification_url':self.url if same and self.state=='awaiting_user' else None,
            'user_code':self.code if same and self.state=='awaiting_user' else None,
            'expires_in':max(0,int(MAX_SECONDS-(time.monotonic()-self.created))),
            'provider_inference_verified':False,'grant_activated':False}


class LoginManager:
    def __init__(self):self.entries={}

    def capacity(self):
        self.entries={k:v for k,v in self.entries.items() if not v.task or not v.task.done() or time.monotonic()-v.created<900}
        if len(self.entries)>=32 or sum(bool(v.task and not v.task.done()) for v in self.entries.values())>=4:
            raise HTTPException(429,'cli_login_capacity')

    async def authority(self,item):
        from .api import managed
        async with Session.begin() as db:
            await check_session(db,item.who)
            row=await managed(db,item.workspace,item.who,item.connection,item.version)
            if row.setup_operation_id!=item.operation or runtime.device_config()!=item.config:
                raise HTTPException(409,'cli_login_scope_changed')
            return row

    async def start(self,db,row,who,version,operation,config):
        previous=self.entries.get(operation)
        if previous:
            if (previous.workspace,previous.actor,previous.connection,previous.session,previous.original_version)!=(row.workspace_id,who.id,row.id,who.token_hash,version):
                raise HTTPException(409,'cli_login_request_conflict')
            return previous.view(who)
        if row.version!=version:raise HTTPException(409,'cli_connection_version_conflict')
        if row.setup_operation_id:raise HTTPException(409,'cli_login_recovery_required')
        if row.status=='connected':raise HTTPException(409,'cli_disconnect_before_auth_change')
        if row.device_id!=config['device_id'] or (row.runtime_image_id,row.binary_sha256,row.binary_version)!=(config['image_id'],config['binary_sha256'],config['binary_version']):
            raise HTTPException(409,'cli_profile_prepare_required')
        self.capacity()
        pin={key:getattr(row,source) for key,source in (('workspace_id','workspace_id'),('actor_id','owner_id'),('connection_id','id'),('profile_id','profile_id'),('device_id','device_id'),('runtime_image_id','runtime_image_id'),('binary_sha256','binary_sha256'),('binary_version','binary_version'))}
        row.setup_operation_id=operation;row.version+=1;row.status='pending';row.auth_checked_at=None
        item=Ceremony(operation,row.workspace_id,who.id,row.id,who.token_hash,version,row.version,who,pin,config)
        await db.commit()
        self.entries[operation]=item
        item.task=asyncio.create_task(self.run(item))
        return item.view(who)

    async def run(self,item):
        transport=LoginTransport(item.pin,item.operation,lambda:self.authority(item));item.transport=transport
        async def publish(data):
            await self.authority(item)
            item.url,item.code,item.state=data['verificationUrl'],data['userCode'],'awaiting_user'
        async def watch():
            while True:
                await asyncio.sleep(1)
                await self.authority(item)
        job=guard=None
        outcome='failed'
        try:
            await self.authority(item)
            job=asyncio.create_task(transport.authenticate(publish));guard=asyncio.create_task(watch())
            async with asyncio.timeout(MAX_SECONDS):
                done,_=await asyncio.wait([job,guard],return_when=asyncio.FIRST_COMPLETED)
                for task in done:task.result()
                if job not in done:raise HTTPException(409,'cli_login_authority_changed')
                await self.authority(item)
                outcome='connected'
        except asyncio.CancelledError:outcome='cancelled'
        except TimeoutError:outcome='expired'
        except Exception:outcome='failed'
        finally:
            item.code=item.url=None
            for task in (job,guard):
                if task:task.cancel()
            await asyncio.gather(*[x for x in (job,guard) if x],return_exceptions=True)
            try:await transport.close()
            except Exception:outcome='cleanup_required'
            if transport.cleanup_verified:
                try:
                    from .api import managed
                    async with Session.begin() as db:
                        row=await db.scalar(select(CliModelConnection).where(CliModelConnection.id==item.connection,CliModelConnection.workspace_id==item.workspace,CliModelConnection.setup_operation_id==item.operation).with_for_update())
                        if row:
                            if outcome=='connected':
                                try:
                                    await check_session(db,item.who)
                                    await managed(db,item.workspace,item.who,item.connection,item.version)
                                    if runtime.device_config()!=item.config:raise ValueError()
                                except Exception:outcome='failed'
                            row.setup_operation_id=None
                            if row.version==item.version:
                                row.status='connected' if outcome=='connected' else 'error'
                                row.auth_checked_at=now() if outcome=='connected' else None
                                row.version+=1;item.version=row.version
                            else:outcome='cancelled'
                        else:outcome='cancelled'
                except Exception:outcome='cleanup_required'
            else:outcome='cleanup_required'
            item.state=outcome

    async def cancel(self,item):
        if item.task and not item.task.done():
            item.task.cancel()
            await asyncio.shield(item.task)

    async def close(self):
        tasks=[self.cancel(item) for item in self.entries.values() if item.task and not item.task.done()]
        if tasks:await asyncio.gather(*tasks,return_exceptions=True)
