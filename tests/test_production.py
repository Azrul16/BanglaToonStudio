import json
import time
from pathlib import Path
import pytest
import app.main as main
from app.voices import voice_manager,elevenlabs,azure
from app.voices.base import VoiceIdentity,VoiceError
from conftest import wait


def wait_take(studio,sid):
    deadline=time.monotonic()+30
    while time.monotonic()<deadline:
        data=studio.get('/api/production/'+sid).json()
        if all(t['status'] not in ('queued','generating') for s in data['segments'] for t in s['takes']):return data
        time.sleep(.03)
    pytest.fail('Speech take timed out')


def test_pronunciation_preserves_original_and_voice_changes_need_confirmation(studio,monkeypatch):
    assert voice_manager.spoken_text(' Nabil এখানে আছে। ',{'Nabil':'নাবিল'})=='নাবিল এখানে আছে।'
    assert voice_manager.spoken_text('Nabilson',{'Nabil':'নাবিল'})=='Nabilson'
    assert studio.put('/api/pronunciation',json={'রাহাত':'রাহাদ'}).status_code==200
    session=studio.post('/api/production',json={'story':main.SAMPLE}).json()
    line=session['segments'][1]
    assert line['original_text']==line['text']
    voice={'provider':'vits','model':'bangladeshi-vits','voice_id':'default_bn','language':'bn'}
    assert studio.put('/api/voices/assignments/rahat',json={'voice':voice}).status_code==200
    monkeypatch.setattr(voice_manager,'catalog',lambda provider:[{'voice_id':'real_account_voice'}])
    cloud={'provider':'elevenlabs','model':'eleven_v4','voice_id':'real_account_voice','language':'bn'}
    assert studio.put('/api/voices/assignments/rahat',json={'voice':cloud}).status_code==422
    assert studio.put('/api/voices/assignments/rahat',json={'voice':cloud,'confirm_change':True}).status_code==200
    new=studio.post('/api/production',json={'story':main.SAMPLE}).json()
    assert next(s for s in new['segments'] if s['speaker']=='rahat')['voice']==cloud
    assert studio.put('/api/voices/assignments/invented',json={'voice':voice}).status_code==404


def test_paid_take_requires_exact_approval_and_never_falls_back(studio,monkeypatch):
    calls=[]
    monkeypatch.setattr(voice_manager,'catalog',lambda provider:[{'voice_id':'account_voice'}])
    session=studio.post('/api/production',json={'story':main.SAMPLE}).json();sid=session['session_id'];line=session['segments'][1]
    voice={'provider':'elevenlabs','model':'eleven_v4','voice_id':'account_voice','language':'bn'}
    base=f'/api/production/{sid}/segments/{line["id"]}'
    assert studio.put(base+'/voice',json=voice).status_code==200
    def unavailable(*args):calls.append(args);raise VoiceError('Cloud account unavailable; no fallback')
    monkeypatch.setattr(elevenlabs,'synthesize',unavailable)
    monkeypatch.setattr(voice_manager.vits,'synthesize',lambda *args:pytest.fail('Cloud failure must never invoke VITS'))
    assert studio.post(base+'/takes',json={}).status_code==409
    assert not calls
    estimate=studio.get(base+'/estimate').json();assert estimate['estimated_usd'] is None
    assert studio.post(base+'/takes',json={'paid_approved':True,'approval_token':'wrong'}).status_code==409
    assert studio.post(base+'/takes',json={'paid_approved':True,'approval_token':estimate['approval_token']}).status_code==202
    result=wait_take(studio,sid)['segments'][1]['takes'][0]
    assert result['status']=='failed' and len(calls)==1
    assert 'no fallback' in result['error']


def test_approved_takes_waveform_cues_freeze_and_individual_regeneration(studio,tone_synth,monkeypatch):
    monkeypatch.setattr(voice_manager.vits,'synthesize',tone_synth)
    session=studio.post('/api/production',json={'story':main.SAMPLE}).json();sid=session['session_id']
    for line in session['segments']:
        assert studio.post(f'/api/production/{sid}/segments/{line["id"]}/takes',json={}).status_code==202
    data=wait_take(studio,sid)
    for line in data['segments']:
        take=line['takes'][0];assert take['status']=='completed',take
        assert studio.get(take['audio_url']).content[:4]==b'RIFF'
        waveform=studio.get(f'/api/production/{sid}/takes/{take["take_id"]}/waveform').json();assert any(waveform['peaks'])
        assert studio.post(f'/api/production/{sid}/segments/{line["id"]}/approve',json={'take_id':take['take_id']}).status_code==200
    assert studio.get('/api/production/'+sid).json()['ready']
    created=studio.post(f'/api/production/{sid}/render',json={});assert created.status_code==202,created.text
    # The render must use approved WAVs, not call main's regular TTS.
    monkeypatch.setattr(main,'synthesize',lambda *args:pytest.fail('Approved speech must be reused'))
    job=wait(studio,created.json()['job_id']);assert job['status']=='completed',job
    assert job['approved_speech'] and job['clips'][0]['synthesis_text']
    first=data['segments'][0];take=first['takes'][0]
    assert studio.put(f'/api/production/{sid}/takes/{take["take_id"]}/cues',json={'mouthCues':[{'start':0,'end':.1,'value':'Z'}]}).status_code==422
    assert studio.put(f'/api/production/{sid}/takes/{take["take_id"]}/cues',json={'mouthCues':[{'start':0,'end':.1,'value':'X'}]}).status_code==200
    assert not studio.get('/api/production/'+sid).json()['ready']
    assert studio.post(f'/api/production/{sid}/render',json={}).status_code==422
    line=data['segments'][1]
    assert studio.put(f'/api/production/{sid}/segments/{line["id"]}',json={'synthesis_text':'নতুন উচ্চারণ।','emotion':'neutral','action':'point','shot':'medium'}).status_code==200
    changed=studio.get('/api/production/'+sid).json();assert changed['segments'][1]['approved_take'] is None
    assert changed['segments'][2]['approved_take']==data['segments'][2]['takes'][0]['take_id']


