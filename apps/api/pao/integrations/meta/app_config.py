"""Installation-local Meta App settings. No network calls or secret responses."""
import hashlib
import hmac
import io
import os
import re
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from cryptography.fernet import Fernet
from dotenv import dotenv_values
from fastapi import HTTPException
from ...config import ROOT, settings

ENV_PATH = ROOT / '.env'
SAFE_FLAGS = ('META_WRITE_ENABLED', 'META_AUTOPILOT_ENABLED', 'ADS_AUTOPILOT_GLOBAL_ENABLED')


def preserve_permissions(source, target):
    os.chmod(target, source.stat().st_mode & 0o777)
    if os.name == 'nt':
        # Atomic replace must not drop a private Windows DACL on the old .env.
        import ctypes
        from ctypes import wintypes
        api = ctypes.WinDLL('advapi32', use_last_error=True)
        get = api.GetFileSecurityW
        get.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
        get.restype = wintypes.BOOL
        required = wintypes.DWORD()
        get(str(source), 4, None, 0, ctypes.byref(required))  # DACL_SECURITY_INFORMATION
        if not required.value:
            raise OSError('Cannot read private file permissions')
        descriptor = ctypes.create_string_buffer(required.value)
        if not get(str(source), 4, descriptor, required.value, ctypes.byref(required)):
            raise OSError('Cannot read private file permissions')
        get_control = api.GetSecurityDescriptorControl
        get_control.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.WORD), ctypes.POINTER(wintypes.DWORD)]
        get_control.restype = wintypes.BOOL
        control, version = wintypes.WORD(), wintypes.DWORD()
        if not get_control(descriptor, ctypes.byref(control), ctypes.byref(version)):
            raise OSError('Cannot read private file permissions')
        # Preserve the protection bit too, not just ACEs; otherwise inherited
        # parent permissions could broaden a deliberately restricted file.
        mask = 4 | (0x80000000 if control.value & 0x1000 else 0x20000000)
        get_dacl = api.GetSecurityDescriptorDacl
        get_dacl.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.BOOL), ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.BOOL)]
        get_dacl.restype = wintypes.BOOL
        present, defaulted, dacl = wintypes.BOOL(), wintypes.BOOL(), ctypes.c_void_p()
        if not get_dacl(descriptor, ctypes.byref(present), ctypes.byref(dacl), ctypes.byref(defaulted)) or not present.value:
            raise OSError('Cannot read private file permissions')
        set_security = api.SetNamedSecurityInfoW
        set_security.argtypes = [wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD,
                                ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
        set_security.restype = wintypes.DWORD
        if set_security(str(target), 1, mask, None, None, dacl, None) != 0:
            raise OSError('Cannot preserve private file permissions')


class MetaAppSave(BaseModel):
    model_config = ConfigDict(extra='forbid')
    app_id: str = Field(pattern=r'^[0-9]{1,64}$')
    api_version: str = Field(pattern=r'^v[0-9]+\.[0-9]+$', max_length=16)
    redirect_uri: str = Field(max_length=512)
    app_secret: SecretStr | None = None
    revision: str = Field(pattern=r'^[a-f0-9]{64}$')

    @field_validator('app_id', 'api_version', 'redirect_uri', 'revision')
    @classmethod
    def no_control_characters(cls, value):
        if any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError('invalid characters')
        return value

    @field_validator('app_secret')
    @classmethod
    def validate_secret(cls, value):
        if value is not None and not re.fullmatch(r'[A-Za-z0-9_-]{16,256}', value.get_secret_value()):
            raise ValueError('invalid secret')
        return value

    @field_validator('redirect_uri')
    @classmethod
    def validate_callback(cls, value):
        uri = urlsplit(value)
        if (uri.username or uri.password or uri.query or uri.fragment or not uri.hostname
                or uri.path != '/v1/integrations/meta/callback'
                or not (uri.scheme == 'https' or uri.scheme == 'http' and uri.hostname in ('localhost', '127.0.0.1'))):
            raise ValueError('invalid callback')
        uri.port  # Validate malformed/out-of-range ports too.
        return value


class MetaAppStatus(BaseModel):
    app_id: str
    api_version: str
    redirect_uri: str
    secret_present: bool
    revision: str
    restart_required: bool
    write_enabled: bool
    autopilot_enabled: bool
    scope: str = 'installation_local'


def read_file():
    try:
        if ENV_PATH.is_symlink() or not ENV_PATH.is_file() or ENV_PATH.stat().st_size > 1_048_576:
            raise OSError('unsafe file')
        raw = ENV_PATH.read_bytes()
        values = dotenv_values(stream=io.StringIO(raw.decode('utf-8-sig')))
        return raw, values
    except (OSError, UnicodeError):
        raise HTTPException(503, 'meta_app_config_unavailable') from None


def revision(raw):
    return hmac.new(settings().jwt_secret.encode(), raw, hashlib.sha256).hexdigest()


def status():
    raw, values = read_file()
    config = settings()
    fields = {'meta_app_id': values.get('META_APP_ID') or '',
              'meta_graph_api_version': values.get('META_GRAPH_API_VERSION') or '',
              'meta_redirect_uri': values.get('META_REDIRECT_URI') or config.meta_redirect_uri,
              'meta_app_secret': values.get('META_APP_SECRET') or '',
              'integration_encryption_key': values.get('INTEGRATION_ENCRYPTION_KEY') or ''}
    pending = any(getattr(config, key) != value for key, value in fields.items())
    pending = pending or (values.get('META_ENABLED', '').lower() in ('true', '1')) != config.meta_enabled
    return MetaAppStatus(app_id=fields['meta_app_id'], api_version=fields['meta_graph_api_version'],
                         redirect_uri=fields['meta_redirect_uri'], secret_present=bool(fields['meta_app_secret']),
                         revision=revision(raw), restart_required=pending,
                         write_enabled=config.meta_write_enabled,
                         autopilot_enabled=config.meta_autopilot_enabled or config.ads_autopilot_global_enabled)


def runtime_ready():
    # Only UI-managed changes add this marker; preserve legacy CLI/test behavior.
    _, values = read_file()
    return values.get('META_APP_CONFIG_SOURCE') != 'settings_ui' or not status().restart_required


def save(body):
    # Environment overrides would survive a restart and make the UI misleading.
    names = ('META_ENABLED', 'META_APP_ID', 'META_APP_SECRET', 'META_GRAPH_API_VERSION',
             'META_REDIRECT_URI', 'INTEGRATION_ENCRYPTION_KEY', *SAFE_FLAGS)
    if any(name in os.environ for name in names):
        raise HTTPException(409, 'meta_app_environment_override')
    if settings().meta_write_enabled or settings().meta_autopilot_enabled or settings().ads_autopilot_global_enabled:
        raise HTTPException(409, 'meta_app_requires_readonly_mode')
    lock = ENV_PATH.with_name('.meta-app-config.lock')
    descriptor = None
    temporary = None
    try:
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            raise HTTPException(409, 'meta_app_config_busy') from None
        raw, values = read_file()
        if not hmac.compare_digest(revision(raw), body.revision):
            raise HTTPException(409, 'meta_app_config_stale')
        secret = body.app_secret.get_secret_value() if body.app_secret is not None else values.get('META_APP_SECRET')
        if not secret or (body.app_id != values.get('META_APP_ID') and body.app_secret is None):
            raise HTTPException(422, 'meta_app_secret_required')
        key = values.get('INTEGRATION_ENCRYPTION_KEY') or Fernet.generate_key().decode()
        try:
            Fernet(key.encode())
        except (ValueError, TypeError):
            raise HTTPException(409, 'meta_app_existing_encryption_key_invalid') from None
        updates = {'META_ENABLED': 'true', 'META_APP_ID': body.app_id, 'META_APP_SECRET': secret,
                   'META_GRAPH_API_VERSION': body.api_version, 'META_REDIRECT_URI': body.redirect_uri,
                   'INTEGRATION_ENCRYPTION_KEY': key, 'META_APP_CONFIG_SOURCE': 'settings_ui',
                   **{flag: 'false' for flag in SAFE_FLAGS}}
        lines = []
        for line in raw.decode('utf-8-sig').splitlines():
            match = re.match(r'^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=', line)
            if not match or match.group(1).upper() not in updates:
                lines.append(line)
        content = '\n'.join(lines + [f'{name}={value}' for name, value in updates.items()]) + '\n'
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=ENV_PATH.parent,
                                         prefix='.meta-app-', suffix='.tmp', delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        preserve_permissions(ENV_PATH, temporary)
        if ENV_PATH.read_bytes() != raw:
            raise HTTPException(409, 'meta_app_config_stale')
        os.replace(temporary, ENV_PATH)
        temporary = None
        return status()
    except OSError:
        raise HTTPException(503, 'meta_app_config_write_failed') from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        if descriptor is not None:
            os.close(descriptor)
            lock.unlink(missing_ok=True)
