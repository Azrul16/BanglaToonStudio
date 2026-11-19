"""Godot Movie Maker -> per-scene AVI -> FFmpeg H.264. No assumed MP4 writer."""
import json
import math
import os
import shutil
import subprocess
import time
from pathlib import Path
from app.assets import safe_path
from app.scene_cache import atomic_json,digest
from app.hardware import ffmpeg_binary,run
from app.director import CartoonDirector
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]


def godot_binary():
    configured=os.getenv('GODOT_BINARY')
    if configured and Path(configured).is_file():return configured
    installed=sorted((ROOT/'tools/godot').glob('*_console.exe'))
    return str(installed[-1]) if installed else shutil.which('godot')


def rig_description(character):
    # Snapshots preserve the derived artwork too, rather than using live layers.
    folder=character['directory']/'articulated/v1'
    path=folder/'rig.json'
    if not path.is_file():raise ValueError(f"{character['character_id']} has no articulated rig; see assets/characters/RIG_LAYER_SPEC.md")
    data=json.loads(path.read_text(encoding='utf-8'))
    if data['source_identity']!=character['identity_hash']:raise ValueError('Articulated rig does not match the registered source identity')
    required_bones={'Hips','Torso','Neck','Head',*[side+part for side in ('Left','Right') for part in ('UpperArm','Forearm','Hand','Thigh','Leg','Foot')]}
    required_parts={'torso','head','hair','brows','eyes_open','eyes_closed',*[f'mouth_{m}' for m in 'ABCDEFGHX'],
                    *[side+'_'+part for side in ('left','right') for part in ('upper_arm','forearm','hand','thigh','leg','foot')]}
    if not required_bones.issubset(data.get('bones',{})) or not required_parts.issubset(data.get('parts',{})):raise ValueError('Articulated rig is missing required bones or artwork layers')
    def point(value):return isinstance(value,list) and len(value)==2 and all(isinstance(v,(float,int)) and math.isfinite(v) for v in value)
    ordered={};pending=dict(data['bones'])
    while pending:
        ready=[name for name,entry in pending.items() if entry.get('parent') is None or entry.get('parent') in ordered]
        if not ready:raise ValueError('Articulated bone hierarchy contains a cycle or missing parent')
        for name in ready:
            entry=pending.pop(name)
            if not point(entry.get('position')):raise ValueError('Invalid articulated pivot')
            ordered[name]=entry
    data['bones']=ordered
    if not point(data.get('feet')):raise ValueError('Articulated ground anchor is missing')
    for part in data['parts'].values():
        if part.get('bone') not in ordered or not point(part.get('origin')) or part.get('file') not in data['hashes']:raise ValueError('Invalid articulated layer mapping')
        with Image.open(safe_path(folder,part['file'])) as image:
            if image.format!='PNG' or list(image.size)!=part.get('size') or image.mode!='RGBA' or image.getchannel('A').getextrema()[1]==0:
                raise ValueError('Articulated layer has invalid size, transparency or empty artwork')
    for name,expected in data['hashes'].items():
        if digest(safe_path(folder,name))!=expected:raise ValueError('Articulated layer changed: '+name)
    return {'id':character['character_id'],'directory':str(folder.resolve()).replace('\\','/'),'rig':data}


def manifest(clips,timeline,plan,directory,chunk):
    from app.video_config import validate_canvas,STAGE_WIDTH,STAGE_HEIGHT
    validate_canvas(timeline['width'],timeline['height'],timeline['fps'])
    from app.rendering.hybrid import resolve_mode,spatial_direction
    environments=resolve_mode(plan)
    direction=plan.get('direction') or CartoonDirector().plan(timeline,plan,clips,plan.get('storyboard'))
    for scene in direction:
        if scene.get('clip_id'):
            scene['mouth_cues']=json.loads((directory/'cues'/f"{scene['clip_id']}.json").read_text(encoding='utf-8'))['mouthCues']
    if environments:direction=spatial_direction(direction,STAGE_WIDTH,environments)
    characters=[{**rig_description(c),'motion_version':plan.get('motion_version',2)} for c in plan['characters'].values()]
    return {'width':timeline['width'],'height':timeline['height'],'fps':timeline['fps'],
            'stage_width':STAGE_WIDTH,'stage_height':STAGE_HEIGHT,
            'schema_version':2,'render_mode':'hybrid_2_5d' if environments else '2d','hybrid_environments':environments,
            'coordinates':{'pixels_per_meter':100,'up_axis':'Y','ground_y':0,'camera':'perspective Camera3D' if environments else 'Camera2D'},
            'capture_viewports':plan.get('capture_hybrid_viewports',False),
            'start_frame':chunk['start_frame'],'end_frame':chunk['end_frame'],
            'font':str(ROOT/'assets/fonts/NotoSansBengali.ttf').replace('\\','/'),
            'characters':characters,
            'backgrounds':{bid:{'file':str(bg['directory']/bg.get('background_file','background.png')).replace('\\','/'),
                                'foreground':str(bg['directory']/bg.get('foreground_file','foreground.png')).replace('\\','/') if bg.get('foreground_file','foreground.png') in bg['file_hashes'] else None}
                           for bid,bg in plan.get('backgrounds',{plan['background']['background_id']:plan['background']}).items()},
            'direction':direction,'progress_file':str(directory/'render/godot-progress.txt').replace('\\','/'),
            'trace_file':str(directory/'render'/f"{chunk['scene_id']}-poses.jsonl").replace('\\','/')}


