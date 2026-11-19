"""Real UI mapping persistence across an EXE restart; restores user's mappings."""
import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
BASE='http://127.0.0.1:8000'
STORY='তারা পরীক্ষার দুর্গে গেল।\nপরীক্ষার সঙ্গী: হ্যালো!'
mapping=ROOT/'workspace/user_mappings.json'

def request(path):
    with urllib.request.urlopen(BASE+path,timeout=5) as r:return json.load(r)

def ready():
    deadline=time.monotonic()+60
    while time.monotonic()<deadline:
        try:return request('/api/desktop/status')
        except OSError:time.sleep(.25)
    raise AssertionError('Server failed to restart')

def run():
    original=mapping.read_bytes() if mapping.exists() else None
    try:
        assert all(j['status'] in ('completed','failed','cancelled') for j in request('/api/jobs'))
        before=ready()
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True,executable_path=str(Path(os.environ['LOCALAPPDATA'])/'ms-playwright/chromium-1248/chrome-win64/chrome.exe'))
            page=browser.new_page()
            page.goto(BASE)
            page.wait_for_function("document.querySelector('#review-status').textContent.includes('validated')",timeout=90000)
            page.locator('#renderer').select_option('pillow')
            def analyze():
                page.locator('#story').fill(STORY);page.locator('#analyze').click()
                page.wait_for_function("!document.querySelector('#analyze').disabled",timeout=30000)
            analyze()
            page.get_by_role('button',name='Choose character',exact=True).click()
            page.get_by_role('button',name='Fahim — ready',exact=True).click()
            page.locator('#remember').check();page.locator('#picker-apply').click()
            page.wait_for_function("!document.querySelector('#picker').open")
            page.get_by_role('button',name='Choose background',exact=True).click()
            page.locator('#asset-search').fill('mango_orchard_day');page.locator('#asset-grid button').first.click()
            page.locator('#mapping-alias').fill('পরীক্ষার দুর্গ')
            page.locator('#remember').check();page.locator('#picker-apply').click()
            page.wait_for_function("!document.querySelector('#picker').open")
            assert page.locator('#generate').is_enabled()
            page.locator('#new-project').click()
            assert page.evaluate("Object.keys(JSON.parse(localStorage.getItem('toon-review-project-v4')).character_mappings).length")==0
            analyze()
            assert page.locator('#generate').is_enabled()
            assert 'Remembered alias' in page.locator('#characters').inner_text()
            subprocess.run([str(ROOT/'Bangla Toon Studio.exe'),'--stop'],check=True,timeout=30)
            deadline=time.monotonic()+20
            while time.monotonic()<deadline:
                try:request('/api/desktop/status');time.sleep(.25)
                except OSError:break
            subprocess.Popen([str(ROOT/'Bangla Toon Studio.exe'),'--no-browser'],creationflags=subprocess.CREATE_NEW_CONSOLE)
            after=ready();assert before['pid']!=after['pid']
            page.reload()
            page.wait_for_function("document.querySelector('#review-status').textContent.includes('validated')",timeout=90000)
            assert 'Remembered alias' in page.locator('#characters').inner_text()
            assert 'Mango Orchard' in page.locator('#scenes').inner_text()
            assert page.locator('#generate').is_enabled()
            result={'result':'passed','before_pid':before['pid'],'after_pid':after['pid'],'character':'fahim','background':'mango_orchard_day','new_project_and_restart':True,'user_mappings_restored':True}
            (ROOT/'workspace/mapping-restart-acceptance.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
            print(json.dumps(result,indent=2));browser.close()
    finally:
        if original is None:
            if mapping.exists():mapping.unlink()
        else:
            temp=mapping.with_suffix('.restore.tmp');temp.write_bytes(original);temp.replace(mapping)

if __name__=='__main__':run()
