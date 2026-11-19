"""Isolated browser audition/configuration check. Speech uses a labeled test tone.

Never registers synthetic test fixtures in the user's production library.
"""
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
import uvicorn
from playwright.sync_api import sync_playwright
import app.main as main
from app.library import AssetLibrary
from app.voices import four_voices as four,variation
from app.voices.chatterbox_bangla import ENGINE
from test_v9 import tone


def main_test():
    with tempfile.TemporaryDirectory(prefix='toon-v9-browser-') as temporary:
        folder=Path(temporary);main.WORKSPACE=folder/'workspace';main.WORKSPACE.mkdir();main.OUTPUT=folder/'output';main.OUTPUT.mkdir()
        main.JOBS={};main.LIBRARY=AssetLibrary(ROOT/'assets',main.WORKSPACE)
        four.CONFIG=folder/'references/four.json';variation.CACHE_ROOT=folder/'cache';calls=[]
        def fake_generate(text,path,reference,settings,device='auto'):
            calls.append(text);path.write_bytes(tone());return {'device':'test_double','sample_rate':24000}
        ENGINE.generate=fake_generate
        server=uvicorn.Server(uvicorn.Config(main.app,host='127.0.0.1',port=0,log_level='error',access_log=False));thread=threading.Thread(target=server.run,daemon=True);thread.start()
        deadline=time.monotonic()+20
        while not server.started:
            if time.monotonic()>deadline:raise RuntimeError('Isolated browser server failed to start')
            time.sleep(.1)
        base='http://127.0.0.1:'+str(server.servers[0].sockets[0].getsockname()[1])
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(headless=True,executable_path=str(Path(os.environ['LOCALAPPDATA'])/'ms-playwright/chromium-1248/chrome-win64/chrome.exe'))
                page=browser.new_page(viewport={'width':1366,'height':1000});errors=[];page.on('pageerror',lambda e:(errors.append(str(e)),print('JS ERROR',str(e),flush=True)))
                page.goto(base);page.locator('#settings-toggle').click();page.locator('#settings-dialog').wait_for(state='visible')
                assert page.locator('[data-voice-category]').count()==4
                assert page.locator('#reference-character,#reference-file,#setting-voice').count()==0
                page.locator('summary').filter(has_text='Default Cartoon Voices').click()
                page.locator('#four-voice-permission').fill('Synthetic test signal owned by this test; no real human voice or production license asserted')
                page.locator('#four-voice-consent').check()
                for index,category in enumerate(four.CATEGORIES):
                    print('Uploading',category,flush=True)
                    box=page.locator('#base-voice-'+category).locator('xpath=../..')
                    box.locator('input[type=file]').set_input_files({'name':category+'.wav','mimeType':'audio/wav','buffer':tone(150+index*30)})
                    with page.expect_response(lambda r:r.url.endswith('/api/default-voices/references') and r.request.method=='POST'):
                        box.get_by_role('button',name='Upload authorized WAV').click()
                    page.wait_for_function('(c)=>!!document.querySelector("#base-voice-"+c).value',arg=category)
                    print('Selected',category,flush=True)
                selected=page.locator('[data-voice-category]').evaluate_all('(nodes)=>nodes.map(n=>n.value)')
                assert len(set(selected))==4
                box=page.locator('#base-voice-child_male').locator('xpath=../..')
                recording=box.locator('audio').first;recording.evaluate('(a)=>a.play()');page.wait_for_timeout(250);assert recording.evaluate('(a)=>a.currentTime')>0
                recording.evaluate('(a)=>a.pause()')
                with page.expect_response(lambda r:r.url.endswith('/api/default-voices') and r.request.method=='PUT'):
                    page.locator('#four-voice-save').click()
                page.wait_for_function('document.querySelector("#four-voice-message").textContent.includes("saved")')
                box=page.locator('#base-voice-child_male').locator('xpath=../..')
                box.get_by_role('button',name='Preview Bengali sample').click()
                page.wait_for_function('document.querySelector("#base-voice-child_male").closest("section").querySelectorAll("audio").length===3',timeout=60000)
                assert len(calls)==1
                processed=box.locator('audio').nth(1);processed.evaluate('(a)=>a.play()');page.wait_for_timeout(250);assert processed.evaluate('(a)=>a.currentTime')>0;processed.evaluate('(a)=>a.pause()')
                assert box.locator('audio').nth(2).get_attribute('src').endswith('/original')
                page.screenshot(path=str(ROOT/'workspace/v9-four-voices.png'),full_page=True)
                page.reload();page.locator('#settings-toggle').click();page.locator('#settings-dialog').wait_for(state='visible')
                assert page.locator('[data-voice-category]').evaluate_all('(nodes)=>nodes.map(n=>n.value)')==selected
                assert not errors,errors
                (ROOT/'workspace/v9-browser-smoke.json').write_text(json.dumps({'passed':True,'voice_selectors':4,'per_character_reference_controls':0,
                    'raw_recording_played':True,'processed_preview_played':True,'original_comparison_available':True,'saved_choices_survive_reload':True,
                    'speech_test_double':True,'production_library_modified':False,'javascript_errors':errors},indent=2),encoding='utf-8')
                browser.close()
        finally:server.should_exit=True;thread.join(timeout=20)


if __name__=='__main__':main_test()
