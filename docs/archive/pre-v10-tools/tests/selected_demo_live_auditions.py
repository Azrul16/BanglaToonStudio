"""Play actual conditioned comparisons for each category after an EXE restart."""
import io
import json
import os
import time
import urllib.request
import zipfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]


def main():
    base='http://127.0.0.1:8000';deadline=time.monotonic()+45
    while True:
        try:
            with urllib.request.urlopen(base+'/api/default-voices',timeout=2):break
        except OSError:
            if time.monotonic()>deadline:raise
            time.sleep(.3)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=str(Path(os.environ['LOCALAPPDATA'])/'ms-playwright/chromium-1248/chrome-win64/chrome.exe'))
        page=browser.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(base);page.locator('#settings-toggle').click();page.locator('#settings-dialog').wait_for(state='visible')
        data=page.request.get(base+'/api/default-voices').json()
        expected={'male':'007','female':'006','child_male':'002','child_female':'005'}
        assert data['mode']=='evaluation' and {c:s['official_sample_id'] for c,s in data['base_voices'].items()}==expected
        assert page.locator('[data-voice-category]').count()==4
        page.get_by_text('Default Cartoon Voices',exact=True).click();page.get_by_text('Preview Character Voices · optional',exact=True).click()
        page.get_by_text('Selected demo conditioning comparisons · evaluation only',exact=True).click()
        for cid in ('rahat','mehna','nabil','anika'):
            for kind in ('processed','original'):
                player=page.locator('audio[src="/api/default-voices/conditioning-comparisons/'+cid+'/'+kind+'"]')
                player.evaluate('(a)=>a.play()');page.wait_for_timeout(180);assert player.evaluate('(a)=>a.currentTime')>0;player.evaluate('(a)=>a.pause()')
        response=page.request.get(base+'/api/default-voices/conditioning-comparisons/archive');assert response.status==200
        assert 'evaluation' in response.headers['content-disposition']
        with zipfile.ZipFile(io.BytesIO(response.body())) as archive:assert all(name in archive.namelist() for name in ('rahat.wav','rahat.original.wav','rahat.model-float.wav','results.json'))
        page.screenshot(path=str(ROOT/'workspace/selected-demo-auditions.png'),full_page=True)
        assert not errors,errors
        (ROOT/'workspace/selected-demo-live-auditions.json').write_text(json.dumps({'passed':True,'selected_samples':expected,'restart_persistence':True,
            'actual_conditioned_audio_playback_categories':4,'before_and_after_players':True,'comparison_archive_downloaded':True,
            'commercial_permissions_verified':False,'human_listening_review':'pending','javascript_errors':errors},indent=2),encoding='utf-8')
        browser.close()


if __name__=='__main__':main()
