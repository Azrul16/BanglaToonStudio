import json
import time
from pathlib import Path
import pytest
import app.main as main
from app.screenplay import ScriptEvent,get_spoken_segments,assert_speakable
from app.engines.story_parser import parse_story
from app.voices import voice_manager
from conftest import wait

CRITICAL='''দৃশ্য: আমবাগান

নাবিল গাছের নিচে দাঁড়িয়ে আছে।

নাবিল (ভয়ে): কে ওখানে?

রায়ান ধীরে সামনে এগিয়ে যায়।

রায়ান: আমি কিছু দেখতে পাচ্ছি না!

ক্যামেরা ধীরে গাছের দিকে এগোয়।'''
FULL='''দৃশ্য: গ্রামের আমবাগান
সময়: বিকেল
চরিত্র: নাবিল, রায়ান
[নাবিল গাছের নিচে দাঁড়িয়ে আছে।]
[হঠাৎ পাতার শব্দ শোনা যায়।]
[SFX: rustling_leaves]
[নাবিল ভয় পেয়ে পেছনে তাকায়।]
নাবিল (ভয়ে): এই রায়ান! তুই কিছু শুনলি?
[রায়ান ধীরে গাছের দিকে হাঁটে।]
রায়ান (কৌতূহলী): হ্যাঁ! মনে হচ্ছে ওখানে কেউ আছে!
[দুজন একে অপরের দিকে তাকায়।]
[ক্যামেরা গাছের দিকে ধীরে এগিয়ে যায়।]'''


def test_critical_only_two_speech_lines(studio):
    data=studio.post('/api/analyze',json={'story':CRITICAL,'renderer':'godot'}).json()
    assert data['ready'],data
    assert [(s['speaker'],s['text']) for s in data['spoken_segments']]==[('nabil','কে ওখানে?'),('rayan','আমি কিছু দেখতে পাচ্ছি না!')]
    assert [e['type'] for e in data['events']]==['scene_description','action','dialogue','action','dialogue','camera']
    assert [e['source_line'] for e in data['events']]==[1,3,5,7,9,11]
    assert data['events'][2]['emotion']=='fear'
    assert not any(e['generate_voice'] for e in data['events'] if e['type'] not in ('dialogue','narration'))


def test_complete_provided_syntax_metadata_and_multiple_actions(studio):
    data=studio.post('/api/analyze',json={'story':FULL,'renderer':'godot'}).json();assert data['ready'],data
    assert len(data['spoken_segments'])==2
    assert data['scenes'][0]['background_id']=='mango_orchard_day'
    event=next(e for e in data['events'] if 'ভয় পেয়ে' in e['source_text'])
    assert event['actions']==['fear','turn'] and event['character_ids']==['nabil']
    assert {e['sound_id'] for e in data['events'] if e['type']=='sound_effect'}=={'rustling_leaves'}


def test_narration_is_explicit_unknown_is_never_spoken(studio):
    parsed=parse_story('অদ্ভুত ঘটনা ঘটেছিল।\nবর্ণনাকারী: সেদিন অদ্ভুত কিছু ঘটেছিল।\nNabil [চিৎকার করে]: কী হয়েছে?\nসময়: বিকেল')
    assert [s['text'] for s in parsed['segments']]==['সেদিন অদ্ভুত কিছু ঘটেছিল।','কী হয়েছে?']
    assert parsed['segments'][0]['explicit_narration']
    assert parsed['segments'][1]['speaker']=='nabil' and parsed['segments'][1]['delivery']=='shout'
    assert parsed['events'][0]['type']=='unresolved_instruction'
    assert parsed['events'][-1]['type']=='metadata'
    with pytest.raises(ValueError):ScriptEvent(event_id='bad',type='action',source_text='walk',source_line=1,source_end_line=1,text='walk',generate_voice=True)
    with pytest.raises(ValueError):assert_speakable({'type':'narration','generate_voice':True,'text':'implicit'})


def test_ambiguous_instruction_project_correction_and_unknown_assets(studio):
    text='দৃশ্য: আমবাগান\nঅদ্ভুত নীল রহস্য।\nনাবিল: কী হয়েছে?'
    data=studio.post('/api/analyze',json={'story':text}).json()
    assert data['ready'] and data['events'][1]['type']=='unresolved_instruction'
    assert data['events'][1]['metadata']['blocking'] is False and not data['events'][1]['generate_voice']
    correction={'event_002':{'source_text':'অদ্ভুত নীল রহস্য।','type':'ignore'}}
    fixed=studio.post('/api/analyze',json={'story':text,'script_corrections':correction}).json();assert fixed['ready'],fixed
    assert len(fixed['spoken_segments'])==1 and fixed['events'][1]['type']=='ignore'
    narration={'event_002':{'source_text':'অদ্ভুত নীল রহস্য।','type':'narration'}}
    fixed=studio.post('/api/analyze',json={'story':text,'script_corrections':narration}).json();assert len(fixed['spoken_segments'])==2
    assert studio.post('/api/analyze',json={'story':'দৃশ্য: পুরোনো দুর্গ\nমিতা: এসো।'}).json()['ready'] is False
    assert parse_story('রং: নীল')['count']==0


def test_mixed_aliases_source_preservation_and_delivery():
    parsed=parse_story('  নাবিল: হ্যালো!  \nRayan: এসো।\nনাবিল ফিসফিস করে।\nNabil: শোন।\nসময়: বিকেল')
    assert [s['speaker'] for s in parsed['segments']]==['nabil','rayan','nabil']
    assert parsed['events'][0]['source_text']=='  নাবিল: হ্যালো!  '
    assert parsed['segments'][-1]['delivery']=='whisper'
    assert parsed['events'][2]['type']=='emotion' and not parsed['events'][2]['generate_voice']


