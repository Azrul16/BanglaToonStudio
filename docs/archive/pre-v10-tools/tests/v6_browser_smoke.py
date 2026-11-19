"""Real browser check of minimal UI, benchmark audio and opt-in privacy controls."""
import json
import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))


def main():
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=str(Path(os.environ['LOCALAPPDATA'])/'ms-playwright/chromium-1248/chrome-win64/chrome.exe'))
        page=browser.new_page(viewport={'width':1366,'height':900});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        saved=page.request.get('http://127.0.0.1:8000/api/preferences').json()
        page.goto('http://127.0.0.1:8000');page.wait_for_selector('#prompt')
        page.locator('#settings-toggle').click();page.locator('#settings-dialog').wait_for(state='visible')
        page.wait_for_function("document.querySelector('#benchmark-select').options.length===7")
        assert page.locator('#setting-understanding').input_value()==saved['interpretation_mode']
        assert page.locator('#setting-ai-consent').is_checked()==saved['semantic_ai_approved']
        assert page.locator('#setting-understanding option[value=assisted]').is_disabled()==(not saved['semantic_ai_configured'])
        page.locator('summary').filter(has_text='Official pronunciation').click()
        page.locator('#benchmark-select').select_option('003')
        audio=page.locator('#benchmark-audio')
        audio.evaluate('(a)=>a.play()')
        page.wait_for_function("document.querySelector('#benchmark-audio').currentTime>0.15")
        assert page.locator('#benchmark-caption').inner_text()
        audio.evaluate('(a)=>a.pause()')
        page.screenshot(path=str(ROOT/'workspace/v6-settings-benchmarks.png'),full_page=True)
        page.locator('#settings-close').click();page.set_viewport_size({'width':390,'height':844})
        page.screenshot(path=str(ROOT/'workspace/v6-mobile.png'),full_page=True)
        assert not errors,errors
        (ROOT/'workspace/v6-browser-smoke.json').write_text(json.dumps({'passed':True,'auditioned_sample':'003','saved_interpretation_mode':saved['interpretation_mode'],'saved_consent':saved['semantic_ai_approved'],'ai_configured':saved['semantic_ai_configured'],'js_errors':errors},indent=2),encoding='utf-8')
        browser.close()


if __name__=='__main__':main()
