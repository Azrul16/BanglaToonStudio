"""Actual local audio/video playback plus an unapproved review-card UI fixture."""
import json
import os
import time
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]

def main():
    base='http://127.0.0.1:8000';deadline=time.monotonic()+45
    while True:
        try:
            with urllib.request.urlopen(base+'/openapi.json',timeout=2) as response:assert json.load(response)['info']['version']=='10.0.1-quality-repair'
            break
        except OSError:
            if time.monotonic()>deadline:raise
            time.sleep(.3)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=str(Path(os.environ['LOCALAPPDATA'])/'ms-playwright/chromium-1248/chrome-win64/chrome.exe'));page=browser.new_page(viewport={'width':1280,'height':900});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto((ROOT/'evaluation/quality-repair/review.html').as_uri())
        video=page.locator('#repaired-video');video.evaluate('(v)=>v.play()');page.wait_for_function('document.getElementById("repaired-video").currentTime>.1');assert video.evaluate('(v)=>!v.error&&v.videoWidth===720&&v.videoHeight===1280&&v.duration>18&&v.duration<20');video.evaluate('(v)=>v.pause()')
        sample=page.locator('audio[src="segment_001/fresh_no_transform.wav"]');sample.evaluate('(a)=>a.play()');page.wait_for_function('document.querySelector(\'audio[src="segment_001/fresh_no_transform.wav"]\').currentTime>.1');sample.evaluate('(a)=>a.pause()')
        page.goto(base);page.locator('#prompt').wait_for();page.wait_for_timeout(500)
        fixture={'id':'f'*32,'prompt':'Speech review UI fixture; no production job','created_at':'2026-11-18T00:00:00Z','status':'needs_audio_review','audio_review':{'token':'fixture-only','clips':[{'speaker':'nabil','text':'এই দেখ!','audio_url':'/api/jobs/35334dd3d8a541c1a9de2ceb54854c4f/audio/segment_001','checks':{'warnings':[]}}]}}
        page.evaluate('(data)=>mount(data)',fixture);button=page.get_by_role('button',name='Render reviewed speech',exact=True);button.click();assert 'Listen to the clips' in page.locator('#connection-message').text_content()
        # Do not tick consent or submit approval for this fixture.
        page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');page.screenshot(path=str(ROOT/'workspace/quality-review-mobile.png'),full_page=True)
        assert not errors,errors
        (ROOT/'evaluation/quality-repair/browser-verification.json').write_text(json.dumps({'local_approved_audio_played':True,'repaired_mp4_played':True,'unapproved_review_ui_blocks_render':True,'ui_fixture_created_no_job':True,'mobile_no_overflow':True,'javascript_errors':errors},indent=2),encoding='utf-8');browser.close();print('Local approved audio/video playback and unapproved review UI checks passed.')
if __name__=='__main__':main()
