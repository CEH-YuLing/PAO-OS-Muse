"""Read-only Windows process identity when CIM account lookup is unavailable.

No impersonation, debug privilege, memory reader or process termination. Uses
query-limited-information handles and the OS command-line information class.
"""
import ctypes,json,re
from ctypes import wintypes as W
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
k=ctypes.WinDLL('kernel32',use_last_error=True)
n=ctypes.WinDLL('ntdll',use_last_error=True)
k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenProcess.restype=W.HANDLE
k.CloseHandle.argtypes=[W.HANDLE];k.CloseHandle.restype=W.BOOL
k.QueryFullProcessImageNameW.argtypes=[W.HANDLE,W.DWORD,W.LPWSTR,ctypes.POINTER(W.DWORD)];k.QueryFullProcessImageNameW.restype=W.BOOL
k.GetProcessTimes.argtypes=[W.HANDLE,ctypes.POINTER(W.FILETIME),ctypes.POINTER(W.FILETIME),ctypes.POINTER(W.FILETIME),ctypes.POINTER(W.FILETIME)];k.GetProcessTimes.restype=W.BOOL
n.NtQueryInformationProcess.argtypes=[W.HANDLE,W.ULONG,ctypes.c_void_p,W.ULONG,ctypes.POINTER(W.ULONG)];n.NtQueryInformationProcess.restype=ctypes.c_long
class Unicode(ctypes.Structure):
    _fields_=[('Length',W.USHORT),('MaximumLength',W.USHORT),('Buffer',ctypes.c_void_p)]
def metadata(pid):
    handle=k.OpenProcess(0x1000,False,pid)
    if not handle:raise RuntimeError('process_query_denied')
    try:
        name=ctypes.create_unicode_buffer(32768);size=W.DWORD(len(name))
        if not k.QueryFullProcessImageNameW(handle,0,name,ctypes.byref(size)):raise RuntimeError('image_query_failed')
        times=[W.FILETIME() for _ in range(4)]
        if not k.GetProcessTimes(handle,*[ctypes.byref(v) for v in times]):raise RuntimeError('time_query_failed')
        needed=W.ULONG();n.NtQueryInformationProcess(handle,60,None,0,ctypes.byref(needed))
        if not 0<needed.value<=131072:raise RuntimeError('command_size_invalid')
        buf=ctypes.create_string_buffer(needed.value)
        if n.NtQueryInformationProcess(handle,60,buf,len(buf),ctypes.byref(needed))!=0:raise RuntimeError('command_query_failed')
        value=Unicode.from_buffer(buf);ptr=value.Buffer
        if value.Length%2 or not ctypes.addressof(buf)<=ptr<ctypes.addressof(buf)+len(buf) or ptr+value.Length>ctypes.addressof(buf)+len(buf):raise RuntimeError('command_bounds_invalid')
        command=ctypes.wstring_at(ptr,value.Length//2)
        ticks=(times[0].dwHighDateTime<<32)+times[0].dwLowDateTime+504911232000000000
        return {'id':pid,'exe':name.value,'started':ticks,'command':command}
    finally:k.CloseHandle(handle)

def main():
    records=json.loads((ROOT/'.runtime/acos-processes.json').read_text())
    rows={}
    for kind,pattern in [('api',r'-m\s+uvicorn\s+pao.main:app.+--host\s+127\.0\.0\.1.+--port\s+8100'),
                         ('worker',r'-m\s+arq\s+pao.runtime.WorkerSettings')]:
        expected=records[kind];value=metadata(expected['id'])
        assert value['started']==expected['started'] and re.search(pattern,value['command'])
        rows[kind]=value
    # Preserve the original launcher's guard against an untracked scoped worker.
    k.K32EnumProcesses.argtypes=[ctypes.POINTER(W.DWORD),W.DWORD,ctypes.POINTER(W.DWORD)]
    k.K32EnumProcesses.restype=W.BOOL
    pids=(W.DWORD*8192)();used=W.DWORD()
    if not k.K32EnumProcesses(pids,ctypes.sizeof(pids),ctypes.byref(used)) or used.value>=ctypes.sizeof(pids):raise RuntimeError('process_inventory_failed')
    for pid in pids[:used.value//ctypes.sizeof(W.DWORD)]:
        handle=k.OpenProcess(0x1000,False,pid)
        if not handle:continue
        try:
            path=ctypes.create_unicode_buffer(32768);size=W.DWORD(len(path))
            matches=k.QueryFullProcessImageNameW(handle,0,path,ctypes.byref(size)) and path.value.lower()==rows['api']['exe'].lower()
        finally:k.CloseHandle(handle)
        if not matches:continue
        value=metadata(pid)
        if re.search(r'-m\s+arq\s+pao.modules.channels.telegram_worker.WorkerSettings',value['command']):
            if not records.get('telegram') or records['telegram']['id']!=pid:raise RuntimeError('untracked_scoped_worker')
    rows['untracked_scoped_worker']=False
    print(json.dumps(rows))
if __name__=='__main__':main()
