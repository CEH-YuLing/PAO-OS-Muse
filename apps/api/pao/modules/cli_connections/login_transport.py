"""Auth-only official Codex RPC in an operator-pinned isolated profile.

No thread/turn/tools/token import. Never log stdout, stderr or device codes.
"""
import asyncio
import json
import os
import re
import tempfile
from uuid import UUID
from urllib.parse import urlsplit

from pao_cli_runtime.contracts import CliFailure
from pao_cli_runtime.docker_transport import DockerTransport, ImagePin, canonical
from pao_cli_runtime.transport import child_environment

# Fixed, server-owned bootstrap in the immutable image. No caller code/argv/env.
BOOTSTRAP="""import hashlib,os,pathlib
p=pathlib.Path('/profile/codex')
assert os.getuid()==65534 and not p.is_symlink()
p.mkdir(mode=0o700,exist_ok=True)
assert p.is_dir() and p.stat().st_uid==65534
os.chmod(p,0o700)
assert hashlib.sha256(pathlib.Path('/usr/local/bin/codex').read_bytes()).hexdigest()=='3e2584f3f3829a43a0495011a1cecb2facbe64a2403e2b682351fd9c2983f970'
os.chdir('/tmp')
os.execve('/usr/local/bin/codex',['codex','app-server'],{'HOME':'/profile','CODEX_HOME':'/profile/codex','TMPDIR':'/tmp','PATH':'/usr/local/bin:/usr/bin:/bin','LC_ALL':'C.UTF-8'})
"""


def challenge(value):
    if not isinstance(value,dict) or value.get('type')!='chatgptDeviceCode':
        raise CliFailure('cli_login_protocol_invalid')
    canonical(value.get('loginId'))
    url=urlsplit(value.get('verificationUrl',''))
    if (url.scheme!='https' or url.netloc!='auth.openai.com' or url.path!='/codex/device'
            or url.query or url.fragment or not re.fullmatch(r'[A-Z0-9]{4}-[A-Z0-9]{4,5}',value.get('userCode',''))):
        raise CliFailure('cli_login_protocol_invalid')
    return {key:value[key] for key in ('loginId','verificationUrl','userCode')}


