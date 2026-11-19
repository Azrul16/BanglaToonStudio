"""Windows server ownership: descendants die when the server process exits."""
import ctypes
from ctypes import wintypes


class BasicLimits(ctypes.Structure):
    _fields_=[('PerProcessUserTimeLimit',ctypes.c_longlong),('PerJobUserTimeLimit',ctypes.c_longlong),
              ('LimitFlags',wintypes.DWORD),('MinimumWorkingSetSize',ctypes.c_size_t),
              ('MaximumWorkingSetSize',ctypes.c_size_t),('ActiveProcessLimit',wintypes.DWORD),
              ('Affinity',ctypes.c_size_t),('PriorityClass',wintypes.DWORD),('SchedulingClass',wintypes.DWORD)]


class Counters(ctypes.Structure):
    _fields_=[(name,ctypes.c_ulonglong) for name in ('ReadOperationCount','WriteOperationCount','OtherOperationCount',
                                                   'ReadTransferCount','WriteTransferCount','OtherTransferCount')]


class ExtendedLimits(ctypes.Structure):
    _fields_=[('BasicLimitInformation',BasicLimits),('IoInfo',Counters),
              ('ProcessMemoryLimit',ctypes.c_size_t),('JobMemoryLimit',ctypes.c_size_t),
              ('PeakProcessMemoryUsed',ctypes.c_size_t),('PeakJobMemoryUsed',ctypes.c_size_t)]


def own_process_tree():
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateJobObjectW.argtypes=[ctypes.c_void_p,wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype=wintypes.HANDLE
    kernel.SetInformationJobObject.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD]
    kernel.SetInformationJobObject.restype=wintypes.BOOL
    kernel.GetCurrentProcess.restype=wintypes.HANDLE
    kernel.AssignProcessToJobObject.argtypes=[wintypes.HANDLE,wintypes.HANDLE]
    kernel.AssignProcessToJobObject.restype=wintypes.BOOL
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    job=kernel.CreateJobObjectW(None,None)
    if not job: raise ctypes.WinError(ctypes.get_last_error())
    limits=ExtendedLimits()
    limits.BasicLimitInformation.LimitFlags=0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not kernel.SetInformationJobObject(job,9,ctypes.byref(limits),ctypes.sizeof(limits)):
        error=ctypes.get_last_error(); kernel.CloseHandle(job); raise ctypes.WinError(error)
    if not kernel.AssignProcessToJobObject(job,kernel.GetCurrentProcess()):
        error=ctypes.get_last_error(); kernel.CloseHandle(job); raise ctypes.WinError(error)
    # Keep this non-inheritable handle open for this process's lifetime. Windows
    # closes it on exit, including console X/forced termination, killing FFmpeg
    # and Rhubarb descendants. Do not close it manually while the server runs.
    return job


def parent_handle(pid):
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel.OpenProcess.restype=wintypes.HANDLE
    handle=kernel.OpenProcess(0x100000,False,pid)  # SYNCHRONIZE
    if not handle: raise ctypes.WinError(ctypes.get_last_error())
    return handle


def process_exited(handle):
    kernel=ctypes.windll.kernel32
    kernel.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]
    return kernel.WaitForSingleObject(handle,0)==0


def close_handle(handle):
    ctypes.windll.kernel32.CloseHandle.argtypes=[wintypes.HANDLE]
    ctypes.windll.kernel32.CloseHandle(handle)


def console_window():
    ctypes.windll.kernel32.GetConsoleWindow.restype=wintypes.HWND
    return ctypes.windll.kernel32.GetConsoleWindow() or 0


def install_control_handler(request_stop,finished):
    callback_type=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.DWORD)
    @callback_type
    def callback(event):
        if event not in (0,1,2,5,6): return False
        request_stop()
        if event in (2,5,6): finished.wait(3.5)
        return True
    ctypes.windll.kernel32.SetConsoleCtrlHandler.argtypes=[callback_type,wintypes.BOOL]
    if not ctypes.windll.kernel32.SetConsoleCtrlHandler(callback,True): raise ctypes.WinError()
    return callback
