import json
import math
import shutil
import subprocess
import wave
from array import array
import pytest
import app.main as main
from app.assets import plan_story,load_character
from app.engines.story_parser import parse_story
from app.engines.lip_sync import generate_mouth_cues,mouth_at,validate_cues
from app.engines.animation import render_scene,compose_character
from app.timeline import build_timeline
from conftest import wait


def test_envelope_and_rhubarb_failure(tmp_path,monkeypatch):
    import app.engines.lip_sync as lip
    path=tmp_path/'voice.wav'
    with wave.open(str(path),'wb') as wav:
        wav.setparams((1,2,8000,0,'NONE','not compressed'))
        wav.writeframes(array('h',[0]*1600+[round(12000*math.sin(i*.2)) for i in range(3200)]+[0]*1600).tobytes())
    monkeypatch.setattr(lip,'rhubarb_binary',lambda:'missing-rhubarb')
    cues=generate_mouth_cues(path,tmp_path/'mouth.json')
    assert cues['method']=='envelope' and 'Rhubarb failed' in cues['fallback_reason']
    assert mouth_at(cues['mouthCues'],.05)=='X'
    assert mouth_at(cues['mouthCues'],.35)!='X'
    assert mouth_at(cues['mouthCues'],.75)=='X'


@pytest.mark.parametrize('cues',[
    [{'start':0,'end':1,'value':'Z'}],
    [{'start':0,'end':float('nan'),'value':'B'}],
    [{'start':.1,'end':.6,'value':'C'},{'start':.4,'end':.8,'value':'D'}],
    [{'start':-.1,'end':.2,'value':'A'}]])
def test_invalid_cues(cues):
    with pytest.raises(ValueError): validate_cues({'mouthCues':cues},1)


def test_actions_and_offscreen_mouth(tmp_path):
    plan=plan_story(parse_story(main.SAMPLE)); char=load_character('rahat')
    first,_=compose_character(char,0,'walk')
    second,_=compose_character(char,.4,'walk')
    assert first.tobytes()!=second.tobytes()
    scene={'plan':plan,'time':2,'total_duration':20,'visible_characters':['rahat'],'action':'afraid',
           'speaker':'unknown_voice','off_screen':True,'local_time':1,'caption':'শেষ ট্রেনটা মিস করো না।'}
    assert render_scene({**scene,'mouth':'D'}).tobytes()==render_scene({**scene,'mouth':'X'}).tobytes()
    assert load_character('rahat')['identity_hash']==char['identity_hash']


def test_duration_clock_and_no_truncation():
    parsed=parse_story(main.SAMPLE); plan=plan_story(parsed)
    clips=[{**s,'duration_seconds':value} for s,value in zip(parsed['segments'],[10.01,2.13,3.42])]
    timeline=build_timeline(clips,plan)
    assert timeline['scenes'][0]['start_frame']==0
    assert all(a['end_frame']==b['start_frame'] for a,b in zip(timeline['scenes'],timeline['scenes'][1:]))
    assert all(s['end']-s['start']>=s['audio_duration'] for s in timeline['scenes'] if s['kind']=='speech')
    assert timeline['duration_seconds']<sum(c['duration_seconds'] for c in clips)+8
    clips[0]['duration_seconds']=45
    longer=build_timeline(clips,plan)
    assert longer['duration_seconds']>50
    assert any('40s target' in warning for warning in longer['warnings'])


@pytest.mark.skipif(not shutil.which('ffmpeg'),reason='FFmpeg required')
def test_mixed_pcm_matches_speech_slots_without_drift(tmp_path,tone_synth):
    from app.engines.video_renderer import build_audio
    parsed=parse_story(main.SAMPLE); plan=plan_story(parsed)
    (tmp_path/'audio').mkdir()
    clips=[]
    for segment in parsed['segments']:
        duration=tone_synth(segment['text'],tmp_path/'audio'/f"{segment['id']}.wav",tmp_path)
        clips.append({**segment,'duration_seconds':duration})
    timeline=build_timeline(clips,plan)
    path=build_audio(clips,timeline,tmp_path)
    with wave.open(str(path),'rb') as audio:
        assert (audio.getframerate(),audio.getnchannels(),audio.getsampwidth())==(48000,1,2)
        samples_per_frame=48000//timeline['fps']
        assert audio.getnframes()==timeline['total_frames']*samples_per_frame
        for scene in timeline['scenes']:
            start=scene['start_frame']*samples_per_frame
            audio.setpos(start+240)
            samples=audio.readframes(256)
            assert bool(any(samples))==(scene['kind']=='speech')
            if scene['kind']=='speech':
                audio.setpos(scene['end_frame']*samples_per_frame-20)
                assert audio.readframes(20)==b'\0\0'*20


@pytest.mark.skipif(not shutil.which('ffmpeg') or not shutil.which('ffprobe'),reason='FFmpeg/ffprobe required')
def test_real_vertical_video_identity_reuse_and_cpu_encoder_fallback(studio,tone_synth,monkeypatch):
    import app.engines.video_renderer as renderer
    from app.hardware import encoder_capabilities
    jobs=[]
    for index,story in enumerate([main.SAMPLE,'রাহাত রেলস্টেশনে অপেক্ষা করছিল।\n\nRahat: শেষ ট্রেন কখন আসবে?']):
        if index==1:
            real=renderer.encode_stream
            def fail_nvenc(*args,**kwargs):
                if args[4]=='h264_nvenc': raise RuntimeError('injected NVENC runtime failure')
                return real(*args,**kwargs)
            monkeypatch.setattr(renderer,'encode_stream',fail_nvenc)
            monkeypatch.setattr(renderer,'encoder_capabilities',lambda:{'encoder':'h264_nvenc','libx264_available':True})
        created=studio.post('/api/generate',json={'story':story})
        assert created.status_code==202,created.text
        job=wait(studio,created.json()['job_id'])
        assert job['status']=='completed',job
        assert (job['width'],job['height'],job['fps'])==(1080,1920,30)
        assert job['validated']
        assert studio.get(job['video_url']).content[4:8]==b'ftyp'
        assert studio.get(job['video_url'],headers={'Range':'bytes=0-31'}).status_code==206
        assert 'attachment' in studio.get(job['video_url']+'?download=true').headers['content-disposition']
        timeline=studio.get(job['timeline_url']).json()
        assert all('unknown_voice' not in s['visible_characters'] for s in timeline['scenes'])
        assert studio.get(job['subtitles_url']).status_code==200
        assert studio.get(job['report_url']).json()['video']['validated']
        jobs.append(job)
    assert jobs[0]['asset_references']['characters']==jobs[1]['asset_references']['characters']
    assert jobs[1]['report']['timings']['encoder']=='libx264'
    assert any('NVENC failed' in w for w in jobs[1]['warnings'])
