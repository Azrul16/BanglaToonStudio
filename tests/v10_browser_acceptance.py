"""Real local browser, selected-demo speech and two-format media acceptance."""
import json
import os
import shutil
import sys
import time
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.scene_cache import atomic_json,digest
from scripts.audit_v4_media import audit

def main():
    base='http://127.0.0.1:8000';story=(ROOT/'samples/v7_benchmark_bn.txt').read_text(encoding='utf-8')
    ready=time.monotonic()+45
    while True:
        try:
            with urllib.request.urlopen(base+'/api/preferences',timeout=2):break
        except OSError:
            if time.monotonic()>ready:raise
            time.sleep(.3)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=str(Path(os.environ['LOCALAPPDATA'])/'ms-playwright/chromium-1248/chrome-win64/chrome.exe'))
        page=browser.new_page(viewport={'width':1366,'height':900},accept_downloads=True);errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(base);page.locator('#settings-toggle').click();page.locator('#settings-dialog').wait_for(state='visible')
        page.get_by_text('Four saved voices',exact=True).click();assert page.locator('[data-voice-category]').count()==4
        for category,sid in {'male':'007','female':'006','child_male':'002','child_female':'005'}.items():assert 'Official Demo '+sid in page.locator('#base-voice-'+category+' option:checked').text_content()
        assert page.locator('#settings-dialog audio').count()==1
        page.screenshot(path=str(ROOT/'workspace/v10-settings.png'),full_page=True);page.locator('#settings-close').click()
        original=page.request.get(base+'/api/preferences').json();saved={k:original[k] for k in ('format','voice_preference','music','interpretation_mode','semantic_ai_approved')}
        def wait(cid):
            deadline=time.monotonic()+900;previous=None
            while time.monotonic()<deadline:
                data=page.request.get(base+'/api/conversations/'+cid).json()
                if data['status']!=previous:print(cid[:8],data['status'],flush=True);previous=data['status']
                assert data['status'] not in ('failed','cancelled','needs_input','needs_payment'),data
                if data['status']=='completed':return data
                page.wait_for_timeout(600)
            raise AssertionError('Actual cartoon generation timed out')
        results=[]
        try:
            for mode in ('shorts','mini'):
                prefs={**saved,'format':mode,'music':True,'voice_preference':'chatterbox_bangla','interpretation_mode':'rules','semantic_ai_approved':False}
                assert page.request.put(base+'/api/preferences',data=prefs).ok
                page.locator('#prompt').fill(story)
                with page.expect_response(lambda r:r.url.endswith('/api/conversations') and r.request.method=='POST',timeout=60000) as response:page.locator('#prompt').press('Control+Enter')
                created=response.value.json();cid=created['id'];assert created['evaluation_only'] and not created['clarifications'],created
                assert page.locator('#submit').is_disabled()
                done=wait(cid);card=page.locator('[data-conversation-id="'+cid+'"]');card.locator('video').wait_for(timeout=15000)
                video=card.locator('video');video.evaluate('(v)=>v.play()');page.wait_for_timeout(400);assert video.evaluate('(v)=>v.currentTime')>0;video.evaluate('(v)=>v.pause()')
                job=page.request.get(base+'/api/jobs/'+done['job_id']).json();assert job['validated'] and job['evaluation_only']
                movie=ROOT/'output'/('v10-'+mode+'-evaluation.mp4');shutil.copyfile(ROOT/'output'/(done['job_id']+'.mp4'),movie)
                with page.expect_download() as download:card.get_by_role('link',name='Download Video').click()
                assert digest(Path(download.value.path()))==digest(movie)
                entry={'job_id':done['job_id'],'video':str(movie),'approved_speech':job['approved_speech']};entry['audit']=audit(entry);entry['conversation_id']=cid;results.append(entry)
                page.screenshot(path=str(ROOT/'workspace'/('v10-'+mode+'-browser.png')),full_page=True)
                if mode=='shorts':
                    with page.expect_response(lambda r:r.url.endswith('/regenerate'),timeout=60000) as regenerated:card.get_by_role('button',name='Regenerate Video',exact=True).click()
                    fresh=regenerated.value.json();assert fresh['id']!=cid;repeat=wait(fresh['id']);assert repeat['job_id']!=done['job_id']
                    results[-1]['regeneration_id']=fresh['id']
            # No speech/render starts for this intentionally unresolved story.
            page.locator('#prompt').fill('দৃশ্য: অজানা দুর্গ\nমিতা: এখানে এসো।')
            with page.expect_response(lambda r:r.url.endswith('/api/conversations') and r.request.method=='POST',timeout=60000) as failed:page.locator('#submit').click()
            uncertain=failed.value.json();assert uncertain['status']=='needs_input'
            card=page.locator('[data-conversation-id="'+uncertain['id']+'"]');card.get_by_role('button',name='Edit story',exact=True).click();assert page.locator('#prompt').input_value()==uncertain['prompt']
            page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.screenshot(path=str(ROOT/'workspace/v10-mobile.png'),full_page=True)
            assert not errors,errors
            atomic_json(ROOT/'workspace/v10-browser-acceptance.json',{'videos':results,'javascript_errors':errors,'mobile_no_overflow':True,'edit_story_restored':True,'four_selected_demo_ids_retained':True,'human_listening_review':'pending','commercial_permission_verified':False})
            print(json.dumps({'videos':[r['audit'] for r in results],'javascript_errors':errors}),flush=True)
        finally:
            page.request.put(base+'/api/preferences',data=saved);browser.close()

if __name__=='__main__':main()
