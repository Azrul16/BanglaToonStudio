"""A real, directed Nabil/Rayan performance and matching legacy comparison."""
import json
import shutil
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.assets import load_character,load_background
from app.engines.video_renderer import build_audio,encode_stream,validate_scene
from app.rendering.godot_adapter import encode_scene
from app.hardware import ffmpeg_binary,encoder_capabilities,run,validate_video
from app.scene_cache import atomic_json


def prepare():
    directory=ROOT/'workspace/godot-portrait-benchmark';directory.mkdir(exist_ok=True)
    for name in ('audio','cues','render/scenes'):(directory/name).mkdir(parents=True,exist_ok=True)
    source=ROOT/'workspace/74e1147bfcad4785a5a10f8dc44be727'
    original=json.loads((source/'job.json').read_text(encoding='utf-8'))['clips']
    selected=[original[3],original[23]];clips=[]
    for index,c in enumerate(selected):
        cid=f'segment_{index+1:03}';clips.append({**c,'id':cid})
        shutil.copyfile(source/'audio'/f"{c['id']}.wav",directory/'audio'/f'{cid}.wav')
        shutil.copyfile(source/'cues'/f"{c['id']}.json",directory/'cues'/f'{cid}.json')
    bg=load_background('mango_orchard_day');plan={'characters':{cid:load_character(cid) for cid in ('nabil','rayan')},'background':bg,'backgrounds':{'mango_orchard_day':bg},'warnings':[],'renderer':'godot'}
    scenes=[];cursor=0
    def add(seconds,kind,action,emotion='neutral',speaker=None,shot='wide',clip=None):
        nonlocal cursor
        count=round(seconds*30) if kind!='speech' else __import__('math').ceil(seconds*30)
        start=cursor/30;end=(cursor+count)/30
        scene={'kind':kind,'start_frame':cursor,'end_frame':cursor+count,'start':start,'end':end,'action':'walk' if action=='walk' else 'talk' if kind=='speech' else 'idle',
               'previous_action':'idle','source_scene_id':'scene_001','background_id':'mango_orchard_day','visible_characters':['nabil','rayan'],
               'off_screen':speaker is None,'speaker':speaker or 'narrator','camera':{'shot':shot,'target':speaker or 'nabil'},'actors':{}}
        for cid in ('nabil','rayan'):
            active=cid==(speaker or 'nabil')
            scene['actors'][cid]={'action':action if active else 'idle','emotion':emotion if active else 'curious' if kind=='speech' else 'neutral',
                                  'gaze':1 if cid=='nabil' else -1,'start':start,'end':end,'from_x':-150 if action=='walk' and active else 0,'to_x':0,'speed':72}
        if clip:scene.update(clip_id=clip['id'],text=clip['text'],speaker_name=clip['speaker_name'],audio_duration=seconds)
        scenes.append(scene);cursor+=count
    add(3.5,'intro','walk')
    add(.8,'reaction','stop')
    add(1.,'reaction','turn',shot='two_shot')
    add(1.2,'reaction','fear','surprised',shot='medium')
    add(clips[0]['duration_seconds'],'speech','explain','curious','nabil','two_shot',clips[0])
    add(2.,'reaction','stop','surprised','rayan','reaction')
    add(clips[1]['duration_seconds'],'speech','point','surprised','rayan','medium',clips[1])
    add(5.,'outro','wave','happy',shot='wide')
    timeline={'width':1080,'height':1920,'fps':30,'total_frames':cursor,'duration_seconds':cursor/30,'scenes':scenes,'warnings':[]}
    plan['direction']=scenes
    atomic_json(directory/'timeline.json',timeline)
    build_audio(clips,timeline,directory)
    return directory,clips,timeline,plan


if __name__=='__main__':
    directory,clips,timeline,plan=prepare()
    count=30 if '--probe' in sys.argv else timeline['total_frames']
    chunk={'scene_id':'render_0001','start_frame':0,'end_frame':count,'duration_seconds':count/30}
    encoder=encoder_capabilities()['encoder']
    print('Godot benchmark frames:',count,flush=True)
    result=encode_scene(clips,timeline,plan,directory,encoder,lambda p:print(p,flush=True),lambda:None,chunk)
    validate_scene(directory/'render/scenes/render_0001.mp4',chunk,(1080,1920),30)
    if '--probe' in sys.argv:print(result);sys.exit()
    output=ROOT/'output/godot-portrait-benchmark.mp4'
    converted=run([ffmpeg_binary(),'-y','-v','error','-i',str(directory/'render/scenes/render_0001.mp4'),'-i',str(directory/'render/timeline.wav'),
                   '-map','0:v','-map','1:a','-c:v','copy','-c:a','aac','-b:a','192k','-t',str(timeline['duration_seconds']),'-movflags','+faststart',str(output)],120)
    assert converted.returncode==0,converted.stderr
    info=validate_video(output,timeline['duration_seconds'],size=(1080,1920),fps=30)
    atomic_json(directory/'acceptance.json',{'video':str(output),'info':info,'metrics':result})
    print(json.dumps(info),flush=True)
