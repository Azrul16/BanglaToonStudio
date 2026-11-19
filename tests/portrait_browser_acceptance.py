"""Actual portrait media playback/download in the existing chat output component.

The completed card is a UI fixture; no production generation/approval is faked.
"""
import json,os,sys,threading,time,tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.scene_cache import digest,atomic_json
from app.hardware import validate_video

def main():
    movie=ROOT/'output/flat-portrait-1080p-evaluation.mp4';errors=[]
    import app.main as app_main
    from app.library import AssetLibrary
    temporary=tempfile.TemporaryDirectory(prefix='toon-portrait-browser-')
    app_main.WORKSPACE=Path(temporary.name);app_main.LIBRARY=AssetLibrary(ROOT/'assets',app_main.WORKSPACE)
    # Serve actual bytes over HTTP: Chromium downloads cannot reliably use
    # Playwright's synthetic route fulfillment.
    import uvicorn
    import app.main as main_app
    from fastapi.responses import FileResponse
    @main_app.app.get('/portrait-acceptance.mp4')
    def media(download:bool=False):
        return FileResponse(movie,media_type='video/mp4',filename='portrait-acceptance.mp4' if download else None)
    server=uvicorn.Server(uvicorn.Config(main_app.app,host='127.0.0.1',port=8013,lifespan='off',log_level='error'))
    worker=threading.Thread(target=server.run,daemon=True);worker.start()
    deadline=time.monotonic()+10
    while not server.started:
        if time.monotonic()>deadline:raise RuntimeError('Browser verification server failed to start')
        time.sleep(.05)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=str(Path(os.environ['LOCALAPPDATA'])/'ms-playwright/chromium-1248/chrome-win64/chrome.exe'))
        page=browser.new_page(viewport={'width':1366,'height':900},accept_downloads=True)
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.route('**/api/conversations',lambda route:route.fulfill(json=[]))
        page.goto('http://127.0.0.1:8013');page.locator('#prompt').wait_for()
        data={'id':'legacy-portrait-ui-fixture','prompt':'Portrait playback verification fixture','created_at':'2026-11-18T00:00:00Z','status':'completed','video_url':'/portrait-acceptance.mp4','duration_seconds':21.3333,'width':1080,'height':1920}
        page.evaluate('(data)=>mount(data)',data)
        video=page.locator('video[aria-label="Generated cartoon"]').last
        video.evaluate('(v)=>v.play()');page.wait_for_function('document.querySelector("video").currentTime>0.2')
        assert video.evaluate('(v)=>[v.videoWidth,v.videoHeight]')==[1080,1920]
        for width,height in ((1366,900),(390,844)):
            page.set_viewport_size({'width':width,'height':height})
            box=video.bounding_box();assert abs(box['width']/box['height']-9/16)<.002
            assert box['height']<height*.7
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.screenshot(path=str(ROOT/f'workspace/portrait-browser-{width}.png'),full_page=True)
        with page.expect_download() as event:page.get_by_role('link',name='Download Video',exact=True).last.click()
        downloaded=ROOT/'workspace/portrait-browser-download.mp4';event.value.save_as(downloaded)
        assert digest(downloaded)==digest(movie)
        result=validate_video(downloaded,21.3333333333)
        assert not errors,errors
        atomic_json(ROOT/'workspace/portrait-browser-verification.json',{'ui_fixture':True,'real_native_video_played':True,'desktop_mobile_portrait':True,'download_hash_matches':True,'download_probe':result,'javascript_errors':errors})
        browser.close()
    server.should_exit=True;worker.join(timeout=10)
    temporary.cleanup()
    print('Portrait preview, playback, download and FFprobe checks passed.')
if __name__=='__main__':main()
