"""Frame-clock audio mixing and bounded-memory vertical MP4 streaming."""
import json
import os
import subprocess
import time
import wave
import gc
from pathlib import Path
from app.engines.animation import render_scene
from app.engines.lip_sync import mouth_at
from app.hardware import encoder_capabilities, ffmpeg_binary, ffprobe_binary, run, validate_video
from app.timeline import build_timeline, FPS
from app.assets import asset_references
from app.scene_cache import PIPELINE_VERSION,digest,fingerprint,atomic_json,cached_file,split_scenes,slice_audio


def ffmpeg_available():
    return bool(ffmpeg_binary())


def timestamp(seconds):
    ms=round(seconds*1000)
    hours,ms=divmod(ms,3600000); minutes,ms=divmod(ms,60000); sec,ms=divmod(ms,1000)
    return f'{hours:02}:{minutes:02}:{sec:02},{ms:03}'


def build_audio(clips,timeline,directory,check_cancel=lambda:None):
    """48kHz PCM has exactly 2000 samples/frame at 24 fps. No AAC joins."""
    by_id={c['id']:c for c in clips}
    target=directory/'render'/'timeline.wav'
    target.parent.mkdir(exist_ok=True)
    rate=48000; written=0; samples=rate//timeline['fps']
    with wave.open(str(target),'wb') as mixed:
        mixed.setparams((1,2,rate,0,'NONE','not compressed'))

        def silence(count):
            while count:
                n=min(count,48000)
                mixed.writeframesraw(b'\0\0'*n); count-=n

        for scene in timeline['scenes']:
            check_cancel()
            start=scene['start_frame']*samples; end=scene['end_frame']*samples
            silence(start-written); written=start
            if scene['kind']=='speech':
                clip=by_id[scene['clip_id']]
                source=directory/'audio'/f"{clip['id']}.wav"
                normalized=directory/'render'/f"{clip['id']}_normalized.wav"
                result=run([ffmpeg_binary(),'-y','-v','error','-i',str(source),'-ac','1','-ar',str(rate),
                            '-af','volume=0.9','-c:a','pcm_s16le',str(normalized)],60)
                if result.returncode: raise RuntimeError('Audio normalization failed: '+result.stderr[-1500:])
                try:
                    with wave.open(str(normalized),'rb') as wav:
                        count=wav.getnframes()
                        if count>end-start:
                            raise RuntimeError('WAV duration exceeds its timeline slot; refusing to truncate speech.')
                        while chunk:=wav.readframes(24000): mixed.writeframesraw(chunk)
                        written+=count
                finally:
                    normalized.unlink(missing_ok=True)
            silence(end-written); written=end
    return target