class LoginTransport:
    def __init__(self,pin,operation,authorize=None):
        canonical(operation)
        self.pin=pin
        self.authorize=authorize
        self.operation=operation
        self.image=ImagePin(pin['runtime_image_id'],pin['binary_sha256'],pin['binary_version'])
        self.docker=DockerTransport(self.image)
        self.name='pao-cli-ui-login-'+UUID(operation).hex
        self.process=None
        self.temporary=None
        self.stderr_task=None
        self.cleanup_verified=False
        self.started=False
        self.login_id=None
        self.notifications=[]
        self.bytes=0
        self.lines=0

    async def open(self):
        if self.authorize is None:raise CliFailure('cli_login_authority_required')
        await self.authorize()
        self.temporary=tempfile.TemporaryDirectory(prefix='pao-codex-login-')
        self.env=child_environment(self.temporary.name)
        self.env['DOCKER_CONFIG']=self.temporary.name
        volume=await self.docker.check_profile(self.pin,self.env)
        labels=['--label','pao.cli.login_operation_id='+self.operation]
        for key in ('workspace_id','actor_id','connection_id','device_id','profile_id'):
            labels+=['--label','pao.cli.'+key+'='+canonical(self.pin.get(key))]
        self.started=True
        raw=await self.docker.command(['create','--interactive','--pull=never','--name',self.name,*labels,
            '--network=bridge','--read-only','--tmpfs','/tmp:rw,noexec,nosuid,size=64m',
            '--cap-drop=ALL','--security-opt=no-new-privileges','--pids-limit=32','--memory=512m','--cpus=1',
            '--user=65534:65534','--mount','type=volume,source='+volume+',target=/profile',
            '--env','HOME=/profile','--env','CODEX_HOME=/profile/codex',
            '--entrypoint=python',self.image.image_id,'-B','-c',BOOTSTRAP],self.env)
        cid=raw.decode('ascii').strip()
        if not re.fullmatch(r'[0-9a-f]{64}',cid):raise CliFailure('cli_login_container_invalid')
        self.process=await asyncio.create_subprocess_exec(*self.docker.docker(),'start','--attach','--interactive',cid,
            stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,
            limit=131072,env=self.env,**({'creationflags':0x08000000} if os.name=='nt' else {}))
        self.stderr_task=asyncio.create_task(self.discard_stderr())
        await self.rpc(1,'initialize',{'clientInfo':{'name':'pao_local','title':'PAO local','version':'0.1.0'}})
        await self.send({'method':'initialized'})

    async def discard_stderr(self):
        size=0
        while chunk:=await self.process.stderr.read(4096):
            size+=len(chunk)
            if size>262144:raise CliFailure('cli_login_output_limit')

    async def send(self,value):
        self.process.stdin.write((json.dumps(value,separators=(',',':'))+'\n').encode())
        await self.process.stdin.drain()

    async def receive(self):
        raw=await self.process.stdout.readline()
        self.bytes+=len(raw);self.lines+=1
        if not raw or len(raw)>131072 or self.bytes>1048576 or self.lines>5000:
            raise CliFailure('cli_login_output_limit')
        value=json.loads(raw)
        if not isinstance(value,dict) or ('method' in value and 'id' in value):
            raise CliFailure('cli_login_protocol_invalid')
        if self.stderr_task.done():self.stderr_task.result()
        return value

    async def rpc(self,number,method,params):
        if method not in ('initialize','account/read','account/login/start'):
            raise CliFailure('cli_login_method_denied')
        if self.authorize is None:raise CliFailure('cli_login_authority_required')
        await self.authorize()
        await self.send({'id':number,'method':method,'params':params})
        async with asyncio.timeout(30):
            while True:
                value=await self.receive()
                if value.get('id')==number:
                    if 'error' in value or not isinstance(value.get('result'),dict):
                        raise CliFailure('cli_login_provider_failed')
                    return value['result']
                self.notification(value)

    def notification(self,value):
        if value.get('method')=='account/login/completed':
            params=value.get('params')
            if not isinstance(params,dict) or type(params.get('success')) is not bool:
                raise CliFailure('cli_login_protocol_invalid')
            if len(self.notifications)>=8:raise CliFailure('cli_login_output_limit')
            self.notifications.append({'loginId':params.get('loginId'),'success':params['success']})

    async def authenticate(self,publish):
        await self.open()
        value=await self.rpc(2,'account/read',{'refreshToken':False})
        account=value.get('account')
        if account is not None:
            if not isinstance(account,dict) or account.get('type')!='chatgpt':
                raise CliFailure('cli_login_subscription_required')
            return
        data=challenge(await self.rpc(3,'account/login/start',{'type':'chatgptDeviceCode'}))
        self.login_id=data['loginId']
        await publish(data)
        while True:
            if self.notifications:
                completed=self.notifications.pop(0)
                if completed['loginId']!=self.login_id:raise CliFailure('cli_login_protocol_invalid')
                if not completed['success']:raise CliFailure('cli_login_provider_failed')
                break
            self.notification(await self.receive())
        value=await self.rpc(4,'account/read',{'refreshToken':False})
        if not isinstance(value.get('account'),dict) or value['account'].get('type')!='chatgpt':
            raise CliFailure('cli_login_subscription_required')

    async def close(self):
        # Fixed name + exact image/scope labels; never touch a different process.
        try:
            if self.started:
                raw=(await self.docker.command(['ps','--all','--quiet','--no-trunc','--filter','name=^/'+self.name+'$'],self.env)).decode('ascii').strip()
                if raw:
                    if not re.fullmatch(r'[0-9a-f]{64}',raw):raise CliFailure('cli_login_cleanup_required')
                    info=json.loads(await self.docker.command(['inspect',raw],self.env))[0]
                    labels=info['Config'].get('Labels') or {}
                    expected={'pao.cli.login_operation_id':self.operation,**{'pao.cli.'+key:self.pin[key] for key in ('workspace_id','actor_id','connection_id','device_id','profile_id')}}
                    if info['Id']!=raw or info['Name']!='/'+self.name or info['Image']!=self.image.image_id or any(labels.get(k)!=v for k,v in expected.items()):
                        raise CliFailure('cli_login_cleanup_required')
                    await self.docker.command(['rm','--force',raw],self.env)
                if (await self.docker.command(['ps','--all','--quiet','--filter','name=^/'+self.name+'$'],self.env)).strip():
                    raise CliFailure('cli_login_cleanup_required')
            self.cleanup_verified=True
        finally:
            if self.stderr_task:
                self.stderr_task.cancel()
                await asyncio.gather(self.stderr_task,return_exceptions=True)
            if self.process:
                if self.process.returncode is None:self.process.kill()
                await asyncio.wait_for(self.process.communicate(),5)
            if self.temporary:self.temporary.cleanup()

    async def recover(self):
        self.temporary=tempfile.TemporaryDirectory(prefix='pao-codex-login-recover-')
        self.env=child_environment(self.temporary.name);self.env['DOCKER_CONFIG']=self.temporary.name
        await self.docker.check_profile(self.pin,self.env)
        self.started=True
        await self.close()
