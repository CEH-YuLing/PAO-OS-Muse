"""Windows CurrentUser DPAPI, never a Google credential store."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
from .bridge import Denied, profile, strict_json, require


class Blob(ctypes.Structure):
    _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_ubyte))]


def crypt(data, decrypt=False):
    require(os.name == 'nt' and isinstance(data, bytes) and 0 < len(data) <= 65536)
    buf = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    source = Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte)))
    output = Blob()
    dll = ctypes.WinDLL('crypt32', use_last_error=True)
    fn = dll.CryptUnprotectData if decrypt else dll.CryptProtectData
    fn.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                   ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    fn.restype = wintypes.BOOL
    # CRYPTPROTECT_UI_FORBIDDEN only; NOT CRYPTPROTECT_LOCAL_MACHINE.
    if not fn(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output)):
        raise Denied('Không mở được hồ sơ bảo vệ của tài khoản Windows này.')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    try:
        return ctypes.string_at(output.pbData, output.cbData)
    finally:
        kernel.LocalFree(output.pbData)


def safe_path(path):
    path = Path(path).absolute()
    for item in (path, *path.parents):
        require(not item.is_symlink() and not item.is_junction())
    return path


def read(path):
    path = safe_path(path)
    try:
        require(path.is_file() and path.stat().st_size <= 65536)
        return profile(strict_json(crypt(path.read_bytes(), True)))
    except OSError:
        raise Denied('Chưa có hồ sơ MCP hoặc hồ sơ đã được ngắt.') from None


def create(path, value):
    path = safe_path(path)
    data = crypt(json.dumps(profile(value), ensure_ascii=False).encode('utf-8'))
    with path.open('xb') as target:
        target.write(data)


def disable(path):
    path = safe_path(path)
    value = read(path)
    value['enabled'] = False
    # A retained encrypted tombstone, no global PAO or Google logout.
    data = crypt(json.dumps(value).encode())
    temp = path.with_name(path.name + '.disabled')
    safe_path(temp)
    with temp.open('xb') as target: target.write(data)
    os.replace(temp, path)
