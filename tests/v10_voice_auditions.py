"""Exercise the single local player for all four saved category recordings."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]

def main():
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=str(Path(os.environ['LOCALAPPDATA'])/'ms-playwright/chromium-1248/chrome-win64/chrome.exe'))
        page=browser.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto('http://127.0.0.1:8000');page.locator('#settings-toggle').click();page.locator('#settings-dialog').wait_for(state='visible');page.get_by_text('Four saved voices',exact=True).click()
        results=[]
        for category,sid in {'male':'007','female':'006','child_male':'002','child_female':'005'}.items():
            menu=page.locator('#base-voice-'+category);assert 'Official Demo '+sid in menu.locator('option:checked').text_content()
            row=page.locator('.voice-row').filter(has=menu);row.get_by_role('button',name='Listen',exact=True).click();audio=page.locator('#voice-audition')
            page.wait_for_function('document.getElementById("voice-audition").currentTime>0.05');assert audio.evaluate('(a)=>!a.error&&a.duration>0');audio.evaluate('(a)=>a.pause()')
            results.append({'category':category,'official_sample_id':sid,'played':True,'duration_seconds':audio.evaluate('(a)=>a.duration')})
        assert not errors,errors
        (ROOT/'workspace/v10-voice-auditions.json').write_text(json.dumps({'samples':results,'javascript_errors':errors,'human_listening_review':'pending','commercial_permission_verified':False},indent=2),encoding='utf-8');browser.close()
        print('Four category recordings played through the shared local player.')
if __name__=='__main__':main()
