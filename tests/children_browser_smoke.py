"""Play/seek/download the real three-child acceptance video in Chromium."""
import hashlib
import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.verify_children import DIALOGUE

if __name__=='__main__':
    acceptance=json.loads((ROOT/'workspace/children-acceptance.json').read_text())
    job_id=acceptance['job_id']; base='http://127.0.0.1:8000'
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,**({'executable_path':sys.argv[1]} if len(sys.argv)>1 else {}))
        page=browser.new_page(viewport={'width':1440,'height':1000},accept_downloads=True)
        errors=[]; page.on('pageerror',lambda err:errors.append(str(err)))
        page.add_init_script('localStorage.setItem("toon-shorts-job-v3",'+json.dumps(job_id)+');localStorage.setItem("toon-shorts-story-v3",'+json.dumps(DIALOGUE)+');')
        page.goto(base)
        page.wait_for_function("document.querySelector('#status').textContent.includes('Your cartoon is ready')",timeout=60000)
        parsed=page.request.post(base+'/api/stories/parse',data={'story':DIALOGUE}).json()
        assert parsed['speakers']==['nabil','rayan','anika']
        page.wait_for_function("document.querySelector('video').readyState>=1")
        page.locator('video').evaluate('(v)=>v.play()')
        page.wait_for_function("document.querySelector('video').currentTime>.2")
        page.locator('video').evaluate('(v)=>v.pause()')
        timeline=page.request.get(base+f'/api/jobs/{job_id}/timeline').json()
        for scene in timeline['scenes']:
            if scene['kind']!='speech': continue
            cues=json.loads((ROOT/'workspace'/job_id/'cues'/f"{scene['clip_id']}.json").read_text())['mouthCues']
            cue=next(c for c in cues if c['value'] not in ('X','A'))
            time=scene['start']+(cue['start']+cue['end'])/2
            page.locator('video').evaluate('(v,t)=>v.currentTime=t',time)
            page.wait_for_function("!document.querySelector('video').seeking && document.querySelector('video').readyState>=2")
            page.locator('video').screenshot(path=str(ROOT/'workspace'/f"children-video-{scene['speaker']}.png"))
        with page.expect_download() as download: page.locator('#download').click()
        destination=ROOT/'workspace/children-browser-download.mp4'
        download.value.save_as(destination)
        assert hashlib.sha256(destination.read_bytes()).hexdigest()==acceptance['video_sha256']
        page.set_viewport_size({'width':390,'height':844})
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        assert not errors,errors
        result={'result':'passed','job_id':job_id,'speakers':['nabil','rayan','anika'],'download_matches_original':True,'browser_errors':errors}
        (ROOT/'workspace/children-browser-acceptance.json').write_text(json.dumps(result,indent=2))
        print(json.dumps(result,indent=2))
        browser.close()
