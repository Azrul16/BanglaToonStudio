"""Restore an actual completed automatic job, without making another speech call."""
import json
import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.scene_cache import atomic_json


def run():
    final=json.loads((ROOT/'workspace/v4-samples-acceptance.json').read_text(encoding='utf-8'))['videos'][0]
    story=(ROOT/'samples/v4_benchmark_bn.txt').read_text(encoding='utf-8')
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=str(Path(os.environ['LOCALAPPDATA'])/'ms-playwright/chromium-1248/chrome-win64/chrome.exe'))
        page=browser.new_page(viewport={'width':1440,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.add_init_script('''data=>{}''')
        page.goto('http://127.0.0.1:8000')
        page.evaluate('''data=>{localStorage.setItem('toon-review-project-v5',JSON.stringify({story:data.story,duration_mode:'shorts',video_format:'auto',renderer:'godot',music:true,character_mappings:{},scenes:null,manualScenes:false}));localStorage.setItem('toon-automatic-v4',data.automatic_id);localStorage.setItem('toon-shorts-job-v3',data.job_id);}''',{**final,'story':story})
        page.reload()
        page.wait_for_function("!document.querySelector('#result').hidden && document.querySelector('#video').readyState>=1",timeout=90000)
        assert not page.locator('#studio-tools').evaluate('(e)=>e.open')
        assert page.locator('#auto-generate').is_visible() and not page.locator('#analyze').is_visible()
        assert page.locator('#voice-studio-panel [role=tab]').count()==4
        page.wait_for_function("document.querySelector('#auto-generate').disabled===false",timeout=30000)
        page.screenshot(path=str(ROOT/'workspace/v4-final-desktop.png'),full_page=True)
        page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(ROOT/'workspace/v4-final-mobile.png'),full_page=True)
        page.reload();page.wait_for_function("!document.querySelector('#result').hidden && document.querySelector('#video').readyState>=1",timeout=90000)
        assert not errors,errors
        plan=page.request.post('http://127.0.0.1:8000/api/automatic/plan',data={'story':story}).json()
        assert plan['review']['ready'] and plan['cached_segments']==3 and not plan['paid']
        assert page.request.get('http://127.0.0.1:8000/openapi.json').json()['info']['version']=='4.0.0-preview'
        atomic_json(ROOT/'workspace/v4-final-ui-acceptance.json',{'result':'passed','restored_job_id':final['job_id'],'automatic_id':final['automatic_id'],'desktop_and_mobile_restore':True,'primary_action':'Generate Cartoon','optional_studio_collapsed':True,'voice_category_tabs':4,'cached_dialogues':3,'browser_errors':errors})
        print('Final v4 desktop/mobile restore and cached plan passed');browser.close()


if __name__=='__main__':run()
