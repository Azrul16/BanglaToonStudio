import pytest
from app.engines.story_parser import parse_story
from app.assets import plan_story,AssetError
from app.main import SAMPLE


def test_sample_order_and_offscreen_identity():
    parsed=parse_story(SAMPLE)
    assert parsed['count']==3
    assert parsed['speakers']==['narrator','rahat','unknown_voice']
    assert parsed['segments'][0]['text']==next(line.split(': ',1)[1] for line in SAMPLE.splitlines() if line.startswith('বর্ণনাকারী:'))
    assert parsed['segments'][1]['text']=='কে ওখানে?'
    assert parsed['segments'][2]['off_screen']
    assert not parsed['segments'][1]['off_screen']
    assert set(plan_story(parsed)['characters'])=={'rahat'}


@pytest.mark.parametrize('line',['Rahat: হ্যালো!','রাহাত： হ্যালো!','**রাহাত:** হ্যালো!','[রাহাত]: হ্যালো!','রাহাত — হ্যালো!','— রাহাত: “হ্যালো!”'])
def test_common_labels_and_aliases(line):
    segment=parse_story(line)['segments'][0]
    assert segment['speaker']=='rahat'
    assert segment['text']=='হ্যালো!'


def test_paragraphs_unicode_and_order():
    parsed=parse_story('এক রাত।\r\nআরেক রাত।\r\n\r\nRahat: কী হয়েছে?\n\nUnknown voice: চলে যাও।')
    assert parsed['count']==2
    assert all(e['type']=='unresolved_instruction' and not e['generate_voice'] for e in parsed['events'][:2])
    assert parsed['segments'][1]['speaker']=='unknown_voice'


@pytest.mark.parametrize('text',['','  ','x'*30001])
def test_invalid_story(text):
    with pytest.raises(ValueError): parse_story(text)


def test_unknown_speaker_rejected_without_substitution():
    with pytest.raises(AssetError,match='Unknown speaker'): parse_story('মিতা: হ্যালো!')


def test_reference_only_character_rejected():
    with pytest.raises(AssetError,match='design references only'): plan_story(parse_story('Arif: হ্যালো!'))


@pytest.mark.parametrize('text',['এক বনে রাহাত হাঁটছিল।','রাহাত একটি classroom এ দাঁড়িয়ে ছিল।','এক জঙ্গল ছিল।'])
def test_unsupported_location_is_not_station(text):
    with pytest.raises(AssetError,match='Unsupported scene'): plan_story(parse_story(text))


def test_ambiguous_location_has_visible_warning():
    plan=plan_story(parse_story('রাহাত: কে ওখানে?'))
    assert plan['warnings']
    assert plan['background']['background_id']=='railway_station_night'


def test_long_paragraph_retains_all_sentences():
    text='এক গভীর রাত ছিল। '*60
    parsed=parse_story('বর্ণনাকারী: '+text)
    assert len(parsed['segments'])>1
    assert ' '.join(s['text'] for s in parsed['segments'])==text.strip()
