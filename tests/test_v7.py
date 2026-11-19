from pathlib import Path
import pytest
from app.emotion import EmotionAnalyzer,EMOTION_RIG
from app.engines.story_parser import parse_story
from app.director import IntelligentCartoonDirector
from app.review import ReviewInput,analyze
from app.timeline import build_timeline
from app.subtitles import bitmap,layout,prepare
ROOT=Path(__file__).resolve().parents[1]


def test_v7_prose_attribution_gaze_and_speech_whitelist(studio):
    report=studio.post('/api/analyze',json={'story':(ROOT/'samples/v7_benchmark_bn.txt').read_text(encoding='utf-8'),'renderer':'godot'}).json()
    assert report['ready'],report['issues']
    assert [s['speaker'] for s in report['spoken_segments']]==['nabil','rayan','anika','nabil','rayan']
    assert report['spoken_segments'][0]['text']=='এই রায়ান! তুই কিছু শুনলি?'
    gaze=next(e for e in report['events'] if e['metadata'].get('gaze_target_label'))
    assert gaze['character_ids']==['nabil'] and gaze['metadata']['gaze_target_id']=='rayan'
    assert report['spoken_segments'][0]['emotion']=='fear'
    assert report['spoken_segments'][3]['metadata']['emotion_states'][0]['emotion']=='embarrassed'
    assert report['spoken_segments'][4]['metadata']['emotion_states'][0]['emotion']=='relieved'
    assert all(not e['generate_voice'] for e in report['events'] if e['type'] not in ('dialogue','narration'))


@pytest.mark.parametrize('text',['নাবিল মনে মনে বলল, "আমি চলে যাব।"','দেয়ালে লেখা ছিল, "এসো এখানে।"','নাবিল একটি নোট লিখল, "চলে যাও।"'])
def test_written_and_internal_quotes_are_not_speech(text):
    assert not parse_story(text)['segments']


def test_emotion_vocabulary_and_negation():
    analyzer=EmotionAnalyzer()
    assert len(EMOTION_RIG)==16
    for name in EMOTION_RIG:assert analyzer.infer(name)[0]==name
    assert analyzer.infer('ভয় নেই, এখন স্বস্তি লাগছে।')[0]=='relieved'
    assert analyzer.infer('রায়ান কিছুক্ষণ চুপ করে ভাবল।')[0]=='thinking'
    assert analyzer.infer('খুশি নই।') is None


def test_other_characters_emotions_do_not_become_speaker_emotions():
    story='[নাবিল ভয় পেয়ে পিছিয়ে যায়।]\nনাবিল: দাঁড়া।\nরায়ান: তুই কি ভয় পেয়েছিস?\nনাবিল: আমি ভয় পাইনি, এখন স্বস্তি লাগছে।'
    rows=parse_story(story)['segments']
    assert rows[0]['emotion']=='fear'
    assert rows[1]['emotion']=='neutral'
    assert rows[2]['metadata']['emotion_states'][0]['emotion']=='relieved'


def test_positions_and_emotions_continue_after_movement(studio):
    import app.main as main
    story='দৃশ্য: আমবাগান\nচরিত্র: নাবিল, রায়ান\n[নাবিল ভয় পেয়ে পিছিয়ে যায়।]\nনাবিল: কে ওখানে?\nরায়ান: আমি এখানে।\nনাবিল: একটু দাঁড়া।'
    report,parsed,plan=analyze(main.LIBRARY,ReviewInput(story=story,renderer='godot'))
    assert report['ready'],report
    clips=[{**s,'duration_seconds':1.23} for s in parsed['segments']]
    timeline=build_timeline(clips,plan,{'renderer':'godot'})
    direction=IntelligentCartoonDirector().plan(timeline,plan,clips)
    moving=[s for s in direction if s['kind']=='action' and s['actors']['nabil']['action']=='step_back'][0]
    later=[s for s in direction if s['start']>=moving['end']]
    assert moving['actors']['nabil']['from_x']==0
    assert moving['actors']['nabil']['to_x']<0
    assert all(s['actors']['nabil']['from_x']==moving['actors']['nabil']['to_x'] for s in later)
    assert all(s['actors']['nabil']['emotion']=='fear' for s in later)
    assert timeline['emotion_track'] and all('trigger_event' in r and r['end']>r['start'] for r in timeline['emotion_track'])


