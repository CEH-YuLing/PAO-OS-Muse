"""Candidate-only native profile binding and secret-free auth status parsing.

No credential reader, provider request or PAO authority is implemented here.
Reservations are not enrolled connections and cannot dispatch inference.
"""
from dataclasses import dataclass
import re
from uuid import UUID
from .claude_plan import VERSION,uuid
from .protocols import AdapterFailure,_object

STAGE='ea3-personal-candidate-v1'

@dataclass(frozen=True)
class Profile:
    workspace_id:str
    actor_id:str
    connection_id:str
    device_id:str
    profile_id:str
    image_id:str
    binary_sha256:str
    binary_version:str

    def __post_init__(self):
        for key in ('workspace_id','actor_id','connection_id','device_id','profile_id'):uuid(getattr(self,key))
        if (not isinstance(self.image_id,str) or not re.fullmatch(r'sha256:[0-9a-f]{64}',self.image_id)
                or not isinstance(self.binary_sha256,str) or not re.fullmatch(r'[0-9a-f]{64}',self.binary_sha256)
                or self.binary_version!=VERSION):raise AdapterFailure('adapter_contract_invalid')

    @property
    def volume(self):return 'pao-claude-profile-'+UUID(self.profile_id).hex

    @property
    def labels(self):
        return {'pao.claude.'+k:getattr(self,k) for k in ('workspace_id','actor_id','connection_id','device_id','profile_id')}

    def check_volume(self,info):
        if (not isinstance(info,dict) or info.get('Name')!=self.volume or info.get('Driver')!='local'
                or info.get('Options') or info.get('Labels')!=self.labels):
            raise AdapterFailure('adapter_contract_invalid')

    def check_image(self,info):
        if (not isinstance(info,dict) or info.get('Id')!=self.image_id
                or info.get('Config',{}).get('User')!='65534:65534'
                or info.get('Config',{}).get('Labels',{}).get('pao.claude.binary-sha256')!=self.binary_sha256
                or info.get('Config',{}).get('Labels',{}).get('pao.claude.version')!=self.binary_version):
            raise AdapterFailure('adapter_contract_invalid')

    def command(self,operation,action):
        uuid(operation)
        if action not in ('login','status'):raise AdapterFailure('adapter_live_disabled')
        args=['create','--pull=never','--label','pao.claude.operation_id='+operation,
              '--network=bridge' if action=='login' else '--network=none',
              '--read-only','--tmpfs','/tmp:rw,noexec,nosuid,size=128m,uid=65534,gid=65534',
              '--cap-drop=ALL','--security-opt=no-new-privileges','--pids-limit=32','--memory=768m','--cpus=1',
              '--user','65534:65534','--mount','type=volume,source='+self.volume+',target=/profile',
              '--env','HOME=/profile','--env','CLAUDE_CONFIG_DIR=/profile/.claude',
              '--entrypoint','/usr/local/bin/claude']
        if action=='login':args+=['--interactive','--tty']
        for key,value in self.labels.items():args+=['--label',key+'='+value]
        # All original auth mechanisms remain in the unmodified binary; this
        # default selects the user's subscription flow, not Console/API billing.
        return args+[self.image_id,'auth','login','--claudeai'] if action=='login' else args+[self.image_id,'auth','status','--json']


def auth_summary(raw,exit_code):
    if not isinstance(raw,bytes) or len(raw)>65536 or type(exit_code) is not int:
        raise AdapterFailure('adapter_contract_invalid')
    value=_object(raw)
    logged=value.get('loggedIn');method=value.get('authMethod')
    if type(logged) is not bool:raise AdapterFailure('adapter_protocol_invalid')
    if logged is False and exit_code==1 and method in (None,'none'):
        state='not_authenticated'
    elif logged is True and exit_code==0 and method=='claude.ai':
        state='signed_in_personal_candidate'
    else:
        state='unsupported_or_unknown_auth'
    # Never return email/org/config-directory/error/token or infer plan quota.
    return {'stage':STAGE,'state':state,'native_connection_enrolled':False,
            'provider_inference_verified':False,'shared_use_allowed':False}
