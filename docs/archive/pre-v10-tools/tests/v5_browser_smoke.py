"""Real conversational generation, inline clarification and restart-safe history."""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.scene_cache import atomic_json,digest
from app.assets import load_character
BASE='http://127.0.0.1:8000'
SCRIPT='''দৃশ্য: আমবাগান
[নাবিল গাছের কাছে হাঁটে।]
নাবিল (ভয়ে): এই! কে ওখানে?
[রায়ান পেছনে তাকায়।]
রায়ান: আমি কিছু দেখিনি!
[SFX: leaves_rustling]'''


def wait_card(page,cid):
    deadline=time.monotonic()+600;last=None
    while time.monotonic()<deadline:
        data=page.request.get(BASE+'/api/conversations/'+cid).json()
        state=(data['status'],data.get('stage'),data.get('progress'))
        if state!=last:print(cid,*state,flush=True);last=state
        assert data['status'] not in ('failed','cancelled'),data
        if data['status']=='completed':return data
        time.sleep(.7)
    raise AssertionError('Chat generation timed out')


def run():
    import urllib.request
    deadline=time.monotonic()+90
    while True:
        try:
            with urllib.request.urlopen(BASE+'/api/preferences',timeout=2):break
        except OSError:
            if time.monotonic()>deadline:raise
            time.sleep(.3)
    source_hashes={cid:load_character(cid)['file_hashes'] for cid in ('nabil','rayan')}
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=str(Path(os.environ['LOCALAPPDATA'])/'ms-playwright/chromium-1248/chrome-win64/chrome.exe'))
        page=browser.new_page(viewport={'width':1440,'height':1000},accept_downloads=True);errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(BASE);page.wait_for_selector('#prompt');page.wait_for_timeout(500)
        assert page.locator('#submit').inner_text().startswith('Generate Cartoon')
        assert page.locator('#settings-dialog').is_hidden() and page.locator('#history').is_hidden()
        assert page.locator('#voice-studio-panel,#picker,#screenplay-panel,pre').count()==0
        page.locator('#prompt').fill('প্রথম লাইন');page.locator('#prompt').press('Enter');assert '\n' in page.locator('#prompt').input_value()
        page.locator('#prompt').fill(SCRIPT);page.screenshot(path=str(ROOT/'workspace/v5-start.png'),full_page=True)
        with page.expect_response(lambda r:r.url.endswith('/api/conversations') and r.request.method=='POST',timeout=90000) as created:
            page.locator('#prompt').press('Control+Enter')
        assert created.value.status==201
        cid=created.value.json()['id'];card=page.locator(f'[data-conversation-id="{cid}"]')
        assert card.count()==1
        first=wait_card(page,cid);job=page.request.get(BASE+'/api/jobs/'+first['job_id']).json()
        assert job['validated'] and job['fps']==30 and (job['width'],job['height'])==(720,1280)
        assert [c['synthesis_text'] for c in job['clips']]==['এই! কে ওখানে?','আমি কিছু দেখিনি!']
        assert [c['speaker'] for c in job['clips']]==['nabil','rayan']
        video=card.locator('video');video.wait_for(timeout=30000)
        page.wait_for_function("id=>document.querySelector(`[data-conversation-id='${id}'] video`)?.readyState>=1",arg=cid)
        video.evaluate('(v)=>v.play()');page.wait_for_function("id=>document.querySelector(`[data-conversation-id='${id}'] video`).currentTime>.2",arg=cid);video.evaluate('(v)=>v.pause()')
        with page.expect_download() as download:card.get_by_role('link',name='Download Video').click()
        path=ROOT/'output/v5-chat-cartoon.mp4';download.value.save_as(path);assert digest(path)==digest(ROOT/'output'/(first['job_id']+'.mp4'))
        page.screenshot(path=str(ROOT/'workspace/v5-video.png'),full_page=True)
        # Missing character stays inline; resolving it resumes this same prompt/card.
        unknown='দৃশ্য: আমবাগান\nমিতা: আমরা আবার এসেছি।'
        page.locator('#prompt').fill(unknown)
        with page.expect_response(lambda r:r.url.endswith('/api/conversations') and r.request.method=='POST') as created:
            page.locator('#submit').click()
        unresolved=created.value.json();assert unresolved['status']=='needs_input';uid=unresolved['id']
        inline=page.locator(f'[data-conversation-id="{uid}"]')
        inline.get_by_label('character clarification').select_option('nabil')
        page.screenshot(path=str(ROOT/'workspace/v5-inline.png'),full_page=True)
        inline.get_by_role('button',name='Continue cartoon').click()
        second=wait_card(page,uid);assert second['id']==uid and second['prompt']==unknown
        assert inline.count()==1
        other=page.request.get(BASE+'/api/jobs/'+second['job_id']).json()
        assert other['approved_speech'][0]['voice']==job['approved_speech'][0]['voice']
        # Minimal preferences persist without being required for generation.
        page.locator('#settings-toggle').click();page.locator('#setting-music').uncheck();page.locator('#settings-form button[type=submit]').click()
        page.wait_for_function("document.querySelector('#settings-message').textContent.includes('saved')")
        page.locator('#settings-close').click();page.reload();page.wait_for_selector(f'[data-conversation-id="{uid}"] video',timeout=60000)
        assert page.request.get(BASE+'/api/preferences').json()['music'] is False
        page.request.put(BASE+'/api/preferences',data={'format':'shorts','voice_preference':'saved','music':True})
        # Real stop/restart, then reopen from server-side history in a fresh context.
        original=digest(ROOT/'output'/(first['job_id']+'.mp4'))
        browser.close()
        subprocess.run([str(ROOT/'Bangla Toon Studio.exe'),'--stop'],cwd=ROOT,check=True)
        subprocess.Popen([str(ROOT/'Bangla Toon Studio.exe'),'--no-browser'],cwd=ROOT,creationflags=subprocess.CREATE_NEW_CONSOLE)
        deadline=time.monotonic()+90
        import urllib.request
        while True:
            try:
                with urllib.request.urlopen(BASE+'/api/preferences',timeout=2):break
            except OSError:
                if time.monotonic()>deadline:raise
                time.sleep(.3)
        browser=p.chromium.launch(headless=True,executable_path=str(Path(os.environ['LOCALAPPDATA'])/'ms-playwright/chromium-1248/chrome-win64/chrome.exe'))
        page=browser.new_page(viewport={'width':390,'height':844});page.on('pageerror',lambda e:errors.append(str(e)));page.goto(BASE)
        page.locator('#history-toggle').click()
        entry=page.locator('#history-list .history-item').filter(has_text='এই! কে ওখানে?')
        if not entry.count():entry=page.locator('#history-list .history-item').filter(has_text='নাবিল গাছের কাছে হাঁটে')
        entry.first.click();restored=page.locator(f'[data-conversation-id="{cid}"]');restored.locator('video').wait_for(timeout=60000)
        assert digest(ROOT/'output'/(first['job_id']+'.mp4'))==original
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(ROOT/'workspace/v5-mobile.png'),full_page=True)
        assert not errors,errors
        for name,value in source_hashes.items():assert load_character(name)['file_hashes']==value
        atomic_json(ROOT/'workspace/v5-browser-acceptance.json',{'result':'passed','conversations':[first,second],'video':str(path),'sha256':digest(path),'actual_tts_inputs':['এই! কে ওখানে?','আমি কিছু দেখিনি!'],
            'restart_history_verified':True,'download_verified':True,'ctrl_enter_submits':True,'enter_keeps_multiline':True,'voice_identity_consistent':True,'browser_errors':errors,'source_character_hashes_unchanged':source_hashes,
            'voice_limit':'Actual offline VITS; no distinct child voice or live cloud request is claimed.'})
        print('V5 real chat generation, inline clarification and restart history passed',flush=True);browser.close()


if __name__=='__main__':run()