def test_multiple_scenes_shared_timing_and_explicit_targets(studio):
    from app.review import ReviewInput,analyze
    from app.timeline import build_timeline
    from app.director import CartoonDirector
    story='দৃশ্য: আমবাগান\nচরিত্র: নাবিল, রায়ান\n[নাবিল হাঁটতে থাকে।]\nনাবিল: এসো।\nRayan: যাচ্ছি।\nদৃশ্য: স্কুল\nচরিত্র: নাবিল\n[নাবিল হাত নাড়ে।]'
    report,parsed,plan=analyze(main.LIBRARY,ReviewInput(story=story,renderer='godot'))
    assert report['ready'],report
    assert [s['background_id'] for s in report['scenes']]==['mango_orchard_day','school_courtyard_day']
    clips=[{**s,'duration_seconds':duration} for s,duration in zip(parsed['segments'],[1.25,2.17])]
    timeline=build_timeline(clips,plan,{'renderer':'godot','duration_mode':'shorts','video_format':'auto'})
    assert len(timeline['speech_track'])==2
    for speech,duration in zip(timeline['speech_track'],[1.25,2.17]):assert speech['end']-speech['start']==pytest.approx(duration)
    direction=CartoonDirector().plan(timeline,plan,clips)
    first=next(s for s in direction if s['kind']=='action')
    assert first['actors']['nabil']['action']=='walk' and first['actors']['rayan']['action']=='idle'
    spoken=next(s for s in direction if s['kind']=='speech')
    assert spoken['actors']['nabil']['action']=='walk' and spoken['actors']['nabil']['start']==first['start']


def test_unknown_actions_and_unsupported_camera_are_blocked(studio):
    story='দৃশ্য: আমবাগান\n[নাবিল আকাশে উড়ে যায়।]'
    data=studio.post('/api/analyze',json={'story':story,'renderer':'godot'}).json()
    assert not data['ready'] and not data['spoken_segments']
    corrections={'event_002':{'source_text':'[নাবিল আকাশে উড়ে যায়।]','type':'action','character_id':'nabil','action':'fly'}}
    assert not studio.post('/api/analyze',json={'story':story,'renderer':'godot','script_corrections':corrections}).json()['ready']
    corrections['event_002'].update(type='camera',camera_action='over_shoulder',action=None)
    assert not studio.post('/api/analyze',json={'story':story,'renderer':'godot','script_corrections':corrections}).json()['ready']


def test_legacy_session_cannot_request_paid_or_local_audio(studio):
    from app.scene_cache import atomic_json
    session=studio.post('/api/production',json={'story':CRITICAL,'renderer':'godot'}).json()
    sid=session['session_id'];session['schema_version']=1
    for line in session['segments']:line.pop('generate_voice',None)
    atomic_json(main.WORKSPACE/'production'/sid/'session.json',session)
    for endpoint in ('estimate','takes'):
        url=f'/api/production/{sid}/segments/segment_001/{endpoint}'
        response=studio.get(url) if endpoint=='estimate' else studio.post(url,json={})
        assert response.status_code==422 and 'Speech blocked' in response.text


def test_recording_provider_receives_only_dialogue(studio,tone_synth,monkeypatch):
    calls=[]
    def record(text,*args):calls.append(text);return tone_synth(text,*args)
    monkeypatch.setattr(voice_manager.vits,'synthesize',record)
    session=studio.post('/api/production',json={'story':CRITICAL,'renderer':'godot'}).json();assert 'session_id' in session,session
    sid=session['session_id']
    for segment in session['segments']:
        assert studio.post(f'/api/production/{sid}/segments/{segment["id"]}/takes',json={}).status_code==202
    deadline=time.monotonic()+30
    while time.monotonic()<deadline:
        data=studio.get('/api/production/'+sid).json()
        if all(s['takes'][0]['status']=='completed' for s in data['segments']):break
        time.sleep(.05)
    assert calls==['কে ওখানে?','আমি কিছু দেখতে পাচ্ছি না!']
    for line in data['segments']:studio.post(f'/api/production/{sid}/segments/{line["id"]}/approve',json={'take_id':line['takes'][0]['take_id']})
    created=studio.post(f'/api/production/{sid}/render',json={});assert created.status_code==202,created.text
    job=wait(studio,created.json()['job_id']);assert job['status']=='completed',job
    assert calls==['কে ওখানে?','আমি কিছু দেখতে পাচ্ছি না!']
    timeline=studio.get(job['timeline_url']).json();assert len(timeline['speech_track'])==2
    assert any(s['kind']=='action' for s in timeline['scenes'])
    assert timeline['speech_track'][1]['start']>timeline['speech_track'][0]['end']
    assert [s['speaker_id'] for s in timeline['speech_track']]==['nabil','rayan']


def test_instructions_only_render_without_tts(studio,monkeypatch):
    def forbidden(*args,**kwargs):pytest.fail('Silent screenplay must make ZERO speech requests')
    monkeypatch.setattr(main,'synthesize',forbidden);monkeypatch.setattr(voice_manager.vits,'synthesize',forbidden)
    story='দৃশ্য: আমবাগান\nচরিত্র: নাবিল\n[নাবিল ধীরে হাঁটে।]\n[SFX: rustling_leaves]'
    data=studio.post('/api/analyze',json={'story':story,'renderer':'godot'}).json();assert data['ready'],data
    assert data['spoken_segments']==[]
    created=studio.post('/api/generate',json={'story':story,'renderer':'godot'});assert created.status_code==202,created.text
    job=wait(studio,created.json()['job_id']);assert job['status']=='completed',job
    assert job['clips']==[] and job['report']['tts']['device']=='not_used'
    timeline=studio.get(job['timeline_url']).json();assert timeline['speech_track']==[] and timeline['effects_track']
