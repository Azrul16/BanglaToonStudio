"""Actual Windows console/EXE lifecycle test, including X during FFmpeg work."""
import ctypes
from ctypes import wintypes
import json
import os
import socket
import subprocess
import time
import urllib.request
from pathlib import Path
import psutil

ROOT=Path(__file__).resolve().parents[1]
EXE=ROOT/'Bangla Toon Studio.exe'
BASE='http://127.0.0.1:8000'


def connected():
    try:
        with socket.create_connection(('127.0.0.1',8000),timeout=.3): return True
    except OSError: return False


def request(path,body=None):
    if path=='/api/generate' and body and 'scenes' not in body:
        body={**body,'scenes':[{'scene_id':'scene_001','start_segment':0,'end_segment':len([line for line in body['story'].splitlines() if line.strip()]),'background_id':'railway_station_night','location_text':'Explicit lifecycle test stage'}]}
    data=json.dumps(body).encode() if body is not None else None
    req=urllib.request.Request(BASE+path,data=data,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=65) as response: return json.load(response)


def until(predicate,timeout=90):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        try:
            result=predicate()
            if result: return result
        except (OSError,ValueError,psutil.Error): pass
        time.sleep(.2)
    raise AssertionError('Timed out waiting for the console/server lifecycle')


def launch():
    process=subprocess.Popen([str(EXE),'--no-browser'],cwd=os.environ.get('TEMP',str(ROOT.parent)),
                             creationflags=subprocess.CREATE_NEW_CONSOLE)
    state=until(lambda:request('/api/desktop/status'))
    assert state['lifecycle']=='console' and state['console_hwnd']
    assert ctypes.windll.user32.IsWindowVisible(wintypes.HWND(state['console_hwnd']))
    assert process.poll() is None,'The console owner must stay alive while the server runs'
    return process,state


def close_console(process,state,children=()):
    hwnd=state['console_hwnd']
    user=ctypes.windll.user32
    user.PostMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
    assert user.PostMessageW(hwnd,0x10,0,0), 'Send the actual console-window Close event'
    until(lambda:not connected(),15)
    process.wait(timeout=15)
    until(lambda:all(not psutil.pid_exists(pid) for pid in [state['pid'],*children]),10)


if __name__=='__main__':
    if connected(): raise SystemExit('Stop the current studio before the console lifecycle test.')
    assert EXE.is_file()
    options={'cwd':str(ROOT),'creationflags':subprocess.CREATE_NO_WINDOW}
    log_path=ROOT/'workspace/desktop-server.log'
    offset=log_path.stat().st_size if log_path.exists() else 0
    summary={}
    try:
        # A real completed generation must print its working stages and details.
        first,state=launch()
        duplicate=subprocess.run([str(EXE),'--no-browser'],timeout=90,**options)
        assert duplicate.returncode==0
        assert request('/api/desktop/status')['instance_id']==state['instance_id']
        health=request('/api/health')
        assert health['hardware']['cuda_available'] and health['hardware']['nvenc_available']
        created=request('/api/generate',{'story':'নাবিল: এই! তোরা কিছু শুনলি?'})
        def complete():
            job=request('/api/jobs/'+created['job_id'])
            if job['status'] in ('failed','cancelled'): raise AssertionError(job)
            return job if job['status']=='completed' else None
        job=until(complete,180)
        with log_path.open('rb') as file:
            file.seek(offset); logs=file.read().decode('utf-8',errors='replace')
        for text in ('QUEUED','generating_audio','Speech 1/1','WAV ready','Lip sync: nabil','rendering','validating','COMPLETE','encoder:'):
            assert text in logs, f'Missing live generation detail: {text}'
        assert first.poll() is None
        close_console(first,state)
        summary.update(real_generation_job=job['job_id'],live_generation_logs=True,console_close_stops_server=True,
                       duplicate_launch_reuses_server=True,cuda_available=True,nvenc_available=True)
        print('Completed generation + live logs + console X passed',flush=True)

        # Close the real console with an actual FFmpeg encoder active.
        second,state=launch()
        created=request('/api/generate',{'story':'নাবিল: এই! তোরা কিছু শুনলি?\nরায়ান: হ্যাঁ! মনে হচ্ছে মাটির নিচে কেউ আছে!\nঅনিকা: দাঁড়া! ওই পাতাগুলো নড়ছে কেন?'})
        def encoder_pid():
            job=request('/api/jobs/'+created['job_id'])
            if job['status']=='failed': raise AssertionError(job)
            for child in psutil.Process(state['pid']).children(recursive=True):
                if child.name().lower()=='ffmpeg.exe' and job['status']=='rendering': return child.pid
            return None
        encoder=until(encoder_pid,180)
        close_console(second,state,[encoder])
        summary['close_during_render_kills_ffmpeg']=True
        print('Console X during real FFmpeg rendering passed',flush=True)

        # Explicit shutdown remains available and exits the owning console too.
        third,state=launch()
        assert subprocess.run([str(EXE),'--stop'],timeout=40,**options).returncode==0
        until(lambda:not connected(),15)
        assert third.wait(timeout=20)==0
        summary['explicit_stop_closes_console']=True
        summary.update(result='passed',exe_bytes=EXE.stat().st_size)
    finally:
        if connected(): subprocess.run([str(EXE),'--stop'],timeout=40,**options)
    (ROOT/'workspace/launcher-acceptance.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))
