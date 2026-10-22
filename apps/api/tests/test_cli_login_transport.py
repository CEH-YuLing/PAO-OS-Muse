"""Auth-only RPC/cancellation containment, all subprocess pipes synthetic."""
import asyncio
import json
from uuid import uuid4
import pytest
from pao.modules.cli_connections.login_transport import LoginTransport


@pytest.fixture
def wire(monkeypatch):
    pin={key:str(uuid4()) for key in ('workspace_id','actor_id','connection_id','device_id','profile_id')}
    pin.update(runtime_image_id='sha256:'+'a'*64,binary_sha256='3e2584f3f3829a43a0495011a1cecb2facbe64a2403e2b682351fd9c2983f970',binary_version='0.157.1')
    state={'methods':[],'commands':[],'removed':False,'authorized':0,'cached':False,'api_key':False,'foreign':False,'login_id':str(uuid4())}
    async def authorized():state['authorized']+=1
    transport=LoginTransport(pin,str(uuid4()),authorized)
    class Process:
        returncode=None
        def __init__(self):
            self.stdout=asyncio.StreamReader();self.stderr=asyncio.StreamReader();self.stderr.feed_eof();self.stdin=self
        def write(self,data):
            value=json.loads(data);method=value['method'];state['methods'].append(method)
            if 'id' not in value:return
            result={}
            if method=='account/read':result={'account':{'type':'apiKey'} if state['api_key'] else {'type':'chatgpt'} if state['cached'] or value['id']==4 else None}
            if method=='account/login/start':result={'type':'chatgptDeviceCode','loginId':state['login_id'],'verificationUrl':'https://auth.openai.com/codex/device','userCode':'ABCD-EFGH'}
            self.stdout.feed_data((json.dumps({'id':value['id'],'result':result})+'\n').encode())
            if method=='account/login/start':self.stdout.feed_data((json.dumps({'method':'account/login/completed','params':{'loginId':state['login_id'],'success':True}})+'\n').encode())
        async def drain(self):pass
        def kill(self):self.returncode=0
        async def communicate(self):return b'',b''
    async def spawn(*args,**kwargs):
        assert kwargs['env'].get('OPENAI_API_KEY') is None and kwargs['env']['DOCKER_CONFIG']!=str(__file__)
        return Process()
    async def check(pin,env):return 'pao-cli-profile-'+pin['profile_id'].replace('-','')
    async def command(args,env,timeout=15):
        state['commands'].append(args)
        if args[0]=='create':
            for flag in ('--interactive','--read-only','--network=bridge','--cap-drop=ALL','--security-opt=no-new-privileges','--user=65534:65534'):assert flag in args
            from pao.modules.cli_connections.login_transport import BOOTSTRAP
            assert args[-1]==BOOTSTRAP and args[-4]==pin['runtime_image_id'] and '--entrypoint=python' in args
            assert not any('type=bind' in x for x in args)
            return ('a'*64).encode()
        if args[0]=='ps':return b'' if state['removed'] else ('a'*64).encode()
        if args[0]=='inspect':
            labels={'pao.cli.login_operation_id':transport.operation,**{'pao.cli.'+key:pin[key] for key in ('workspace_id','actor_id','connection_id','device_id','profile_id')}}
            return json.dumps([{'Id':'a'*64,'Name':'/'+transport.name,'Image':'sha256:'+'b'*64 if state['foreign'] else pin['runtime_image_id'],'Config':{'Labels':labels}}]).encode()
        assert args==['rm','--force','a'*64];state['removed']=True;return b''
    monkeypatch.setattr(asyncio,'create_subprocess_exec',spawn)
    monkeypatch.setattr(transport.docker,'check_profile',check)
    monkeypatch.setattr(transport.docker,'command',command)
    return transport,state


async def test_official_auth_only_methods_and_complete_cleanup(wire):
    transport,state=wire;published=[]
    async def publish(value):published.append(value)
    try:
        await transport.authenticate(publish)
        assert len(published)==1 and set(published[0])=={'loginId','verificationUrl','userCode'}
        assert state['methods']==['initialize','initialized','account/read','account/login/start','account/read']
        assert state['authorized']==5
    finally:await transport.close()
    assert transport.cleanup_verified and state['removed']


async def test_existing_own_profile_uses_chatgpt_without_login_or_token_import(wire):
    transport,state=wire;state['cached']=True
    async def forbidden(value):raise AssertionError('Cached profile must not start login')
    try:await transport.authenticate(forbidden)
    finally:await transport.close()
    assert 'account/login/start' not in state['methods']


async def test_api_key_auth_is_not_silently_used_as_subscription(wire):
    transport,state=wire;state['api_key']=True
    async def publish(value):raise AssertionError()
    try:
        with pytest.raises(Exception):await transport.authenticate(publish)
    finally:await transport.close()
    assert 'account/login/start' not in state['methods']


async def test_cleanup_refuses_other_image_and_rpc_refuses_tools(wire):
    transport,state=wire
    await transport.open()
    with pytest.raises(Exception):await transport.rpc(99,'turn/start',{})
    state['foreign']=True
    with pytest.raises(Exception):await transport.close()
    assert not transport.cleanup_verified and not state['removed']
