import json
import time
import uuid
import pytest
import app.main as main
from app.scene_cache import atomic_json,digest
from app.voices import voice_manager
from app.chat import preferences

SCRIPT='দৃশ্য: আমবাগান\n[নাবিল হাঁটে।]\nনাবিল: কে ওখানে?\nরায়ান: আমি এখানে।\n[SFX: rustling_leaves]'


def wait_chat(client,cid):
    deadline=time.monotonic()+90
    while time.monotonic()<deadline:
        data=client.get('/api/conversations/'+cid).json()
        if data['status'] in ('completed','failed','cancelled','needs_input','needs_payment'):return data
        time.sleep(.04)
    pytest.fail('Conversation generation timed out')


def test_chat_is_primary_and_settings_persist(studio):
    html=studio.get('/').text
    assert 'Generate Cartoon' in html and 'chat.js' in html
    for obsolete in ('voice-studio-panel','screenplay-panel','picker','auto-generate','app.js','production.js'):assert obsolete not in html
    assert 'আপনার বাংলা কার্টুনের গল্প লিখুন বা পেস্ট করুন...' in html
    saved={'format':'mini','voice_preference':'saved','music':False,'interpretation_mode':'rules','semantic_ai_approved':False}
    assert studio.put('/api/preferences',json=saved).status_code==200
    assert preferences(main.WORKSPACE).model_dump()==saved
    assert studio.get('/api/preferences').json()['format']=='mini'
    assert studio.put('/api/preferences',json={**saved,'api_key':'must-not-be-stored'}).status_code==422


def test_inline_unknown_assets_resume_original_prompt(studio,tone_synth,monkeypatch):
    calls=[]
    monkeypatch.setattr(voice_manager.vits,'synthesize',lambda text,*args:(calls.append(text) or tone_synth(text,*args)))
    story='দৃশ্য: পুরোনো দুর্গ\nমিতা: আমি এখানে।'
    created=studio.post('/api/conversations',json={'prompt':story}).json();cid=created['id']
    assert created['status']=='needs_input' and not calls
    questions=created['clarifications'];assert {q['kind'] for q in questions}=={'character','background'}
    character=next(q for q in questions if q['kind']=='character');background=next(q for q in questions if q['kind']=='background')
    assert 'nabil' in {r['value'] for r in character['options']}
    events=studio.get('/api/conversations/'+cid+'/events');assert events.headers['content-type'].startswith('text/event-stream') and 'event: update' in events.text
    resolved=studio.post('/api/conversations/'+cid+'/resolve',json={'revision':created['revision'],'character_mappings':{character['key']:'nabil'},'backgrounds':{background['key']:'mango_orchard_day'}})
    assert resolved.status_code==200,resolved.text
    done=wait_chat(studio,cid);assert done['status']=='completed',done
    assert done['prompt']==story and calls==['আমি এখানে।']
    assert studio.get(done['video_url']).content[:4]==b'\x00\x00\x00 '
    assert done['selected_assets']['characters']==['nabil']
    assert done['selected_assets']['backgrounds']==['mango_orchard_day']
    stored=json.loads((main.WORKSPACE/'conversations'/(cid+'.json')).read_text(encoding='utf-8'))
    assert stored['prompt']==story and stored['payload']['character_mappings'][character['key']]=='nabil'


def test_dialogue_only_generation_history_and_real_video(studio,tone_synth,monkeypatch):
    calls=[];monkeypatch.setattr(voice_manager.vits,'synthesize',lambda text,*args:(calls.append(text) or tone_synth(text,*args)))
    request_id=uuid.uuid4().hex
    created=studio.post('/api/conversations',json={'prompt':SCRIPT,'request_id':request_id}).json()
    assert studio.post('/api/conversations',json={'prompt':SCRIPT,'request_id':request_id}).json()['id']==request_id
    assert studio.post('/api/conversations',json={'prompt':SCRIPT+'\nনতুন গল্প।','request_id':request_id}).status_code==409
    done=wait_chat(studio,created['id']);assert done['status']=='completed',done
    assert calls==['কে ওখানে?','আমি এখানে।']
    job=main.JOBS[done['job_id']];assert job['validated'] and job['fps']==30 and (job['width'],job['height'])==(1080,1920)
    before=digest(main.OUTPUT/(done['job_id']+'.mp4'))
    history=studio.get('/api/conversations').json()
    assert len([r for r in history if r['job_id']==done['job_id']])==1
    reopened=studio.get('/api/conversations/'+created['id']).json();assert reopened['video_url']==done['video_url']
    assert digest(main.OUTPUT/(done['job_id']+'.mp4'))==before
    second=studio.post('/api/conversations',json={'prompt':SCRIPT}).json()
    repeated=wait_chat(studio,second['id']);assert repeated['status']=='completed',repeated
    assert studio.get('/api/conversations?limit=1').json()[0]['id']!=studio.get('/api/conversations?limit=1&offset=1').json()[0]['id']
    assert calls==['কে ওখানে?','আমি এখানে।']
    assert main.JOBS[repeated['job_id']]['approved_speech'][0]['voice']==job['approved_speech'][0]['voice']
    # Existing videos are indexed without copying or deleting them.
    (main.WORKSPACE/'conversations'/(created['id']+'.json')).rename(main.WORKSPACE/(created['id']+'.conversation-backup'))
    legacy=studio.get('/api/conversations').json()
    assert any(r['id']=='legacy-'+done['job_id'] for r in legacy)
    assert studio.get('/api/conversations/legacy-'+done['job_id']).json()['video_url']==done['video_url']
    assert digest(main.OUTPUT/(done['job_id']+'.mp4'))==before


