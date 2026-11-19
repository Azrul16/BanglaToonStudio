from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_exact_v6_script(studio):
    script=(ROOT/'samples/v6_regression_bn.txt').read_text(encoding='utf-8')
    response=studio.post('/api/analyze',json={'story':script,'renderer':'godot'})
    assert response.status_code==200,response.text
    report=response.json()
    assert report['ready'],report['issues']
    assert len(report['scenes'])==1
    assert report['scenes'][0]['background_id']=='mango_orchard_day'
    assert [s['speaker'] for s in report['spoken_segments']]==['nabil','rayan','anika','nabil','rayan']
    assert len(report['spoken_segments'])==5
    assert {c for e in report['events'] for c in e['character_ids']}=={'nabil','rayan','anika'}
    assert any(e['type']=='screen_text' for e in report['events'])
    assert any(e['metadata'].get('music_control')=='fade_out' for e in report['events'])
    assert all(not e['generate_voice'] for e in report['events'] if e['type'] not in ('dialogue','narration'))


def test_scene_context_and_unspoken_prose(studio):
    report=studio.post('/api/analyze',json={'story':'চরিত্র: নাবিল, রায়ান\nদৃশ্য: আমবাগান\n[নাবিল ভয় পেয়ে পিছিয়ে যায়।]\nনাবিল: ওরে বাবা!\n[সে মাথা চুলকায়।]\n[রায়ান হেসে ওঠে।]\nএক অদ্ভুত বিকেল।','renderer':'godot'}).json()
    assert report['ready'],report['issues']
    assert len(report['spoken_segments'])==1
    assert report['spoken_segments'][0]['emotion']=='fear'
    scratch=next(e for e in report['events'] if 'সে মাথা' in e['source_text'])
    assert scratch['character_ids']==['nabil']


def test_unknown_identity_still_blocks_once(studio):
    report=studio.post('/api/analyze',json={'story':'Scene: আমবাগান\nMita: Hello!\nMita: Again!','renderer':'godot'}).json()
    assert not report['ready']
    assert len([i for i in report['issues'] if i['type']=='character'])==1


def test_mixed_commands_no_dialogue(studio):
    report=studio.post('/api/analyze',json={'story':'Title: Test\nGenre: comedy\nScene: আমবাগান\nBackground: mango_orchard\nCharacters: Nabil\n[Nabil মাথা চুলকায়।]\n[ক্যামেরা ধীরে কাছে আসে।]\n[SCREEN_TEXT: সমাপ্ত]\n[SFX: unavailable_nonessential]','renderer':'godot'}).json()
    assert report['ready'],report['issues']
    assert not report['spoken_segments']


def test_essential_action_cannot_be_hidden_by_minor_gesture(studio):
    report=studio.post('/api/analyze',json={'story':'দৃশ্য: আমবাগান\n[নাবিল হাততালি দিয়ে আকাশে উড়ে যায়।]','renderer':'godot'}).json()
    assert not report['ready']
    assert report['events'][-1]['type']=='unresolved_instruction'
    assert not report['spoken_segments']
