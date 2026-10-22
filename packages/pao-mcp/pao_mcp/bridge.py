"""Fixed GET routes only. No database, Google credentials, shell or model calls."""
import asyncio
import json
import re
from uuid import UUID
import httpx

BASE = 'http://127.0.0.1:8100'
MAX_HTTP = 1_048_576
MAX_RESULT = 60_000


class Denied(Exception):
    pass


def require(value):
    if not value:
        raise Denied('Yêu cầu hoặc phạm vi không hợp lệ.')


def uid(value):
    try:
        require(isinstance(value, str) and str(UUID(value)) == value)
    except (ValueError, TypeError, AttributeError):
        raise Denied('Định danh không hợp lệ.') from None
    return value


def integer(value, low, high):
    require(type(value) is int and low <= value <= high)
    return value


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result)
            result[key] = value
        return result
    try:
        value = json.loads(raw, object_pairs_hook=pairs,
                           parse_constant=lambda _: require(False))
        json.dumps(value, ensure_ascii=False).encode('utf-8')
        return value
    except (ValueError, UnicodeError, RecursionError, TypeError):
        raise Denied('JSON không hợp lệ.') from None


def profile(value):
    require(isinstance(value, dict) and set(value) == {
        'version', 'actor_id', 'workspace_id', 'projects', 'brains', 'token', 'consent', 'enabled'})
    require(type(value['version']) is int and value['version'] == 1)
    require(value['enabled'] is True and value['consent'] is True)
    uid(value['actor_id']); uid(value['workspace_id'])
    require(isinstance(value['projects'], list) and len(value['projects']) <= 20)
    for item in value['projects']: uid(item)
    require(len(set(value['projects'])) == len(value['projects']))
    require(isinstance(value['brains'], dict) and len(value['brains']) <= 20)
    for brain, brand in value['brains'].items():
        uid(brain)
        if brand is not None: uid(brand)
    require(isinstance(value['token'], str) and
            re.fullmatch(r'[A-Za-z0-9_.-]{20,8192}', value['token']))
    return value


def tool(name, description, properties, required=()):
    return {'name': name, 'description': description,
            'inputSchema': {'type': 'object', 'properties': properties,
                            'required': list(required), 'additionalProperties': False},
            'annotations': {'readOnlyHint': True, 'destructiveHint': False,
                            'idempotentHint': True, 'openWorldHint': False}}


ID = {'type': 'string', 'format': 'uuid'}
TOOLS = [
    tool('pao_scope', 'Đọc phạm vi PAO đã được bạn cho phép; không mở rộng quyền.', {}),
    tool('pao_list_tasks', 'Đọc tối đa20 công việc trong một dự án đã chọn.',
         {'project_id': ID, 'limit': {'type': 'integer', 'minimum': 1, 'maximum': 20}}, ['project_id']),
    tool('pao_get_task', 'Đọc một công việc trong tối đa500 công việc gần nhất của dự án đã chọn.',
         {'project_id': ID, 'task_id': ID}, ['project_id', 'task_id']),
    tool('pao_list_sources', 'Đọc danh mục nguồn trong kho tri thức được chọn; không đọc bộ nhớ cũ.',
         {'brain_id': ID, 'offset': {'type': 'integer', 'minimum': 0, 'maximum': 1000}}, ['brain_id']),
    tool('pao_preview_source', 'Đọc trích đoạn phiên bản nguồn đã parse, kiểm tra quyền và toàn vẹn ở PAO.',
         {'brain_id': ID, 'source_id': ID, 'version': {'type': 'integer', 'minimum': 1},
          'start_line': {'type': 'integer', 'minimum': 1},
          'lines': {'type': 'integer', 'minimum': 1, 'maximum': 100}}, ['brain_id', 'source_id', 'version']),
]


