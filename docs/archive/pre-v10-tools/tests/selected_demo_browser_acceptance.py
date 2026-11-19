"""Actual one-prompt evaluation generation using selected demo conditioning caches."""
import json
import os
import shutil
import sys
import time
import urllib.request
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.test_selected_demo_conditioning import TEXT
from app.scene_cache import atomic_json,digest


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--resume-conversation');args=parser.parse_args()
    script='দৃশ্য: আমবাগান\nচরিত্র: নাবিল, রায়ান, ফাহিম, অনিকা\n[নাবিল ধীরে হাঁটে।]\n'+'\n'.join(name+': '+TEXT for name in ('নাবিল','রায়ান','ফাহিম','অনিকা'))
    base='http://127.0.0.1:8000'
    ready=time.monotonic()+45
    while True:
        try:
            with urllib.request.urlopen(base+'/api/default-voices',timeout=2):break
        except OSError:
            if time.monotonic()>ready:raise
            time.sleep(.3)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=str(Path(os.environ['LOCALAPPDATA'])/'ms-playwright/chromium-1248/chrome-win64/chrome.exe'))
        page=browser.new_page(viewport={'width':1366,'height':900},accept_downloads=True);errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(base);page.locator('#settings-toggle').click();page.locator('#settings-dialog').wait_for(state='visible')
        assert page.locator('[data-voice-category]').count()==4
        page.get_by_text('Default Cartoon Voices',exact=True).click()
        for category,sid in {'male':'007','female':'006','child_male':'002','child_female':'005'}.items():
            assert 'Official Demo '+sid in page.locator('#base-voice-'+category).locator('option:checked').text_content()
        assert page.locator('#voice-usage-mode').input_value()=='evaluation'
        page.locator('#settings-close').click()
        if args.resume_conversation:
            cid=args.resume_conversation;page.evaluate('(cid)=>localStorage.setItem("toon-chat-selected-v5",cid)',cid);page.reload()
            card=page.locator('[data-conversation-id="'+cid+'"]');card.wait_for()
            with page.expect_response(lambda r:r.url.endswith('/'+cid+'/retry') and r.request.method=='POST',timeout=60000) as resumed:card.get_by_role('button',name='Resume unfinished scenes').click()
            data=resumed.value.json()
        else:
            page.locator('#prompt').fill(script)
            with page.expect_response(lambda r:r.url.endswith('/api/conversations') and r.request.method=='POST',timeout=60000) as created:page.locator('#submit').click()
            data=created.value.json();cid=data['id']
        assert data['evaluation_only'] and not data['clarifications'],data
        deadline=time.monotonic()+600;last=None
        while time.monotonic()<deadline:
            data=page.request.get(base+'/api/conversations/'+cid).json()
            if data['status']!=last:print('Cartoon',data['status'],flush=True);last=data['status']
            assert data['status'] not in ('failed','cancelled','needs_input','needs_payment'),data
            if data['status']=='completed':break
            time.sleep(.5)
        assert data['status']=='completed',data
        page.wait_for_function('(url)=>[...document.querySelectorAll("video")].some(v=>v.getAttribute("src")===url)',arg=data['video_url'],timeout=10000)
        video=page.locator('video[src="'+data['video_url']+'"]')
        video.evaluate('(v)=>v.play()');page.wait_for_timeout(300);assert video.evaluate('(v)=>v.currentTime')>0;video.evaluate('(v)=>v.pause()')
        job=page.request.get(base+'/api/jobs/'+data['job_id']).json();assert job['evaluation_only'] and job['validated']
        response=page.request.get(base+data['video_url']+'?download=true');assert 'evaluation-' in response.headers['content-disposition']
        path=ROOT/'output'/(data['job_id']+'.mp4');assert digest(path)==__import__('hashlib').sha256(response.body()).hexdigest()
        shutil.copyfile(path,ROOT/'output/selected-demo-evaluation.mp4')
        page.screenshot(path=str(ROOT/'workspace/selected-demo-evaluation-browser.png'),full_page=True)
        assert not errors,errors
        atomic_json(ROOT/'workspace/selected-demo-browser-acceptance.json',{'passed':True,'conversation':data,'job_id':data['job_id'],'video':str(ROOT/'output/selected-demo-evaluation.mp4'),
            'approved_speech':job['approved_speech'],'playback':True,'evaluation_download_label':True,'javascript_errors':errors})
        browser.close()


if __name__=='__main__':main()
