"""HTTPS only; connect to a checked numeric address while retaining TLS SNI.

No environment proxies, redirects, automatic retries, or server-driven client
actions. Version is deliberately pinned; unsupported versions fail closed.
"""
import asyncio,ipaddress,json,re,socket,ssl
from urllib.parse import urlsplit
from uuid import uuid4
import httpx,httpcore
from httpcore._backends.auto import AutoBackend
from ..studio.contracts import canonical,digest,safe_schema,validate_value
from ...credential_guard import require_clean_payload,CredentialPayloadError

PROTOCOL='2025-11-25'
MAX_BYTES=65536


class ConnectorFailure(RuntimeError):
    """Stable public code, never raw provider text/URLs/credentials."""


def endpoint(value):
    if not isinstance(value,str) or len(value)>1000 or any(ord(c)<33 or ord(c)>126 for c in value):
        raise ConnectorFailure('connector_endpoint_invalid')
    try:
        url=urlsplit(value)
        host=url.hostname or ''
        if url.scheme!='https' or url.username or url.password or url.query or url.fragment or url.port not in (None,443):
            raise ValueError()
        if not re.fullmatch(r'[a-zA-Z0-9](?:[a-zA-Z0-9.-]{0,251}[a-zA-Z0-9])?',host) or '.' not in host or '..' in host:
            raise ValueError()
        try:ipaddress.ip_address(host)
        except ValueError:pass
        else:raise ConnectorFailure('connector_ip_endpoint_denied')
        if not re.fullmatch(r'/[a-zA-Z0-9_/-]{0,200}',url.path) or '..' in url.path:
            raise ValueError()
    except (ValueError,TypeError):
        raise ConnectorFailure('connector_endpoint_invalid') from None
    return 'https://'+host.lower()+url.path


def public_addresses(addresses):
    if not addresses or len(addresses)>16:raise ConnectorFailure('connector_dns_denied')
    values=[]
    for address in addresses:
        try:ip=ipaddress.ip_address(address)
        except ValueError:raise ConnectorFailure('connector_dns_denied') from None
        if not ip.is_global or ip.is_multicast or getattr(ip,'ipv4_mapped',None):
            raise ConnectorFailure('connector_dns_denied')
        values.append(str(ip))
    return list(dict.fromkeys(values))


async def resolve(host):
    try:
        async with asyncio.timeout(3):
            rows=await asyncio.get_running_loop().getaddrinfo(host,443,type=socket.SOCK_STREAM)
    except (OSError,TimeoutError):raise ConnectorFailure('connector_dns_unavailable') from None
    return public_addresses([row[4][0] for row in rows])


class PinnedBackend(AutoBackend):
    async def connect_tcp(self,host,port,timeout=None,local_address=None,socket_options=None):
        if port!=443 or local_address:raise ConnectorFailure('connector_port_denied')
        # Re-resolve and validate EVERY physical connection; never let the
        # underlying backend resolve the original hostname a second time.
        addresses=await resolve(host)
        return await super().connect_tcp(addresses[0],port,timeout=timeout,socket_options=socket_options)


class PinnedTransport(httpx.AsyncHTTPTransport):
    def __init__(self):
        super().__init__(verify=True,trust_env=False,retries=0)
        self._pool=httpcore.AsyncConnectionPool(ssl_context=ssl.create_default_context(),
            max_connections=1,max_keepalive_connections=0,retries=0,network_backend=PinnedBackend())


def clean(value,token=None):
    try:require_clean_payload(value,token)
    except CredentialPayloadError as exc:
        raise ConnectorFailure('connector_sensitive_result' if str(exc)=='payload_credential_reflected' else 'connector_response_limit') from None


def decode(raw,mime,rid,token=None):
    try:
        if len(raw)>MAX_BYTES:raise ConnectorFailure('connector_response_limit')
        text=raw.decode('utf-8')
        if mime=='application/json':
            messages=[json.loads(text)]
        elif mime=='text/event-stream':
            messages=[]
            for block in text.replace('\r\n','\n').split('\n\n'):
                data='\n'.join(line[5:].lstrip(' ') for line in block.split('\n') if line.startswith('data:'))
                if data:messages.append(json.loads(data))
                if len(messages)>16:raise ConnectorFailure('connector_event_limit')
        else:raise ConnectorFailure('connector_content_type')
        answers=[]
        for message in messages:
            clean(message,token) # Includes errors, unused metadata and dict keys.
            if not isinstance(message,dict) or message.get('jsonrpc')!='2.0':raise ValueError()
            if 'method' in message:
                # Never grant roots, sampling, elicitation or server-driven work.
                raise ConnectorFailure('connector_server_message_denied')
            if message.get('id')!=rid or 'error' in message or not isinstance(message.get('result'),dict):raise ValueError()
            answers.append(message['result'])
        if len(answers)!=1:raise ValueError()
        return answers[0]
    except (ValueError,UnicodeError,TypeError,RecursionError):
        raise ConnectorFailure('connector_protocol_invalid') from None