def encode_stream(clips,timeline,plan,directory,encoder,progress,check_cancel,stage=lambda name:None,chunk=None):
    from app.video_config import validate_canvas
    validate_canvas(timeline['width'],timeline['height'],timeline['fps'])
    binary=ffmpeg_binary(); parts=directory/'render'
    by_id={clip['id']:clip for clip in clips}
    output=parts/'scenes'/f"{chunk['scene_id']}.mp4" if chunk else directory/'cartoon.mp4'
    first=chunk['start_frame'] if chunk else 0;last=chunk['end_frame'] if chunk else timeline['total_frames']
    size=(timeline['width'],timeline['height'])
    fps=timeline['fps']
    video_options=['-c:v',encoder,'-preset','p4','-cq','23','-b:v','0'] if encoder=='h264_nvenc' else ['-c:v','libx264','-preset','veryfast','-crf','23']
    command=[binary,'-y','-hide_banner','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24','-s',f'{size[0]}x{size[1]}',
             '-r',str(fps),'-i','pipe:0']
    if chunk:command+=['-an']
    else:command+=['-i',str(parts/'timeline.wav'),'-map','0:v:0','-map','1:a:0','-c:a','aac','-b:a','192k','-ar','48000']
    command += [*video_options,'-vf','setsar=1','-g','48','-pix_fmt','yuv420p','-movflags','+faststart','-frames:v',str(last-first),str(output)]
    render_seconds=pipe_seconds=0.
    log_path=parts/(f"{chunk['scene_id']}-{encoder}.log" if chunk else f'{encoder}.log')
    started=time.perf_counter()
    with log_path.open('wb') as log:
        process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=log,
                                 creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        try:
            for scene in timeline['scenes']:
                if scene['end_frame']<=first or scene['start_frame']>=last:continue
                clip=by_id.get(scene.get('clip_id'))
                cues=json.loads((directory/'cues'/f"{clip['id']}.json").read_text(encoding='utf-8'))['mouthCues'] if clip else []
                count=scene['end_frame']-scene['start_frame']
                for frame in range(max(0,first-scene['start_frame']),min(count,last-scene['start_frame'])):
                    absolute_frame=scene['start_frame']+frame
                    if absolute_frame%12==0:
                        check_cancel(); progress(round((absolute_frame-first)/(last-first)*100))
                    local=frame/fps
                    before=time.perf_counter()
                    image=render_scene({**scene,'plan':plan,'time':absolute_frame/fps,'local_time':local,
                                        'total_duration':timeline['duration_seconds'],
                                        'output_size':size,
                                        'mouth':mouth_at(cues,local) if clip and local<clip['duration_seconds'] else 'X',
                                        'caption':clip['text'] if clip and local<clip['duration_seconds'] else ''})
                    if absolute_frame==0: image.save(directory/'poster.png')
                    raw=image.tobytes()
                    render_seconds+=time.perf_counter()-before
                    before=time.perf_counter()
                    process.stdin.write(raw)
                    pipe_seconds+=time.perf_counter()-before
            if not chunk:stage('encoding')
            drain_started=time.perf_counter()
            process.stdin.close()
            check_cancel()
            if process.wait(timeout=120): raise RuntimeError('Encoder returned a nonzero exit status')
            drain_seconds=time.perf_counter()-drain_started
        except BaseException as exc:
            process.kill(); process.wait(timeout=15)
            # Read the file only after process exit, avoiding stderr pipe deadlocks.
            message=log_path.read_text(encoding='utf-8',errors='replace')[-2500:]
            if isinstance(exc,(BrokenPipeError,OSError)) or process.returncode not in (0,None) and isinstance(exc,RuntimeError):
                raise RuntimeError(f'{encoder} encoding failed: {message or str(exc)}') from exc
            raise
    return {'sprite_render_seconds':round(render_seconds,4),'pipe_wait_seconds':round(pipe_seconds,4),
            'stream_wall_seconds':round(time.perf_counter()-started,4),'encoder_drain_seconds':round(drain_seconds,4),'encoder':encoder}


def validate_scene(path,chunk,size,fps=30):
    from app.video_config import validate_canvas
    validate_canvas(*size,fps)
    result=run([ffprobe_binary(),'-v','error','-select_streams','v:0','-show_streams','-of','json',str(path)],60)
    if result.returncode:raise RuntimeError('Invalid cached scene video: '+result.stderr[-1000:])
    try:
        video=json.loads(result.stdout)['streams'][0]
        if (video['width'],video['height'],video['codec_name'],video['pix_fmt'])!=(*size,'h264','yuv420p'):raise ValueError('wrong format')
        if int(video['nb_frames'])!=chunk['end_frame']-chunk['start_frame']:raise ValueError('wrong frame count')
        if abs(float(video['duration'])-chunk['duration_seconds'])>1/fps:raise ValueError('wrong duration')
        if video['r_frame_rate']!=f'{fps}/1':raise ValueError('wrong frame rate')
    except (KeyError,ValueError,IndexError) as exc:raise RuntimeError('Scene validation failed: '+str(exc)) from exc


