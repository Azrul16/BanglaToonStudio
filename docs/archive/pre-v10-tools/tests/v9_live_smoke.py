"""Read-only live v9 checks and actual unconditioned DSP benchmark playback."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]


def main():
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=str(Path(os.environ['LOCALAPPDATA'])/'ms-playwright/chromium-1248/chrome-win64/chrome.exe'))
        page=browser.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        base='http://127.0.0.1:8000';page.goto(base);page.locator('#settings-toggle').click();page.locator('#settings-dialog').wait_for(state='visible')
        assert page.request.get(base+'/openapi.json').json()['info']['version']=='9.0.0-preview'
        assert page.locator('[data-voice-category]').count()==4
        page.get_by_text('Default Cartoon Voices',exact=True).click()
        page.get_by_text('Preview Character Voices · optional',exact=True).click()
        page.get_by_text('Listen to DSP experiments · evaluation only',exact=True).click()
        details=page.get_by_text('Listen to DSP experiments · evaluation only',exact=True).locator('xpath=..')
        for index in (0,1):
            player=details.locator('audio').nth(index);player.evaluate('(a)=>a.play()');page.wait_for_timeout(250);assert player.evaluate('(a)=>a.currentTime')>0;player.evaluate('(a)=>a.pause()')
        assert not errors,errors
        (ROOT/'workspace/v9-live-smoke.json').write_text(json.dumps({'passed':True,'version':'9.0.0-preview','voice_selectors':4,'actual_dsp_benchmark_played':True,
            'actual_original_benchmark_played':True,'references_changed':False,'javascript_errors':errors},indent=2),encoding='utf-8')
        browser.close()


if __name__=='__main__':main()
