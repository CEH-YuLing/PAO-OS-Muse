"""Owned Muse profile and official device-login host. Never reads credentials.

This host only admits metadata/auth methods: no session/start or turn/start.
Native login material is written by Muse into its own private runtime profile.
"""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import time
from urllib.parse import urlsplit
from uuid import uuid4

from ...config import ROOT

PROFILE = ROOT / '.runtime/muse-profile'
_active = None
_lock = asyncio.Lock()
ALLOWED = {'initialize','account/read','model/list','account/loginStart','account/loginCancel'}


class ProfileFailure(RuntimeError):
    pass


def environment():
    # Process-only configuration, supported by the SDK profile convention.
    # Do not repoint the existing user's profile, copy auth files or export keys.
    for path in (PROFILE,*PROFILE.parents):
        if path.is_symlink() or path.is_junction(): raise ProfileFailure('muse_profile_linked')
    dirs = {'HOME':PROFILE,'USERPROFILE':PROFILE,'APPDATA':PROFILE/'AppData/Roaming',
        'LOCALAPPDATA':PROFILE/'AppData/Local','XDG_CONFIG_HOME':PROFILE/'.config',
        'XDG_DATA_HOME':PROFILE/'.local/share','MUSE_HOME':PROFILE/'.local/share/muse',
        'TEMP':PROFILE/'tmp','TMP':PROFILE/'tmp'}
    env = {k:os.environ[k] for k in ('SystemRoot','WINDIR','PATH','USERNAME','USERDOMAIN') if k in os.environ}
    for key,path in dirs.items():
        for parent in (path,*path.parents):
            if parent.is_symlink() or parent.is_junction(): raise ProfileFailure('muse_profile_linked')
        path.mkdir(parents=True,exist_ok=True)
        env[key] = str(path)
    env['NO_COLOR'] = '1'
    return env


class Host:
    def __init__(self, binary, schema):
        self.binary,self.schema = binary,schema
        self.process = self.stderr_task = None
        self.ordinal = 0

    async def open(self):
        env = environment()
        cwd = PROFILE/'metadata-workspace'
        cwd.mkdir(exist_ok=True)
        if cwd.is_symlink() or cwd.is_junction(): raise ProfileFailure('muse_profile_linked')
        self.process = await asyncio.create_subprocess_exec(str(self.binary),'serve','--provider','meta',
            '--no-session-log','--disable-write','--disable-shell','--disable-request-user-input',
            cwd=cwd,env=env,stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,limit=262144,creationflags=subprocess.CREATE_NO_WINDOW)
        async def drain():
            total = 0
            while chunk := await self.process.stderr.read(4096):
                total += len(chunk)
                if total > 262144: raise ProfileFailure('muse_output_limit')
        self.stderr_task = asyncio.create_task(drain())
        init = await self.query('initialize',{'clientInfo':{'name':'pao_muse_profile','version':'1'},
            'capabilities':{'experimentalApi':True,'userInputDialogs':False}})
        if init.get('schema',{}).get('fingerprint') != self.schema:
            raise ProfileFailure('muse_schema_changed')
        home = init.get('museHome')
        if not isinstance(home,str) or not Path(home).resolve().is_relative_to(PROFILE.resolve()):
            raise ProfileFailure('muse_profile_not_isolated')
        await self.send({'jsonrpc':'2.0','method':'initialized','params':{}})
        return self

    async def send(self, value):
        self.process.stdin.write(json.dumps(value,separators=(',',':')).encode()+b'\n')
        await self.process.stdin.drain()

    async def query(self, method, params=None):
        if method not in ALLOWED: raise ProfileFailure('muse_method_not_admitted')
        self.ordinal += 1
        key = self.ordinal
        async with asyncio.timeout(20):
            await self.send({'jsonrpc':'2.0','id':key,'method':method,'params':params or {}})
            total = 0
            for _ in range(32):
                if self.stderr_task and self.stderr_task.done(): await self.stderr_task
                raw = await self.process.stdout.readline()
                total += len(raw)
                if not raw or total>262144: raise ProfileFailure('muse_protocol_invalid')
                value = json.loads(raw)
                if not isinstance(value,dict) or value.get('jsonrpc')!='2.0': raise ProfileFailure('muse_protocol_invalid')
                if 'method' in value:
                    if 'id' not in value and value['method'] in ('account/changed','account/loginCompleted','usage/changed'):
                        continue
                    raise ProfileFailure('muse_unexpected_request')
                if value.get('id')!=key or 'error' in value: raise ProfileFailure('muse_metadata_rejected')
                result = value.get('result')
                if not isinstance(result,dict): raise ProfileFailure('muse_protocol_invalid')
                return result
            raise ProfileFailure('muse_output_limit')

    async def close(self):
        if self.process and self.process.returncode is None:
            self.process.kill()
            await asyncio.shield(asyncio.wait_for(self.process.wait(),5))
        if self.stderr_task:
            self.stderr_task.cancel()
            await asyncio.gather(self.stderr_task,return_exceptions=True)