def render_cached_scenes(clips,timeline,plan,directory,encoder,caps,progress,check_cancel,scene_progress,warnings):
    parts=directory/'render'/'scenes';parts.mkdir(exist_ok=True)
    chunks=split_scenes(timeline)
    from app.rendering.hybrid import resolve_mode
    if plan.get('renderer')=='godot':resolve_mode(plan)
    key=fingerprint({'version':PIPELINE_VERSION,'motion_version':plan.get('motion_version',2),'timeline':timeline,'assets':asset_references(plan),
                     'renderer':plan.get('renderer','pillow'),'storyboard':plan.get('storyboard',{}),'direction':plan.get('direction'),
                     'render_mode':plan.get('render_mode','auto'),'environment_registry':digest(Path(__file__).resolve().parents[2]/'assets/environments/library.json') if (Path(__file__).resolve().parents[2]/'assets/environments/library.json').exists() else None,
                     'hybrid_environments':plan.get('hybrid_environments',{}),'hybrid_planner':digest(Path(__file__).resolve().parents[1]/'rendering/hybrid.py'),
                     'godot_adapter':digest(Path(__file__).resolve().parents[1]/'rendering/godot_adapter.py'),
                     'environment_specs':{p.name:digest(p) for p in (Path(__file__).resolve().parents[2]/'assets/environments').glob('*.json')},
                     'godot_code':{str(p.name):digest(p) for p in (Path(__file__).resolve().parents[2]/'godot/scripts').glob('*.gd')} if plan.get('renderer')=='godot' else {},
                     'plan_configuration':{kind:{cid:{k:v for k,v in c.items() if k not in ('directory','animations')} for cid,c in plan[kind].items()}
                                           for kind in ('characters',) if kind in plan},
                     'pcm':digest(directory/'render/timeline.wav'),
                     'cues':{c['id']:digest(directory/'cues'/f"{c['id']}.json") for c in clips}})
    metrics={name:0. for name in ('sprite_render_seconds','pipe_wait_seconds','stream_wall_seconds','encoder_drain_seconds')}
    metrics.update(encoder=encoder,scenes_reused=0,scenes_rendered=0)
    def publish():
        state={'pipeline_version':PIPELINE_VERSION,'key':key,'scenes':chunks}
        atomic_json(directory/'scenes.json',state);scene_progress(chunks)
    publish()
    used=[]
    for chunk in chunks:
        check_cancel()
        path=parts/f"{chunk['scene_id']}.mp4";meta=path.with_suffix('.json');pcm=path.with_suffix('.wav')
        cached=cached_file(path,meta,fingerprint({'key':key,'chunk':{k:chunk[k] for k in ('scene_id','start_frame','end_frame')}}))
        started=time.perf_counter()
        try:
            if cached and pcm.is_file() and digest(pcm)==cached.get('pcm_sha256'):
                validate_scene(path,chunk,(timeline['width'],timeline['height']),timeline['fps'])
                chunk.update(status='completed',progress=100,cached=True,processing_seconds=0.,original_processing_seconds=cached['processing_seconds'],encoder=cached['encoder'])
                metrics['scenes_reused']+=1
            else:
                chunk.update(status='rendering',cached=False);publish()
                def advance(value):
                    if value!=chunk['progress']:
                        chunk['progress']=value;publish()
                    progress(round((chunk['start_frame']+(chunk['end_frame']-chunk['start_frame'])*value/100)/timeline['total_frames']*100))
                try:
                    if plan.get('renderer')=='godot':
                        from app.rendering.godot_adapter import encode_scene
                        result=encode_scene(clips,timeline,plan,directory,encoder,advance,check_cancel,chunk)
                    else:result=encode_stream(clips,timeline,plan,directory,encoder,advance,check_cancel,chunk=chunk)
                except RuntimeError as exc:
                    check_cancel()
                    if encoder!='h264_nvenc' or not caps['libx264_available']:raise
                    if plan.get('renderer')=='godot' and not str(exc).startswith('Godot intermediate encoding failed:'):raise
                    warnings.append(f'NVENC failed during rendering; re-encoded this scene with libx264: {exc}')
                    if plan.get('renderer')=='godot':result=encode_scene(clips,timeline,plan,directory,'libx264',advance,check_cancel,chunk)
                    else:result=encode_stream(clips,timeline,plan,directory,'libx264',advance,check_cancel,chunk=chunk)
                validate_scene(path,chunk,(timeline['width'],timeline['height']),timeline['fps'])
                slice_audio(directory/'render/timeline.wav',pcm,chunk['start_frame'],chunk['end_frame'],timeline['fps'])
                seconds=round(time.perf_counter()-started,4)
                atomic_json(meta,{'key':fingerprint({'key':key,'chunk':{k:chunk[k] for k in ('scene_id','start_frame','end_frame')}}),
                                  'sha256':digest(path),'pcm_sha256':digest(pcm),'processing_seconds':seconds,'encoder':result['encoder']})
                chunk.update(status='completed',progress=100,processing_seconds=seconds,encoder=result['encoder'])
                for name in ('sprite_render_seconds','pipe_wait_seconds','stream_wall_seconds','encoder_drain_seconds'):metrics[name]+=result[name]
                metrics['scenes_rendered']+=1
            used.append(chunk['encoder']);publish()
            progress(round(chunk['end_frame']/timeline['total_frames']*100))
        except BaseException as exc:
            chunk.update(status='failed',error=str(exc),processing_seconds=round(time.perf_counter()-started,4));publish();raise
        finally:gc.collect()
    (parts/'concat.txt').write_text(''.join(f"file '{c['scene_id']}.mp4'\n" for c in chunks),encoding='utf-8')
    metrics['encoder']=used[0] if len(set(used))==1 else 'mixed H.264 (NVENC/libx264)'
    metrics['scene_count']=len(chunks)
    return metrics


