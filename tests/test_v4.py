import json
import time
import uuid
import unicodedata
import pytest
import app.main as main
from app.scene_cache import atomic_json
from app.voices import voice_manager
from app.motion import contacts,smooth,DEFAULT
from app.audio.sound_director import SoundDirector
from app.engines.story_parser import parse_story

STORY='''দৃশ্য: আমবাগান
চরিত্র: নাবিল, রায়ান, অনিকা
সংগীত: adventure
[নাবিল ধীরে গাছের কাছে যায়।]
নাবিল বলল, “কিছু একটা নড়ছে!”
[রায়ান নাবিলের দিকে তাকায়।]
রায়ান (কৌতূহলী): কোথায়?
[অনিকা মাথা ঘোরায়।]
অনিকা: ওই পাতাগুলো দেখ!
[SFX: leaves_rustling]
ক্যামেরা: reaction'''


def auto_wait(studio,aid):
    deadline=time.monotonic()+90
    while time.monotonic()<deadline:
        data=studio.get('/api/automatic/'+aid).json()
        if data['status'] in ('completed','failed','cancelled'):return data
        time.sleep(.05)
    pytest.fail('Automatic cartoon timed out')


def test_four_categories_and_explicit_alternatives(studio,monkeypatch):
    from app.voices.studio import Registry
    with pytest.raises(ValueError):Registry(voice_categories={'male':[]})
    data=studio.get('/api/voice-studio').json()
    assert [c['id'] for c in data['categories']]==['male','female','child_male','child_female']
    categories={c['id']:c['category'] for c in data['characters']}
    assert categories['nabil']=='child_male' and categories['anika']=='child_female'
    assert categories['rahat']=='male' and categories['mehna']=='female'
    voice={'provider':'vits','model':'bangladeshi-vits','voice_id':'default_bn','language':'bn'}
    assert studio.post('/api/voice-studio/presets',json={'category':'child_male','voice':voice,'label':'Offline alternative'}).status_code==422
    assert studio.post('/api/voice-studio/presets',json={'category':'child_male','voice':voice,'label':'Offline alternative','accept_alternative':True}).status_code==200
    assert studio.get('/api/voice-studio').json()['voice_categories']['child_male'][0]['voice']==voice
    assert (main.WORKSPACE/'voice_studio.json').is_file()


def test_quoted_prose_music_and_sfx_never_spoken(studio):
    story='নাবিল আমবাগানে গেল। নাবিল বলল, “কে ওখানে?” রায়ান উত্তর দিল, “আমি এখানে।”'
    parsed=parse_story(story)
    assert [(s['speaker'],s['text']) for s in parsed['segments']]==[('nabil','কে ওখানে?'),('rayan','আমি এখানে।')]
    assert all(e['source_line']==1 for e in parsed['events'])
    data=studio.post('/api/analyze',json={'story':STORY,'renderer':'godot'}).json()
    assert data['ready'],data
    assert len(data['spoken_segments'])==3 and next(e for e in data['events'] if e['type']=='sound_effect')['sound_id']=='rustling_leaves'


def test_paste_to_video_and_reuse_without_manual_approval(studio,tone_synth,monkeypatch):
    calls=[]
    def record(text,*args):calls.append(text);return tone_synth(text,*args)
    monkeypatch.setattr(voice_manager.vits,'synthesize',record)
    result=studio.post('/api/automatic/generate',json={'story':STORY});assert result.status_code==202,result.text
    aid=result.json()['automatic_id'];completed=auto_wait(studio,aid)
    assert completed['status']=='completed',completed
    assert calls==[unicodedata.normalize('NFC',s) for s in ['কিছু একটা নড়ছে!','কোথায়?','ওই পাতাগুলো দেখ!']]
    job=completed['render'];assert job['validated'] and job['fps']==30
    assert {c['speaker'] for c in job['clips']}=={'nabil','rayan','anika'}
    # Music/volume changes reuse the exact approved audio, without more provider calls.
    repeated=studio.post('/api/automatic/generate',json={'story':STORY,'music':False,'audio_levels':{'sfx':.8}})
    assert repeated.status_code==202,repeated.text
    second=auto_wait(studio,repeated.json()['automatic_id']);assert second['status']=='completed',second
    assert second['reused_speech']==3 and len(calls)==3
    original={s['audio_hash'] for s in job['approved_speech']};assert {s['audio_hash'] for s in second['render']['approved_speech']}==original


