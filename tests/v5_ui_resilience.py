"""Isolated negative UI tests: dropped requests and untrusted prompt text."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]


def run():
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=str(Path(os.environ['LOCALAPPDATA'])/'ms-playwright/chromium-1248/chrome-win64/chrome.exe'))
        page=browser.new_page(viewport={'width':1280,'height':900});calls=[];pending={};script='<img src=x onerror="window.promptExecuted=true">'
        def post(route):
            body=route.request.post_data_json;calls.append(body);pending.update(body)
            if len(calls)==1:route.abort();return
            data={'id':body['request_id'],'prompt':body['prompt'],'created_at':'2026-11-17T14:00:00Z','status':'needs_input','message':'এই লাইনটি কীভাবে ব্যবহার করব?','revision':1,
                  'clarifications':[{'kind':'instruction','key':'event_001','source':script,'source_text':script,'text':script,'question':'লাইনটির অর্থ কী?',
                                     'characters':[],'actions':[],'shots':[],'options':[{'value':'ignore','label':'বাদ দিন'}]}]}
            route.fulfill(status=201,content_type='application/json',body=json.dumps(data))
        def intercept(route):
            if route.request.method=='POST':post(route)
            else:route.continue_()
        page.route('**/api/conversations',intercept)
        page.route('**/api/conversations/*',lambda route:route.fulfill(status=404,content_type='application/json',body='{"detail":"Not received"}') if route.request.method=='GET' and route.request.url.endswith(pending.get('request_id','NOT_A_REAL_ID')) else route.continue_())
        page.goto('http://127.0.0.1:8000');page.wait_for_selector('#prompt');page.locator('#prompt').fill(script);page.locator('#submit').click()
        page.wait_for_function("localStorage.getItem('toon-chat-pending-v5')!==null && document.querySelector('.turn:last-child .text-button')===null")
        page.wait_for_function("document.querySelector('.turn:last-child .status-line').textContent.includes('সংযোগ')")
        cid=pending['request_id'];assert json.loads(page.evaluate("localStorage.getItem('toon-chat-pending-v5')"))['prompt']==script
        page.reload();card=page.locator(f'[data-conversation-id="{cid}"]');card.get_by_role('button',name='আবার চেষ্টা করুন').wait_for(timeout=30000)
        card.get_by_role('button',name='আবার চেষ্টা করুন').click()
        card.locator('.clarification').wait_for();assert calls[0]==calls[1]
        assert not page.evaluate('Boolean(window.promptExecuted)') and card.locator('img').count()==0
        assert script in card.inner_text()
        assert page.evaluate("localStorage.getItem('toon-chat-pending-v5')") is None
        (ROOT/'workspace/v5-ui-resilience.json').write_text(json.dumps({'result':'passed','tests':['Unsent prompt survives reload','Explicit retry uses the same request ID','Prompt HTML is displayed as text'],
            'method':'Only negative transport/clarification responses are mocked. No generated video or speech success is simulated.'},indent=2),encoding='utf-8')
        print('V5 unsent-prompt and text-safety UI checks passed');browser.close()


if __name__=='__main__':run()
