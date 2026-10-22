"""Owned process groups / Windows Job Objects, only for the known fixture.

This is process lifetime containment, NOT a filesystem/network sandbox. The
fixture waits on stdin until attachment. Future arbitrary/provider executables
need an independently verified race-free launch and OS isolation policy.
"""
import os
import signal

from .contracts import CliFailure


if os.name == 'nt':
    import ctypes
    from ctypes import wintypes

    class _Basic(ctypes.Structure):
        _fields_ = [('PerProcessUserTimeLimit', ctypes.c_int64), ('PerJobUserTimeLimit', ctypes.c_int64),
                    ('LimitFlags', wintypes.DWORD), ('MinimumWorkingSetSize', ctypes.c_size_t),
                    ('MaximumWorkingSetSize', ctypes.c_size_t), ('ActiveProcessLimit', wintypes.DWORD),
                    ('Affinity', ctypes.c_size_t), ('PriorityClass', wintypes.DWORD), ('SchedulingClass', wintypes.DWORD)]

    class _IO(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in ('ReadOperationCount', 'WriteOperationCount',
                    'OtherOperationCount', 'ReadTransferCount', 'WriteTransferCount', 'OtherTransferCount')]

    class _Extended(ctypes.Structure):
        _fields_ = [('BasicLimitInformation', _Basic), ('IoInfo', _IO), ('ProcessMemoryLimit', ctypes.c_size_t),
                    ('JobMemoryLimit', ctypes.c_size_t), ('PeakProcessMemoryUsed', ctypes.c_size_t),
                    ('PeakJobMemoryUsed', ctypes.c_size_t)]

    _kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    _kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    _kernel.CreateJobObjectW.restype = wintypes.HANDLE
    _kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    _kernel.SetInformationJobObject.restype = wintypes.BOOL
    _kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _kernel.OpenProcess.restype = wintypes.HANDLE
    _kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    _kernel.AssignProcessToJobObject.restype = wintypes.BOOL
    _kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    _kernel.TerminateJobObject.restype = wintypes.BOOL
    _kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    _kernel.CloseHandle.restype = wintypes.BOOL


class Containment:
    def __init__(self, process):
        self.process = process
        self.job = None
        if os.name != 'nt':
            return
        job = _kernel.CreateJobObjectW(None, None)
        if not job:
            raise CliFailure('cli_process_isolation_failed')
        self.job = job
        limits = _Extended()
        limits.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE
        handle = None
        try:
            if not _kernel.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
                raise CliFailure('cli_process_isolation_failed')
            handle = _kernel.OpenProcess(0x0100 | 0x0001, False, process.pid)
            if not handle or not _kernel.AssignProcessToJobObject(job, handle):
                raise CliFailure('cli_process_isolation_failed')
        except BaseException:
            _kernel.CloseHandle(job)
            self.job = None
            raise
        finally:
            if handle:
                _kernel.CloseHandle(handle)

    def stop(self):
        if os.name == 'nt':
            if self.job:
                try:
                    if not _kernel.TerminateJobObject(self.job, 1):
                        raise CliFailure('cli_cleanup_failed')
                finally:
                    _kernel.CloseHandle(self.job)
                    self.job = None
        else:
            # Group created by start_new_session, not a system-wide name/PID scan.
            try:
                os.killpg(self.process.pid, signal.SIGTERM)
            except ProcessLookupError:
                return
            # Always kill surviving descendants, even if their leader exited.
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
