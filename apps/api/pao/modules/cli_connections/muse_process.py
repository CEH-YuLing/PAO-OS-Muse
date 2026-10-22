"""Windows lifetime containment: attach a suspended child before any instruction.

This is NOT a filesystem/network sandbox. Muse's empty native preset and the
separate profile policy form the tool/context boundary; this module only owns
and terminates the exact process tree, without name-based process scanning.
"""
import os
import subprocess
import time

if os.name == 'nt':
    import ctypes
    from ctypes import wintypes as W
    from pao_cli_runtime.containment import Containment
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    class ThreadEntry(ctypes.Structure):
        _fields_=[('size',W.DWORD),('usage',W.DWORD),('id',W.DWORD),('owner',W.DWORD),
                  ('priority',W.LONG),('delta',W.LONG),('flags',W.DWORD)]
    k.CreateToolhelp32Snapshot.argtypes=[W.DWORD,W.DWORD];k.CreateToolhelp32Snapshot.restype=W.HANDLE
    k.Thread32First.argtypes=[W.HANDLE,ctypes.POINTER(ThreadEntry)];k.Thread32First.restype=W.BOOL
    k.Thread32Next.argtypes=[W.HANDLE,ctypes.POINTER(ThreadEntry)];k.Thread32Next.restype=W.BOOL
    k.OpenThread.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenThread.restype=W.HANDLE
    k.GetProcessIdOfThread.argtypes=[W.HANDLE];k.GetProcessIdOfThread.restype=W.DWORD
    k.ResumeThread.argtypes=[W.HANDLE];k.ResumeThread.restype=W.DWORD
    k.CloseHandle.argtypes=[W.HANDLE];k.CloseHandle.restype=W.BOOL
    class JobAccounting(ctypes.Structure):
        _fields_=[('user',ctypes.c_int64),('kernel',ctypes.c_int64),('period_user',ctypes.c_int64),
            ('period_kernel',ctypes.c_int64),('faults',W.DWORD),('total',W.DWORD),('active',W.DWORD),('terminated',W.DWORD)]
    k.QueryInformationJobObject.argtypes=[W.HANDLE,ctypes.c_int,ctypes.c_void_p,W.DWORD,ctypes.c_void_p];k.QueryInformationJobObject.restype=W.BOOL
    k.TerminateJobObject.argtypes=[W.HANDLE,W.UINT];k.TerminateJobObject.restype=W.BOOL


def resume_owned(process):
    snapshot=k.CreateToolhelp32Snapshot(4,0)
    if snapshot in (None,ctypes.c_void_p(-1).value):raise RuntimeError('muse_thread_snapshot_failed')
    threads=[]
    try:
        row=ThreadEntry();row.size=ctypes.sizeof(row)
        present=k.Thread32First(snapshot,ctypes.byref(row))
        while present:
            if row.owner==process.pid:threads.append(row.id)
            present=k.Thread32Next(snapshot,ctypes.byref(row))
    finally:k.CloseHandle(snapshot)
    if len(threads)!=1 or process.poll() is not None:raise RuntimeError('muse_suspended_identity_invalid')
    thread=k.OpenThread(0x0002|0x0800,False,threads[0])
    if not thread:raise RuntimeError('muse_thread_open_failed')
    try:
        if k.GetProcessIdOfThread(thread)!=process.pid or k.ResumeThread(thread)!=1:
            raise RuntimeError('muse_thread_resume_failed')
    finally:k.CloseHandle(thread)


class Child:
    def __init__(self,command,*,cwd,env):
        if os.name!='nt':raise RuntimeError('muse_platform_unavailable')
        self.containment=None;self.cleanup_verified=False
        self.process=subprocess.Popen(command,cwd=cwd,env=env,stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW|0x00000004)  # CREATE_SUSPENDED
        try:self.containment=Containment(self.process)
        except BaseException:
            self.process.kill();self.process.wait(timeout=5);raise

    def resume(self):resume_owned(self.process)

    def close(self):
        try:
            if self.containment and self.containment.job:
                job=self.containment.job
                if not k.TerminateJobObject(job,1):raise RuntimeError('muse_cleanup_failed')
                deadline=time.monotonic()+5
                while True:
                    value=JobAccounting()
                    if not k.QueryInformationJobObject(job,1,ctypes.byref(value),ctypes.sizeof(value),None):raise RuntimeError('muse_cleanup_unverified')
                    if value.active==0:break
                    if time.monotonic()>deadline:raise RuntimeError('muse_cleanup_unverified')
                    time.sleep(.02)
                k.CloseHandle(job);self.containment.job=None
            self.process.wait(timeout=5)
            self.cleanup_verified=True
        finally:
            if self.containment and self.containment.job:
                # Closing this owned KILL_ON_JOB_CLOSE handle is still a best
                # effort stop, never reported as verified if the query failed.
                k.CloseHandle(self.containment.job);self.containment.job=None
            for stream in (self.process.stdout,self.process.stderr):
                if stream:stream.close()
