"""Actual console X during Godot, then checkpoint resume with approved speech."""
import ctypes
from ctypes import wintypes
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
import psutil
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.scene_cache import digest,atomic_json
BASE='http://127.0.0.1:8000';EXE=ROOT/'Bangla Toon Studio.exe'


def request(path,body=None):
    data=json.dumps(body).encode() if body is not None else None
    with urllib.request.urlopen(urllib.request.Request(BASE+path,data=data,headers={'Content-Type':'application/json'}),timeout=20) as response:return json.load(response)


def until(fn,timeout=180):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        try:
            value=fn()
            if value:return value
        except (OSError,ValueError,psutil.Error):pass
        time.sleep(.25)
    raise AssertionError('Acceptance wait timed out')


if __name__=='__main__':
    assert all(j['status'] in ('completed','failed','cancelled') for j in request('/api/jobs'))
    subprocess.run([str(EXE),'--stop'],timeout=40,check=True)
    until(lambda:not psutil.pid_exists(json.loads((ROOT/'workspace/desktop-launcher.json').read_text()).get('pid',0)) if (ROOT/'workspace/desktop-launcher.json').exists() else True,30)
    subprocess.Popen([str(EXE),'--no-browser'],creationflags=subprocess.CREATE_NEW_CONSOLE)
    owner=until(lambda:request('/api/desktop/status'),90)
    source=json.loads((ROOT/'workspace/v3-browser-acceptance.json').read_text(encoding='utf-8'))
    productions={r['mode']:r['production_id'] for r in source['videos']}
    audio_before={p.name:digest(p) for p in (ROOT/'workspace/production'/productions['mini']/'audio').glob('*.wav')}
    mini=request(f"/api/production/{productions['mini']}/render",{})['job_id']
    print('Final mini with current Godot clock:',mini,flush=True)
    def active_second_scene():
        job=request('/api/jobs/'+mini)
        if job['status']=='failed':raise AssertionError(job['error'])
        scenes=job.get('render_scenes',[])
        if len(scenes)>1 and scenes[0]['status']=='completed' and scenes[1]['status']=='rendering':
            children=[p.pid for p in psutil.Process(owner['pid']).children(recursive=True) if 'godot' in p.name().lower()]
            if children:return children
    godot_pids=until(active_second_scene)
    cached=digest(ROOT/'workspace'/mini/'render/scenes/render_0001.mp4')
    user=ctypes.windll.user32
    user.PostMessageW.argtypes=[wintypes.HWND,wintypes.UINT,wintypes.WPARAM,wintypes.LPARAM]
    assert user.PostMessageW(owner['console_hwnd'],0x10,0,0)
    until(lambda:not psutil.pid_exists(owner['pid']),30)
    until(lambda:all(not psutil.pid_exists(pid) for pid in godot_pids),30)
    print('Real console X stopped server and active Godot processes',flush=True)
    subprocess.Popen([str(EXE),'--no-browser'],creationflags=subprocess.CREATE_NEW_CONSOLE)
    after=until(lambda:request('/api/desktop/status'),90);assert after['pid']!=owner['pid']
    interrupted=request('/api/jobs/'+mini);assert interrupted['status'] in ('failed','cancelled')
    request('/api/jobs/'+mini+'/resume',{})
    short=request(f"/api/production/{productions['shorts']}/render",{})['job_id']
    results=[]
    for mode,jid in [('mini',mini),('shorts',short)]:
        deadline=time.monotonic()+1200;previous=None
        while time.monotonic()<deadline:
            job=request('/api/jobs/'+jid);state=(job['status'],job['progress'])
            if state!=previous:print(mode,*state,flush=True);previous=state
            if job['status']=='failed':raise AssertionError(job['error'])
            if job['status']=='completed':break
            time.sleep(1)
        else:raise AssertionError('Final validation export timed out')
        assert job['fps']==30 and job['validated']
        assert (120<=job['duration_seconds']<=180) if mode=='mini' else (30<=job['duration_seconds']<=40)
        results.append({'mode':mode,'job_id':jid,'output':f'output/{jid}.mp4','duration_seconds':job['duration_seconds'],
                        'size':[job['width'],job['height']],'fps':job['fps'],'report':job['report'],'sha256':digest(ROOT/'output'/f'{jid}.mp4')})
    assert digest(ROOT/'workspace'/mini/'render/scenes/render_0001.mp4')==cached
    assert audio_before=={p.name:digest(p) for p in (ROOT/'workspace/production'/productions['mini']/'audio').glob('*.wav')}
    assert results[0]['report']['timings']['scenes_reused']>=1
    atomic_json(ROOT/'workspace/v3-resume-acceptance.json',{'result':'passed','closed_active_godot_pids':godot_pids,
                'server_and_godot_stopped_with_console':True,'approved_audio_unchanged':True,'scene_one_unchanged':True,'videos':results})
    print(json.dumps([{k:v for k,v in r.items() if k!='report'} for r in results],indent=2),flush=True)
