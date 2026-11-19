"""Console-owned server with live/file logs and process-tree cleanup."""
import argparse
import json
import logging
import os
import re
import sys
import threading
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


class Tee:
    def __init__(self,console,file,lock): self.console,self.file,self.lock=console,file,lock
    def write(self,text):
        with self.lock:
            if not self.file.closed: self.file.write(text); self.file.flush()
            if self.console:
                try: self.console.write(text); self.console.flush()
                except (OSError,ValueError): pass
        return len(text)
    def flush(self):
        with self.lock:
            if not self.file.closed: self.file.flush()
            if self.console:
                try: self.console.flush()
                except (OSError,ValueError): pass
    def isatty(self): return bool(self.console and self.console.isatty())
    @property
    def encoding(self): return 'utf-8'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--instance',required=True)
    parser.add_argument('--parent-pid',required=True,type=int)
    args=parser.parse_args()
    if not re.fullmatch(r'[a-f0-9]{32}',args.instance): parser.error('Invalid desktop instance')
    from scripts.windows_lifecycle import own_process_tree,parent_handle,process_exited,close_handle,console_window,install_control_handler
    tree_job=own_process_tree()
    owner=parent_handle(args.parent_pid)
    workspace=ROOT/'workspace'; workspace.mkdir(exist_ok=True)
    log=(workspace/'desktop-server.log').open('a',encoding='utf-8',buffering=1)
    stdout,stderr=sys.stdout,sys.stderr
    for stream in (stdout,stderr):
        if stream and hasattr(stream,'reconfigure'): stream.reconfigure(encoding='utf-8',errors='replace',line_buffering=True)
    lock=threading.RLock()
    sys.stdout=Tee(stdout,log,lock); sys.stderr=Tee(stderr,log,lock)
    logging.basicConfig(level=logging.INFO,stream=sys.stdout,format='%(asctime)s %(levelname)-7s %(name)s | %(message)s',force=True)
    logger=logging.getLogger('bangla_toon.desktop')
    import uvicorn
    from app.main import app
    state_path=workspace/'desktop-launcher.json'
    stop_path=workspace/f'desktop-stop-{args.instance}'
    state={'application':'bangla-toon-studio','instance_id':args.instance,'pid':os.getpid(),
           'lifecycle':'console','launcher_pid':args.parent_pid,'console_hwnd':console_window()}

    @app.get('/api/desktop/status',include_in_schema=False)
    def desktop_status(): return state

    server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8000,workers=1,log_level='info',access_log=False))
    finished=threading.Event()

    def shutdown():
        server.should_exit=True

    control=install_control_handler(shutdown,finished)

    def watch():
        while not finished.wait(.25):
            if stop_path.is_file() or process_exited(owner):
                logger.info('Console owner closed or stop requested. Stopping server and active jobs.')
                shutdown(); return

    state_path.write_text(json.dumps(state),encoding='utf-8')
    watcher=threading.Thread(target=watch,name='console-lifetime',daemon=True)
    watcher.start()
    logger.info('Server PID %s | console owner PID %s | process-tree cleanup enabled',os.getpid(),args.parent_pid)
    try: server.run()
    finally:
        finished.set(); watcher.join(timeout=2)
        close_handle(owner)
        stop_path.unlink(missing_ok=True)
        try:
            if json.loads(state_path.read_text(encoding='utf-8')).get('instance_id')==args.instance: state_path.unlink(missing_ok=True)
        except (OSError,ValueError): pass
        logger.info('Server stopped. This console can now close.')
        sys.stdout.flush(); sys.stderr.flush()
        sys.stdout,sys.stderr=stdout,stderr
        log.close()


if __name__=='__main__': main()