def export_video(clips,directory,options,progress=lambda value:None,check_cancel=lambda:None,stage=lambda value:None,plan=None,scene_progress=lambda value:None):
    if not plan: raise ValueError('Validated scene assets are required')
    if not ffmpeg_available() or not ffprobe_binary(): raise RuntimeError('FFmpeg and ffprobe must be installed on PATH.')
    timeline=build_timeline(clips,plan,options)
    parts=directory/'render'; parts.mkdir(exist_ok=True)
    from app.subtitles import prepare as prepare_subtitles
    subtitle_track=prepare_subtitles(timeline,directory)
    from app.director import IntelligentCartoonDirector
    plan['direction']=IntelligentCartoonDirector().plan(timeline,plan,clips,plan.get('storyboard'))
    subtitles=[]
    by_id={clip['id']:clip for clip in clips}
    for scene in timeline['scenes']:
        if scene['kind']!='speech': continue
        clip=by_id[scene['clip_id']]
        scene['lip_sync']=json.loads((directory/'cues'/f"{clip['id']}.json").read_text(encoding='utf-8'))['method']
        scene['audio_start']=scene['start']; scene['audio_end']=scene['start']+clip['duration_seconds']
        cue=scene['subtitle']
        subtitles.append(f'{len(subtitles)+1}\n{timestamp(cue["start"])} --> {timestamp(cue["end"])}\n'+ '\n'.join(cue['lines'])+'\n')
    (directory/'timeline.json').write_text(json.dumps(timeline,ensure_ascii=False,indent=2),encoding='utf-8')
    (directory/'subtitles.srt').write_text('\n'.join(subtitles),encoding='utf-8')
    warnings=list(timeline['warnings'])
    metrics={}
    try:
        before=time.perf_counter()
        audio_key=fingerprint({'timeline':timeline,'audio':{c['id']:digest(directory/'audio'/f"{c['id']}.wav") for c in clips},
                               'renderer':plan.get('renderer'),'storyboard':plan.get('storyboard'),
                               'sounds':options.get('sound_effects',True),'music':options.get('music',False),'levels':options.get('audio_levels',{}),
                               'sound_library':digest(Path(__file__).resolve().parents[2]/'assets/sounds/library.json'),
                               'sound_code':{name:digest(Path(__file__).resolve().parents[1]/name) for name in ('audio/mixer.py','audio/sound_director.py','motion.py','director.py')}})
        if not cached_file(parts/'timeline.wav',parts/'audio-cache.json',audio_key):
            build_audio(clips,timeline,directory,check_cancel)
            if plan.get('renderer')=='godot' and options.get('sound_effects',True):
                from app.audio.mixer import mix
                from app.director import CartoonDirector
                direction=plan.get('direction') or CartoonDirector().plan(timeline,plan,clips,plan.get('storyboard'))
                mix(parts/'timeline.wav',direction,directory,options.get('music',False),options.get('audio_levels'))
            atomic_json(parts/'audio-cache.json',{'key':audio_key,'sha256':digest(parts/'timeline.wav')})
        metrics['audio_preparation_seconds']=round(time.perf_counter()-before,4)
        caps=encoder_capabilities()
        encoder=caps['encoder']
        if options.get('encoder')=='libx264': encoder='libx264'
        stage('rendering')
        metrics.update(render_cached_scenes(clips,timeline,plan,directory,encoder,caps,progress,check_cancel,scene_progress,warnings))
        stage('encoding')
        before=time.perf_counter()
        concat=parts/'scenes'/'concat.txt'
        result=run([ffmpeg_binary(),'-y','-v','error','-f','concat','-safe','1','-i',str(concat),'-i',str(parts/'timeline.wav'),
                    '-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','192k','-ar','48000',
                    '-t',str(timeline['duration_seconds']),'-movflags','+faststart',
                    *(['-metadata','comment=EVALUATION ONLY - demo voice commercial permissions unverified'] if options.get('evaluation_only') else []),str(directory/'cartoon.mp4')],180)
        if result.returncode:raise RuntimeError('Scene concatenation failed: '+result.stderr[-2500:])
        check_cancel();metrics['concatenation_seconds']=round(time.perf_counter()-before,4)
        progress(100)
        stage('validating')
        before=time.perf_counter()
        info=validate_video(directory/'cartoon.mp4',timeline['duration_seconds'],check_cancel,(timeline['width'],timeline['height']),timeline['fps'])
        metrics['validation_seconds']=round(time.perf_counter()-before,4)
        # Pipe writes and encoder draining overlap CPU composition. Do not claim
        # either is an independent GPU time; the report labels the overlap.
        metrics['encoding_overlap_note']='Encoding runs concurrently with CPU compositing; stream wall time and pipe wait are measured, not an isolated GPU encode time.'
        return {**info,'warnings':warnings,'render_metrics':metrics,'render_mode':plan.get('effective_render_mode','2d'),'planned_duration_seconds':timeline['duration_seconds']}
    finally:
        # PCM and completed scene encodes are intentional resumable caches.
        gc.collect()
