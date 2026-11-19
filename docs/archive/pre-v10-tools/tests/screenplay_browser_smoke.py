"""Real local VITS, Rhubarb, Godot and browser acceptance; no mocked media."""
import json
import os
import shutil
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.scene_cache import atomic_json,digest
from app.assets import load_character
BASE='http://127.0.0.1:8000'
CRITICAL=(ROOT/'samples/screenplay_critical_bn.txt').read_text(encoding='utf-8').strip()
SILENT='দৃশ্য: আমবাগান\nচরিত্র: নাবিল\n[নাবিল ধীরে হাঁটে।]\n[SFX: rustling_leaves]'
EXPECTED=['কে ওখানে?','আমি কিছু দেখতে পাচ্ছি না!']


def run():
    hashes={cid:load_character(cid)['file_hashes'] for cid in ('nabil','rayan')}
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=str(Path(os.environ['LOCALAPPDATA'])/'ms-playwright/chromium-1248/chrome-win64/chrome.exe'))
        page=browser.new_page(viewport={'width':1440,'height':1050},accept_downloads=True)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(BASE)
        page.locator('#studio-tools').evaluate('(e)=>e.open=true')
        page.wait_for_function("document.querySelector('#review-status').textContent.includes('validated')",timeout=120000)
        # Ambiguous text is blocked and can be corrected in the actual event editor.
        page.locator('#story').fill(CRITICAL+'\nঅদ্ভুত নীল রহস্য।')
        page.locator('#analyze').click()
        row=page.locator('[data-event-id="event_007"]');row.wait_for()
        assert page.locator('#generate').is_disabled()
        blocked=page.request.post(BASE+'/api/production',data={'story':CRITICAL+'\nঅদ্ভুত নীল রহস্য।','renderer':'godot'})
        assert blocked.status==422
        row.get_by_label('Event type',exact=True).select_option('ignore')
        row.get_by_role('button',name='Save event correction',exact=True).click()
        page.wait_for_function("document.querySelector('#review-status').textContent.includes('validated')")
        page.reload()
        page.wait_for_function("document.querySelector('[data-event-id=event_007] summary')?.textContent.includes('IGNORE')")
        assert page.locator('#spoken-preview li').count()==2
        # Render the exact supplied critical screenplay, without extra ignored lines.
        page.locator('#story').fill(CRITICAL);page.locator('#analyze').click()
        page.wait_for_function("document.querySelector('#review-status').textContent.includes('validated')")
        assert page.locator('#screenplay-events > details').count()==6
        preview=page.locator('#spoken-preview').inner_text()
        assert all(text in preview for text in EXPECTED) and 'দাঁড়িয়ে' not in preview and 'ক্যামেরা' not in preview
        page.locator('#prepare-production').click()
        page.wait_for_function("document.querySelectorAll('.speech-line').length===2")
        sid=page.evaluate("localStorage.getItem('toon-production-v3')")
        session=page.request.get(BASE+'/api/production/'+sid).json()
        assert session['schema_version']==2
        assert [s['synthesis_text'] for s in session['segments']]==EXPECTED
        assert [s['speaker'] for s in session['segments']]==['nabil','rayan']
        assert session['segments'][0]['emotion']=='fear'
        assert all(s['voice']['provider']=='vits' for s in session['segments'])
        page.locator('#generate-local-previews').click()
        deadline=time.monotonic()+600
        while time.monotonic()<deadline:
            session=page.request.get(BASE+'/api/production/'+sid).json()
            failed=[t for s in session['segments'] for t in s['takes'] if t['status']=='failed'];assert not failed,failed
            if all(s['takes'] and s['takes'][-1]['status']=='completed' for s in session['segments']):break
            time.sleep(1)
        else:raise AssertionError('Real VITS timed out')
        page.wait_for_function("document.querySelectorAll('#speech-lines audio').length===2",timeout=30000)
        takes=[]
        for i,line in enumerate(session['segments']):
            take=line['takes'][0];takes.append(take)
            assert take['synthesis_text']==EXPECTED[i] and take['provider_metrics']['provider']=='vits'
            cues=page.request.get(f"{BASE}/api/production/{sid}/takes/{take['take_id']}/cues").json()
            assert cues['method']=='rhubarb' and cues['mouthCues']
            shutil.copyfile(ROOT/f"workspace/production/{sid}/audio/{take['take_id']}.wav",ROOT/f"output/screenplay-{line['speaker']}.wav")
            row=page.locator('.speech-line').nth(i)
            if not row.evaluate('(e)=>e.open'):row.locator('summary').first.click()
            row.locator('audio').evaluate('(a)=>a.play()')
            page.wait_for_function("i=>document.querySelectorAll('#speech-lines audio')[i].currentTime>.1",arg=i)
            row.locator('audio').evaluate('(a)=>a.pause()')
            row.get_by_role('button',name='Approve this take',exact=True).click()
            page.wait_for_function("i=>document.querySelectorAll('.speech-line')[i].querySelector('summary').textContent.includes('· approved ·')",arg=i)
        results=[]
        for name,story in [('dialogue',CRITICAL),('silent',SILENT)]:
            if name=='silent':
                page.locator('#story').fill(story);page.locator('#analyze').click()
                page.wait_for_function("document.querySelector('#review-status').textContent.includes('validated')")
                assert 'No spoken lines' in page.locator('#spoken-preview').inner_text()
                assert page.locator('#speech-lines .speech-line').count()==0
                assert page.locator('#production-actions').is_hidden()
            assert page.locator('#generate').is_enabled()
            previous=page.evaluate("localStorage.getItem('toon-shorts-job-v3')")
            page.locator('#generate').click()
            page.wait_for_function("old=>localStorage.getItem('toon-shorts-job-v3')!==old",arg=previous,timeout=60000)
            jid=page.evaluate("localStorage.getItem('toon-shorts-job-v3')");print(name,jid,flush=True)
            deadline=time.monotonic()+600;last=None
            while time.monotonic()<deadline:
                job=page.request.get(BASE+'/api/jobs/'+jid,timeout=10000).json()
                state=(job['status'],job['progress'])
                if state!=last:print(state,flush=True);last=state
                assert job['status'] not in ('failed','cancelled'),job.get('error')
                if job['status']=='completed':break
                time.sleep(1)
            else:raise AssertionError('Godot render timed out')
            assert job['validated'] and job['fps']==30 and (job['width'],job['height'])==(720,1280)
            timeline=page.request.get(BASE+job['timeline_url']).json()
            if name=='dialogue':
                assert [c['text'] for c in job['clips']]==EXPECTED
                assert [s['speaker_id'] for s in timeline['speech_track']]==['nabil','rayan']
                assert timeline['speech_track'][1]['start']>timeline['speech_track'][0]['end']
                assert any(s['kind']=='camera' for s in timeline['scenes']) and any(s['kind']=='action' for s in timeline['scenes'])
            else:
                assert job['clips']==[] and timeline['speech_track']==[] and job['report']['tts']['device']=='not_used'
                assert [e['sound'] for e in timeline['effects_track']]==['rustling_leaves']
            page.wait_for_function("document.querySelector('#status').textContent.includes('Your cartoon is ready')",timeout=30000)
            page.wait_for_function("document.querySelector('#video').readyState>=1",timeout=30000)
            page.locator('#video').evaluate('(v)=>v.play()')
            page.wait_for_function("document.querySelector('#video').currentTime>.2")
            page.locator('#video').evaluate('(v)=>v.pause()')
            page.locator('#video').screenshot(path=str(ROOT/f'workspace/screenplay-{name}-video.png'))
            with page.expect_download() as download:page.locator('#download').click()
            target=ROOT/f'output/screenplay-{name}.mp4';download.value.save_as(target)
            assert digest(target)==digest(ROOT/'output'/f'{jid}.mp4')
            results.append({'test':name,'job_id':jid,'video':str(target),'duration_seconds':job['duration_seconds'],'fps':30,'sha256':digest(target),'speech_track':timeline['speech_track'],'effects_track':timeline['effects_track'],'report':job['report']})
        page.screenshot(path=str(ROOT/'workspace/screenplay-studio.png'),full_page=True)
        page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(ROOT/'workspace/screenplay-mobile.png'),full_page=True)
        assert not errors,errors
        for cid,original in hashes.items():assert load_character(cid)['file_hashes']==original
        atomic_json(ROOT/'workspace/screenplay-browser-acceptance.json',{'result':'passed','production_id':sid,'tts_inputs':EXPECTED,'takes':takes,'videos':results,'browser_errors':errors,'unchanged_character_hashes':hashes,'listening_review':'Real local VITS audio produced; pronunciation quality requires human listening. No cloud provider called.'})
        print('Real screenplay browser acceptance passed',flush=True);browser.close()


if __name__=='__main__':run()