def test_provider_request_shapes_and_ssml_escape(monkeypatch):
    records=[]
    monkeypatch.setenv('ELEVENLABS_API_KEY','test-not-real')
    monkeypatch.setattr(elevenlabs,'fetch',lambda *args,**kwargs:(records.append(args) or (b'audio',{})))
    elevenlabs.synthesize('কে ওখানে?',VoiceIdentity(provider='elevenlabs',model='eleven_v4',voice_id='returned-by-catalog'),'curious')
    body=json.loads(records[-1][2]);assert body['model_id']=='eleven_v4' and body['inputs'][0]['voice_id']=='returned-by-catalog'
    monkeypatch.setenv('AZURE_SPEECH_KEY','test-not-real');monkeypatch.setenv('AZURE_SPEECH_REGION','eastus')
    monkeypatch.setattr(azure,'fetch',lambda *args,**kwargs:(records.append(args) or (b'audio',{})))
    azure.synthesize('A < B & C',VoiceIdentity(provider='azure',model='azure-neural',voice_id='bn-BD-NabanitaNeural'),'fear')
    assert b'&lt;' in records[-1][2] and b'&amp;' in records[-1][2]
    assert b'express-as' not in records[-1][2]


def test_thirty_fps_pcm_and_real_godot_export(studio,tone_synth,monkeypatch):
    from app.rendering.godot_adapter import godot_binary
    if not godot_binary():pytest.skip('Godot 4 binary required for real movie export')
    monkeypatch.setattr(voice_manager.vits,'synthesize',tone_synth)
    story='নাবিল আমবাগানে হাঁটছিল।\nনাবিল: কে ওখানে?\nরায়ান: আমি এখানে।'
    analyzed=studio.post('/api/analyze',json={'story':story,'renderer':'godot'}).json();assert analyzed['ready'],analyzed
    choices={'story':story,'renderer':'godot','music':True,'character_mappings':analyzed['character_mappings'],
             'scenes':[{k:s[k] for k in ('scene_id','start_segment','end_segment','background_id','location_text')} for s in analyzed['scenes']]}
    session=studio.post('/api/production',json=choices).json();sid=session['session_id']
    for line in session['segments']:studio.post(f'/api/production/{sid}/segments/{line["id"]}/takes',json={})
    data=wait_take(studio,sid)
    for line in data['segments']:studio.post(f'/api/production/{sid}/segments/{line["id"]}/approve',json={'take_id':line['takes'][0]['take_id']})
    created=studio.post(f'/api/production/{sid}/render',json={});assert created.status_code==202,created.text
    job=wait(studio,created.json()['job_id']);assert job['status']=='completed',job
    assert job['fps']==30 and job['validated']
    directory=main.WORKSPACE/job['job_id']
    assert (directory/'sound-events.json').is_file()
    assert any(e['track']=='music' and e['sound'].startswith('music_') for e in json.loads((directory/'sound-events.json').read_text())['events'])
    assert (directory/'direction.json').is_file()
    assert (directory/'asset_snapshot/characters/nabil/articulated/v1/rig.json').is_file()
    preview=studio.post(f'/api/production/{sid}/segments/{data["segments"][1]["id"]}/preview',json={})
    assert preview.status_code==202,preview.text
    preview_job=wait(studio,preview.json()['job_id']);assert preview_job['status']=='completed',preview_job
    assert len(preview_job['clips'])==1 and preview_job['fps']==30
    # Renderer/script failures are not mislabeled as NVENC failures or retried
    # as a paid speech request / another animation engine.
    import app.engines.video_renderer as renderer
    import app.rendering.godot_adapter as adapter
    calls=[]
    monkeypatch.setattr(renderer,'encoder_capabilities',lambda:{'encoder':'h264_nvenc','libx264_available':True})
    def broken(*args,**kwargs):calls.append(args[4]);raise RuntimeError('Godot render failed: invalid scene script')
    monkeypatch.setattr(adapter,'encode_scene',broken)
    jid=job['job_id'];main.update_job(jid,status='failed')
    assert studio.post(f'/api/jobs/{jid}/scenes/render_0001/retry',json={}).status_code==202
    failed=wait(studio,jid)
    assert failed['status']=='failed' and 'invalid scene script' in failed['error']
    assert calls==['h264_nvenc']
