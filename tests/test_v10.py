import json
import uuid
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.maintenance import maintenance_router
from app.scene_cache import atomic_json,digest
import app.main as main
from test_chat import wait_chat,SCRIPT

def test_cleanup_only_terminal_owned_intermediates(tmp_path):
    app=FastAPI();app.include_router(maintenance_router(lambda:tmp_path))
    expected=[]
    for status in ('failed','rendering'):
        jid=uuid.uuid4().hex;job=tmp_path/jid;(job/'render').mkdir(parents=True)
        atomic_json(job/'job.json',{'job_id':jid,'status':status})
        for name in ('render_001.avi','render_notes.avi','scene.mp4','dialogue.wav','scene.json'):
            p=job/'render'/name;p.write_bytes(b'preserve');expected.append(p)
    removed=expected.pop(0)
    with TestClient(app) as client:
        assert client.get('/api/storage/disposable').json()=={'files':1,'bytes':8}
        assert client.post('/api/storage/disposable').json()['removed_files']==1
        assert not removed.exists() and all(p.read_bytes()==b'preserve' for p in expected)
        assert client.post('/api/storage/disposable').json()['removed_files']==0

def test_regeneration_new_history_idempotent_original_unchanged(studio,tone_synth,monkeypatch):
    monkeypatch.setattr('app.voices.voice_manager.vits.synthesize',tone_synth)
    first=studio.post('/api/conversations',json={'prompt':SCRIPT}).json()
    done=wait_chat(studio,first['id']);assert done['status']=='completed',done
    old=main.OUTPUT/(done['job_id']+'.mp4');sha=digest(old)
    rid=uuid.uuid4().hex;body={'prompt':SCRIPT,'request_id':rid};url=f"/api/conversations/{first['id']}/regenerate"
    new=studio.post(url,json=body);assert new.status_code==201,new.text
    assert studio.post(url,json=body).json()['id']==rid
    repeated=wait_chat(studio,rid);assert repeated['status']=='completed',repeated
    assert repeated['job_id']!=done['job_id'] and digest(old)==sha
    data=json.loads((main.WORKSPACE/'conversations'/(rid+'.json')).read_text(encoding='utf-8'))
    assert data['payload']['paid_approved'] is False and data['payload']['approval_token'] is None
    assert data['regenerated_from']==first['id']

def test_missing_optional_sound_skipped_with_diagnostic(tmp_path):
    from app.audio.sound_director import SoundDirector
    atomic_json(tmp_path/'library.json',{'sounds':{'wind':{'file':'missing.wav','license':'CC0'}}})
    director=SoundDirector(tmp_path)
    scene={'source_scene_id':'scene_001','start':0,'end':1,'background_id':'mango_orchard_day','kind':'hold','actors':{}}
    assert director.plan([scene],True)==[]
    assert 'Missing or invalid sound' in director.diagnostics[0]
    absent=SoundDirector(tmp_path/'absent')
    assert absent.plan([scene],True)==[] and absent.diagnostics

def test_queued_cancel_does_not_terminate_another_worker(studio,monkeypatch):
    from app.voices.chatterbox_bangla import ENGINE
    calls=[]
    monkeypatch.setattr(main.executor,'submit',lambda *args:None)
    monkeypatch.setattr(ENGINE,'cancel_inference',lambda:calls.append('terminate'))
    result=studio.post('/api/automatic/generate',json={'story':'দৃশ্য: আমবাগান\nনাবিল: এখানে এসো।'}).json()
    stopped=studio.post('/api/automatic/'+result['automatic_id']+'/cancel').json()
    assert stopped['status']=='cancelled' and stopped['cancel_requested'] and not calls

def test_worker_cancel_terminates_only_live_process():
    from app.voices.chatterbox_bangla import LocalChatterbox
    class Process:
        def __init__(self):self.dead=False
        def poll(self):return 0 if self.dead else None
        def terminate(self):self.dead=True
    engine=LocalChatterbox();engine.cancel_inference();engine.process=Process();engine.cancel_inference()
    assert engine.process.dead

def test_unknown_speaker_chatterbox_requests_assets_before_voice(studio,monkeypatch):
    monkeypatch.setenv('DEFAULT_TTS_PROVIDER','chatterbox_bangla')
    from app.voices import four_voices
    from app.voices.assignment import resolve_voices
    monkeypatch.setattr(four_voices,'reference',lambda *args:(_ for _ in ()).throw(AssertionError('Unresolved names must not request a voice')))
    identities,issues=resolve_voices(main.LIBRARY,[{'speaker':'unresolved','speaker_name':'মিতা'}])
    assert identities=={'unresolved':None} and not issues
    created=studio.post('/api/conversations',json={'prompt':'দৃশ্য: অজানা দুর্গ\nমিতা: এখানে এসো।'}).json()
    assert created['status']=='needs_input',created
    assert {q['kind'] for q in created['clarifications']}=={'character','background'}
