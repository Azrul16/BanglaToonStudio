"""Live minimal UI plus playback of the actual two v7 MP4s, without changing preferences."""
import functools
import hashlib
import json
import os
import threading
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass
    def copyfile(self,source,outputfile):
        try:super().copyfile(source,outputfile)
        except (ConnectionResetError,ConnectionAbortedError,BrokenPipeError):pass  # Browser cancels playback requests when navigating.


def main():
    server=ThreadingHTTPServer(('127.0.0.1',0),functools.partial(QuietHandler,directory=str(ROOT/'output')))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    results=[]
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True,executable_path=str(Path(os.environ['LOCALAPPDATA'])/'ms-playwright/chromium-1248/chrome-win64/chrome.exe'))
            page=browser.new_page(viewport={'width':1366,'height':900});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto('http://127.0.0.1:8000');page.wait_for_selector('#prompt')
            assert page.request.get('http://127.0.0.1:8000/openapi.json').json()['info']['version']=='7.0.0-preview'
            assert page.locator('#submit').inner_text().startswith('Generate Cartoon')
            assert page.locator('#voice-studio-panel,#screenplay-panel,#picker,#camera-panel').count()==0
            assert page.locator('#settings-dialog').is_hidden()
            plan=page.request.post('http://127.0.0.1:8000/api/automatic/plan',data={'story':(ROOT/'samples/v7_benchmark_bn.txt').read_text(encoding='utf-8'),'voice_preference':'chatterbox_bangla'}).json()
            assert len(plan['lines'])==5
            assert all(i['type']=='voice' and i['reason']=='reference_required' for i in plan['review']['issues']),plan['review']['issues']
            page.screenshot(path=str(ROOT/'workspace/v7-chat.png'),full_page=True)
            for format,size in [('landscape',(1280,720)),('vertical',(720,1280))]:
                file=ROOT/'output'/f'v7-{format}-evaluation.mp4'
                url=f'http://127.0.0.1:{server.server_port}/{file.name}'
                page.goto(url);video=page.locator('video');video.wait_for();video.evaluate('(v)=>v.play()')
                page.wait_for_function('document.querySelector("video").currentTime>0.2')
                actual=video.evaluate('(v)=>[v.videoWidth,v.videoHeight]');assert actual==list(size)
                video.evaluate('(v)=>v.pause()')
                downloaded=page.request.get(url).body();assert hashlib.sha256(downloaded).hexdigest()==hashlib.sha256(file.read_bytes()).hexdigest()
                results.append({'format':format,'played':True,'resolution':actual,'download_hash_verified':True})
            assert not errors,errors
            (ROOT/'workspace/v7-browser-smoke.json').write_text(json.dumps({'passed':True,'version':'7.0.0-preview','minimal_ui':True,'unnecessary_script_questions':0,
                'production_reference_questions':len(plan['review']['issues']),'playback':results,'javascript_errors':errors},indent=2),encoding='utf-8')
            browser.close()
    finally:server.shutdown();server.server_close();thread.join(timeout=3)


if __name__=='__main__':main()