class Client:
    def __init__(self,url,token=None,transport=None):
        self.url=endpoint(url);self.token=token;self.session=None
        self.transport=transport  # Constructor-only test injection, not config/API.

    async def rpc(self,http,method,params=None,notify=False):
        rid=uuid4().hex
        payload={'jsonrpc':'2.0','method':method}
        if not notify:payload['id']=rid
        if params is not None:payload['params']=params
        headers={'Accept':'application/json, text/event-stream','MCP-Protocol-Version':PROTOCOL}
        if self.token:headers['Authorization']='Bearer '+self.token
        if self.session:headers['MCP-Session-Id']=self.session
        try:
            async with asyncio.timeout(10):
                async with http.stream('POST',self.url,json=payload,headers=headers) as response:
                    if response.status_code in (401,403):raise ConnectorFailure('connector_auth_denied')
                    if response.status_code not in ((202,) if notify else (200,)):
                        raise ConnectorFailure('connector_http_denied')
                    raw=bytearray()
                    async for chunk in response.aiter_bytes():
                        raw.extend(chunk)
                        if len(raw)>MAX_BYTES:raise ConnectorFailure('connector_response_limit')
                    if notify:
                        if raw:raise ConnectorFailure('connector_protocol_invalid')
                        return {}
                    result=decode(bytes(raw),response.headers.get('content-type','').split(';')[0].strip().lower(),rid,self.token)
                    if method=='initialize':
                        session=response.headers.get('mcp-session-id')
                        clean(session,self.token) # Never resend a reflected key as a session ID.
                        if session and not re.fullmatch(r'[\x21-\x7e]{1,200}',session):raise ConnectorFailure('connector_session_invalid')
                        self.session=session
                    return result
        except (TimeoutError,httpx.TimeoutException):raise ConnectorFailure('connector_timeout') from None
        except httpx.HTTPError:raise ConnectorFailure('connector_network_unavailable') from None

    async def initialize(self,http):
        result=await self.rpc(http,'initialize',{'protocolVersion':PROTOCOL,'capabilities':{},
            'clientInfo':{'name':'PAO read-only','version':'p5.1'}})
        if result.get('protocolVersion')!=PROTOCOL or not isinstance(result.get('capabilities'),dict) or 'tools' not in result['capabilities']:
            raise ConnectorFailure('connector_capabilities_unsupported')
        await self.rpc(http,'notifications/initialized',notify=True)
        return digest({'protocol':PROTOCOL,'capabilities':result['capabilities']})

    async def discover(self,http):
        capability=await self.initialize(http)
        tools={};cursor=None;seen=set()
        for _ in range(3):
            page=await self.rpc(http,'tools/list',{'cursor':cursor} if cursor else {})
            rows=page.get('tools')
            if not isinstance(rows,list) or len(rows)>32:raise ConnectorFailure('connector_tools_limit')
            for row in rows:
                if not isinstance(row,dict):raise ConnectorFailure('connector_tool_invalid')
                name=row.get('name','');annotations=row.get('annotations',{})
                if not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_-]{0,19}',name) or name in tools:
                    raise ConnectorFailure('connector_tool_invalid')
                # Server claims alone never authorize use; explicit owner grant
                # and published skill allowlist are separate later gates.
                if not isinstance(annotations,dict) or annotations.get('readOnlyHint') is not True or annotations.get('destructiveHint') is not False:
                    continue
                try:
                    inp=safe_schema(row.get('inputSchema'));out=safe_schema(row.get('outputSchema'))
                    if inp['type']!='object' or out['type']!='object':raise ValueError()
                    safe_annotations={'readOnlyHint':True,'destructiveHint':False}
                    if type(annotations.get('idempotentHint')) is bool:safe_annotations['idempotentHint']=annotations['idempotentHint']
                    definition={'name':name,'input_schema':inp,'output_schema':out,'annotations':safe_annotations}
                    if len(canonical(definition).encode())>12000:raise ValueError()
                except (ValueError,TypeError,KeyError,RecursionError):
                    continue  # Unsupported schemas are never partially trusted.
                tools[name]={**definition,'hash':digest(definition)}
                if len(tools)>32:raise ConnectorFailure('connector_tools_limit')
            cursor=page.get('nextCursor')
            if cursor is None:return {'protocol':PROTOCOL,'capability_hash':capability,'tools':tools}
            if not isinstance(cursor,str) or not 1<=len(cursor)<=200 or cursor in seen:raise ConnectorFailure('connector_pagination_invalid')
            seen.add(cursor)
        raise ConnectorFailure('connector_pagination_limit')

    async def exchange(self,approved=None):
        try:
            async with asyncio.timeout(30),httpx.AsyncClient(transport=self.transport or PinnedTransport(),
                timeout=httpx.Timeout(10,connect=5),trust_env=False,follow_redirects=False) as http:
                manifest=await self.discover(http)
                if approved is None:return manifest
                if digest(manifest)!=approved['manifest_hash']:raise ConnectorFailure('connector_schema_drift')
                tool=manifest['tools'].get(approved['name'])
                if not tool or tool['hash']!=approved['hash']:raise ConnectorFailure('connector_schema_drift')
                validate_value(tool['input_schema'],approved['arguments'])
                result=await self.rpc(http,'tools/call',{'name':approved['name'],'arguments':approved['arguments']})
                if result.get('isError') is True:raise ConnectorFailure('connector_tool_failed')
                output=result.get('structuredContent')
                validate_value(tool['output_schema'],output)
                return output
        except TimeoutError:raise ConnectorFailure('connector_timeout') from None
        except (ValueError,TypeError,KeyError,RecursionError):raise ConnectorFailure('connector_result_invalid') from None