class Bridge:
    def __init__(self, load_profile, transport=None):
        self.load_profile = load_profile
        self.transport = transport

    async def call(self, name, arguments):
        definitions = {item['name']: item for item in TOOLS}
        require(name in definitions and isinstance(arguments, dict))
        schema = definitions[name]['inputSchema']
        require(set(arguments) <= set(schema['properties']) and set(schema['required']) <= set(arguments))
        # Validate before any HTTP call, including object-shaped UUID attacks.
        for key, value in arguments.items():
            if key.endswith('_id'): uid(value)
            else: integer(value, 0 if key == 'offset' else 1,
                          {'offset': 1000, 'limit': 20, 'lines': 100}.get(key, 2_147_483_647))
        cfg = profile(self.load_profile())
        try:
            async with asyncio.timeout(20):
                async with httpx.AsyncClient(base_url=BASE, transport=self.transport, trust_env=False,
                        follow_redirects=False, timeout=4, headers={
                            'Authorization': 'Bearer ' + cfg['token'], 'Accept': 'application/json',
                            'User-Agent': 'PAO-MCP-Readonly/0.1'}) as client:
                    async def get(path, params=None):
                        # Only internal hardcoded paths assembled from canonical UUIDs.
                        require(path.startswith('/v1/') and '?' not in path and '..' not in path)
                        async with client.stream('GET', path, params=params) as response:
                            if response.status_code != 200:
                                raise Denied('PAO từ chối truy cập. Kiểm tra phiên, quyền hoặc trạng thái dữ liệu.')
                            require(response.headers.get('content-type', '').split(';')[0] == 'application/json')
                            data = bytearray()
                            async for chunk in response.aiter_bytes():
                                data.extend(chunk); require(len(data) <= MAX_HTTP)
                            return strict_json(data)

                    async def authority():
                        me = await get('/v1/me')
                        require(isinstance(me, dict) and me.get('id') == cfg['actor_id'])
                        context = await get('/v1/workspaces/' + cfg['workspace_id'] + '/context')
                        require(isinstance(context, dict) and context.get('id') == cfg['workspace_id']
                                and context.get('role') in ('owner', 'admin'))

                    async def brain_access(brain_id):
                        require(brain_id in cfg['brains'])
                        rows = await get('/v1/brains', {'workspace_id': cfg['workspace_id']})
                        require(isinstance(rows, list))
                        matching = [row for row in rows if isinstance(row, dict) and row.get('id') == brain_id]
                        require(len(matching) == 1)
                        row = matching[0]
                        require(row.get('workspace_id') == cfg['workspace_id'] and not row.get('archived_at')
                                and row.get('brand_id') == cfg['brains'][brain_id])
                        # Private legacy facts have no export tool in this bridge.
                        return row

                    await authority()
                    if name == 'pao_scope':
                        result = {'actor_id': cfg['actor_id'], 'workspace_id': cfg['workspace_id'],
                                  'projects': cfg['projects'], 'brains': cfg['brains'], 'read_only': True,
                                  'notice': 'Phạm vi đã chọn, không chứng minh mọi nguồn còn truy cập được.'}
                    elif name in ('pao_list_tasks', 'pao_get_task'):
                        if name == 'pao_list_tasks':
                            require(arguments['project_id'] in cfg['projects'])
                            rows = await get('/v1/tasks', {'workspace_id': cfg['workspace_id'],
                                'project_id': arguments['project_id'], 'limit': arguments.get('limit', 20)})
                            require(isinstance(rows, list) and len(rows) <= arguments.get('limit', 20))
                        else:
                            require(arguments['project_id'] in cfg['projects'])
                            allowed = await get('/v1/tasks', {'workspace_id': cfg['workspace_id'],
                                'project_id': arguments['project_id'], 'limit': 500})
                            require(isinstance(allowed, list) and len(allowed) <= 500)
                            require(all(isinstance(row, dict) and row.get('workspace_id') == cfg['workspace_id']
                                        and row.get('project_id') == arguments['project_id'] for row in allowed))
                            require(any(row.get('id') == arguments['task_id'] for row in allowed))
                            rows = [await get('/v1/tasks/' + arguments['task_id'])]
                        selected = []
                        for row in rows:
                            require(isinstance(row, dict) and row.get('workspace_id') == cfg['workspace_id']
                                    and row.get('project_id') in cfg['projects'])
                            if name == 'pao_list_tasks': require(row['project_id'] == arguments['project_id'])
                            else: require(row.get('id') == arguments['task_id'] and row['project_id'] == arguments['project_id'])
                            fields = ('id', 'project_id', 'title', 'status', 'priority', 'progress', 'due_at', 'version')
                            if name == 'pao_get_task': fields += ('description', 'success_criteria')
                            selected.append({key: row[key] for key in fields if key in row})
                        result = {'items': selected, 'bounded': True}
                    else:
                        brain = arguments['brain_id']
                        await brain_access(brain)
                        prefix = '/v1/brains/' + brain + '/sources'
                        if name == 'pao_list_sources':
                            rows = await get(prefix, {'limit': 20, 'offset': arguments.get('offset', 0)})
                            require(isinstance(rows, list) and len(rows) <= 20)
                            fields = ('id', 'title', 'kind', 'current_version', 'parse_status', 'stale', 'origin_trashed')
                            require(all(isinstance(row, dict) and row.get('brain_id') == brain
                                        and not row.get('archived_at') for row in rows))
                            result = {'items': [{k: row[k] for k in fields if k in row} for row in rows], 'bounded': True}
                        else:
                            result = await get(prefix + '/' + arguments['source_id'] + '/versions/' +
                                str(arguments['version']) + '/preview',
                                {'start_line': arguments.get('start_line', 1), 'lines': arguments.get('lines', 50)})
                            require(isinstance(result, dict) and result.get('source_id') == arguments['source_id']
                                    and result.get('version') == arguments['version'] and result.get('format') == 'plain_text')
                            result = {key: result[key] for key in ('source_id', 'version_id', 'version',
                                'source_sha256', 'parsed_sha256', 'parser_version', 'start_line', 'end_line',
                                'content', 'truncated', 'format') if key in result}
                        await brain_access(brain)
                    await authority()
                    require(profile(self.load_profile()) == cfg)
                    require(len(json.dumps(result, ensure_ascii=False).encode('utf-8')) <= MAX_RESULT)
                    return result
        except (httpx.HTTPError, TimeoutError):
            raise Denied('Không đọc được PAO trong thời gian cho phép; không tự thử lại.') from None