def login_view(flow, actor):
    if not flow or flow['actor']!=actor:
        return {'status':'none','profile':'pao_isolated','credentials_stored_in_PAO':False}
    result = {k:flow[k] for k in ('status','id')}
    if flow['status']=='pending':
        result.update(verification_url=flow['url'],user_code=flow['code'])
    return {**result,'profile':'pao_isolated','credentials_stored_in_PAO':False}


async def start_login(actor, binary, schema):
    global _active
    async with _lock:
        if _active and _active['status']=='pending':
            if _active['actor']!=actor: raise ProfileFailure('muse_login_busy')
            return login_view(_active,actor)
        host = Host(binary,schema)
        try:
            await host.open()
            state = await host.query('account/read')
            if state.get('state')=='accountLogin':
                await host.close()
                _active = {'actor':actor,'id':str(uuid4()),'status':'granted'}
                return login_view(_active,actor)
            if state.get('state')!='loggedOut': raise ProfileFailure('muse_profile_account_not_subscription_login')
            result = await host.query('account/loginStart',{'type':'deviceCode'})
            url,code = result.get('verificationUrl'),result.get('userCode')
            if not isinstance(url,str) or not isinstance(code,str) or not 1<=len(code)<=64:
                raise ProfileFailure('muse_login_invalid')
            parsed = urlsplit(url)
            if (parsed.scheme!='https' or parsed.hostname not in
                    ('auth.meta.com','www.meta.com','meta.com','dev.meta.ai','accountscenter.meta.com','www.facebook.com')
                    or parsed.username or parsed.password or parsed.port not in (None,443)):
                raise ProfileFailure('muse_login_invalid')
            flow = {'actor':actor,'id':str(uuid4()),'status':'pending','url':url,'code':code,'host':host}
            _active = flow
            async def wait():
                try:
                    deadline = time.monotonic()+600
                    while time.monotonic()<deadline and flow['status']=='pending':
                        await asyncio.sleep(2)
                        value = await host.query('account/read')
                        if value.get('state')=='accountLogin':
                            flow['status']='granted'
                            break
                    if flow['status']=='pending': flow['status']='expired'
                except asyncio.CancelledError:
                    flow['status']='cancelled'
                    raise
                except (ProfileFailure,OSError,ValueError,TimeoutError):
                    flow['status']='failed'
                finally:
                    flow.pop('url',None);flow.pop('code',None)
                    await host.close()
            flow['task'] = asyncio.create_task(wait())
            return login_view(flow,actor)
        except BaseException:
            await host.close()
            raise


async def cancel_login(actor=None):
    if _active and (actor is None or _active['actor']==actor) and _active.get('task'):
        task = _active['task']
        if not task.done(): task.cancel()
        await asyncio.gather(task,return_exceptions=True)
        # A task cancelled before its first instruction never enters `finally`.
        # Always close the exact host owned by this flow as well.
        if _active.get('host'): await _active['host'].close()


def status(actor):
    return login_view(_active,actor)
