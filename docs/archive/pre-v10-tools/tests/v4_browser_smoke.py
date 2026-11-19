"""Actual one-click UI, local speech, Godot, sound and cached remix acceptance."""
import json
import os
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.scene_cache import atomic_json,digest
from app.assets import load_character
BASE='http://127.0.0.1:8000'


def run():
    originals={cid:load_character(cid)['file_hashes'] for cid in ('nabil','rayan','anika')}
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=str(Path(os.environ['LOCALAPPDATA'])/'ms-playwright/chromium-1248/chrome-win64/chrome.exe'))
        page=browser.new_page(viewport={'width':1440,'height':1000},accept_downloads=True)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(BASE);page.wait_for_function("document.querySelector('#readiness').textContent.includes('Model:')",timeout=90000)
        assert not page.locator('#studio-tools').evaluate('(e)=>e.open')
        assert not page.locator('#prepare-production').is_visible() and not page.locator('#analyze').is_visible()
        assert page.locator('[role=tablist] [role=tab]').count()==4
        story=(ROOT/'samples/v4_benchmark_bn.txt').read_text(encoding='utf-8')
        page.locator('#story').fill(story)
        page.screenshot(path=str(ROOT/'workspace/v4-simple-start.png'),full_page=True)
        results=[]
        for name in ('benchmark','remix'):
            if name=='remix':
                page.locator('#studio-tools').evaluate('(e)=>e.open=true')
                page.locator('#music').evaluate('(e)=>e.closest("details").open=true')
                page.locator('#music').uncheck()
                page.locator('#studio-tools').evaluate('(e)=>e.open=false')
            previous=page.evaluate("localStorage.getItem('toon-automatic-v4')")
            page.locator('#auto-generate').click()
            page.wait_for_function("old=>localStorage.getItem('toon-automatic-v4')!==old",arg=previous,timeout=90000)
            aid=page.evaluate("localStorage.getItem('toon-automatic-v4')");print(name,aid,flush=True)
            deadline=time.monotonic()+900;last=None
            while time.monotonic()<deadline:
                auto=page.request.get(BASE+'/api/automatic/'+aid,timeout=10000).json()
                state=(auto['status'],auto.get('completed_segments'),auto.get('render',{}).get('progress'))
                if state!=last:print(state,flush=True);last=state
                assert auto['status'] not in ('failed','cancelled'),auto.get('error')
                if auto['status']=='completed':break
                time.sleep(1)
            else:raise AssertionError('Automatic cartoon timed out')
            job=auto['render'];jid=job['job_id']
            assert job['validated'] and job['fps']==30 and (job['width'],job['height'])==(720,1280)
            assert [s['speaker'] for s in job['clips']]==['nabil','rayan','anika']
            assert len(auto['spoken_preview'])==3
            timeline=page.request.get(BASE+job['timeline_url']).json()
            assert len(timeline['speech_track'])==3
            sounds=json.loads((ROOT/'workspace'/jid/'sound-events.json').read_text(encoding='utf-8'))
            assert set(sounds['tracks'])=={'dialogue','narration','music','ambience','sfx','action'}
            assert any(e['sound']=='rustling_leaves' for e in sounds['events'])
            assert any(e['track']=='action' and e.get('foot') for e in sounds['events'])
            if name=='benchmark':assert any(e['sound']=='music_mystery' for e in sounds['events'])
            else:assert auto['reused_speech']==3 and not any(e['track']=='music' for e in sounds['events'])
            page.wait_for_function("document.querySelector('#status').textContent.includes('Your cartoon is ready')",timeout=30000)
            page.wait_for_function("document.querySelector('#video').readyState>=1",timeout=30000)
            page.locator('#video').evaluate('(v)=>v.play()');page.wait_for_function("document.querySelector('#video').currentTime>.2")
            page.locator('#video').evaluate('(v)=>v.pause()')
            if name=='benchmark':
                for label,point in [('walk',2.),('speech',timeline['speech_track'][0]['start']+.6),('reaction',timeline['scenes'][-1]['start']+.4)]:
                    page.locator('#video').evaluate('(v,t)=>v.currentTime=t',point)
                    page.wait_for_function("!document.querySelector('#video').seeking && document.querySelector('#video').readyState>=2")
                    page.locator('#video').screenshot(path=str(ROOT/f'workspace/v4-{label}.png'))
            with page.expect_download() as download:page.locator('#download').click()
            target=ROOT/f'output/v4-{name}.mp4';download.value.save_as(target)
            assert digest(target)==digest(ROOT/'output'/f'{jid}.mp4')
            results.append({'name':name,'automatic_id':aid,'job_id':jid,'duration_seconds':job['duration_seconds'],'video':str(ROOT/'output'/f'{jid}.mp4'),'downloaded_name_at_test':str(target),'sha256':digest(target),
                            'approved_speech':job['approved_speech'],'reused_speech':auto.get('reused_speech',0),'report':job['report'],'sounds':sounds})
        assert [s['audio_hash'] for s in results[0]['approved_speech']]==[s['audio_hash'] for s in results[1]['approved_speech']]
        # Four categories are optional configuration, not gates in automatic generation.
        page.locator('#studio-tools').evaluate('(e)=>e.open=true')
        for category in ('male','female','child_male','child_female'):
            page.locator(f'[data-category={category}]').click()
            assert page.locator(f'[data-category={category}]').get_attribute('aria-selected')=='true'
        page.locator('#studio-tools').evaluate('(e)=>e.open=false')
        page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(ROOT/'workspace/v4-simple-mobile.png'),full_page=True)
        # Unknown assets surface only the necessary choices and cannot spend speech.
        page.locator('#story').fill('দৃশ্য: অজানা দুর্গ\nমিতা: এসো।');page.locator('#auto-generate').click()
        page.wait_for_function("document.querySelector('#studio-tools').open && !document.querySelector('#issues').hidden")
        assert 'choice' in page.locator('#status').inner_text()
        assert not errors,errors
        for cid,hashes in originals.items():assert load_character(cid)['file_hashes']==hashes
        atomic_json(ROOT/'workspace/v4-browser-acceptance.json',{'result':'passed','videos':results,'browser_errors':errors,'source_character_hashes_unchanged':originals,
            'voice_quality':'One real offline VITS voice. Distinct adult/child cloud voices not verified: credentials unavailable. No fabricated category auditions.'})
        print('V4 automatic browser acceptance passed',flush=True);browser.close()


if __name__=='__main__':run()