@pytest.mark.parametrize('size',[(720,1280),(1080,1920)])
def test_shaped_two_line_subtitles_use_real_take_times(tmp_path,size):
    text='দায়িত্ব, যুক্তি, শ্রদ্ধা ও স্বাধীনতা—আমরা একসঙ্গে শিখব।'
    image,settings=bitmap(text,*size)
    assert len(settings['lines'])<=2 and settings['font_size']>=18
    assert image.mode=='RGBA' and image.getpixel((0,0))[3]==0
    timeline={'width':size[0],'height':size[1],'scenes':[{'kind':'speech','start':1.,'end':3.,'audio_duration':1.967,'text':text},
        {'kind':'action','start':3.,'end':4.,'text':'[হাঁটে]'}, {'kind':'screen_text','start':4.,'end':6.,'screen_text':'সমাপ্ত'}]}
    cues=prepare(timeline,tmp_path)
    assert len(cues)==1 and cues[0]['end']==pytest.approx(2.967)
    assert cues[0]['alignment']=='full_approved_take' and not cues[0]['background_box'] and not cues[0]['speaker_prefix']


def test_long_dialogue_is_chunked_before_synthesis():
    text=' '.join(['আমরা একসঙ্গে গল্প শুনব।']*25)
    rows=parse_story('নাবিল: '+text)['segments']
    assert len(rows)>1 and all(len(r['text'])<=140 for r in rows)
    assert ' '.join(r['text'] for r in rows)==text


def test_bengali_instruction_headings(studio):
    story='দৃশ্য: আমবাগান\nচরিত্র: নাবিল\nঅ্যাকশন: নাবিল মাথা চুলকায়।\nসংলাপ: নাবিল: কী হয়েছে?\nঅ্যাম্বিয়েন্স: birds_soft_wind\nসাউন্ড ইফেক্ট: leaves_rustling\nবর্ণনা: তখন বিকেল।'
    report=studio.post('/api/analyze',json={'story':story,'renderer':'godot'}).json()
    assert report['ready'],report['issues']
    assert [s['text'] for s in report['spoken_segments']]==['কী হয়েছে?','তখন বিকেল।']


def test_prose_listener_is_present_without_declared_cast(studio):
    report=studio.post('/api/analyze',json={'story':'দৃশ্য: আমবাগান\nনাবিল রায়ানের দিকে তাকিয়ে বলল, "দাঁড়া।"','renderer':'godot'}).json()
    assert report['ready'],report['issues']
    assert set(report['scenes'][0]['visible_characters'])=={'nabil','rayan'}


def test_continuous_walk_has_no_boundary_teleport(studio):
    import app.main as main
    script='দৃশ্য: আমবাগান\n[নাবিল হাঁটতে থাকে।]\nনাবিল: আমি হাঁটছি।\nনাবিল: চলো।\n[নাবিল থামে।]'
    report,parsed,plan=analyze(main.LIBRARY,ReviewInput(story=script,renderer='godot'))
    assert report['ready'],report
    clips=[{**s,'duration_seconds':1.53} for s in parsed['segments']]
    timeline=build_timeline(clips,plan,{'renderer':'godot'})
    shots=IntelligentCartoonDirector().plan(timeline,plan,clips)
    def position(actor,t):
        p=max(0,min(1,(t-actor['start'])/(actor['end']-actor['start'])));p=p*p*(3-2*p)
        return actor['from_x']+(actor['to_x']-actor['from_x'])*p
    for before,after in zip(shots,shots[1:]):
        assert position(before['actors']['nabil'],before['end'])==pytest.approx(position(after['actors']['nabil'],after['start']))


def test_offscreen_narration_does_not_trigger_targetless_zoom(studio):
    import app.main as main
    report,parsed,plan=analyze(main.LIBRARY,ReviewInput(story='দৃশ্য: আমবাগান\nচরিত্র: নাবিল\nবর্ণনা: তখন বিকেল।',renderer='godot'))
    assert report['ready'],report
    clips=[{**s,'duration_seconds':1.53} for s in parsed['segments']]
    timeline=build_timeline(clips,plan,{'renderer':'godot'})
    direction=IntelligentCartoonDirector().plan(timeline,plan,clips)
    assert next(s for s in direction if s['kind']=='speech')['camera']=={'shot':'wide','target':None}
