"""Play and download the validated full mini cartoon through chat history."""
import hashlib
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]

def main():
    result=json.loads((ROOT/'workspace/v10-mini-verification.json').read_text(encoding='utf-8'));cid=result['conversation_id']
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=str(Path(os.environ['LOCALAPPDATA'])/'ms-playwright/chromium-1248/chrome-win64/chrome.exe'))
        page=browser.new_page(viewport={'width':1366,'height':900},accept_downloads=True);errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto('http://127.0.0.1:8000');page.evaluate('(cid)=>localStorage.setItem("toon-chat-selected-v5",cid)',cid);page.reload()
        card=page.locator('[data-conversation-id="'+cid+'"]');video=card.locator('video');video.wait_for();video.evaluate('(v)=>v.play()')
        page.wait_for_function('Array.from(document.querySelectorAll("video")).some(v=>v.currentTime>0.1)')
        assert video.evaluate('(v)=>!v.error&&v.duration>=120&&v.videoWidth===1280&&v.videoHeight===720')
        video.evaluate('(v)=>v.pause()');video.evaluate('(v)=>v.currentTime=65');page.wait_for_timeout(500)
        with page.expect_download() as download:card.get_by_role('link',name='Download Video').click()
        actual=hashlib.sha256(Path(download.value.path()).read_bytes()).hexdigest();expected=hashlib.sha256((ROOT/'output/v10-mini-cartoon-evaluation.mp4').read_bytes()).hexdigest();assert actual==expected
        page.screenshot(path=str(ROOT/'workspace/v10-final-app.png'),full_page=True)
        assert not errors,errors
        (ROOT/'workspace/v10-delivery-smoke.json').write_text(json.dumps({'conversation_id':cid,'browser_playback':True,'download_checksum_matches':True,'javascript_errors':errors,'evaluation_download_name':download.value.suggested_filename,'human_listening_review':'pending'},indent=2),encoding='utf-8');browser.close()
        print('Full mini cartoon played and downloaded through chat history.')
if __name__=='__main__':main()
