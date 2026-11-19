import json
import subprocess
import sys
import pytest
from app.voices import four_voices as four
from app.voices.assignment import resolve_voices
from app.voices.base import VoiceError
from test_v9 import tone


@pytest.fixture
def selected(monkeypatch,tmp_path):
    monkeypatch.setattr(four,'CONFIG',tmp_path/'references/four.json')
    before=four.configuration()['character_presets']
    data=four.select_official_evaluation()
    assert data['character_presets']==before
    return data


def test_exact_official_outputs_persist_without_permission_claims(selected):
    assert selected['mode']=='evaluation'
    assert selected['official_evaluation_selections']=={'male':'007','female':'006','child_male':'002','child_female':'005'}
    for category,sid in four.OFFICIAL_SELECTIONS.items():
        row,path=four.reference(category)
        assert path.is_file() and row['official_sample_id']==sid
        assert row['source_kind']=='official_generated_demo_output'
        assert row['approved'] is False and row['commercial_permission_verified'] is False
        assert row['authorization'] is None
    code='import sys,json;from pathlib import Path;from app.voices import four_voices as f;f.CONFIG=Path(sys.argv[1]);print(json.dumps({c:f.reference(c)[0]["official_sample_id"] for c in f.CATEGORIES}))'
    actual=json.loads(subprocess.check_output([sys.executable,'-c',code,str(four.CONFIG)],text=True))
    assert actual==four.OFFICIAL_SELECTIONS


def test_production_cannot_use_evaluation_outputs(selected):
    selections={c:row['reference_id'] for c,row in selected['base_voices'].items()}
    with pytest.raises(VoiceError,match='production'):four.save_four(selections,'production')
    assert four.configuration()['mode']=='evaluation'


def test_licensed_replacement_retains_distribution_and_variations(selected):
    rid=four.upload(tone(314),'Synthetic licensed test fixture','Test-owned synthetic signal; no real voice permission asserted',True)
    choices={c:row['reference_id'] for c,row in selected['base_voices'].items()};choices['male']=rid
    changed=four.save_four(choices,'evaluation')
    assert changed['character_presets']==selected['character_presets']
    assert changed['official_evaluation_selections']==four.OFFICIAL_SELECTIONS
    assert four.reference('male')[0]['approved'] is True
    assert four.category_for('rahat')==four.category_for('arif')==four.category_for('sami')=='male'


def test_all_ten_characters_use_selected_category_without_questions(studio,selected,monkeypatch):
    import app.main as main
    monkeypatch.setenv('DEFAULT_TTS_PROVIDER','chatterbox_bangla')
    characters=list(four.PITCH)[:10]
    identities,issues=resolve_voices(main.LIBRARY,[{'speaker':c,'speaker_name':c} for c in characters],'chatterbox_bangla')
    assert not issues
    for cid,voice in identities.items():
        assert voice['official_sample_id']==four.OFFICIAL_SELECTIONS[four.category_for(cid)]
        assert voice['usage_mode']=='evaluation'
    monkeypatch.setattr(main.executor,'submit',lambda *args:None)
    response=studio.post('/api/conversations',json={'prompt':'দৃশ্য: আমবাগান\nনাবিল: এসো।\nরায়ান: দাঁড়া।\nঅনিকা: আচ্ছা।'}).json()
    assert response['status']=='queued' and not response['clarifications'] and response['evaluation_only']


def test_settings_auditions_evaluation_but_will_not_approve_production(studio,selected):
    data=studio.get('/api/default-voices').json()
    assert data['mode']=='evaluation' and set(data['status'].values())=={'evaluation_only'}
    for choice in data['base_voices'].values():
        assert studio.get('/api/default-voices/references/'+choice['reference_id']+'/audio').status_code==200
    response=studio.put('/api/default-voices',json={'mode':'production','base_voices':{c:v['reference_id'] for c,v in data['base_voices'].items()}})
    assert response.status_code==422


def test_atomic_progress_save_retries_transient_windows_file_lock(tmp_path,monkeypatch):
    import app.scene_cache as cache
    original=cache.os.replace;attempts=[]
    def locked(source,target):
        attempts.append(source)
        if len(attempts)<4:raise PermissionError('Simulated Windows file sharing violation')
        return original(source,target)
    monkeypatch.setattr(cache.os,'replace',locked)
    path=tmp_path/'progress.json';path.write_text('{"old":true}',encoding='utf-8')
    cache.atomic_json(path,{'new':'বাংলা'})
    assert json.loads(path.read_text(encoding='utf-8'))=={'new':'বাংলা'}
    assert len(attempts)==4 and not list(tmp_path.glob('*.tmp'))


def test_old_missing_category_prompt_clears_without_starting_generation(studio,selected,monkeypatch):
    import app.main as main
    from app.scene_cache import atomic_json
    monkeypatch.setenv('DEFAULT_TTS_PROVIDER','chatterbox_bangla');calls=[]
    monkeypatch.setattr(main.executor,'submit',lambda *args:calls.append(args))
    created=studio.post('/api/conversations',json={'prompt':'দৃশ্য: আমবাগান\nনাবিল: এসো।'}).json()
    path=main.WORKSPACE/'conversations'/(created['id']+'.json')
    saved=json.loads(path.read_text(encoding='utf-8'));saved['status']='needs_input';saved.pop('automatic_id',None)
    saved['clarifications']=[{'kind':'category_reference','key':'category-child_male','question':'Old missing voice message'}];atomic_json(path,saved)
    before=len(calls);current=studio.get('/api/conversations/'+created['id']).json()
    assert current['status']=='waiting' and current['clarifications']==[] and len(calls)==before
