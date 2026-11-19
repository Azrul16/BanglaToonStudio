import json
import shutil
from pathlib import Path
import pytest
from PIL import Image
import app.main as main
from app.library import AssetLibrary
from app.review import ReviewInput,analyze
from conftest import wait

KNOWN='নাবিল আর রায়ান আমবাগানে গেল।\n\nনাবিল: এই! তোরা কিছু শুনলি?\nরায়ান: মনে হচ্ছে মাটির নিচে কেউ আছে!'


def scene(background='railway_station_night',end=1):
    return [{'scene_id':'scene_001','start_segment':0,'end_segment':end,'background_id':background,'location_text':'Chosen stage'}]


def test_discovery_readiness_and_safe_actual_previews(studio):
    characters=studio.get('/api/characters').json(); backgrounds=studio.get('/api/backgrounds').json()
    assert len(characters)==10 and len(backgrounds)==10
    assert {r['id'] for r in characters if r['status']=='ready'}=={'rahat','nabil','rayan','fahim','anika','maliha'}
    assert next(r for r in characters if r['id']=='arif')['status']=='reference_only'
    assert all(r['status']=='ready' for r in backgrounds)
    for row in (characters[0],backgrounds[0]):
        response=studio.get(row['preview_url']); assert response.status_code==200
        import io
        with Image.open(io.BytesIO(response.content)) as image: assert image.size==(240,300)
    assert studio.get('/api/assets/characters/not-real/preview').status_code==404
    assert studio.get('/api/characters',params={'search':'Nabil','age_group':'child','status':'ready'}).json()[0]['id']=='nabil'
    assert {b['time_of_day'] for b in studio.get('/api/backgrounds',params={'time_of_day':'dusk'}).json()}=={'dusk'}


def test_known_characters_and_orchard_need_no_selection(studio):
    response=studio.post('/api/analyze',json={'story':KNOWN})
    assert response.status_code==200,response.text
    data=response.json(); assert data['ready'],data
    assert {c['character_id'] for c in data['characters']}=={'nabil','rayan'}
    assert len(data['spoken_segments'])==2
    assert data['scenes'][0]['background_id']=='mango_orchard_day'
    assert data['review_token'] and data['estimated_duration']['is_estimate']


def test_unknown_speaker_has_real_candidates_and_manual_resolution(studio):
    story='অচেনা ছেলে: তোমরা এখানে কী করছ?'
    data=studio.post('/api/analyze',json={'story':story}).json()
    assert not data['ready']
    unknown=data['characters'][0]
    assert unknown['status']=='unresolved' and unknown['character_id'] is None
    assert set(unknown['candidates'])=={'nabil','rayan','fahim'}
    resolved=studio.post('/api/resolve',json={'story':story,'character_mappings':{'অচেনা ছেলে':'fahim'},'scenes':scene()}).json()
    assert resolved['ready'],resolved
    assert resolved['segments'][0]['speaker']=='fahim' and not resolved['segments'][0]['off_screen']


@pytest.mark.parametrize('role,kind',[('unknown_voice','dialogue'),('narrator','narration')])
def test_explicit_offscreen_and_narration_roles(studio,role,kind):
    data=studio.post('/api/resolve',json={'story':'কেউ: এখানে এসো।','character_mappings':{'কেউ':role},'scenes':scene()}).json()
    assert data['ready'] and data['segments'][0]['off_screen']
    assert data['segments'][0]['kind']==kind


def test_unmatched_castle_is_unresolved_then_selected(studio):
    story='তারা একটি পুরোনো দুর্গে পৌঁছাল।'
    auto=studio.post('/api/analyze',json={'story':story}).json()
    assert not auto['ready'] and auto['scenes'][0]['background_id'] is None
    assert 'দুর্গ' in auto['scenes'][0]['location_text']
    manual=studio.post('/api/resolve',json={'story':story,'scenes':scene('village_home_evening')}).json()
    assert manual['ready'] and manual['scenes'][0]['background_id']=='village_home_evening'


@pytest.mark.parametrize('text,expected',[
 ('নাবিল কুয়াশাচ্ছন্ন আমবাগানে গেল।','mango_orchard_misty'),
 ('নাবিল সন্ধ্যায় বাজারে গেল।','village_market_dusk'),
 ('গভীর রাতে রাহাত রেলস্টেশনে দাঁড়িয়ে ছিল।','railway_station_night'),
 ('নাবিল স্কুলে গেল।','school_courtyard_day')])
