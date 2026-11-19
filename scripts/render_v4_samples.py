"""Run the same automatic endpoint as the one-click UI, with real offline speech."""
import json
import shutil
import sys
import time
import urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.scene_cache import atomic_json,digest
BASE='http://127.0.0.1:8000'


def request(route,data=None):
    raw=json.dumps(data,ensure_ascii=False).encode() if data is not None else None
    with urllib.request.urlopen(urllib.request.Request(BASE+route,raw,headers={'Content-Type':'application/json'}),timeout=90) as response:return json.load(response)


def run():
    deadline=time.monotonic()+90
    while True:
        try:request('/api/desktop/status');break
        except OSError:
            if time.monotonic()>deadline:raise
            time.sleep(.3)
    results=[];short_only='--short-only' in sys.argv
    previous=json.loads((ROOT/'workspace/v4-samples-acceptance.json').read_text(encoding='utf-8')) if short_only else None
    selected=[('shorts','v4_benchmark_bn.txt','v4-benchmark.mp4'),('mini','mini_cartoon_bn.txt','v4-mini-cartoon.mp4')]
    for mode,sample,target in selected[:1] if short_only else selected:
        body={'story':(ROOT/'samples'/sample).read_text(encoding='utf-8'),'duration_mode':mode,'renderer':'godot','music':True}
        plan=request('/api/automatic/plan',body)
        assert plan['review']['ready'],plan['review']['issues']
        assert not plan['paid'],'This acceptance script does not authorize paid requests'
        created=request('/api/automatic/generate',body);aid=created['automatic_id'];last=None;deadline=time.monotonic()+1800
        print(mode,aid,flush=True)
        while time.monotonic()<deadline:
            data=request('/api/automatic/'+aid);job=data.get('render',{})
            state=(data['status'],data.get('completed_segments'),job.get('progress'))
            if state!=last:print(state,flush=True);last=state
            assert data['status'] not in ('failed','cancelled'),data.get('error')
            if data['status']=='completed':break
            time.sleep(1)
        else:raise AssertionError('Sample export timed out')
        assert job['validated'] and job['fps']==30
        if mode=='shorts':assert 30<=job['duration_seconds']<=40 and (job['width'],job['height'])==(1080,1920)
        else:assert 120<=job['duration_seconds']<=180 and (job['width'],job['height'])==(1080,1920)
        movie=ROOT/'output'/target;shutil.copyfile(ROOT/'output'/(job['job_id']+'.mp4'),movie)
        results.append({'mode':mode,'automatic_id':aid,'job_id':job['job_id'],'duration_seconds':job['duration_seconds'],'video':str(movie),'sha256':digest(movie),
                        'production_id':data['production_id'],'reused_speech':data.get('reused_speech',0),'approved_speech':job['approved_speech'],'report':job['report']})
        saved=results+[v for v in previous['videos'] if v['mode']=='mini'] if short_only else results
        atomic_json(ROOT/'workspace/v4-samples-acceptance.json',{'result':'passed' if short_only or mode=='mini' else 'in_progress','videos':saved,'provider':'Actual local VITS; no cloud calls authorized'})
    print('V4 real samples passed',flush=True)


if __name__=='__main__':run()
