"""Read-only preflight: missing services only, no untracked native worker."""
import asyncio
import ctypes
from ctypes import wintypes as W
import json
from pathlib import Path
import re
import sys
from read_owned_pao_processes import k,metadata
from check_p84_foundation import primary_schema

ROOT=Path(__file__).resolve().parents[1]


def main():
    assert ROOT==Path('F:/PAO-ACOS')
    assert asyncio.run(primary_schema())['revision']=='0075'
    records=json.loads((ROOT/'.runtime/acos-processes.json').read_text())
    k.K32EnumProcesses.argtypes=[ctypes.POINTER(W.DWORD),W.DWORD,ctypes.POINTER(W.DWORD)]
    k.K32EnumProcesses.restype=W.BOOL
    pids=(W.DWORD*8192)();used=W.DWORD()
    assert k.K32EnumProcesses(pids,ctypes.sizeof(pids),ctypes.byref(used)) and used.value<ctypes.sizeof(pids)
    for pid in pids[:used.value//ctypes.sizeof(W.DWORD)]:
        handle=k.OpenProcess(0x1000,False,pid)
        if not handle:continue
        try:
            path=ctypes.create_unicode_buffer(32768);size=W.DWORD(len(path))
            matches=k.QueryFullProcessImageNameW(handle,0,path,ctypes.byref(size)) and path.value.lower()==str(Path(sys.executable).resolve()).lower()
        finally:k.CloseHandle(handle)
        if not matches:continue
        value=metadata(pid)
        assert pid not in (records['api']['id'],records['worker']['id'])
        if re.search(r'-m\s+(uvicorn\s+pao.main:app|arq\s+pao\.runtime\.WorkerSettings)',value['command']):
            raise RuntimeError('Untracked PAO API/worker exists; refuse duplicate startup')
    print('missing_services_verified; schema0075; no untracked API/worker; no migration')


if __name__=='__main__':main()
