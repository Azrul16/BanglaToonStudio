"""Console EXE supervisor. Closing its window stops the local server tree."""
import argparse
import ctypes
import hashlib
import json
import logging
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
import webbrowser
from pathlib import Path

URL='http://127.0.0.1:8000'
ROOT=Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[1]
WORKSPACE=ROOT/'workspace'


def get_json(path,timeout=2):
    with urllib.request.urlopen(URL+path,timeout=timeout) as response: return json.load(response)


def is_studio():
    try:
        info=get_json('/openapi.json')
        return info.get('info',{}).get('title')=='Bangla Toon Studio' and '/api/generate' in info.get('paths',{})
    except (OSError,ValueError,urllib.error.URLError): return False


def port_open():
    try:
        with socket.create_connection(('127.0.0.1',8000),timeout=.3): return True
    except OSError: return False


def stop_studio():
    path=WORKSPACE/'desktop-launcher.json'
    if not path.is_file():
        if is_studio(): raise RuntimeError('Stop the externally started server in its terminal with Ctrl+C.')
        return
    state=json.loads(path.read_text(encoding='utf-8')); instance=state.get('instance_id','')
    if len(instance)!=32 or any(c not in '0123456789abcdef' for c in instance): raise RuntimeError('Invalid launcher state')
    try: live=get_json('/api/desktop/status')
    except (OSError,ValueError,urllib.error.URLError): return
    if live.get('instance_id')!=instance: raise RuntimeError('Another instance owns this server; it was not stopped.')
    (WORKSPACE/f'desktop-stop-{instance}').touch()
    logging.info('Shutdown requested. Waiting for the current operation to stop...')
    deadline=time.monotonic()+30
    while time.monotonic()<deadline:
        if not port_open(): return
        time.sleep(.25)
    logging.info('Shutdown is still waiting for an active blocking operation. Close the main console to stop immediately.')


def show_hardware():
    health=get_json('/api/health',60); hardware=health['hardware']
    logging.info('CPU: %s logical cores | RAM: %s GB',hardware['cpu_count'],hardware['ram_gb'])
    logging.info('NVIDIA: %s',hardware.get('nvidia') or 'not detected')
    logging.info('Speech device: %s | Torch: %s','CUDA' if hardware['cuda_available'] else 'CPU',hardware.get('torch_version','not installed'))
    logging.info('Encoder: %s | NVENC probe passed: %s | Sprite compositor: CPU Pillow',hardware['encoder'],hardware['nvenc_available'])
    logging.info('Rhubarb: %s | VITS model cached: %s',health['rhubarb_found'],health['model_cached'])


