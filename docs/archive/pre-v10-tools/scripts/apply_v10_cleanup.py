"""One-time, exact-path source archival after the v10 backup."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def edit(name,old,new):
    p=ROOT/name;s=p.read_text(encoding='utf-8');assert old in s,name;p.write_text(s.replace(old,new),encoding='utf-8')
def archive(name):
    source=(ROOT/name).resolve();target=(ROOT/'docs/archive/legacy-studio'/name).resolve()
    assert source.is_relative_to(ROOT) and target.is_relative_to(ROOT/'docs/archive')
    if source.exists():
        assert not target.exists();target.parent.mkdir(parents=True,exist_ok=True);source.rename(target)
for name in ['app/templates/index.html',*[f'app/static/{x}' for x in ['app.js','production.js','screenplay.js','voice-studio.js','automatic.js','style.css']]]:archive(name)
edit('app/main.py',"from app.voice_profiles import reference_router\napp.include_router(reference_router(lambda:LIBRARY))\n",'')
edit('app/main.py',"def legacy_studio():return FileResponse(ROOT/'app/templates/index.html')","def legacy_studio():\n    from fastapi.responses import RedirectResponse\n    return RedirectResponse('/',status_code=307)")
edit('app/main.py',"version='9.0.0-preview'","version='10.0.0-preview'")
p=ROOT/'app/voice_profiles.py';s=p.read_text(encoding='utf-8');routes=s[s.index("    @router.get('/api/benchmarks/chatterbox')"):];print(routes)
api=ROOT/'app/voices/four_voice_api.py';text=api.read_text(encoding='utf-8');routes=routes.rsplit('    return router',1)[0].replace('ROOT/', 'voices.ROOT/')
routes='''    @router.get('/api/voice-references')
    @router.post('/api/voice-references/{cid}')
    def retired_references(cid:str=''):
        raise HTTPException(410,'Use /api/default-voices for four category voices. Existing recordings are preserved.')
'''+routes
text=text.replace('    return router',routes+'    return router');api.write_text(text,encoding='utf-8');archive('app/voice_profiles.py')
p=ROOT/'app/engines/animation.py';s=p.read_text(encoding='utf-8');start=s.index('@lru_cache(maxsize=128)\ndef subtitle_pages');end=s.index('def interpolate',start);p.write_text(s[:start]+s[end:],encoding='utf-8')
p=ROOT/'app/engines/video_renderer.py';s=p.read_text(encoding='utf-8').replace(',subtitle_pages','').replace('subtitle_pages,','');p.write_text(s,encoding='utf-8')
edit('tests/test_api.py',"assert 'Analyze Script' in studio.get('/studio').text","assert studio.get('/studio',follow_redirects=False).headers['location']=='/'")
edit('tests/test_v4.py',"assert 'auto-generate' in page and 'studio-tools' in page and 'voice-studio.js' in page","assert 'Generate Cartoon' in page and 'voice-studio.js' not in page")
edit('tests/test_chat.py','আপনার কার্টুনের গল্প লিখুন বা পেস্ট করুন...','আপনার বাংলা কার্টুনের গল্প লিখুন বা পেস্ট করুন...')
p=ROOT/'tests/test_v6_safety.py';s=p.read_text(encoding='utf-8').replace('from app import voice_profiles as refs\n','');a=s.index('def test_reference_permissions_and_duplicate_guard');b=s.index('def test_semantic_ai_is_opt_in',a);s=s[:a]+'''def test_retired_reference_setup_preserves_category_workflow(studio):
    assert studio.get('/api/voice-references').status_code==410
    assert studio.post('/api/voice-references/nabil',json={}).status_code==410


'''+s[b:];p.write_text(s,encoding='utf-8')
