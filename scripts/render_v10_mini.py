"""Render the complete existing mini story with selected category voices."""
import json
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.scene_cache import atomic_json
from scripts.audit_v4_media import audit
BASE='http://127.0.0.1:8000'
def request(path,body=None,method='POST'):
    raw=json.dumps(body).encode() if body is not None else None
    with urllib.request.urlopen(urllib.request.Request(BASE+path,data=raw,method=method if raw else 'GET',headers={'Content-Type':'application/json'}),timeout=90) as response:return json.load(response)
def main():
    # Avoid competing with the browser's shared single-worker acceptance run.
    deadline=time.monotonic()+1200
    while not (ROOT/'workspace/v10-browser-acceptance.json').is_file():
        if time.monotonic()>deadline:raise RuntimeError('Browser acceptance did not complete; mini run was not submitted')
        time.sleep(2)
    previous=request('/api/preferences');prefs={k:previous[k] for k in ('format','voice_preference','music','interpretation_mode','semantic_ai_approved')}
    try:
        request('/api/preferences',{**prefs,'format':'mini','voice_preference':'chatterbox_bangla','music':True,'interpretation_mode':'rules','semantic_ai_approved':False},'PUT')
        created=request('/api/conversations',{'prompt':(ROOT/'samples/v10_mini_cartoon_bn.txt').read_text(encoding='utf-8')})
    finally:request('/api/preferences',prefs,'PUT')
    atomic_json(ROOT/'workspace/v10-mini-submitted.json',created);cid=created['id'];started=time.monotonic();previous=None
    while time.monotonic()-started<1800:
        data=request('/api/conversations/'+cid);state=(data['status'],data.get('speech_completed'),data.get('scene_completed'))
        if state!=previous:print(state,flush=True);previous=state
        if data['status']=='completed':break
        if data['status'] in ('failed','cancelled','needs_input','needs_payment','waiting'):raise RuntimeError(str(data))
        time.sleep(1)
    assert data['status']=='completed',data
    job=request('/api/jobs/'+data['job_id']);assert job['validated'] and job['evaluation_only']
    output=ROOT/'output/v10-mini-cartoon-evaluation.mp4';shutil.copyfile(ROOT/'output'/(data['job_id']+'.mp4'),output)
    entry={'job_id':data['job_id'],'video':str(output),'approved_speech':job['approved_speech']};result=audit(entry)
    assert result['resolution']==[1080,1920] and 120<=result['duration_seconds']<=180,result
    atomic_json(ROOT/'workspace/v10-mini-verification.json',{'conversation_id':cid,'media':result,'elapsed_seconds':time.monotonic()-started,'human_listening_review':'pending','commercial_permission_verified':False})
    print(json.dumps(result),flush=True)
if __name__=='__main__':main()