def test_background_keywords_inflections_and_time(studio,text,expected):
    data=studio.post('/api/analyze',json={'story':text}).json()
    assert data['ready'],data
    assert data['scenes'][0]['background_id']==expected


def test_multiple_locations_are_ambiguous_not_arbitrarily_selected(studio):
    data=studio.post('/api/analyze',json={'story':'নাবিল আমবাগান থেকে বাজারে গেল।'}).json()
    assert not data['ready'] and data['scenes'][0]['status']=='ambiguous'
    assert data['scenes'][0]['background_id'] is None


def test_automatic_different_backgrounds_and_manual_boundaries(studio):
    story='নাবিল আমবাগানে গেল।\nনাবিল: এসো!\nসন্ধ্যায় রায়ান বাজারে গেল।\nরায়ান: চলুন।'
    data=studio.post('/api/analyze',json={'story':story}).json()
    assert data['ready'],data
    assert [s['background_id'] for s in data['scenes']]==['mango_orchard_day','village_market_dusk']
    assert [(s['start_segment'],s['end_segment']) for s in data['scenes']]==[(0,2),(2,4)]
    bad=studio.post('/api/resolve',json={'story':story,'scenes':scene(end=2)})
    assert bad.status_code==422 and 'issues' in bad.json()['detail']


def test_project_mapping_does_not_leak_to_future_stories(studio):
    saved=studio.post('/api/mappings',json={'asset_type':'character','alias':'আমার বন্ধু','asset_id':'fahim'}).json()
    assert not saved['saved'] and saved['scope']=='project'
    assert not (main.LIBRARY.storage/'user_mappings.json').exists()
    data=studio.post('/api/analyze',json={'story':'আমার বন্ধু: কে আছ?'}).json()
    assert data['characters'][0]['status']=='unresolved'


def test_remembered_character_and_background_survive_new_library(studio,monkeypatch):
    for kind,alias,cid in [('character','আমার বন্ধু','fahim'),('background','পুরোনো দুর্গ','village_courtyard_day')]:
        response=studio.post('/api/mappings',json={'asset_type':kind,'alias':alias,'asset_id':cid,'scope':'remember'})
        assert response.status_code==200 and response.json()['saved']
    old=main.LIBRARY
    monkeypatch.setattr(main,'LIBRARY',AssetLibrary(old.root,old.storage))
    data=studio.post('/api/analyze',json={'story':'তারা পুরোনো দুর্গে পৌঁছাল।\nআমার বন্ধু: কে আছ?'}).json()
    assert data['ready'],data
    assert data['segments'][1]['speaker']=='fahim'
    assert data['scenes'][0]['background_id']=='village_courtyard_day'
    assert not (old.storage/'user_mappings.tmp').exists()


def test_alias_conflict_and_generic_warning_require_confirmation(studio):
    payload={'asset_type':'character','alias':'নাবিল','asset_id':'rayan','scope':'remember'}
    assert studio.post('/api/mappings',json=payload).status_code==409
    assert studio.post('/api/mappings',json={**payload,'confirm_conflict':True}).status_code==200
    generic={'asset_type':'character','alias':'একজন ছেলে','asset_id':'fahim','scope':'remember'}
    assert studio.post('/api/mappings',json=generic).status_code==409
    assert studio.post('/api/mappings',json={**generic,'confirm_generic':True}).status_code==200
    assert studio.post('/api/mappings',json={**payload,'alias':'nabil','confirm_conflict':True}).status_code==422


def test_incomplete_assets_and_bad_mappings_never_pass_preflight(studio):
    assert studio.post('/api/mappings',json={'asset_type':'character','alias':'বন্ধু','asset_id':'arif','scope':'remember'}).status_code==422
    data=studio.post('/api/preflight',json={'story':'অচেনা ছেলে: কে আছ?'}).json()
    assert not data['ready'] and {i['type'] for i in data['issues']}=={'character','background'}
    response=studio.post('/api/generate',json={'story':'অচেনা ছেলে: কে আছ?'})
    assert response.status_code==422 and not main.JOBS
    path=main.LIBRARY.storage/'user_mappings.json'; path.write_text('{broken',encoding='utf-8')
    response=studio.post('/api/mappings',json={'asset_type':'character','alias':'বন্ধু','asset_id':'fahim','scope':'remember'})
    assert response.status_code==422 and path.read_text()=='{broken'


