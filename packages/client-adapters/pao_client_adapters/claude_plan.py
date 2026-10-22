"""Inert, text-only native CLI invocation plan. NO process/auth/DB API.

The caller must separately pass native authorization, accounting and OS
isolation gates. Shape validation is not an entitlement or a launch grant.
"""
from dataclasses import dataclass,field
import json
import re
from uuid import UUID
from .protocols import AdapterFailure

VERSION='2.1.220'
REQUIRED_FLAGS=frozenset({'--print','--input-format','--output-format','--verbose','--model',
    '--session-id','--tools','--permission-mode','--strict-mcp-config','--mcp-config',
    '--settings','--setting-sources','--no-session-persistence','--disable-slash-commands'})
SETTINGS={'disableAllHooks':True,'autoMemoryEnabled':False,'enableAllProjectMcpServers':False}


def uuid(value):
    try:
        if not isinstance(value,str) or str(UUID(value))!=value:raise ValueError()
    except (ValueError,TypeError,AttributeError):
        raise AdapterFailure('adapter_contract_invalid') from None
    return value


@dataclass(frozen=True)
class NativeScope:
    workspace_id:str
    actor_id:str
    connection_id:str
    device_id:str
    profile_id:str
    attempt_id:str

    def __post_init__(self):
        for value in vars(self).values():uuid(value)


@dataclass(frozen=True)
class ClaudeTextPlan:
    scope:NativeScope
    model:str
    argv:tuple[str,...]=field(repr=False)
    stdin:bytes=field(repr=False)
    live_dispatch_allowed:bool=field(default=False,init=False)


def metadata_environment():
    """Explicit container environment; never copy parent env or user home."""
    return {'HOME':'/profile','CLAUDE_CONFIG_DIR':'/profile/.claude','TMPDIR':'/tmp',
            'PATH':'/usr/local/bin:/usr/bin:/bin','LC_ALL':'C.UTF-8'}


def prepare(scope,model,messages,*,binary_version,flags):
    if (not isinstance(scope,NativeScope) or binary_version!=VERSION or not isinstance(flags,frozenset)
            or not REQUIRED_FLAGS<=flags or not isinstance(model,str)
            or not re.fullmatch(r'claude-[a-zA-Z0-9][a-zA-Z0-9._-]{0,112}',model)):
        raise AdapterFailure('adapter_contract_invalid')
    if (not isinstance(messages,list) or not 1<=len(messages)<=128
            or any(not isinstance(m,dict) or set(m)!={'role','content'}
                   or m['role'] not in ('system','user','assistant') or not isinstance(m['content'],str)
                   or '\x00' in m['content'] for m in messages)):
        raise AdapterFailure('adapter_contract_invalid')
    try:payload=json.dumps({'messages':messages},ensure_ascii=False,separators=(',',':')).encode('utf-8')+b'\n'
    except UnicodeError:raise AdapterFailure('adapter_contract_invalid') from None
    if len(payload)>65536:raise AdapterFailure('adapter_contract_invalid')
    args=('/usr/local/bin/claude','--print','--input-format','text','--output-format','stream-json','--verbose',
          '--model',model,'--session-id',scope.attempt_id,'--tools','','--permission-mode','dontAsk',
          '--strict-mcp-config','--mcp-config','{"mcpServers":{}}','--setting-sources','',
          '--settings',json.dumps(SETTINGS,separators=(',',':')),
          '--disable-slash-commands','--no-session-persistence')
    return ClaudeTextPlan(scope,model,args,payload)