def test_paid_speech_requires_inline_explicit_approval(studio,monkeypatch):
    voice={'provider':'elevenlabs','model':'eleven_v4','voice_id':'mock-accessible-voice','language':'bn'}
    atomic_json(main.WORKSPACE/'voice_assignments.json',{'nabil':voice})
    monkeypatch.setattr('app.autopilot.configured',lambda provider:True)
    submitted=[]
    monkeypatch.setitem(main.AUTOMATIC,'start',lambda payload:(submitted.append(payload) or {'automatic_id':uuid.uuid4().hex,'status':'queued'}))
    created=studio.post('/api/conversations',json={'prompt':'দৃশ্য: আমবাগান\nনাবিল: কে ওখানে?'}).json()
    assert created['status']=='needs_payment' and not submitted
    assert created['payment']['lines'][0]['text']=='কে ওখানে?'
    wrong=studio.post('/api/conversations/'+created['id']+'/resolve',json={'paid_approved':True,'approval_token':'stale'}).json()
    assert wrong['status']=='needs_payment' and not submitted
    approved=studio.post('/api/conversations/'+created['id']+'/resolve',json={'paid_approved':True,'approval_token':wrong['payment']['approval_token']}).json()
    assert approved['status']=='queued' and submitted[0].paid_approved


def test_unavailable_voice_gets_one_time_inline_choice(studio,tone_synth,monkeypatch):
    monkeypatch.setattr(voice_manager.vits,'synthesize',tone_synth)
    studio.put('/api/preferences',json={'format':'shorts','voice_preference':'elevenlabs','music':False})
    created=studio.post('/api/conversations',json={'prompt':'দৃশ্য: আমবাগান\nনাবিল: আমি এখানে।'}).json()
    assert created['status']=='needs_input'
    voice=next(q for q in created['clarifications'] if q['kind']=='voice')
    assert voice['key']=='nabil'
    selection={'speaker_id':'nabil','voice':{'provider':'vits','model':'bangladeshi-vits','voice_id':'default_bn','language':'bn'}}
    assert studio.post('/api/conversations/'+created['id']+'/resolve',json={'voices':[selection]}).status_code==422
    selection['accept_alternative']=True
    assert studio.post('/api/conversations/'+created['id']+'/resolve',json={'voices':[selection]}).status_code==200
    done=wait_chat(studio,created['id']);assert done['status']=='completed',done
    assert voice_manager.settings(main.WORKSPACE)['nabil']['provider']=='vits'
    again=studio.post('/api/conversations',json={'prompt':'দৃশ্য: আমবাগান\nনাবিল: আমি এখানে।'}).json()
    assert again['status']!='needs_input'
    assert wait_chat(studio,again['id'])['status']=='completed'


def test_unknown_instruction_never_becomes_speech(studio,monkeypatch):
    created=studio.post('/api/conversations',json={'prompt':'দৃশ্য: আমবাগান\n[নাবিল আকাশে উড়ে যায়।]'}).json()
    assert created['status']=='needs_input'
    q=next(q for q in created['clarifications'] if q['kind']=='instruction')
    assert q['source_text']=='[নাবিল আকাশে উড়ে যায়।]'
    assert studio.post('/api/conversations/'+created['id']+'/resolve',json={'revision':0,'corrections':{}}).status_code==409
    assert studio.post('/api/conversations/'+created['id']+'/cancel',json={}).json()['status']=='cancelled'
    assert studio.get('/api/conversations/../../secret').status_code==404


def test_approved_category_default_becomes_stable_character_identity(studio):
    from app.voices.assignment import resolve_voices
    from app.voices.studio import registry
    from app.engines.story_parser import parse_story
    voice={'provider':'vits','model':'bangladeshi-vits','voice_id':'default_bn','language':'bn'}
    config=registry(main.WORKSPACE).model_dump()
    config['voice_categories']['child_male']=[{'category':'child_male','voice':voice,'label':'Accepted offline alternative','bengali_reviewed':True,'accept_alternative':True}]
    atomic_json(main.WORKSPACE/'voice_studio.json',config)
    result,issues=resolve_voices(main.LIBRARY,parse_story('নাবিল: কে ওখানে?')['segments'])
    assert not issues and result['nabil']==voice
    assert voice_manager.settings(main.WORKSPACE)['nabil']==voice
    config['voice_categories']['child_male']=[];atomic_json(main.WORKSPACE/'voice_studio.json',config)
    assert resolve_voices(main.LIBRARY,parse_story('Nabil: আবার এলাম।')['segments'])[0]['nabil']==voice


def test_failed_render_resumes_without_regenerating_dialogue(studio,tone_synth,monkeypatch):
    calls=[];monkeypatch.setattr(voice_manager.vits,'synthesize',lambda text,*args:(calls.append(text) or tone_synth(text,*args)))
    export=main.export_video;attempts=[]
    def fail_once(*args,**kwargs):
        attempts.append(True)
        if len(attempts)==1:raise RuntimeError('private render detail D:/hidden/path must remain in backend logs')
        return export(*args,**kwargs)
    monkeypatch.setattr(main,'export_video',fail_once)
    created=studio.post('/api/conversations',json={'prompt':SCRIPT}).json();failed=wait_chat(studio,created['id'])
    assert failed['status']=='failed' and 'D:/' not in failed['message'] and 'private render' not in failed['message']
    assert len(calls)==2
    retry=studio.post('/api/conversations/'+created['id']+'/retry',json={});assert retry.status_code==200,retry.text
    assert retry.json()['job_id']==failed['job_id']
    done=wait_chat(studio,created['id']);assert done['status']=='completed',done
    assert len(calls)==2 and len(attempts)==2
