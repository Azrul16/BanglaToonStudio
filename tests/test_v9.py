import base64
import io
import json
import math
import wave
from array import array
from pathlib import Path
import pytest
from app.voices import four_voices as four
from app.voices import variation
from app.voices.base import VoiceIdentity,VoiceError
from app.voices.assignment import resolve_voices
from app.scene_cache import digest


def tone(frequency=150):
    out=io.BytesIO()
    with wave.open(out,'wb') as wav:
        wav.setparams((1,2,24000,0,'NONE','not compressed'))
        wav.writeframes(array('h',[int(5000*math.sin(i*2*math.pi*frequency/24000)) for i in range(96000)]).tobytes())
    return out.getvalue()


@pytest.fixture
def four_config(monkeypatch,tmp_path):
    monkeypatch.setattr(four,'CONFIG',tmp_path/'references/four.json')
    monkeypatch.setattr(variation,'CACHE_ROOT',tmp_path/'cache')
    return tmp_path


def configure():
    references={c:four.upload(tone(150+i*30),c,'Synthetic test signal owned by this test, not a production human voice',True) for i,c in enumerate(four.CATEGORIES)}
    four.save_four(references);return references


def test_four_persist_and_all_characters_map(four_config):
    refs=configure();data=four.configuration()
    assert data['schema_version']==2 and len(data['base_voices'])==4
    for cid,category in four.CHARACTER_CATEGORIES.items():
        assert four.category_for(cid)==category
        assert four.reference(category)[0]['id']==refs[category]
        assert cid in data['character_presets']
    assert json.loads(four.CONFIG.read_text(encoding='utf-8'))==four.configuration()
    import subprocess,sys
    output=subprocess.check_output([sys.executable,'-c','import sys,json;from pathlib import Path;from app.voices import four_voices as f;f.CONFIG=Path(sys.argv[1]);print(json.dumps(f.configuration()))',str(four.CONFIG)],text=True)
    assert json.loads(output)==data  # Fresh process reads the exact saved references/presets.


def test_only_required_categories_and_grouped_messages(studio,four_config,monkeypatch):
    import app.main as main
    monkeypatch.setenv('DEFAULT_TTS_PROVIDER','chatterbox_bangla')
    segments=[{'speaker':cid,'speaker_name':cid} for cid in ('nabil','rayan','fahim','anika')]
    identities,issues=resolve_voices(main.LIBRARY,segments)
    assert len(issues)==2 and {r['category'] for r in issues}=={'child_male','child_female'}
    assert all('speaker_id' not in i for i in issues)
    refs=configure();identities,issues=resolve_voices(main.LIBRARY,segments)
    assert not issues
    assert identities['nabil']['reference_audio_hash']==identities['rayan']['reference_audio_hash']
    assert identities['nabil']['variation']!=identities['rayan']['variation']
    data=four.configuration();data['base_voices']['male']=None;data['base_voices']['female']=None
    from app.scene_cache import atomic_json
    atomic_json(four.CONFIG,data)
    assert not resolve_voices(main.LIBRARY,segments)[1]


def test_four_voice_api_and_missing_category_chat(studio,four_config,monkeypatch):
    monkeypatch.setenv('DEFAULT_TTS_PROVIDER','chatterbox_bangla')
    response=studio.post('/api/conversations',json={'prompt':'দৃশ্য: আমবাগান\nনাবিল: এসো।\nরায়ান: দাঁড়া।\nঅনিকা: আচ্ছা।'}).json()
    assert len(response['clarifications'])==2
    assert {q['kind'] for q in response['clarifications']}=={'category_reference'}
    refs=configure()
    assert studio.put('/api/default-voices',json={'base_voices':refs}).status_code==200
    assert studio.put('/api/default-voices',json={'base_voices':{'male':'fake'}}).status_code==422
    assert studio.get('/api/default-voices').json()['status']==dict.fromkeys(four.CATEGORIES,'configured')


def test_old_prompts_migrate_and_four_saved_voices_need_no_character_setup(studio,four_config,monkeypatch):
    import app.main as main
    from app.scene_cache import atomic_json
    monkeypatch.setenv('DEFAULT_TTS_PROVIDER','chatterbox_bangla')
    story='দৃশ্য: আমবাগান\nনাবিল: এসো।\nরায়ান: দাঁড়া।\nঅনিকা: আচ্ছা।'
    created=studio.post('/api/conversations',json={'prompt':story}).json()
    path=main.WORKSPACE/'conversations'/(created['id']+'.json');saved=json.loads(path.read_text(encoding='utf-8'))
    saved['clarifications']=[{'kind':'reference','key':cid,'source':cid,'question':'Old character reference question'} for cid in ('nabil','rayan','anika')];atomic_json(path,saved)
    migrated=studio.get('/api/conversations/'+created['id']).json()
    assert len(migrated['clarifications'])==2 and {q['kind'] for q in migrated['clarifications']}=={'category_reference'}
    assert migrated['prompt']==story and migrated['status']=='needs_input'
    configure();monkeypatch.setattr(main.executor,'submit',lambda *args:None)
    ready=studio.post('/api/conversations',json={'prompt':story}).json()
    assert ready['status']=='queued' and not ready['clarifications']
    assert studio.post('/api/voice-references/nabil',json={'wav_base64':base64.b64encode(tone()).decode(),'authorization':'Synthetic test permission only','consent':True}).status_code==410