def test_unknowns_and_paid_approval_block_before_queue(studio,monkeypatch):
    assert studio.post('/api/automatic/generate',json={'story':'দৃশ্য: অজানা দুর্গ\nমিতা: এসো।'}).status_code==422
    voice={'provider':'elevenlabs','model':'eleven_v4','voice_id':'real-id-in-mocked-account-catalog','language':'bn'}
    atomic_json(main.WORKSPACE/'voice_assignments.json',{'nabil':voice})
    monkeypatch.setattr('app.autopilot.configured',lambda provider:True)
    monkeypatch.setattr(main.executor,'submit',lambda *args:None)
    body={'story':'দৃশ্য: আমবাগান\nনাবিল: হ্যালো।','request_id':uuid.uuid4().hex}
    denied=studio.post('/api/automatic/generate',json=body);assert denied.status_code==409
    plan=denied.json()['detail']['plan'];assert plan['characters']>0 and plan['paid']
    allowed=studio.post('/api/automatic/generate',json={**body,'paid_approved':True,'approval_token':plan['approval_token']});assert allowed.status_code==202
    assert studio.post('/api/automatic/generate',json={**body,'paid_approved':True,'approval_token':plan['approval_token']}).json()['automatic_id']==body['request_id']
    # Changed text cannot spend an old batch authorization.
    assert studio.post('/api/automatic/generate',json={**body,'request_id':uuid.uuid4().hex,'story':body['story']+' নতুন কথা।','paid_approved':True,'approval_token':plan['approval_token']}).status_code==409


def test_foot_contacts_follow_eased_distance_and_sound_moods():
    actor={'action':'walk','start':0.,'end':3.,'from_x':-120.,'to_x':0.,'speed':60.,'motion':dict(DEFAULT),'emotion':'neutral'}
    points=contacts(actor,.8);assert points
    for contact in points:assert 120*smooth(contact['time']/3)/(.8*DEFAULT['stride'])==pytest.approx(contact['cycle'],abs=1e-5)
    scene={'kind':'action','start':0.,'end':3.,'source_scene_id':'scene_001','background_id':'mango_orchard_day','actors':{'nabil':actor},'instruction':{'source_text':'অভিযান','metadata':{}},'emotion':'neutral'}
    events=SoundDirector().plan([scene],True)
    assert next(e for e in events if e['track']=='music')['sound']=='music_adventure'
    assert [e['start'] for e in events if e['track']=='action']==[p['time'] for p in points]
    scene['instruction']['metadata']['intentional_silence']=True
    assert not any(e['track'] in ('music','ambience') for e in SoundDirector().plan([scene],True))


def test_simple_home_and_registered_sound_previews(studio):
    page=studio.get('/studio').text
    assert 'Generate Cartoon' in page and 'voice-studio.js' not in page
    for mood in ('happy','comedy','mystery','suspense','adventure','emotional','calm','dramatic'):
        assert studio.get('/api/sounds/music_'+mood+'/audio').content[:4]==b'RIFF'
    assert studio.get('/api/sounds/missing/audio').status_code==404


def test_music_ducking_has_smooth_attack_release_and_overlap():
    import numpy as np
    from app.audio.mixer import ducking_envelope
    clock=np.arange(0,4,.001)
    envelope=ducking_envelope(clock,[{'start':1.,'end':2.},{'start':2.2,'end':3.}])
    assert envelope[0]==1 and envelope[1000]==pytest.approx(.16) and envelope[3999]==1
    assert envelope[1100]==pytest.approx(.16) and .16<envelope[2075]<1
    assert np.max(np.abs(np.diff(envelope)))<.008


def test_cached_cloud_audio_needs_no_credentials_or_new_spend(studio,tone_synth,monkeypatch):
    from app.scene_cache import digest
    voice={'provider':'elevenlabs','model':'eleven_v4','voice_id':'mocked-account-voice','language':'bn'}
    atomic_json(main.WORKSPACE/'voice_assignments.json',{'nabil':voice})
    story='দৃশ্য: আমবাগান\nনাবিল: হ্যালো।'
    data=studio.post('/api/production',json={'story':story,'renderer':'godot'}).json()
    sid=data['session_id'];line=data['segments'][0];tid=uuid.uuid4().hex
    directory=main.WORKSPACE/'production'/sid;wav=directory/'audio'/(tid+'.wav');cues=wav.with_suffix('.json')
    duration=tone_synth(line['synthesis_text'],wav,None)
    atomic_json(cues,{'mouthCues':[{'start':0.,'end':duration,'value':'X'}]})
    line['takes']=[{'take_id':tid,'status':'completed','voice':voice,'synthesis_text':line['synthesis_text'],'emotion':line['emotion'],
                    'line_revision':line['revision'],'audio_hash':digest(wav),'cues_hash':digest(cues),'duration_seconds':duration}]
    line['approved_take']=tid;data['ready']=True;atomic_json(directory/'session.json',data)
    monkeypatch.setattr('app.autopilot.configured',lambda provider:False)
    result=studio.post('/api/automatic/plan',json={'story':story,'music':False}).json()
    assert result['review']['ready'] and not result['paid'] and result['characters']==0
    assert result['cached_production_id']==sid
    monkeypatch.setattr('app.autopilot.configured',lambda provider:True)
    partial=studio.post('/api/automatic/plan',json={'story':story+'\nনাবিল: এসো।'}).json()
    assert partial['review']['ready'] and partial['cached_segments']==1 and partial['paid']
    assert partial['usage'][0]['cached'] and not partial['usage'][1]['cached']
    assert partial['characters']==partial['usage'][1]['characters']
