"""Real 2–3 minute browser acceptance; no synthesized speech or video is mocked."""
import hashlib
import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.assets import load_character
from app.engines.lip_sync import validate_cues
from app.scene_cache import digest
BASE='http://127.0.0.1:8000'


def run():
    deadline=time.monotonic()+90
    while True:
        try:
            with urllib.request.urlopen(BASE+'/openapi.json',timeout=3):break
        except OSError:
            if time.monotonic()>deadline:raise
            time.sleep(.25)
    story=(ROOT/'samples/mini_cartoon_bn.txt').read_text(encoding='utf-8')
    before={cid:load_character(cid)['file_hashes'] for cid in ('nabil','rayan','anika')}
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=str(Path(os.environ['LOCALAPPDATA'])/'ms-playwright/chromium-1248/chrome-win64/chrome.exe'))
        page=browser.new_page(viewport={'width':1440,'height':1050},accept_downloads=True)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(BASE)
        page.wait_for_function("document.querySelector('#review-status').textContent.includes('validated')",timeout=120000)
        page.locator('#renderer').select_option('pillow')  # Keep this older 24 FPS benchmark.
        page.locator('#duration-mode').select_option('mini')
        assert page.locator('#video-format').input_value()=='landscape'
        assert '1280 × 720' in page.locator('#format-summary').inner_text()
        page.locator('#video-format').select_option('vertical')
        assert '720 × 1280' in page.locator('#format-summary').inner_text()
        page.locator('#video-format').select_option('landscape')
        page.locator('#story').fill(story);page.locator('#analyze').click()
        page.wait_for_function("document.querySelector('#review-status').textContent.includes('validated')",timeout=60000)
        assert page.locator('#generate').is_enabled()
        assert page.locator('#scenes .asset-row').count()==3
        page.locator('#generate').click()
        page.wait_for_function("localStorage.getItem('toon-shorts-job-v3')!==null",timeout=60000)
        jid=page.evaluate("localStorage.getItem('toon-shorts-job-v3')")
        print('Real mini cartoon job:',jid,flush=True)
        directory=ROOT/'workspace'/jid
        deadline=time.monotonic()+1800;last=None;interrupted=False;cached_video=None;cached_audio=None
        while time.monotonic()<deadline:
            started=time.monotonic();job=page.request.get(BASE+'/api/jobs/'+jid,timeout=10000).json()
            assert time.monotonic()-started<10,'Job progress must remain responsive'
            state=(job['status'],job['progress'])
            if state!=last:print(*state,flush=True);last=state
            if job['status']=='failed':raise AssertionError(job['error'])
            scenes=job.get('render_scenes',[])
            if not interrupted and len(scenes)>1 and scenes[0]['status']=='completed' and scenes[1]['status']=='rendering':
                cached_video=digest(directory/'render/scenes/render_0001.mp4')
                cached_audio={f.name:(digest(f),f.stat().st_mtime_ns) for f in (directory/'audio').glob('*.wav')}
                page.locator('#cancel').click()
                page.wait_for_function("document.querySelector('#status').textContent.startsWith('Cancelled')",timeout=120000)
                page.get_by_role('button',name='Resume unfinished scenes',exact=True).click()
                interrupted=True;print('Cancelled after scene 1 and resumed cached work',flush=True)
                time.sleep(2)
            if job['status']=='completed':break
            time.sleep(1)
        else:raise AssertionError('Mini cartoon did not finish in 30 minutes')
        assert interrupted and job['validated']
        assert (job['width'],job['height'],job['fps'])==(1280,720,24)
        assert 120<=job['duration_seconds']<=180,job['duration_seconds']
        assert cached_video==digest(directory/'render/scenes/render_0001.mp4')
        assert cached_audio=={f.name:(digest(f),f.stat().st_mtime_ns) for f in (directory/'audio').glob('*.wav')}
        assert job['report']['timings']['scenes_reused']>=1
        assert job['report']['tts']['device']=='cuda'
        timeline=page.request.get(BASE+job['timeline_url']).json()
        assert timeline['total_frames']==sum(s['end_frame']-s['start_frame'] for s in job['render_scenes'])
        assert len({s['background_id'] for s in timeline['scenes']})==3
        shapes={}
        for clip in job['clips']:
            if clip['off_screen']:continue
            cues=validate_cues(json.loads((directory/'cues'/f"{clip['id']}.json").read_text(encoding='utf-8')),clip['duration_seconds'])
            assert cues['method']=='rhubarb'
            for cue in cues['mouthCues']:
                assert f"mouths/{cue['value']}.png" in before[clip['speaker']]
                shapes.setdefault(clip['speaker'],set()).add(cue['value'])
        assert all(values-{'X','A'} for values in shapes.values())
        for cid,hashes in before.items():assert load_character(cid)['file_hashes']==hashes
        page.wait_for_function("document.querySelector('#status').textContent.includes('Your cartoon is ready')",timeout=30000)
        page.wait_for_function("document.querySelector('#video').readyState>=1",timeout=30000)
        page.locator('#video').evaluate('(v)=>v.play()')
        page.wait_for_function("document.querySelector('#video').currentTime>.3")
        page.locator('#video').evaluate('(v)=>v.pause()')
        selected=[]
        for bg in ('village_courtyard_day','mango_orchard_day','school_courtyard_day'):
            scene=next(s for s in timeline['scenes'] if s['background_id']==bg and s['kind']=='speech' and not s['off_screen'])
            selected.append(scene['start'])
            page.locator('#video').evaluate('(v,t)=>v.currentTime=t',scene['start']+.5)
            page.wait_for_function("!document.querySelector('#video').seeking && document.querySelector('#video').readyState>=2")
            page.locator('#video').screenshot(path=str(ROOT/f'workspace/mini-{bg}.png'))
        with page.expect_download(timeout=60000) as download:page.locator('#download').click()
        downloaded=ROOT/'workspace/mini-browser-download.mp4';download.value.save_as(downloaded)
        assert digest(downloaded)==digest(ROOT/'output'/f'{jid}.mp4')
        page.screenshot(path=str(ROOT/'workspace/mini-studio-browser.png'),full_page=True)
        page.set_viewport_size({'width':390,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(ROOT/'workspace/mini-studio-mobile.png'),full_page=True)
        assert not errors,errors
        summary={'result':'passed','job_id':jid,'output':f'output/{jid}.mp4','duration_seconds':job['duration_seconds'],
                 'width':job['width'],'height':job['height'],'fps':24,'source_scenes':3,'render_scenes':len(job['render_scenes']),
                 'resumed_after_scene_one':True,'wav_bytes_and_mtimes_unchanged':True,'scene_one_bytes_unchanged':True,
                 'mouth_shapes':{k:sorted(v) for k,v in shapes.items()},'character_hashes_unchanged':True,
                 'browser_errors':errors,'download_sha256':digest(downloaded),'report':job['report'],'attempts':job['attempts']}
        (ROOT/'workspace/mini-cartoon-acceptance.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in summary.items() if k!='report'},indent=2),flush=True)
        browser.close()

if __name__=='__main__':run()
