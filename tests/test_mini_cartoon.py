import json
import wave
import pytest
import app.main as main
from app.video_modes import output_size
from app.scene_cache import split_scenes,digest
from app.review import ReviewInput
from app.timeline import build_timeline
from app.assets import plan_story
from app.engines.story_parser import parse_story
from conftest import wait


def test_modes_and_review_binding(studio):
    assert output_size()==(1080,1920)
    assert output_size({'duration_mode':'mini'})==(1080,1920)
    assert output_size({'duration_mode':'mini','video_profile':'low_memory'})==(720,1280)
    with pytest.raises(ValueError):ReviewInput(story='hello',video_format='landscape')
    before=studio.post('/api/preflight',json={'story':main.SAMPLE}).json()
    assert studio.post('/api/generate',json={'story':main.SAMPLE,'duration_mode':'mini','review_token':before['review_token']}).status_code==409


def test_long_timeline_partition_and_duration_targets():
    parsed=parse_story(main.SAMPLE);plan=plan_story(parsed)
    clips=[{**segment,'duration_seconds':45.013} for segment in parsed['segments']]
    timeline=build_timeline(clips,plan,{'duration_mode':'mini'})
    assert (timeline['width'],timeline['height'])==(1080,1920)
    chunks=split_scenes(timeline)
    assert 120<timeline['duration_seconds']<180
    assert not timeline['warnings']
    assert chunks[0]['start_frame']==0 and chunks[-1]['end_frame']==timeline['total_frames']
    assert all(a['end_frame']==b['start_frame'] for a,b in zip(chunks,chunks[1:]))
    assert max(s['duration_seconds'] for s in chunks)<=12


@pytest.mark.parametrize('video_profile,size',[('production',(1080,1920)),('low_memory',(720,1280))])
def test_real_portrait_failed_scene_resume_and_cache_integrity(studio,tone_synth,monkeypatch,video_profile,size):
    import app.engines.video_renderer as renderer
    original=renderer.encode_stream
    failure=[True]
    def fail_scene(*args,**kwargs):
        if kwargs['chunk']['scene_id']=='render_0002' and failure[0]:
            failure[0]=False;raise RuntimeError('Injected second scene failure')
        return original(*args,**kwargs)
    monkeypatch.setattr(renderer,'encode_stream',fail_scene)
    monkeypatch.setattr(renderer,'encoder_capabilities',lambda:{'encoder':'libx264','libx264_available':True})
    story='নাবিল: এসো!\nরায়ান: ঠিক আছে।\nঅনিকা: চল!'
    choices={'story':story,'duration_mode':'mini','video_profile':video_profile,'scenes':[
        {'scene_id':f'scene_{i+1:03}','start_segment':i,'end_segment':i+1,'background_id':bg}
        for i,bg in enumerate(('village_courtyard_day','mango_orchard_day','school_courtyard_day'))]}
    created=studio.post('/api/generate',json=choices);assert created.status_code==202,created.text
    jid=created.json()['job_id'];job=wait(studio,jid)
    assert job['status']=='failed' and 'second scene failure' in job['error']
    assert [s['status'] for s in job['render_scenes']]==['completed','failed','pending']
    directory=main.WORKSPACE/jid
    first=digest(directory/'render/scenes/render_0001.mp4')
    hashes={p.name:digest(p) for p in (directory/'audio').glob('*.wav')}
    def no_speech(*args):raise AssertionError('Resume must use cached speech and mouth cues')
    monkeypatch.setattr(main,'synthesize',no_speech);monkeypatch.setattr(main,'generate_mouth_cues',no_speech)
    assert studio.post(f'/api/jobs/{jid}/scenes/not_real/retry',json={}).status_code==404
    resumed=studio.post(f'/api/jobs/{jid}/scenes/render_0002/retry',json={})
    assert resumed.status_code==202 and resumed.json()['job_id']==jid
    job=wait(studio,jid);assert job['status']=='completed',job
    assert (job['width'],job['height'])==size and job['validated']
    assert digest(directory/'render/scenes/render_0001.mp4')==first
    assert hashes=={p.name:digest(p) for p in (directory/'audio').glob('*.wav')}
    assert job['report']['timings']['scenes_reused']==1 and job['report']['timings']['scenes_rendered']==2
    timeline=json.loads((directory/'timeline.json').read_text(encoding='utf-8'))
    with wave.open(str(directory/'render/timeline.wav'),'rb') as full:
        combined=b''
        for s in job['render_scenes']:
            with wave.open(str(directory/'render/scenes'/f"{s['scene_id']}.wav"),'rb') as wav:
                assert wav.getnframes()==(s['end_frame']-s['start_frame'])*1600
                combined+=wav.readframes(wav.getnframes())
        assert combined==full.readframes(full.getnframes())
        assert full.getnframes()==timeline['total_frames']*1600
    # A tampered completed chunk must be regenerated, never trusted by its name.
    (directory/'render/scenes/render_0001.mp4').write_bytes(b'corrupt')
    main.update_job(jid,status='failed')
    assert studio.post(f'/api/jobs/{jid}/resume',json={}).status_code==202
    job=wait(studio,jid);assert job['status']=='completed',job
    assert job['report']['timings']['scenes_reused']==2 and job['report']['timings']['scenes_rendered']==1
    assert studio.post(f'/api/jobs/{jid}/resume',json={}).status_code==409


def test_scene_concat_with_mid_video_nvenc_fallback(studio,tone_synth,monkeypatch):
    import app.engines.video_renderer as renderer
    from app.hardware import encoder_capabilities
    if not encoder_capabilities().get('nvenc_available'):pytest.skip('Real NVENC required for mixed encoder acceptance')
    original=renderer.encode_stream
    def fail_second(*args,**kwargs):
        if args[4]=='h264_nvenc' and kwargs['chunk']['scene_id']=='render_0002':raise RuntimeError('Injected NVENC failure in the middle scene')
        return original(*args,**kwargs)
    monkeypatch.setattr(renderer,'encode_stream',fail_second)
    story='নাবিল: এসো!\nরায়ান: ঠিক আছে।\nঅনিকা: চল!'
    choices={'story':story,'duration_mode':'mini','scenes':[
        {'scene_id':f'scene_{i+1:03}','start_segment':i,'end_segment':i+1,'background_id':'mango_orchard_day'} for i in range(3)]}
    created=studio.post('/api/generate',json=choices)
    job=wait(studio,created.json()['job_id'])
    assert job['status']=='completed' and job['validated'],job
    assert [s['encoder'] for s in job['render_scenes']]==['h264_nvenc','libx264','h264_nvenc']
    assert any('NVENC failed' in w for w in job['warnings'])
