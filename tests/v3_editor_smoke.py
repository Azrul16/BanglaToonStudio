"""Actual actor editor, waveform/cue approval and short Godot preview."""
import json
import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.scene_cache import atomic_json
BASE='http://127.0.0.1:8000'

if __name__=='__main__':
    prior=json.loads((ROOT/'workspace/v3-browser-acceptance.json').read_text(encoding='utf-8'))['videos'][0]
    sid=prior['production_id'];session=json.loads((ROOT/'workspace/production'/sid/'session.json').read_text(encoding='utf-8'))
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=str(Path(os.environ['LOCALAPPDATA'])/'ms-playwright/chromium-1248/chrome-win64/chrome.exe'))
        page=browser.new_page(viewport={'width':1440,'height':1050})
        project={'story':session['review']['story'],'character_mappings':session['review']['character_mappings'],'scenes':session['review']['scenes'],'manualScenes':True,'duration_mode':'shorts','video_format':'auto','renderer':'godot'}
        page.add_init_script('localStorage.setItem("toon-review-project-v4",'+json.dumps(json.dumps(project))+');localStorage.setItem("toon-production-v3",'+json.dumps(sid)+');')
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(BASE)
        page.wait_for_function("document.querySelector('#generate').disabled===false",timeout=90000)
        first=page.locator('.speech-line').nth(0)
        first.get_by_label('Acting character',exact=True).select_option('nabil')
        with page.expect_response(lambda r:r.request.method=='PUT' and '/segments/' in r.url) as response:
            first.get_by_role('button',name='Save line / direction',exact=True).click()
        assert response.value.json()['actor_id']=='nabil'
        page.wait_for_function("document.querySelectorAll('.speech-line')[0].querySelector('[aria-label=\"Acting character\"]').value==='nabil'")
        line=page.locator('.speech-line').nth(1);line.locator('summary').first.click()
        line.get_by_text('Waveform & mouth cue correction',exact=True).click()
        page.wait_for_function("document.querySelectorAll('.speech-line')[1].querySelector('[aria-label=\"Rhubarb mouth cue JSON\"]').value.length>5",timeout=30000)
        canvas=line.locator('canvas').first
        assert canvas.evaluate("c=>Array.from(c.getContext('2d').getImageData(0,0,c.width,c.height).data).some(v=>v!==0)")
        line.get_by_role('button',name='Save mouth cues',exact=True).click()
        page.wait_for_function("document.querySelector('#generate').disabled===true")
        line=page.locator('.speech-line').nth(1)
        if not line.evaluate('(d)=>d.open'):line.locator('summary').first.click()
        line.get_by_role('button',name='Approve this take',exact=True).click()
        page.wait_for_function("document.querySelector('#generate').disabled===false")
        line=page.locator('.speech-line').nth(1)
        if not line.evaluate('(d)=>d.open'):line.locator('summary').first.click()
        line.get_by_role('button',name='Preview animation',exact=True).click()
        page.wait_for_function("document.querySelector('#status').textContent.includes('Your cartoon is ready') || !document.querySelector('#error').hidden",timeout=180000)
        assert page.locator('#error').is_hidden(),page.locator('#error').inner_text()
        jid=page.evaluate("localStorage.getItem('toon-shorts-job-v3')")
        job=page.request.get(BASE+'/api/jobs/'+jid).json()
        assert job['validated'] and job['fps']==30 and len(job['clips'])==1
        page.screenshot(path=str(ROOT/'workspace/v3-editor-desktop.png'),full_page=True)
        page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(ROOT/'workspace/v3-editor-mobile.png'),full_page=True)
        assert not errors,errors
        result={'result':'passed','preview_job':jid,'actor_selection_saved':True,'waveform_drawn':True,'cue_edit_required_reapproval':True,'one_line_preview_validated':True,'browser_errors':errors}
        atomic_json(ROOT/'workspace/v3-editor-acceptance.json',result);print(json.dumps(result,indent=2))
        browser.close()