def test_permissions_bad_audio_and_reset(four_config):
    with pytest.raises(VoiceError):four.upload(tone(),'tone','test permission declaration has enough characters',False)
    with pytest.raises(VoiceError):four.upload(b'not wave','x','test permission declaration has enough characters',True)
    configure();four.reset_variations()
    assert all(p['pitch_semitones']==0 for p in four.configuration()['character_presets'].values())


def test_real_rubberband_preserves_frames_and_cache_isolates(four_config,tmp_path):
    source=tmp_path/'source.wav';source.write_bytes(tone())
    engine=variation.VoiceVariationEngine()
    nabil=engine.process(source,tmp_path/'nabil.wav','nabil',{'pitch_semitones':.7,'formant':'preserved'})
    rayan=engine.process(source,tmp_path/'rayan.wav','rayan',{'pitch_semitones':-.5,'formant':'preserved'})
    assert nabil['final']['frames']==nabil['original']['frames']
    assert rayan['key']!=nabil['key']
    assert engine.process(source,tmp_path/'repeat.wav','nabil',{'pitch_semitones':.7,'formant':'preserved'})['cache_hit']
    assert not nabil['transformation_applied'] and not rayan['transformation_applied']
    assert nabil['sha256']==rayan['sha256']==digest(source)


def test_two_caches_do_not_repeat_tts_for_variation_change(four_config,tmp_path):
    refs=configure();row,path=four.reference('child_male')
    class Engine:
        calls=0;result={}
        def generate(self,text,target,reference,settings,device='auto'):
            self.calls+=1;target.write_bytes(tone());return {'device':'test_double','sample_rate':24000}
    engine=Engine()
    identity=VoiceIdentity(provider='chatterbox_bangla',voice_id='nabil',reference_audio_hash=row['sha256'],variation={'pitch_semitones':.7,'formant':'preserved'})
    variation.synthesize_cached('পরীক্ষা',identity,tmp_path/'a.wav',path,'neutral',engine,four.SETTINGS)
    identity.variation={'pitch_semitones':0.,'formant':'preserved'}
    variation.synthesize_cached('পরীক্ষা',identity,tmp_path/'b.wav',path,'neutral',engine,four.SETTINGS)
    assert engine.calls==1 and engine.result['original_cache_hit']
    assert (tmp_path/'a.original.wav').read_bytes()==(tmp_path/'b.original.wav').read_bytes()


def test_migration_preserves_files_and_refuses_ambiguous_category(four_config):
    from app.scene_cache import atomic_json,digest
    parent=four.CONFIG.parent;parent.mkdir(parents=True)
    children={}
    for cid,freq in [('nabil',180),('rayan',200),('anika',240)]:
        path=parent/(cid+'.wav');path.write_bytes(tone(freq));children[cid]={'reference_audio':path.name,'reference_audio_hash':digest(path),'authorization':'Synthetic test recording owned for testing only','name':cid}
    atomic_json(parent/'profiles.json',{'schema_version':1,'characters':children})
    config=four.configuration()
    assert config['base_voices']['child_male'] is None and len(config['migration_conflicts']['child_male'])==2
    assert config['base_voices']['child_female']
    assert (parent/'migration-v9-backup/profiles.json').exists()
    assert all((parent/(cid+'.wav')).is_file() for cid in children)


def test_production_lipsync_reads_processed_audio(studio,four_config,monkeypatch):
    import app.main as main
    import app.production as production
    from app.voices.chatterbox_bangla import ENGINE
    from app.scene_cache import digest
    from test_production import wait_take
    configure();monkeypatch.setenv('DEFAULT_TTS_PROVIDER','chatterbox_bangla')
    submitted=[];cue_hashes=[]
    def generate(text,target,reference,settings,device='auto'):
        submitted.append(text);target.write_bytes(tone());return {'device':'test_double','sample_rate':24000}
    original_cues=production.generate_mouth_cues
    def cues(source,target,mode):
        cue_hashes.append(digest(source));return original_cues(source,target,mode)
    monkeypatch.setattr(ENGINE,'generate',generate);monkeypatch.setattr(production,'generate_mouth_cues',cues)
    session=studio.post('/api/production',json={'story':'দৃশ্য: আমবাগান\n[নাবিল পেছনে তাকায়।]\nনাবিল: এসো।\nরায়ান: এসো।','renderer':'godot'}).json()
    sid=session['session_id']
    for row in session['segments']:assert studio.post(f'/api/production/{sid}/segments/{row["id"]}/takes',json={}).status_code==202
    complete=wait_take(studio,sid)
    takes=[s['takes'][0] for s in complete['segments']]
    assert all(t['status']=='completed' for t in takes),takes
    assert submitted==['এসো।']  # One shared original take, separate final character processing.
    assert cue_hashes==[t['audio_hash'] for t in takes]
    assert takes[0]['audio_hash']==takes[1]['audio_hash']  # Neutral repair policy preserves pronunciation over pitch distinctions.