def test_preflight_reports_missing_tools_without_starting_work(studio,monkeypatch):
    import app.screenplay_review as review
    monkeypatch.setattr(review,'ffmpeg_binary',lambda:None)
    data=studio.post('/api/preflight',json={'story':KNOWN}).json()
    assert not data['ready'] and any(i['type']=='tool' for i in data['issues'])
    assert studio.post('/api/generate',json={'story':KNOWN}).status_code==422
    assert not main.JOBS


@pytest.fixture
def copied_library(tmp_path,monkeypatch):
    root=tmp_path/'assets'
    for cid in ('nabil','rayan'):
        shutil.copytree(main.ROOT/'assets/characters'/cid,root/'characters'/cid)
    shutil.copytree(main.ROOT/'assets/backgrounds/mango_orchard_day',root/'backgrounds/mango_orchard_day')
    library=AssetLibrary(root,tmp_path/'storage')
    monkeypatch.setattr(main,'LIBRARY',library)
    return library


def test_ambiguous_aliases_and_exact_names(copied_library):
    for cid in ('nabil','rayan'):
        path=copied_library.root/'characters'/cid/'character.json'
        meta=json.loads(path.read_text(encoding='utf-8'));meta['aliases']=['বন্ধু','রায়'] if cid=='nabil' else ['বন্ধু']
        path.write_text(json.dumps(meta,ensure_ascii=False),encoding='utf-8')
    data,_,_=analyze(copied_library,ReviewInput(story='বন্ধু: হ্যালো!'))
    assert data['characters'][0]['status']=='ambiguous'
    assert set(data['characters'][0]['candidates'])=={'nabil','rayan'}
    rayan,_,_=analyze(copied_library,ReviewInput(story='রায়ান: হ্যালো!'))
    assert rayan['characters'][0]['character_id']=='rayan'


def test_refresh_finds_new_character_and_detects_incomplete_rig(studio,copied_library):
    assert len(studio.get('/api/characters').json())==2
    folder=copied_library.root/'characters/new_child'
    shutil.copytree(copied_library.root/'characters/nabil',folder)
    meta=json.loads((folder/'character.json').read_text(encoding='utf-8'))
    meta.update(character_id='new_child',name_bn='লীলা',name_en='Leela')
    (folder/'character.json').write_text(json.dumps(meta,ensure_ascii=False),encoding='utf-8')
    assert studio.post('/api/assets/refresh',json={}).json()['characters']==3
    data=studio.post('/api/analyze',json={'story':'লীলা: এসো!'}).json()
    assert data['characters'][0]['character_id']=='new_child'
    (folder/'body.png').unlink()
    assert next(c for c in studio.get('/api/characters').json() if c['id']=='new_child')['status']=='incomplete'


def test_generate_uses_approved_characters_and_two_backgrounds(studio,tone_synth):
    story='তারা একটি পুরোনো দুর্গে পৌঁছাল।\nঅচেনা ছেলে: এখানে এসো।\nনাবিল: আমি আসছি।'
    choices={'story':story,'character_mappings':{'অচেনা ছেলে':'fahim'},'scenes':[
       {'scene_id':'scene_001','start_segment':0,'end_segment':2,'background_id':'school_courtyard_day','location_text':'Castle chosen as school stage'},
       {'scene_id':'scene_002','start_segment':2,'end_segment':3,'background_id':'village_home_evening','location_text':'Second selected stage'}]}
    approved=studio.post('/api/preflight',json=choices).json(); assert approved['ready'],approved
    assert studio.post('/api/generate',json={**choices,'review_token':'stale'}).status_code==409
    assert not main.JOBS
    created=studio.post('/api/generate',json={**choices,'review_token':approved['review_token']})
    assert created.status_code==202,created.text
    job=wait(studio,created.json()['job_id']);assert job['status']=='completed',job
    assert {c['character_id'] for c in job['asset_references']['characters']}=={'fahim','nabil'}
    assert {b['background_id'] for b in job['asset_references']['backgrounds']}=={'school_courtyard_day','village_home_evening'}
    timeline=studio.get(job['timeline_url']).json()
    speech=[s for s in timeline['scenes'] if s['kind']=='speech']
    assert [s['background_id'] for s in speech]==['school_courtyard_day','village_home_evening']
    assert speech[0]['speaker']=='fahim'
    assert len(job['clips'])==2
    assert (main.WORKSPACE/job['job_id']/'asset_snapshot/characters/fahim/body.png').is_file()


