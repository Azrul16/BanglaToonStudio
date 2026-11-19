import hashlib
import json
import shutil
import unicodedata
import pytest
from PIL import Image,ImageChops
from app.assets import ROOT,AssetError,load_character,plan_story,speaker_info
from app.engines.animation import character_layout,compose_character
from app.engines.story_parser import parse_story
from app.engines.lip_sync import mouth_at

CHILDREN={'নাবিল':'nabil','রায়ান':'rayan','ফাহিম':'fahim','অনিকা':'anika','মালিহা':'maliha'}
DIALOGUE='''নাবিল: এই! তোরা কিছু শুনলি?
রায়ান: হ্যাঁ! মনে হচ্ছে মাটির নিচে কেউ আছে!
অনিকা: দাঁড়া! ওই পাতাগুলো নড়ছে কেন?'''


@pytest.mark.parametrize('name,cid',CHILDREN.items())
def test_children_names_unicode_and_real_rigs(name,cid):
    assert speaker_info(name)['character_id']==cid
    assert speaker_info(cid.title())['character_id']==cid
    copied='\ufeff  '+unicodedata.normalize('NFD',name[:1])+'\u200b'+unicodedata.normalize('NFD',name[1:])+'\u00a0 '
    assert speaker_info(copied)['character_id']==cid
    assert parse_story(copied+': হ্যালো!')['segments'][0]['speaker']==cid
    character=load_character(cid)
    assert character['animation_ready'] and character['voice_id']=='default_bn'
    assert len(character['file_hashes'])==28
    assert character['reference_sha256']==hashlib.sha256((ROOT/'characters'/cid/'character_sheet.png').read_bytes()).hexdigest()
    for filename in character['file_hashes']:
        if filename.endswith('.png'):
            with Image.open(ROOT/'characters'/cid/filename) as image:
                assert image.mode=='RGBA' and image.size==(384,640)
                assert image.getchannel('A').getbbox()


def test_exact_requested_three_speakers():
    parsed=parse_story(DIALOGUE)
    assert parsed['speakers']==['nabil','rayan','anika']
    assert [s['text'] for s in parsed['segments']]==['এই! তোরা কিছু শুনলি?','হ্যাঁ! মনে হচ্ছে মাটির নিচে কেউ আছে!','দাঁড়া! ওই পাতাগুলো নড়ছে কেন?']
    plan=plan_story(parsed)
    assert list(plan['characters'])==['nabil','rayan','anika']
    assert not any(s['off_screen'] for s in parsed['segments'])


def test_unique_permanent_identity_and_narrative_lookup():
    characters=[load_character(cid) for cid in CHILDREN.values()]
    for layer in ('body.png','head.png','hair.png'):
        assert len({c['file_hashes'][layer] for c in characters})==5
    assert len({c['identity_hash'] for c in characters})==5
    plan=plan_story(parse_story('নাবিল ও অনিকা রেলস্টেশনে দাঁড়িয়েছিল।'))
    assert set(plan['characters'])=={'nabil','anika'}
    english=plan_story(parse_story('Nabil clarified the mystery at the railway station.'))
    assert set(english['characters'])=={'nabil'}


@pytest.mark.parametrize('cid',CHILDREN.values())
def test_mouth_mapping_blink_walk_and_unchanged_assets(cid):
    character=load_character(cid)
    identity=character['identity_hash']
    for shape in 'ABCDEFGHX':
        cue=[{'start':0,'end':1,'value':shape}]
        selected=mouth_at(cue,.5)
        image,_=compose_character(character,1,'talk',selected)
        assert image.getchannel('A').getbbox()
        if shape=='D': opened=image
        if shape=='X': closed=image
    assert ImageChops.difference(opened,closed).convert('RGB').getbbox()
    before,_=compose_character(character,1,'idle')
    blink,_=compose_character(character,1,'blink')
    assert ImageChops.difference(before,blink).convert('RGB').getbbox()
    a,_=compose_character(character,.2,'walk'); b,_=compose_character(character,.6,'walk')
    assert a.tobytes()!=b.tobytes()
    assert load_character(cid)['identity_hash']==identity


def test_multi_character_layout_keeps_every_child_on_stage():
    for ids in (['nabil','rayan','anika'],list(CHILDREN.values())):
        bounds=[]
        for i,cid in enumerate(ids):
            character=load_character(cid)
            x,y,scale=character_layout(character,i,len(ids))
            left=x-character['anchors']['feet'][0]*scale
            right=left+384*scale
            assert 42<left<right<858
            bounds.append((left,right))
        assert all(a[1]<b[0] for a,b in zip(bounds,bounds[1:]))


def test_mouth_changes_only_at_the_speaking_child():
    from app.engines.animation import render_scene
    plan=plan_story(parse_story(DIALOGUE))
    centers=[]
    for cid in ('nabil','rayan','anika'):
        scene={'plan':plan,'kind':'speech','time':2,'local_time':1,'total_duration':15,'visible_characters':list(plan['characters']),
               'action':'talk','speaker':cid,'off_screen':False}
        opened=render_scene({**scene,'mouth':'D'})
        closed=render_scene({**scene,'mouth':'X'})
        bbox=ImageChops.difference(opened,closed).getbbox()
        assert bbox and bbox[2]-bbox[0]<50 and bbox[3]-bbox[1]<50
        centers.append((bbox[0]+bbox[2])/2)
    assert centers[1]-centers[0]>100 and centers[2]-centers[1]>100


def test_registration_rejects_incomplete_child_rig(tmp_path):
    root=tmp_path/'assets'
    shutil.copytree(ROOT/'characters/nabil',root/'characters/nabil')
    shutil.copy2(ROOT/'registry.json',root/'registry.json')
    (root/'characters/nabil/mouths/D.png').unlink()
    with pytest.raises(AssetError,match='Missing locked asset'):
        speaker_info('নাবিল',root)


def test_supplied_flat_station_is_locked_without_changing_image():
    from app.assets import load_background
    background=load_background('railway_station_night')
    assert background['layer_mode']=='flat'
    assert set(background['file_hashes'])=={'background.png'}
    assert background['canvas']==[background['width'],background['height']]
