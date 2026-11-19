"""Real Godot/approved-VITS Shorts and episode acceptance, no mocked media."""
import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.scene_cache import digest,atomic_json
from app.assets import load_character
BASE='http://127.0.0.1:8000'


def run():
    deadline=time.monotonic()+90
    while True:
        try:
            with urllib.request.urlopen(BASE+'/api/voices/providers',timeout=3):break
        except OSError:
            if time.monotonic()>deadline:raise
            time.sleep(.25)
    originals={cid:load_character(cid)['file_hashes'] for cid in ('nabil','rayan','anika')}
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=str(Path(os.environ['LOCALAPPDATA'])/'ms-playwright/chromium-1248/chrome-win64/chrome.exe'))
        page=browser.new_page(viewport={'width':1440,'height':1050},accept_downloads=True)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(BASE)
        page.wait_for_function("document.querySelector('#review-status').textContent.includes('validated')",timeout=120000)
        assert page.locator('#renderer').input_value()=='godot'
        assert page.locator('#generate').is_disabled()
        results=[]
        for mode,sample in [('shorts','short_cartoon_bn.txt'),('mini','mini_cartoon_bn.txt')]:
            page.locator('#duration-mode').select_option(mode)
            page.locator('#story').fill((ROOT/'samples'/sample).read_text(encoding='utf-8'))
            page.locator('#analyze').click()
            page.wait_for_function("document.querySelector('#review-status').textContent.includes('validated')",timeout=60000)
            page.locator('#prepare-production').click()
            expected=5 if mode=='shorts' else 25
            page.wait_for_function("n=>document.querySelectorAll('.speech-line').length===n",arg=expected,timeout=60000)
            sid=page.evaluate("localStorage.getItem('toon-production-v3')")
            print(mode,'production',sid,flush=True)
            page.locator('#generate-local-previews').click()
            deadline=time.monotonic()+600
            while time.monotonic()<deadline:
                session=page.request.get(BASE+'/api/production/'+sid).json()
                if all(s['takes'] and s['takes'][-1]['status']=='completed' for s in session['segments']):break
                failed=[t for s in session['segments'] for t in s['takes'] if t['status']=='failed']
                assert not failed,failed
                time.sleep(1)
            else:raise AssertionError('Real speech previews timed out')
            # Let the normal frontend polling display all completed takes.
            page.wait_for_function("n=>document.querySelectorAll('#speech-lines audio').length===n",arg=expected,timeout=30000)
            if mode=='shorts':
                first=page.locator('.speech-line').nth(0)
                first.locator('audio').first.evaluate('(a)=>a.play()')
                page.wait_for_function("document.querySelector('#speech-lines audio').currentTime>.2",timeout=30000)
                first.locator('audio').first.evaluate('(a)=>a.pause()')
                # Edit one spoken line/direction, keeping its original caption and other takes.
                text=first.locator('textarea').first.input_value().replace('পৌঁছাল','এসেছিল')
                first.locator('textarea').first.fill(text)
                first.get_by_label('Action',exact=True).select_option('walk')
                first.get_by_role('button',name='Save line / direction',exact=True).click()
                page.wait_for_function("document.querySelectorAll('.speech-line')[0].dataset.revision==='2'")
                first.get_by_role('button',name='Generate another take',exact=True).click()
                deadline=time.monotonic()+120
                while time.monotonic()<deadline:
                    session=page.request.get(BASE+'/api/production/'+sid).json()
                    if len(session['segments'][0]['takes'])==2 and session['segments'][0]['takes'][-1]['status']=='completed':break
                    time.sleep(.5)
                assert len(session['segments'][0]['takes'])==2
                assert all(len(s['takes'])==1 for s in session['segments'][1:])
                assert 'পৌঁছাল' in session['segments'][0]['original_text']
                page.wait_for_function("document.querySelectorAll('.speech-line')[0].querySelectorAll('audio').length===2",timeout=30000)
            # Explicitly approve through the actual UI, selecting the newest current take.
            for i in range(expected):
                row=page.locator('.speech-line').nth(i)
                if not row.evaluate('(d)=>d.open'):row.locator('summary').first.click()
                row.get_by_role('button',name='Approve this take',exact=True).last.click()
                page.wait_for_function("i=>document.querySelectorAll('.speech-line')[i].querySelector('summary').textContent.includes('· approved ·')",arg=i,timeout=30000)
            assert page.locator('#generate').is_enabled()
            previous=page.evaluate("localStorage.getItem('toon-shorts-job-v3')")
            page.locator('#generate').click()
            page.wait_for_function("old=>localStorage.getItem('toon-shorts-job-v3')!==old",arg=previous,timeout=60000)
            jid=page.evaluate("localStorage.getItem('toon-shorts-job-v3')")
            print(mode,'Godot render',jid,flush=True)
            deadline=time.monotonic()+1200;last=None
            while time.monotonic()<deadline:
                job=page.request.get(BASE+'/api/jobs/'+jid,timeout=10000).json()
                state=(job['status'],job['progress'])
                if state!=last:print(*state,flush=True);last=state
                assert job['status'] not in ('failed','cancelled'),job.get('error')
                if job['status']=='completed':break
                time.sleep(1)
            else:raise AssertionError('Godot episode timed out')
            assert job['fps']==30 and job['validated'] and job['report']['sprite_renderer'].startswith('Godot')
            if mode=='shorts':assert 30<=job['duration_seconds']<=40 and (job['width'],job['height'])==(720,1280)
            else:assert 120<=job['duration_seconds']<=180 and (job['width'],job['height'])==(1280,720)
            assert job['approved_speech'] and len(job['approved_speech'])==expected
            page.wait_for_function("document.querySelector('#status').textContent.includes('Your cartoon is ready')",timeout=30000)
            page.wait_for_function("document.querySelector('#video').readyState>=1",timeout=30000)
            page.locator('#video').evaluate('(v)=>v.play()')
            page.wait_for_function("document.querySelector('#video').currentTime>.2")
            page.locator('#video').evaluate('(v)=>v.pause()')
            timeline=page.request.get(BASE+job['timeline_url']).json()
            for bg in {s['background_id'] for s in timeline['scenes']}:
                scene=next(s for s in timeline['scenes'] if s['background_id']==bg and s['kind']=='speech')
                page.locator('#video').evaluate('(v,t)=>v.currentTime=t',scene['start']+.3)
                page.wait_for_function("!document.querySelector('#video').seeking && document.querySelector('#video').readyState>=2")
                page.locator('#video').screenshot(path=str(ROOT/f'workspace/v3-{mode}-{bg}.png'))
            with page.expect_download(timeout=60000) as download:page.locator('#download').click()
            path=ROOT/f'workspace/v3-{mode}-download.mp4';download.value.save_as(path)
            assert digest(path)==digest(ROOT/'output'/f'{jid}.mp4')
            page.screenshot(path=str(ROOT/f'workspace/v3-{mode}-studio.png'),full_page=True)
            results.append({'mode':mode,'job_id':jid,'production_id':sid,'duration_seconds':job['duration_seconds'],
                            'size':[job['width'],job['height']],'fps':30,'sha256':digest(path),'report':job['report']})
        for cid,hashes in originals.items():assert load_character(cid)['file_hashes']==hashes
        page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(ROOT/'workspace/v3-mobile.png'),full_page=True)
        assert not errors,errors
        atomic_json(ROOT/'workspace/v3-browser-acceptance.json',{'result':'passed','videos':results,'browser_errors':errors,'original_character_hashes_unchanged':True,
                    'cloud_voice_calls':'not executed; credentials unavailable','listening_quality':'Requires user listening review; local voice is unchanged VITS, not claimed as distinct natural voices'})
        print(json.dumps([{k:v for k,v in r.items() if k!='report'} for r in results],indent=2),flush=True)
        browser.close()

if __name__=='__main__':run()
