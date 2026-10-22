"""Human-run local setup only: actual PAO login, own profile, official Codex login.

Never run this through a captured agent terminal: the official device code is for
the human user's own terminal. No cached host auth, token import, grants or jobs.
"""
import argparse
import asyncio
import getpass
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'packages/cli-runtime'))
BASE = 'http://127.0.0.1:8100'


class SetupFailure(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SetupFailure('PAO trả chuyển hướng; đã dừng để bảo vệ thông tin đăng nhập.')


class LocalAPI:
    def __init__(self):
        self.opener = build_opener(ProxyHandler({}), NoRedirect())
        self.token = None

    def call(self, method, path, data=None):
        # Fixed loopback API only; no caller-supplied server or redirect target.
        if not path.startswith('/v1/') and path != '/openapi.json':
            raise SetupFailure('Địa chỉ API không hợp lệ.')
        if any(c in path for c in ('?', '#', '\\', '\r', '\n')) or '..' in path:
            raise SetupFailure('Địa chỉ API không hợp lệ.')
        headers = {'Content-Type': 'application/json'}
        if self.token:
            headers['Authorization'] = 'Bearer ' + self.token
        request = Request(BASE + path, method=method, headers=headers,
                          data=json.dumps(data).encode() if data is not None else None)
        try:
            with self.opener.open(request, timeout=60) as response:
                raw = response.read(8 * 1024 * 1024 + 1)
                if len(raw) > 8 * 1024 * 1024:
                    raise SetupFailure('Phản hồi PAO vượt giới hạn.')
                return json.loads(raw)
        except HTTPError as error:
            # Never echo response bodies, headers or submitted credentials.
            raise SetupFailure('PAO từ chối yêu cầu (HTTP ' + str(error.code) + ').') from None


def identity(api, selected):
    me = api.call('GET', '/v1/me')
    wid, uid = selected['workspace_id'], selected['current_owner_user_id']
    if str(UUID(wid)) != wid or str(UUID(uid)) != uid or me.get('id') != uid:
        raise SetupFailure('Tài khoản không phải chủ doanh nghiệp đã chọn; chưa tạo hồ sơ.')
    context = api.call('GET', '/v1/workspaces/' + wid + '/context')
    if context.get('id') != wid or context.get('role') != 'owner':
        raise SetupFailure('Không có quyền chủ doanh nghiệp hiện tại; chưa tạo hồ sơ.')
    return wid, uid, context['name']


def checked_row(row, workspace, actor, model, config):
    from pao_cli_runtime.docker_transport import canonical
    if (row.get('workspace_id') != workspace or row.get('owner_id') != actor
            or row.get('provider') != 'codex_cli' or row.get('model') != model
            or row.get('device_id') != config['device_id']
            or row.get('scope') != 'local_personal_self_only'
            or row.get('credentials_stored_in_PAO') is not False
            or row.get('tools_enabled') is not False or row.get('activation_required') is not True
            or type(row.get('version')) is not int or row['version'] < 1):
        raise SetupFailure('Phạm vi hồ sơ không khớp; đã dừng.')
    for name in ('id', 'profile_id'):
        canonical(row.get(name))
    return row


def local_config():
    from pao_cli_runtime.docker_transport import ImagePin, canonical
    from pao_cli_runtime.source_pin import library_digest
    path = ROOT / '.runtime/cli-device.json'
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 16384:
        raise SetupFailure('Runtime Codex chưa được cài; không đăng nhập.')
    value = json.loads(path.read_text(encoding='utf-8'))
    if (set(value) != {'version', 'device_id', 'image_id', 'binary_sha256', 'binary_version', 'host_runtime_sha256'}
            or value['version'] != 2 or value['host_runtime_sha256'] != library_digest()):
        raise SetupFailure('Pin runtime không khớp; không đăng nhập.')
    canonical(value['device_id'])
    ImagePin(value['image_id'], value['binary_sha256'], value['binary_version'])
    return value


async def cleanup_login(admin, name, operation, env):
    """Only this generated login container; never volumes or another session."""
    args = ['ps', '--all', '--quiet', '--no-trunc', '--filter', 'name=^/' + name + '$']
    raw = (await admin.transport.command(args, env)).decode('ascii').strip()
    if not raw:
        return
    if not re.fullmatch(r'[0-9a-f]{64}', raw):
        raise SetupFailure('Không xác minh được container đăng nhập; không kiểm tra auth hoặc chạy model.')
    info = json.loads(await admin.transport.command(['inspect', raw], env))[0]
    if (info['Id'] != raw or info['Name'] != '/' + name
            or info['Image'] != admin.image.image_id
            or info['Config']['Labels'].get('pao.cli.login_operation_id') != operation):
        raise SetupFailure('Danh tính container đăng nhập không khớp; không dừng tiến trình khác.')
    await admin.transport.command(['rm', '--force', raw], env)
    if (await admin.transport.command(args, env)).strip():
        raise SetupFailure('Chưa xác nhận được dọn container đăng nhập; không kiểm tra auth hoặc chạy model.')


def login_pin(row, config):
    pin = {key: row[source] for key, source in (
        ('workspace_id', 'workspace_id'), ('actor_id', 'owner_id'), ('connection_id', 'id'),
        ('device_id', 'device_id'), ('profile_id', 'profile_id'))}
    # check_profile validates the complete image/binary pin, not only tenant
    # labels. The registry was checked against the host source before setup.
    pin.update(binary_sha256=config['binary_sha256'], binary_version=config['binary_version'],
               runtime_image_id=config['image_id'])
    return pin


def official_login(row, config, command):
    from pao_cli_runtime.docker_transport import ImagePin
    from pao_cli_runtime.profile_transport import ProfileAdmin
    from pao_cli_runtime.transport import child_environment
    pin = login_pin(row, config)
    admin = ProfileAdmin(ImagePin(config['image_id'], config['binary_sha256'], config['binary_version']))
    if command != admin.login_command(pin):
        raise SetupFailure('Lệnh đăng nhập không đúng mẫu cố định; không chạy.')
    operation = str(uuid4())
    name = 'pao-cli-human-login-' + UUID(operation).hex
    index = len(admin.transport.docker()) + 1  # Just after the fixed `run` verb.
    command = [*command[:index], '--name', name, '--label',
               'pao.cli.login_operation_id=' + operation, *command[index:]]
    with tempfile.TemporaryDirectory(prefix='pao-cli-human-login-') as temporary:
        env = child_environment(temporary)
        env['DOCKER_CONFIG'] = temporary
        asyncio.run(admin.transport.check_profile(pin, env))
        # Inherit the human console only. Do not capture or persist device codes.
        try:
            completed = subprocess.run(command, shell=False, env=env, timeout=900)
        finally:
            asyncio.run(cleanup_login(admin, name, operation, env))
    if completed.returncode:
        raise SetupFailure('Đăng nhập Codex chưa đạt; giữ hồ sơ để thử lại bằng ID, không tạo bản sao.')


def main():
    parser = argparse.ArgumentParser(description='Đăng nhập Codex riêng cho chủ doanh nghiệp PAO; không chạy model.')
    parser.add_argument('--model', required=True, help='Mã model muốn dùng; lưu hồ sơ chưa chứng minh quyền truy cập model.')
    parser.add_argument('--connection-id', type=UUID, help='Dùng lại hồ sơ đang chờ nếu lượt trước bị ngắt.')
    args = parser.parse_args()
    if ROOT != Path('F:/PAO-ACOS') or os.name != 'nt' or not sys.stdin.isatty() or not sys.stdout.isatty():
        raise SetupFailure('Hãy chạy trực tiếp trong PowerShell của bạn tại F:\\PAO-ACOS; không chạy qua log tự động.')
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9._:/+\-]{0,119}', args.model):
        raise SetupFailure('Mã model không hợp lệ.')
    config = local_config()
    selected = json.loads((ROOT / '.runtime/p84-selected-enterprise.json').read_text(encoding='utf-8'))
    api = LocalAPI()
    # Compare the installed public API with the local source before sending a password.
    contract = json.loads((ROOT / 'packages/contracts/openapi.json').read_text(encoding='utf-8'))
    if api.call('GET', '/openapi.json') != contract or not any('/cli-connections' in p for p in contract['paths']):
        raise SetupFailure('Backend đang chạy chưa khớp bản CLI đã cài; không gửi mật khẩu.')
    print('Chỉ đăng nhập cho doanh nghiệp đã chọn. Không cấp quyền model, chạy job hay đổi model mặc định.')
    email = input('Email tài khoản PAO: ').strip()
    password = getpass.getpass('Mật khẩu PAO (không hiện ký tự): ')
    try:
        login = api.call('POST', '/v1/auth/token', {'email': email, 'password': password})
    finally:
        password = None
    if not isinstance(login.get('access_token'), str) or login.get('token_type') != 'bearer':
        raise SetupFailure('Phản hồi đăng nhập PAO không hợp lệ.')
    api.token = login['access_token']
    login = None
    try:
        wid, uid, name = identity(api, selected)
        print('Doanh nghiệp: ' + name)
        print('Thuê bao Codex chỉ dùng cho chính tài khoản PAO này, không chia sẻ cho nhân viên.')
        if input('Gõ DONG Y để chuẩn bị hồ sơ và mở đăng nhập OpenAI chính thức: ').strip() != 'DONG Y':
            raise SetupFailure('Đã dừng theo lựa chọn của bạn; chưa tạo hồ sơ.')
        base = '/v1/workspaces/' + wid + '/cli-connections'
        if args.connection_id:
            rows = api.call('GET', base)['items']
            matches = [r for r in rows if r.get('id') == str(args.connection_id)]
            if len(matches) != 1:
                raise SetupFailure('Không tìm thấy hồ sơ riêng trong doanh nghiệp hiện tại.')
            row = matches[0]
        else:
            row = api.call('POST', base, {'request_key': str(uuid4()), 'model': args.model})
        checked_row(row, wid, uid, args.model, config)
        print('ID hồ sơ để tiếp tục nếu bị ngắt: ' + row['id'])
        if row.get('status') == 'connected':
            print('PAO đã ghi nhận hồ sơ kết nối. Không đổi auth hoặc chạy model trong công cụ này.')
            return
        row = api.call('POST', base + '/' + row['id'] + '/prepare', {'version': row['version']})
        checked_row(row, wid, uid, args.model, config)
        if local_config() != config:
            raise SetupFailure('Runtime đã đổi trong lúc chuẩn bị; không mở đăng nhập.')
        # Recheck current membership/session immediately before handing control to CLI.
        identity(api, selected)
        official_login(row, config, row.get('login_command'))
        result = api.call('POST', base + '/' + row['id'] + '/check-auth', {'version': row['version']})
        checked_row(result, wid, uid, args.model, config)
        if result.get('authentication_ready') is not True:
            raise SetupFailure('Chưa xác nhận được đăng nhập ChatGPT trong hồ sơ riêng.')
        print('Đã xác nhận đăng nhập. Chưa cấp grant hoặc kiểm thử suy luận; không đồng nghĩa model/quota đã được nghiệm thu.')
    finally:
        try:
            api.call('POST', '/v1/auth/sessions/revoke-current')
        except Exception:
            print('Không xác nhận được thu hồi phiên PAO vừa tạo. Hãy thu hồi phiên đó trong Cài đặt; token không được lưu ra tệp.')
        api.token = None


if __name__ == '__main__':
    try:
        main()
    except (SetupFailure, KeyboardInterrupt, EOFError) as error:
        print(str(error) if isinstance(error, SetupFailure) else 'Đã dừng. Hồ sơ đã tạo được giữ nguyên; không tự chạy lại.')
        raise SystemExit(1)
    except Exception:
        print('Thiết lập chưa hoàn tất. Không in lỗi thô hoặc thông tin đăng nhập; kiểm tra trạng thái PAO trước khi thử lại.')
        raise SystemExit(1)
