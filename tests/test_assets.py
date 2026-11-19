import hashlib
import json
import shutil
import pytest
from app.assets import ROOT,load_character,load_background,AssetError


@pytest.fixture
def assets(tmp_path):
    root=tmp_path/'assets'
    shutil.copytree(ROOT/'characters/rahat',root/'characters/rahat',ignore=shutil.ignore_patterns('*reference.png','*sheet.png'))
    shutil.copytree(ROOT/'backgrounds',root/'backgrounds')
    return root


def test_locked_assets_repeat_across_loads():
    first=load_character('rahat'); second=load_character('rahat')
    assert first['identity_hash']==second['identity_hash']
    assert first['file_hashes']==second['file_hashes']
    assert first['voice_id']=='default_bn'
    assert load_background('railway_station_night')['identity_hash']


def test_tampered_sprite_rejected(assets):
    path=assets/'characters/rahat/body.png'
    path.write_bytes(path.read_bytes()+b'changed')
    with pytest.raises(AssetError,match='identity mismatch'): load_character('rahat',assets)


def test_missing_mouth_rejected(assets):
    (assets/'characters/rahat/mouths/D.png').unlink()
    with pytest.raises(AssetError,match='Missing locked asset'): load_character('rahat',assets)


@pytest.mark.parametrize('change',[{'rig_version':'2.0.0'},{'anchors':{'head':[-10,0]}},{'version':'bad'}])
def test_version_and_anchor_validation(assets,change):
    path=assets/'characters/rahat/character.json'
    meta=json.loads(path.read_text(encoding='utf-8')); meta.update(change)
    path.write_text(json.dumps(meta),encoding='utf-8')
    with pytest.raises(AssetError): load_character('rahat',assets)


def test_invisible_layer_rejected_even_with_updated_hash(assets):
    from PIL import Image
    directory=assets/'characters/rahat'
    Image.new('RGBA',(384,640)).save(directory/'body.png')
    path=directory/'character.json'; meta=json.loads(path.read_text(encoding='utf-8'))
    meta['file_hashes']['body.png']=hashlib.sha256((directory/'body.png').read_bytes()).hexdigest()
    path.write_text(json.dumps(meta),encoding='utf-8')
    with pytest.raises(AssetError,match='visible artwork'): load_character('rahat',assets)


def test_missing_background_rejected(assets):
    with pytest.raises(AssetError): load_background('forest',assets)


def test_path_escape_rejected(assets):
    with pytest.raises(AssetError): load_character('../rahat',assets)