def encode_scene(clips,timeline,plan,directory,encoder,progress,check_cancel,chunk):
    binary=godot_binary()
    if not binary:raise RuntimeError('Godot 4 is required for the articulated renderer. Install it or explicitly choose the legacy renderer.')
    project=directory/'render/godot_project';project.mkdir(exist_ok=True)
    for area in ('scripts','scenes'):
        shutil.copytree(ROOT/'godot'/area,project/area,dirs_exist_ok=True)
    import re
    config=(ROOT/'godot/project.godot').read_text(encoding='utf-8')
    config=re.sub(r'viewport_width=\d+',f"viewport_width={timeline['width']}",config)
    config=re.sub(r'viewport_height=\d+',f"viewport_height={timeline['height']}",config)
    data=manifest(clips,timeline,plan,directory,chunk)
    if data['render_mode']=='hybrid_2_5d':config=config.replace('res://scenes/movie.tscn','res://scenes/hybrid.tscn')
    (project/'project.godot').write_text(config,encoding='utf-8')
    path=directory/'render'/f"{chunk['scene_id']}-godot.json";atomic_json(path,data)
    atomic_json(directory/'direction.json',data['direction'])
    movie=directory/'render'/f"{chunk['scene_id']}.avi"
    log_path=directory/'render'/f"{chunk['scene_id']}-godot.log"
    count=chunk['end_frame']-chunk['start_frame'];started=time.perf_counter()
    progress_path=Path(data['progress_file']);progress_path.unlink(missing_ok=True)
    command=[binary,'--path',str(project.resolve()),'--rendering-method','gl_compatibility','--position','-10000,-10000',
             '--disable-vsync','--write-movie',str(movie.resolve()),'--fixed-fps',str(timeline['fps']),
             '--quit-after',str(count+600),'--',str(path.resolve())]
    with log_path.open('wb') as log:
        process=subprocess.Popen(command,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        try:
            deadline=time.monotonic()+max(180,count*3)
            last=-1
            while process.poll() is None:
                check_cancel()
                if time.monotonic()>deadline:raise RuntimeError('Godot scene export timed out; inspect its log')
                try:done=int(progress_path.read_text());value=min(99,round(done/count*100))
                except (OSError,ValueError):value=0
                if value!=last:progress(value);last=value
                time.sleep(.1)
            message=log_path.read_text(encoding='utf-8',errors='replace')
            if process.returncode or 'SCRIPT ERROR' in message or 'Parse Error' in message or not movie.is_file():
                raise RuntimeError('Godot render failed: '+message[-5000:])
        except BaseException:
            if process.poll() is None:process.kill();process.wait(timeout=15)
            raise
    godot_seconds=time.perf_counter()-started
    output=directory/'render/scenes'/f"{chunk['scene_id']}.mp4"
    options=['-c:v',encoder,'-preset','p4','-cq','23','-b:v','0'] if encoder=='h264_nvenc' else ['-c:v','libx264','-preset','veryfast','-crf','23']
    result=run([ffmpeg_binary(),'-y','-v','error','-i',str(movie),'-an','-vf','scale=in_range=full:out_range=tv,format=yuv420p,setsar=1',*options,'-color_range','tv','-pix_fmt','yuv420p','-r',str(timeline['fps']),'-frames:v',str(count),'-movflags','+faststart',str(output)],180)
    if result.returncode:raise RuntimeError('Godot intermediate encoding failed: '+result.stderr[-2500:])
    movie.unlink(missing_ok=True);progress(100)
    return {'sprite_render_seconds':round(godot_seconds,4),'pipe_wait_seconds':0.,'stream_wall_seconds':round(time.perf_counter()-started,4),
            'encoder_drain_seconds':round(time.perf_counter()-started-godot_seconds,4),'encoder':encoder}
