"""Whitelist only model identifiers and defaults, not account metadata or tools."""
import re
from .login_transport import LoginTransport
from pao_cli_runtime.contracts import CliFailure

def models(value):
    if not isinstance(value,dict) or not isinstance(value.get('data'),list) or len(value['data'])>100 or value.get('nextCursor'):
        raise CliFailure('cli_protocol_invalid')
    result=[];seen=set()
    for row in value['data']:
        if not isinstance(row,dict):raise CliFailure('cli_protocol_invalid')
        model=row.get('model')
        if not isinstance(model,str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._:/+-]{0,119}',model) or model in seen or type(row.get('isDefault')) is not bool:
            raise CliFailure('cli_protocol_invalid')
        item={'model':model,'is_default':row['isDefault']}
        if 'supportedReasoningEfforts' in row:
            values=row['supportedReasoningEfforts']
            if not isinstance(values,list) or len(values)>12:raise CliFailure('cli_protocol_invalid')
            efforts=[]
            for value in values:
                effort=value.get('reasoningEffort') if isinstance(value,dict) else None
                if not isinstance(effort,str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,23}',effort) or effort in efforts:raise CliFailure('cli_protocol_invalid')
                efforts.append(effort)
            default=row.get('defaultReasoningEffort')
            if default is not None and default not in efforts:raise CliFailure('cli_protocol_invalid')
            item.update(reasoning_efforts=efforts,default_effort=default)
        if 'displayName' in row:
            label=row['displayName']
            if not isinstance(label,str) or not 1<=len(label)<=160 or any(ord(c)<32 for c in label):raise CliFailure('cli_protocol_invalid')
            item['display_name']=label
        seen.add(model);result.append(item)
    if not result or sum(row['is_default'] for row in result)>1:raise CliFailure('cli_protocol_invalid')
    return result

class CatalogTransport(LoginTransport):
    async def read(self):
        await self.open()
        account=await self.rpc(2,'account/read',{'refreshToken':False})
        if not isinstance(account.get('account'),dict) or account['account'].get('type')!='chatgpt':
            raise CliFailure('cli_access_denied')
        # Narrow extension: no arbitrary RPC, turn/start, tools or login mutation.
        import asyncio
        result=[];cursor=None;seen=set();names=set()
        async with asyncio.timeout(30):
            for page in range(5):
                await self.authorize()
                params={'limit':100,'includeHidden':False}
                if cursor:params['cursor']=cursor
                await self.send({'id':3+page,'method':'model/list','params':params})
                while True:
                    value=await self.receive()
                    if value.get('id')==3+page:
                        if 'error' in value:raise CliFailure('cli_provider_failed')
                        payload=value.get('result')
                        if not isinstance(payload,dict):raise CliFailure('cli_protocol_invalid')
                        cursor=payload.get('nextCursor')
                        if cursor is not None and (not isinstance(cursor,str) or not 1<=len(cursor)<=1024 or cursor in seen or any(ord(c)<33 or ord(c)==127 for c in cursor)):
                            raise CliFailure('cli_protocol_invalid')
                        rows=models({**payload,'nextCursor':None})
                        if any(row['model'] in names for row in rows):raise CliFailure('cli_protocol_invalid')
                        names.update(row['model'] for row in rows);result.extend(rows)
                        if sum(row['is_default'] for row in result)>1:raise CliFailure('cli_protocol_invalid')
                        if cursor is None:return result
                        seen.add(cursor)
                        break
                    self.notification(value)
        raise CliFailure('cli_protocol_invalid')