def main():
    parser=argparse.ArgumentParser(description='Run Bangla Toon Studio with a live console')
    parser.add_argument('--no-browser',action='store_true')
    parser.add_argument('--stop',action='store_true')
    parser.add_argument('--status',action='store_true')
    args=parser.parse_args()
    if args.status: return 0 if is_studio() else 3
    WORKSPACE.mkdir(exist_ok=True)
    for stream in (sys.stdout,sys.stderr):
        if stream and hasattr(stream,'reconfigure'): stream.reconfigure(encoding='utf-8',errors='replace',line_buffering=True)
    ctypes.windll.kernel32.SetConsoleOutputCP(65001)
    ctypes.windll.kernel32.SetConsoleTitleW('Bangla Toon Studio - Live Server Logs')
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)-7s %(message)s',
                        handlers=[logging.FileHandler(WORKSPACE/'launcher.log',encoding='utf-8'),logging.StreamHandler(sys.stdout)],force=True)
    mutex=None; process=None; instance=None
    finished=threading.Event()
    try:
        kernel=ctypes.windll.kernel32
        kernel.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p]
        kernel.CreateMutexW.restype=ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong]
        kernel.ReleaseMutex.argtypes=[ctypes.c_void_p]; kernel.CloseHandle.argtypes=[ctypes.c_void_p]
        name='Local\\BanglaToonStudio-'+hashlib.sha256(str(ROOT).casefold().encode()).hexdigest()[:20]
        mutex=kernel.CreateMutexW(None,True,name)
        if not mutex: raise ctypes.WinError()
        if kernel.GetLastError()==183 and kernel.WaitForSingleObject(mutex,90000) not in (0,128):
            raise RuntimeError('Another launcher is still starting. Try again shortly.')
        if args.stop: stop_studio(); return 0
        print('\n  BANGLA TOON STUDIO | LIVE SERVER\n  '+URL+'\n  Keep this window open. Ctrl+C stops cleanly; closing X stops the server.\n',flush=True)
        if is_studio():
            state=get_json('/api/desktop/status')
            if state.get('lifecycle')!='console':
                raise RuntimeError('An older background studio is running. Use Stop Studio.cmd, then reopen this executable.')
            logging.info('Already running in the original console, PID %s. No second server was started.',state['launcher_pid'])
            if not args.no_browser: webbrowser.open(URL,new=2)
            return 0
        if port_open(): raise RuntimeError('Port 8000 is occupied. Close the program using it and try again.')
        python=ROOT/'.venv/Scripts/python.exe'; helper=ROOT/'scripts/desktop_server.py'
        if not python.is_file() or not helper.is_file(): raise RuntimeError('Keep the EXE beside .venv, app, scripts and assets. See README.md for setup.')
        instance=uuid.uuid4().hex

        def request_stop():
            if process is not None and process.poll() is None:
                (WORKSPACE/f'desktop-stop-{instance}').touch()

        from scripts.windows_lifecycle import install_control_handler
        control=install_control_handler(request_stop,finished)
        environment=os.environ.copy(); environment.update(PYTHONUTF8='1',PYTHONUNBUFFERED='1')
        frozen=getattr(sys,'frozen',False)
        if frozen: kernel.SetDllDirectoryW(None)
        try:
            # Inherit THIS console. The server installs a kill-on-exit process
            # job before it can start FFmpeg/Rhubarb or other descendants.
            process=subprocess.Popen([str(python),'-u',str(helper),'--instance',instance,'--parent-pid',str(os.getpid())],
                                     cwd=str(ROOT),env=environment,stdin=subprocess.DEVNULL)
        finally:
            if frozen: kernel.SetDllDirectoryW(sys._MEIPASS)
        logging.info('Starting local server. Logs are also saved to workspace/desktop-server.log.')
        deadline=time.monotonic()+60
        while time.monotonic()<deadline:
            if process.poll() is not None: raise RuntimeError('Server startup failed. Review the error above and workspace/desktop-server.log.')
            try:
                if get_json('/api/desktop/status',1).get('instance_id')==instance: break
            except (OSError,ValueError,urllib.error.URLError): pass
            time.sleep(.25)
        else: raise RuntimeError('Server startup timed out.')
        # Release the startup mutex BEFORE staying alive, so stop/duplicate
        # commands can run while this console owns the server.
        kernel.ReleaseMutex(mutex); kernel.CloseHandle(mutex); mutex=None
        show_hardware()
        logging.info('READY: %s | Console owner PID %s',URL,os.getpid())
        if not args.no_browser: webbrowser.open(URL,new=2)
        while process.poll() is None:
            try: process.wait(timeout=.25)
            except subprocess.TimeoutExpired: continue
            except KeyboardInterrupt: request_stop()
        logging.info('Server exited with code %s. Studio stopped.',process.returncode)
        return process.returncode
    except Exception:
        logging.exception('Studio could not continue')
        if not args.no_browser and not args.stop and sys.stdin and sys.stdin.isatty():
            try: input('\nPress Enter to close this window...')
            except (EOFError,KeyboardInterrupt): pass
        return 1
    finally:
        if process is not None and process.poll() is None:
            (WORKSPACE/f'desktop-stop-{instance}').touch()
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired: pass  # Parent monitor + server job enforce cleanup on exit.
        if mutex:
            ctypes.windll.kernel32.ReleaseMutex(mutex); ctypes.windll.kernel32.CloseHandle(mutex)
        finished.set()


if __name__=='__main__': sys.exit(main())
