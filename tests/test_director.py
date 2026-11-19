import json
import pytest
from app.director import CartoonDirector
from app.assets import load_character,load_background
from app.scene_cache import fingerprint
from app.voices.base import VoiceIdentity,VoiceError
from app.voices.voice_manager import usage


def test_director_named_actor_listener_and_manual_override():
    bg=load_background('mango_orchard_day')
    plan={'characters':{cid:load_character(cid) for cid in ('rayan','nabil')},'background':bg}
    segment={'kind':'narration','text':'নাবিল একটা অদ্ভুত শব্দ শুনে ভয় পেয়ে গেল।','id':'segment_001'}
    scene={'kind':'speech','clip_id':'segment_001','speaker':'narrator','off_screen':True,'start':0.,'end':4.,
           'start_frame':0,'end_frame':120,'visible_characters':['rayan','nabil'],'source_scene_id':'scene_001','background_id':'mango_orchard_day'}
    timeline={'fps':30,'width':1280,'height':720,'scenes':[scene]}
    direction=CartoonDirector().plan(timeline,plan,[segment])[0]
    assert direction['actors']['nabil']['action']=='fear'
    assert direction['actors']['rayan']['action']=='idle'
    assert direction['actors']['rayan']['gaze']==1
    assert direction['actors']['nabil']['emotion']=='fear'
    assert direction['actors']['rayan']['reason'].endswith('mouth closed.')
    revised=CartoonDirector().plan(timeline,plan,[segment],{'segment_001':{'actor_id':'rayan','action':'wave','emotion':'happy','shot':'two_shot'}})[0]
    assert revised['actors']['rayan']['action']=='wave' and revised['actors']['nabil']['action']=='idle'
    with pytest.raises(ValueError):CartoonDirector().plan(timeline,plan,[segment],{'segment_001':{'actor_id':'invented'}})


def test_paid_approval_binds_emotion_and_pricing_is_not_fabricated(monkeypatch):
    monkeypatch.delenv('TOON_ELEVENLABS_USD_PER_MILLION',raising=False)
    identity=VoiceIdentity(provider='elevenlabs',model='eleven_v4',voice_id='mock-catalog-id')
    first=usage('এই! তোরা কিছু শুনলি?',identity,'curious')
    second=usage('এই! তোরা কিছু শুনলি?',identity,'fear')
    assert first['approval_token']!=second['approval_token']
    assert first['characters']>first['spoken_characters'] and first['estimated_usd'] is None
    monkeypatch.setenv('TOON_ELEVENLABS_USD_PER_MILLION','nan')
    with pytest.raises(VoiceError):usage('হ্যালো',identity)


def test_incomplete_articulated_rig_rejected_without_substitution(tmp_path):
    from app.rendering.godot_adapter import rig_description
    directory=tmp_path/'character';(directory/'articulated/v1').mkdir(parents=True)
    data={'source_identity':'same','bones':{'Hips':{}},'parts':{},'hashes':{}}
    (directory/'articulated/v1/rig.json').write_text(json.dumps(data))
    with pytest.raises(ValueError,match='missing required'):
        rig_description({'directory':directory,'character_id':'nabil','identity_hash':'same'})
