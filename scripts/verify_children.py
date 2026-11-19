"""Real VITS + Rhubarb + MP4 acceptance for the supplied child dialogue."""
import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.assets import load_character,plan_story,asset_references
from app.engines.story_parser import parse_story
from app.engines.animation import compose_character,render_scene
from app.engines.lip_sync import mouth_at,validate_cues
from app.library import AssetLibrary
from app.review import ReviewInput,analyze

DIALOGUE='''নাবিল: এই! তোরা কিছু শুনলি?
রায়ান: হ্যাঁ! মনে হচ্ছে মাটির নিচে কেউ আছে!
অনিকা: দাঁড়া! ওই পাতাগুলো নড়ছে কেন?'''
IDS=['nabil','rayan','fahim','anika','maliha']
BASE='http://127.0.0.1:8000'


def request(path,body=None):
    data=json.dumps(body).encode('utf-8') if body is not None else None
    req=urllib.request.Request(BASE+path,data=data,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=40) as response: return json.load(response)


def previews():
    canvas=Image.new('RGB',(1500,640),'#edf0ef')
    draw=ImageDraw.Draw(canvas)
    font=ImageFont.truetype(str(ROOT/'assets/fonts/NotoSansBengali.ttf'),26)
    for index,cid in enumerate(IDS):
        c=load_character(cid); rig,_=compose_character(c,1,'idle')
        rig=rig.resize((276,460),Image.Resampling.LANCZOS)
        canvas.paste(rig,(index*300+12,70),rig)
        draw.text((index*300+35,24),c['name_en'],font=font,fill='#203448')
        draw.text((index*300+35,551),c['name_bn'],font=font,fill='#203448')
    canvas.save(ROOT/'workspace/children-rigs-preview.png')


if __name__=='__main__':
    previews()
    choices={'story':DIALOGUE,'scenes':[{'scene_id':'scene_001','start_segment':0,'end_segment':3,'background_id':'railway_station_night','location_text':'Explicit station stage'}]}
    approved,parsed,plan=analyze(AssetLibrary(ROOT/'assets'),ReviewInput(**choices))
    assert approved['ready'],approved
    before=asset_references(plan)
    job_id=request('/api/generate',{**choices,'review_token':approved['review_token']})['job_id']
    print('Real child animation job:',job_id,flush=True)
    deadline=time.monotonic()+300; previous=None
    while time.monotonic()<deadline:
        job=request('/api/jobs/'+job_id)
        state=(job['status'],job['progress'])
        if state!=previous: print(*state,flush=True); previous=state
        if job['status'] in ('failed','cancelled'): raise RuntimeError(job.get('error',job['status']))
        if job['status']=='completed': break
        time.sleep(1)
    else: raise TimeoutError('Child animation did not finish in five minutes')
    assert job['validated'] and (job['width'],job['height'],job['fps'])==(720,1280,24)
    assert job['asset_references']==before
    timeline=request(job['timeline_url'])
    results=[]
    for clip in job['clips']:
        c=load_character(clip['speaker'])
        cue_path=ROOT/'workspace'/job_id/'cues'/f"{clip['id']}.json"
        cues=validate_cues(json.loads(cue_path.read_text(encoding='utf-8')),clip['duration_seconds'])
        assert cues['method']=='rhubarb','This real acceptance requires actual Rhubarb, not the fallback'
        shapes=sorted({cue['value'] for cue in cues['mouthCues']})
        assert set(shapes)-{'X','A'},'Expected speaking mouth shapes'
        scene=next(s for s in timeline['scenes'] if s.get('clip_id')==clip['id'])
        cue=next(cue for cue in cues['mouthCues'] if cue['value'] not in ('X','A'))
        local=(cue['start']+cue['end'])/2
        mouth=mouth_at(cues['mouthCues'],local)
        assert f'mouths/{mouth}.png' in c['file_hashes']
        image=render_scene({**scene,'plan':plan,'time':scene['start']+local,'local_time':local,
                            'total_duration':timeline['duration_seconds'],'mouth':mouth,'caption':clip['text']})
        image.save(ROOT/'workspace'/f"children-speaking-{clip['speaker']}.png")
        results.append({'speaker':clip['speaker'],'mouth_shapes':shapes,'identity_hash':c['identity_hash']})
    assert asset_references(analyze(AssetLibrary(ROOT/'assets'),ReviewInput(**choices))[2])==before
    assert [r['speaker'] for r in results]==['nabil','rayan','anika']
    with urllib.request.urlopen(BASE+job['video_url']+'?download=true') as response:
        video=response.read()
        assert response.status==200 and video[4:8]==b'ftyp'
    summary={'result':'passed','job_id':job_id,'video':f'output/{job_id}.mp4','duration_seconds':job['duration_seconds'],
             'tts_device':job['report']['tts']['device'],'encoder':job['report']['timings']['encoder'],
             'generation_seconds':job['report']['total_generation_seconds'],'speakers':results,
             'all_five_validated':[{'character_id':cid,'version':load_character(cid)['version'],'identity_hash':load_character(cid)['identity_hash']} for cid in IDS],
             'video_sha256':hashlib.sha256(video).hexdigest()}
    (ROOT/'workspace/children-acceptance.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary,indent=2))
