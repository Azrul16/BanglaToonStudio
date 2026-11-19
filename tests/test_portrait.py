import json
from types import SimpleNamespace
import pytest
from pydantic import ValidationError
from app.video_config import output_size,validate_canvas
from app.review import ReviewInput
from app.chat import preferences
from app import hardware


@pytest.mark.parametrize('mode',['shorts','mini'])
def test_duration_never_changes_orientation(mode):
    assert output_size({'duration_mode':mode})==(1080,1920)
    assert output_size({'duration_mode':mode,'video_profile':'low_memory'})==(720,1280)
    assert ReviewInput(story='Nabil: Hello').video_profile=='production'


@pytest.mark.parametrize('format',['landscape','horizontal','square','16:9'])
def test_reject_horizontal_configuration(format):
    with pytest.raises(ValueError):output_size({'video_format':format})
    with pytest.raises(ValidationError):ReviewInput(story='Nabil: Hello',video_format=format)


@pytest.mark.parametrize('canvas',[(1920,1080),(1280,720),(1080,1080),(720,1280,24)])
def test_reject_non_portrait_canvas(canvas):
    with pytest.raises(ValueError):validate_canvas(*canvas)


def test_legacy_preferences_migrate_without_touching_video(tmp_path):
    old={'format':'vertical_mini','music':False,'voice_preference':'saved'}
    (tmp_path/'preferences.json').write_text(json.dumps(old))
    video=tmp_path/'old-landscape.mp4';video.write_bytes(b'preserved historical video')
    assert preferences(tmp_path).format=='mini'
    assert preferences(tmp_path).music is False
    assert json.loads((tmp_path/'preferences-before-portrait-only.json').read_text())==old
    assert video.read_bytes()==b'preserved historical video'


@pytest.mark.parametrize('change',[{'width':1280,'height':720},{'sample_aspect_ratio':'2:1'},{'side_data_list':[{'rotation':90}]}])
def test_probe_rejects_invalid_display_before_decode(monkeypatch,change):
    stream={'codec_type':'video','width':1080,'height':1920,'codec_name':'h264','pix_fmt':'yuv420p','r_frame_rate':'30/1','sample_aspect_ratio':'1:1',**change}
    data={'streams':[stream,{'codec_type':'audio','codec_name':'aac'}],'format':{'duration':'1'}}
    monkeypatch.setattr(hardware,'ffprobe_binary',lambda:'probe')
    calls=[]
    def run(args,timeout):
        calls.append(args);return SimpleNamespace(returncode=0,stdout=json.dumps(data),stderr='')
    monkeypatch.setattr(hardware,'run',run)
    with pytest.raises(RuntimeError):hardware.validate_video('invalid.mp4',1)
    assert len(calls)==1


@pytest.mark.parametrize('width,height',[(1080,1920),(720,1280)])
def test_subtitles_inside_social_safe_area(width,height):
    from app.subtitles import bitmap
    image,settings=bitmap('এই! তোরা কিছু শুনলি?',width,height)
    left,top,right,bottom=image.getbbox()
    assert len(settings['lines'])<=2
    assert left>=width*.07 and right<=width*.93
    assert settings['bottom_margin']==round(height*.12)
    assert image.height+settings['bottom_margin']<height*.35


@pytest.mark.parametrize('mode',['flat','hybrid'])
def test_real_native_benchmark_download(studio,mode):
    from pathlib import Path
    import shutil
    import app.main as main
    from app.scene_cache import digest
    source=Path(__file__).resolve().parents[1]/'output'/f'{mode}-portrait-1080p-evaluation.mp4'
    if not source.is_file():pytest.skip('Run the real portrait benchmark first')
    result=hardware.validate_video(source,21.3333333333)
    jid=('a' if mode=='flat' else 'b')*32
    target=main.OUTPUT/(jid+'.mp4');shutil.copyfile(source,target)
    main.JOBS[jid]={'job_id':jid,'status':'completed',**result}
    response=studio.get('/api/videos/'+jid+'?download=true')
    assert response.status_code==200 and response.headers['content-type']=='video/mp4'
    assert 'attachment' in response.headers['content-disposition']
    import hashlib
    assert hashlib.sha256(response.content).hexdigest()==digest(source)
