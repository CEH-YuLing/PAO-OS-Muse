"""Local MCP setup/stdio entrypoint. Never starts agy or reads Google auth."""
import argparse
import asyncio
import getpass
import json
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/pao-mcp'))
from pao_mcp.bridge import BASE, Bridge, Denied, profile, strict_json, require, uid
from pao_mcp import profile as store
from pao_mcp.stdio import serve
import httpx

HOME = ROOT / '.runtime/pao-mcp'


def target(value):
    path = store.safe_path(value)
    require(path.parent == HOME / 'profiles' and path.suffix == '.dpapi')
    uid(path.stem)
    return path


def pick(rows, label, multiple=False):
    print(label)
    for index, row in enumerate(rows, 1):
        # Escape control characters and ANSI in raw user-supplied names.
        name = json.dumps(row.get('name', row.get('id')), ensure_ascii=False)
        print(f'{index}. {name} ({row["id"]})')
    if not rows:
        if multiple: return []
        raise Denied('Không có lựa chọn phù hợp.')
    answer = input('Nhập số, cách nhau bằng dấu phẩy; Enter để không chia sẻ: ' if multiple else 'Chọn một số: ').strip()
    if not answer and multiple: return []
    values = answer.split(',')
    require((multiple or len(values) == 1) and len(values) <= 20)
    require(all(v.strip().isdigit() and 1 <= int(v) <= len(rows) for v in values))
    indexes = [int(v) - 1 for v in values]
    require(len(set(indexes)) == len(indexes))
    return [rows[i] for i in indexes]


async def setup():
    print('PAO MCP chỉ đọc — kết nối từ Antigravity chính chủ vào PAO.')
    print('Không đăng nhập Google tại đây. Không nhập token Google, App Secret hoặc API key.')
    print('Chỉ chủ sở hữu/quản trị viên; tài khoản Windows hiện tại giữ phiên PAO mã hóa.')
    email = input('Email đăng nhập PAO: ').strip()
    password = getpass.getpass('Mật khẩu PAO (không hiện ký tự khi gõ): ')
    require(email and password)
    async with httpx.AsyncClient(base_url=BASE, trust_env=False, follow_redirects=False, timeout=10) as client:
        response = await client.post('/v1/auth/token', json={'email': email, 'password': password})
        password = None
        if response.status_code != 200:
            raise Denied('PAO từ chối đăng nhập; không tự thử lại.')
        payload = strict_json(response.content)
        require(isinstance(payload, dict) and isinstance(payload.get('access_token'), str))
        token = payload['access_token']
        client.headers['Authorization'] = 'Bearer ' + token
        async def get(path, params=None):
            reply = await client.get(path, params=params)
            require(reply.status_code == 200 and len(reply.content) <= 1_048_576)
            return strict_json(reply.content)
        me = await get('/v1/me')
        rows = [row for row in me['workspaces'] if row.get('role') in ('owner', 'admin')]
        selected = pick(rows, 'Doanh nghiệp được kết nối:')[0]
        workspace = uid(selected['id'])
        projects = await get('/v1/projects', {'workspace_id': workspace})
        require(isinstance(projects, list) and all(row.get('workspace_id') == workspace for row in projects))
        chosen_projects = pick(projects, 'Dự án được chia sẻ công việc (không tự bao gồm dự án khác):', True)
        # Brain feature may be unavailable; never enable it automatically.
        status = await get('/v1/brains/status', {'workspace_id': workspace})
        brains = await get('/v1/brains', {'workspace_id': workspace}) if status.get('enabled') is True else []
        require(isinstance(brains, list) and all(row.get('workspace_id') == workspace for row in brains))
        brains = [row for row in brains if not row.get('archived_at') and not row.get('legacy_default')]
        chosen_brains = pick(brains, 'Kho tri thức được chia sẻ nguồn (bộ nhớ legacy không được cung cấp):', True)
        print('LƯU Ý: công việc và nguồn bạn chọn có thể được gửi tới model của Google khi bạn gọi công cụ trong Antigravity.')
        print('Không chọn tài liệu chứa mật khẩu, khóa bí mật hoặc thông tin bạn không có quyền chia sẻ ra ngoài.')
        require(input('Gõ DONG Y để lưu phạm vi này; giá trị khác sẽ hủy: ').strip() == 'DONG Y')
        value = profile({'version': 1, 'actor_id': uid(me['id']), 'workspace_id': workspace,
                         'projects': [uid(p['id']) for p in chosen_projects],
                         'brains': {uid(b['id']): b.get('brand_id') for b in chosen_brains},
                         'token': token, 'consent': True, 'enabled': True})
        # Recheck actor/session/workspace before persisting. No project/source content read.
        require((await get('/v1/me'))['id'] == value['actor_id'])
        require((await get('/v1/workspaces/' + workspace + '/context'))['role'] in ('owner', 'admin'))
    ident = str(uuid4())
    for folder in (HOME, HOME / 'profiles', HOME / 'workspaces'):
        store.safe_path(folder); folder.mkdir(exist_ok=True)
    path = HOME / 'profiles' / (ident + '.dpapi')
    store.create(path, value)
    project = HOME / 'workspaces' / ident
    project.mkdir()
    (project / '.agents').mkdir()
    config = {'mcpServers': {'pao-readonly': {'command': sys.executable,
              'args': ['-I', '-B', str(ROOT / 'scripts/pao_mcp.py'), 'serve', '--profile', str(path)],
              'cwd': str(project)}}}
    with (project / '.agents/mcp_config.json').open('x', encoding='utf-8') as out:
        json.dump(config, out, ensure_ascii=False, indent=2)
    print('Đã lưu hồ sơ mã hóa riêng. Chưa xác nhận Antigravity đã kết nối hoặc model đã dùng dữ liệu.')
    print('Mở thư mục sau bằng Antigravity chính chủ, vào /mcp để xem pao-readonly:')
    print(project)
    print('Không thay cấu hình Antigravity/Javis toàn máy. Không cần khởi động lại PAO.')
    print('Ngắt bằng lệnh trong hướng dẫn, với hồ sơ: ' + str(path))


def main():
    parser = argparse.ArgumentParser(description='PAO MCP local chỉ đọc')
    parser.add_argument('action', choices=('setup', 'serve', 'check', 'disconnect'))
    parser.add_argument('--profile')
    args = parser.parse_args()
    try:
        if args.action == 'setup':
            require(args.profile is None); asyncio.run(setup()); return
        path = target(args.profile or '')
        if args.action == 'disconnect':
            store.disable(path); print('Đã ngắt riêng hồ sơ MCP. Không đăng xuất Google/Javis hoặc phiên PAO khác.'); return
        bridge = Bridge(lambda: store.read(path))
        if args.action == 'check':
            asyncio.run(bridge.call('pao_scope', {})); print('Phiên PAO và phạm vi hợp lệ; chưa phải kết nối/model Antigravity thật.')
        else: asyncio.run(serve(bridge))
    except (Denied, OSError, ValueError, KeyError, TypeError, httpx.HTTPError, KeyboardInterrupt, EOFError):
        print('Thiết lập chưa hoàn tất hoặc quyền đã thay đổi. Không gửi mật khẩu/token trong chat; xem hướng dẫn PAO MCP.', file=sys.stderr)
        raise SystemExit(2) from None


if __name__ == '__main__':
    main()
