"""Real browser/VITS acceptance for asset review. Requires the console app running."""
import hashlib
import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
BASE='http://127.0.0.1:8000'
KNOWN='নাবিল আর রায়ান আমবাগানে গেল।\nনাবিল: এই! তোরা কিছু শুনলি?\nরায়ান: হ্যাঁ! মনে হচ্ছে মাটির নিচে কেউ আছে!'
UNKNOWN='তারা একটি পুরোনো দুর্গে পৌঁছাল।\nঅচেনা ছেলে: তোমরা এখানে কী করছ?\nনাবিল: আমরা কিছু শুনেছি।'

def run():
    deadline=time.monotonic()+60
    while True:
        try:
            with urllib.request.urlopen(BASE+'/openapi.json',timeout=3):break
        except OSError:
            if time.monotonic()>deadline:raise
            time.sleep(.25)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=str(Path(os.environ['LOCALAPPDATA'])/'ms-playwright/chromium-1248/chrome-win64/chrome.exe'))
        page=browser.new_page(viewport={'width':1440,'height':1050},accept_downloads=True)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(BASE)
        page.wait_for_function("document.querySelector('#review-status').textContent.includes('validated')",timeout=90000)
        page.locator('#renderer').select_option('pillow')  # Legacy workflow regression.
        page.locator('#browse-characters').click()
        assert page.get_by_role('button',name='Arif — reference only',exact=True).is_visible()
        assert page.locator('#asset-grid img').count()==10
        page.locator('#picker-close').click()
        def analyze(story):
            page.locator('#story').fill(story)
            page.locator('#analyze').click()
            page.wait_for_function("!document.querySelector('#analyze').disabled && !document.querySelector('#review-status').textContent.includes('Discovering')",timeout=60000)
            assert page.locator('#error').is_hidden(),page.locator('#error').inner_text()
        def choose(name):
            page.get_by_role('button',name=name,exact=True).click()
            page.locator('#picker-apply').click()
            page.wait_for_function("!document.querySelector('#picker').open",timeout=30000)
        analyze(KNOWN)
        assert page.locator('#generate').is_enabled()
        assert 'mango_orchard_day' in page.evaluate("JSON.parse(localStorage.getItem('toon-review-project-v4')).scenes[0].background_id")
        analyze(UNKNOWN)
        assert page.locator('#generate').is_disabled()
        page.get_by_role('button',name='Choose character',exact=True).click()
        choose('Fahim — ready')
        page.get_by_role('button',name='Choose background',exact=True).click()
        page.locator('#asset-search').fill('village_courtyard_day')
        # Search includes asset aliases, which include the stable folder ID.
        page.locator('#asset-grid button').first.click()
        page.locator('#picker-apply').click()
        page.wait_for_function("!document.querySelector('#picker').open")
        page.locator('#boundaries summary').click()
        page.get_by_role('checkbox',name='Start scene at segment 3',exact=True).check()
        page.get_by_role('button',name='Choose background',exact=True).click()
        page.locator('#asset-search').fill('mango_orchard_day')
        page.locator('#asset-grid button').first.click()
        page.locator('#picker-apply').click()
        page.wait_for_function("!document.querySelector('#picker').open")
        results=[]
        for i in range(2):
            if i: analyze(KNOWN)
            assert page.locator('#generate').is_enabled()
            previous=page.evaluate("localStorage.getItem('toon-shorts-job-v3')")
            page.locator('#generate').click()
            page.wait_for_function("previous=>localStorage.getItem('toon-shorts-job-v3')!==previous",arg=previous,timeout=60000)
            page.wait_for_function("document.querySelector('#status').textContent.includes('Your cartoon is ready') || !document.querySelector('#error').hidden",timeout=600000)
            assert page.locator('#error').is_hidden(),page.locator('#error').inner_text()
            jid=page.evaluate("localStorage.getItem('toon-shorts-job-v3')")
            job=page.request.get(BASE+'/api/jobs/'+jid).json()
            assert job['validated'] and job['status']=='completed',job
            assert (job['width'],job['height'],job['fps'])==(720,1280,24)
            assert job['report']['tts']['device']=='cuda'
            timeline=page.request.get(BASE+job['timeline_url']).json()
            if not i:
                assert {c['character_id'] for c in job['asset_references']['characters']}=={'fahim','nabil'}
                assert {b['background_id'] for b in job['asset_references']['backgrounds']}=={'village_courtyard_day','mango_orchard_day'}
                assert [s['background_id'] for s in timeline['scenes'] if s['kind']=='speech']==['village_courtyard_day','village_courtyard_day','mango_orchard_day']
            page.wait_for_function("document.querySelector('#video').readyState>=1",timeout=30000)
            page.locator('#video').evaluate('(v)=>v.play()')
            page.wait_for_function("document.querySelector('#video').currentTime>.2")
            page.locator('#video').evaluate('(v)=>v.pause()')
            with page.expect_download() as download: page.locator('#download').click()
            path=ROOT/f'workspace/review-download-{i+1}.mp4';download.value.save_as(path)
            assert hashlib.sha256(path.read_bytes()).hexdigest()==hashlib.sha256(Path(job['report']['output']).read_bytes()).hexdigest()
            page.screenshot(path=str(ROOT/f'workspace/review-browser-{i+1}.png'),full_page=True)
            results.append(job)
        nabil=lambda j:next(c for c in j['asset_references']['characters'] if c['character_id']=='nabil')
        assert nabil(results[0])==nabil(results[1])
        page.set_viewport_size({'width':390,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(ROOT/'workspace/review-mobile.png'),full_page=True)
        assert not errors,errors
        summary={'result':'passed','jobs':[j['job_id'] for j in results],'browser_errors':errors,'nabil_assets':nabil(results[0]),'devices':[j['report']['tts']['device'] for j in results],'encoders':[j['report']['timings']['encoder'] for j in results]}
        (ROOT/'workspace/review-browser-acceptance.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
        print(json.dumps(summary,indent=2))
        browser.close()

if __name__=='__main__':run()