def test_changed_queued_asset_fails_before_speech(studio,copied_library,monkeypatch):
    calls=[]
    monkeypatch.setattr(main.executor,'submit',lambda *args:None)
    monkeypatch.setattr(main,'synthesize',lambda *args:calls.append(args))
    story='নাবিল আমবাগানে গেল।\nনাবিল: এসো!'
    created=studio.post('/api/generate',json={'story':story})
    assert created.status_code==202,created.text
    path=copied_library.root/'characters/nabil/body.png';path.write_bytes(path.read_bytes()+b'changed')
    main.run_job(created.json()['job_id'])
    job=studio.get('/api/jobs/'+created.json()['job_id']).json()
    assert job['status']=='failed' and 'changed while queued' in job['error']
    assert not calls


def test_snapshot_preserves_approved_bytes_after_library_changes(copied_library,tmp_path):
    from app.review import snapshot_plan
    from app.assets import load_character
    from app.engines.animation import render_scene
    data,_,plan=analyze(copied_library,ReviewInput(story='নাবিল আমবাগানে গেল।'))
    assert data['ready']
    job=tmp_path/'job';job.mkdir()
    frozen=snapshot_plan(plan,job)
    original=(frozen['characters']['nabil']['directory']/'body.png').read_bytes()
    path=copied_library.root/'characters/nabil/body.png';path.write_bytes(path.read_bytes()+b'changed')
    assert (frozen['characters']['nabil']['directory']/'body.png').read_bytes()==original
    assert load_character('nabil',job/'asset_snapshot')['identity_hash']==plan['characters']['nabil']['identity_hash']
    image=render_scene({'plan':frozen,'time':1,'local_time':1,'total_duration':3,'visible_characters':['nabil'],'action':'idle'})
    assert image.size==(720,1280)


def test_custom_canvas_is_rendered_and_discovered(copied_library):
    import hashlib
    from app.engines.animation import compose_character
    from app.assets import load_character
    directory=copied_library.root/'characters/nabil';path=directory/'character.json'
    meta=json.loads(path.read_text(encoding='utf-8'))
    for name in meta['file_hashes']:
        file=directory/name
        if name.endswith('.png'):
            with Image.open(file) as image: smaller=image.resize((192,320),Image.Resampling.NEAREST)
            smaller.save(file);meta['file_hashes'][name]=hashlib.sha256(file.read_bytes()).hexdigest()
    meta['canvas']=[192,320];meta['anchors']={k:[v/2 for v in values] for k,values in meta['anchors'].items()}
    path.write_text(json.dumps(meta,ensure_ascii=False),encoding='utf-8')
    character=load_character('nabil',copied_library.root)
    rig,_=compose_character(character,1,'talk','D')
    assert rig.size==(192,320)
    assert next(r for r in copied_library.public('characters') if r['id']=='nabil')['status']=='ready'


def test_ambiguous_later_location_does_not_reuse_previous_stage(studio):
    data=studio.post('/api/analyze',json={'story':'দৃশ্য: আমবাগান\nচরিত্র: নাবিল\nদৃশ্য: স্কুলের মাঠ আর নদীর ঘাট'}).json()
    assert not data['ready']
    assert len(data['scenes'])==2
    assert data['scenes'][0]['background_id']=='mango_orchard_day'
    assert data['scenes'][1]['background_id'] is None


def test_metadata_change_invalidates_review(copied_library):
    payload=ReviewInput(story='নাবিল আমবাগানে গেল।')
    before,_,_=analyze(copied_library,payload)
    path=copied_library.root/'characters/nabil/character.json'
    meta=json.loads(path.read_text(encoding='utf-8'));meta['anchors']['mouth'][1]+=1
    path.write_text(json.dumps(meta,ensure_ascii=False),encoding='utf-8')
    after,_,_=analyze(copied_library,payload)
    assert after['ready'] and before['review_token']!=after['review_token']
