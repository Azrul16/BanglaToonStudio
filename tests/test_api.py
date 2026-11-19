import threading
import app.main as main
from conftest import wait


def test_health_and_minimal_home(studio,monkeypatch):
    monkeypatch.setattr(main,'hardware_info',lambda:{'ffmpeg':'ffmpeg','ffprobe':'ffprobe','tts_installed':True})
    assert studio.get('/api/health').json()['format']=={'width':1080,'height':1920,'fps':30,'orientation':'portrait','aspect_ratio':'9:16'}
    page=studio.get('/').text
    assert 'Generate Cartoon' in page and 'Cartoon story' in page
    assert 'id="picker"' not in page and 'chat.js' in page and 'app.js' not in page
    assert studio.get('/studio',follow_redirects=False).headers['location']=='/'
    assert studio.get('/api/font').status_code==200


def test_parse_api_validation(studio):
    assert studio.post('/api/stories/parse',json={'story':main.SAMPLE}).json()['count']==3
    for story in (' ','মিতা: হ্যালো!'):
        assert studio.post('/api/generate',json={'story':story}).status_code==422
    assert studio.post('/api/generate',json={'story':'এক বন ছিল।'}).status_code==422
    assert studio.post('/api/audio/generate',json={'story':main.SAMPLE,'engine':'preview'}).status_code==422
    assert studio.get('/api/videos/not-a-uuid').status_code==404


def test_audio_job_and_restart(studio,tone_synth):
    created=studio.post('/api/audio/generate',json={'story':main.SAMPLE})
    assert created.status_code==202
    job=wait(studio,created.json()['job_id'])
    assert job['status']=='completed',job
    assert len(job['clips'])==3
    assert studio.get(job['clips'][0]['audio_url']).status_code==200
    assert studio.get('/api/videos/'+job['job_id']).status_code==404
    main.JOBS.clear(); main.recover_jobs()
    assert studio.get('/api/jobs/'+job['job_id']).json()['status']=='completed'
    main.update_job(job['job_id'],status='rendering')
    main.JOBS.clear(); main.recover_jobs()
    assert studio.get('/api/jobs/'+job['job_id']).json()['status']=='failed'
    retry=studio.post(f"/api/jobs/{job['job_id']}/retry")
    assert wait(studio,retry.json()['job_id'])['status']=='completed'


def test_cancellation_queue_limit_and_single_worker(studio,monkeypatch,tone_synth):
    entered=threading.Event(); release=threading.Event()
    def blocking(*args):
        entered.set(); release.wait(timeout=10); return tone_synth(*args)
    monkeypatch.setattr(main,'synthesize',blocking)
    try:
        first=studio.post('/api/audio/generate',json={'story':'রাহাত: অপেক্ষা করো।'}).json()
        assert entered.wait(3)
        others=[studio.post('/api/audio/generate',json={'story':'রাহাত: হ্যালো!'}).json() for _ in range(3)]
        assert studio.post('/api/audio/generate',json={'story':'রাহাত: হ্যালো!'}).status_code==429
        assert all(studio.get('/api/jobs/'+j['job_id']).json()['status']=='queued' for j in others)
        for j in others: assert studio.post('/api/jobs/'+j['job_id']+'/cancel').status_code==200
        assert studio.post('/api/jobs/'+first['job_id']+'/cancel').status_code==200
    finally: release.set()
    assert wait(studio,first['job_id'])['status']=='cancelled'
    assert all(wait(studio,j['job_id'])['status']=='cancelled' for j in others)


def test_failure_is_not_success_or_silent_audio(studio,monkeypatch):
    def fail(*args): raise RuntimeError('VITS inference failed')
    monkeypatch.setattr(main,'synthesize',fail)
    job=studio.post('/api/audio/generate',json={'story':main.SAMPLE}).json()
    result=wait(studio,job['job_id'])
    assert result['status']=='failed' and result['error']=='VITS inference failed'
    assert not result['clips']
    assert studio.get('/api/videos/'+job['job_id']).status_code==404
