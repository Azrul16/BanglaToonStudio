"""One-click local Bengali sprite Shorts generator. One Uvicorn worker only."""
from __future__ import annotations
import json
import logging
import re
import shutil
import threading
import time
import uuid
import wave
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime,timezone
from pathlib import Path
from typing import Literal
from fastapi import FastAPI,HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,Field,ConfigDict
from app.assets import plan_story,asset_references,AssetError
from app.engines.story_parser import parse_story
from app.video_config import VIDEO_WIDTH,VIDEO_HEIGHT,VIDEO_FPS,VIDEO_ORIENTATION,VIDEO_ASPECT_RATIO
from app.engines.bangla_tts import synthesize,ENGINE,MODEL_ID
from app.engines.lip_sync import generate_mouth_cues,rhubarb_binary
from app.engines.video_renderer import export_video
from app.hardware import hardware_info,encoder_capabilities,ffmpeg_binary,ffprobe_binary,ResourceMonitor
from app.library import AssetLibrary
from app.review import ReviewInput,analyze,snapshot_plan,resolver,read_mappings
from app.asset_api import asset_router
from app.job_cache import cached_audio,remember_audio,cached_cues,remember_cues,remember_plan,restore_plan
from app.production import production_router,approved_speech,freeze_speech,recover_sessions
from app.screenplay import get_spoken_segments,assert_speakable
from app.autopilot import automatic_router,recover_automatic
from app.voices.studio import studio_router
from app.chat import chat_router

ROOT=Path(__file__).resolve().parents[1]
WORKSPACE=ROOT/'workspace'
OUTPUT=ROOT/'output'
WORKSPACE.mkdir(exist_ok=True); OUTPUT.mkdir(exist_ok=True)
LIBRARY=AssetLibrary(ROOT/'assets',WORKSPACE)
JOB_LOCK=threading.RLock()
JOBS={}
executor=ThreadPoolExecutor(max_workers=1)
TERMINAL={'completed','failed','cancelled'}
ACTIVE={'queued','parsing','generating_audio','lip_sync','rendering','encoding','validating','running'}
LOGGER=logging.getLogger('bangla_toon.jobs')
SAMPLE='''দৃশ্য: পুরোনো রেলস্টেশন
সময়: রাত
চরিত্র: রাহাত
[রাহাত ধীরে হাঁটে।]
বর্ণনাকারী: এক গভীর রাতে রাহাত গ্রামের পুরোনো রেলস্টেশনে দাঁড়িয়ে ছিল। হঠাৎ সে শুনতে পেল কেউ তাকে ডাকছে।

রাহাত: কে ওখানে?

অচেনা কণ্ঠ: শেষ ট্রেনটা মিস করো না।'''


def recover_jobs():
    for path in WORKSPACE.glob('*/job.json'):
        try:
            job=json.loads(path.read_text(encoding='utf-8'))
            if job['job_id']!=path.parent.name or not re.fullmatch(r'[a-f0-9]{32}',job['job_id']): continue
            if job['status'] not in TERMINAL:
                job.update(status='failed',stage='interrupted',error='The server stopped during this job. Retry to generate again.')
                path.write_text(json.dumps(job,ensure_ascii=False,indent=2),encoding='utf-8')
            JOBS[job['job_id']]=job
        except (OSError,ValueError,KeyError): continue


@asynccontextmanager
async def lifespan(app):
    global executor
    executor=ThreadPoolExecutor(max_workers=1)
    recover_jobs()
    recover_sessions(WORKSPACE)
    recover_automatic(WORKSPACE)
    try:
        yield
    finally:
        from app.voices.chatterbox_bangla import ENGINE
        with JOB_LOCK:
            for job in list(JOBS.values()):
                if job['status'] not in TERMINAL:update_job(job['job_id'],cancel_requested=True)
        ENGINE.cancel_inference()
        executor.shutdown(wait=True,cancel_futures=True)
        ENGINE.release()
        with JOB_LOCK:
            for job in list(JOBS.values()):
                if job['status'] not in TERMINAL:update_job(job['job_id'],status='failed',error='Interrupted by server shutdown; retry this job.')


app=FastAPI(title='Bangla Toon Studio',version='10.0.1-quality-repair',lifespan=lifespan)
from app.maintenance import maintenance_router
app.include_router(maintenance_router(lambda:WORKSPACE,lambda:JOB_LOCK))
from app.voices.four_voice_api import four_voice_router
app.include_router(four_voice_router(lambda:executor,lambda:WORKSPACE))
app.mount('/static',StaticFiles(directory=ROOT/'app/static'),name='static')
app.include_router(asset_router(lambda:LIBRARY))
app.include_router(production_router(lambda:LIBRARY,lambda:executor,lambda payload:create_job(payload,approved=payload)))
app.include_router(studio_router(lambda:LIBRARY))
AUTOMATIC={}
app.include_router(automatic_router(lambda:LIBRARY,lambda:executor,lambda payload:create_job(payload,approved=payload),lambda jid:get_job(jid),lambda jid:cancel_job(jid),services=AUTOMATIC))
app.include_router(chat_router(lambda:LIBRARY,AUTOMATIC,lambda jid:get_job(jid),lambda:list(JOBS.values()),lambda jid:enqueue_resume(jid),lambda jid:cancel_job(jid),lambda job:(OUTPUT/(job['job_id']+'.mp4')).is_file()))


class StoryInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    story:str=Field(min_length=1,max_length=30000)


class SpeechInput(StoryInput):
    """Compatibility API; the one-click UI always uses the fixed defaults."""
    engine:Literal['vits']='vits'
    lip_sync:Literal['auto','rhubarb','envelope']='auto'


class Cancelled(RuntimeError): pass


def update_job(job_id,**values):
    with JOB_LOCK:
        previous=dict(JOBS[job_id])
        JOBS[job_id].update(values)
        directory=WORKSPACE/job_id; directory.mkdir(parents=True,exist_ok=True)
        temporary=directory/'job.tmp'
        temporary.write_text(json.dumps(JOBS[job_id],ensure_ascii=False,indent=2),encoding='utf-8')
        temporary.replace(directory/'job.json')
        current=JOBS[job_id]
        if (current.get('status')!=previous.get('status') or current.get('completed_segments')!=previous.get('completed_segments')
                or current.get('progress',0)//5!=previous.get('progress',0)//5):
            LOGGER.info('JOB %s | %-17s | %3s%% | clips %s/%s',job_id[:8],current['status'],current.get('progress',0),
                        current.get('completed_segments',0),current.get('total_segments',0))
        if values.get('error'): LOGGER.error('JOB %s | %s',job_id[:8],values['error'])


def get_job(job_id):
    if not re.fullmatch(r'[a-f0-9]{32}',job_id): raise HTTPException(404,'Job not found')
    with JOB_LOCK:
        if job_id not in JOBS: raise HTTPException(404,'Job not found')
        return dict(JOBS[job_id])


def check_cancel(job_id):
    if get_job(job_id).get('cancel_requested'): raise Cancelled('Job cancelled')


def run_job(job_id):
    job=get_job(job_id); directory=WORKSPACE/job_id
    started=time.perf_counter(); timings={}; warnings=[]
    monitor=ResourceMonitor()

    def stage(name,progress=None):
        check_cancel(job_id)
        update_job(job_id,status=name,stage=name,**({'progress':progress} if progress is not None else {}))

    try:
        with monitor:
            stage('parsing',1)
            before=time.perf_counter()
            if job.get('resume_requested') and (directory/'snapshot-ready.json').is_file():
                plan=restore_plan(directory)
                parsed=json.loads((directory/'story.json').read_text(encoding='utf-8'))
            elif job.get('approved_review'):
                reviewed=ReviewInput(**job['approved_review'])
                analysis,parsed,plan=analyze(LIBRARY,reviewed)
                if not analysis['ready'] or analysis['review_token']!=reviewed.review_token:
                    raise AssetError('Reviewed assets or selections changed while queued. Analyze and approve this story again.')
                plan=snapshot_plan(plan,directory)
            else:
                parsed=parse_story(job['story']); plan=plan_story(parsed)
            plan['renderer']=job['options'].get('renderer','pillow')
            plan['storyboard']=job.get('storyboard',{})
            LOGGER.info('JOB %s | Parsed %s clips | characters: %s | background: %s',job_id[:8],parsed['count'],
                        ', '.join(plan['characters']) or 'off-screen only',plan['background']['background_id'])
            timings['parsing_and_assets_seconds']=time.perf_counter()-before
            references=asset_references(plan)
            warnings.extend(plan['warnings'])
            (directory/'story.json').write_text(json.dumps(parsed,ensure_ascii=False,indent=2),encoding='utf-8')
            (directory/'assets.json').write_text(json.dumps(references,ensure_ascii=False,indent=2),encoding='utf-8')
            if job.get('approved_review'):remember_plan(plan,directory)
            (directory/'audio').mkdir(exist_ok=True); (directory/'cues').mkdir(exist_ok=True)
            needed=512*1024**2+(1100*1024**2 if parsed['segments'] and not (ROOT/'models/bangla-vits/pytorch_model.pth').is_file() else 0)
            if shutil.disk_usage(directory).free<needed:
                raise RuntimeError(f'Insufficient disk space: approximately {needed/1024**2:.0f} MB of free working/model-download space is required.')
            manifest=[]
            stage('generating_audio',3)
            before=time.perf_counter()
            speech_segments=get_spoken_segments(parsed['segments'])
            for index,segment in enumerate(speech_segments):
                assert_speakable(segment)
                check_cancel(job_id)
                LOGGER.info('JOB %s | Speech %s/%s | %s | %s characters',job_id[:8],index+1,parsed['count'],segment['speaker'],len(segment['text']))
                path=directory/'audio'/f"{segment['id']}.wav"
                approved_line=next((s for s in job.get('approved_speech',[]) if s['segment_id']==segment['id']),None)
                cached=cached_audio(path,segment)
                if approved_line:
                    from app.scene_cache import digest
                    if digest(path)!=approved_line['audio_hash']:raise ValueError('Approved speech changed; refusing to synthesize a substitute')
                    duration=approved_line['duration_seconds']
                    segment={**segment,'synthesis_text':approved_line['synthesis_text'],'voice_identity':approved_line['voice']}
                elif cached is not None:
                    duration=cached
                    LOGGER.info('JOB %s | Reusing cached WAV %s',job_id[:8],path.name)
                elif job.get('source_job_id'):
                    source=WORKSPACE/job['source_job_id']/'audio'/path.name
                    shutil.copyfile(source,path)
                    with wave.open(str(path),'rb') as wav: duration=wav.getnframes()/wav.getframerate()
                else: duration=synthesize(segment['text'],path,ROOT/'models/bangla-vits')
                from app.audio.quality import require_audio
                require_audio(path,segment.get('synthesis_text',segment['text']),duration)
                remember_audio(path,segment)
                if cached is None and not approved_line:update_job(job_id,tts_runtime=ENGINE.report())
                LOGGER.info('JOB %s | WAV ready: %s | %.3fs | device: %s',job_id[:8],path.name,duration,ENGINE.device)
                manifest.append({**segment,'duration_seconds':duration,'audio_url':f"/api/jobs/{job_id}/audio/{segment['id']}"})
                update_job(job_id,clips=manifest,completed_segments=index+1,progress=3+round((index+1)/parsed['count']*30))
            timings['speech_seconds']=time.perf_counter()-before
            (directory/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
            if job['kind']=='video':
                stage('lip_sync',34)
                before=time.perf_counter()
                for index,clip in enumerate(manifest):
                    check_cancel(job_id)
                    target=directory/'cues'/f"{clip['id']}.json"
                    audio=directory/'audio'/f"{clip['id']}.wav"
                    cached=cached_cues(target,audio,job['options']['lip_sync'],clip)
                    approved_line=next((s for s in job.get('approved_speech',[]) if s['segment_id']==clip['id']),None)
                    if approved_line:
                        from app.scene_cache import digest
                        if digest(target)!=approved_line['cues_hash']:raise ValueError('Approved mouth cues changed; reapprove this dialogue')
                    elif cached:
                        LOGGER.info('JOB %s | Reusing mouth cues: %s',job_id[:8],clip['speaker'])
                        if cached.get('fallback_reason'):warnings.append(cached['fallback_reason'])
                    elif clip['kind']=='dialogue' and not clip['off_screen']:
                        cue=generate_mouth_cues(directory/'audio'/f"{clip['id']}.wav",target,job['options']['lip_sync'])
                        LOGGER.info('JOB %s | Lip sync: %s | %s | %s mouth cues',job_id[:8],clip['speaker'],cue['method'],len(cue['mouthCues']))
                        if cue.get('fallback_reason'): warnings.append(cue['fallback_reason'])
                    else:
                        target.write_text(json.dumps({'method':'off_screen','mouthCues':[]}),encoding='utf-8')
                    remember_cues(target,audio,job['options']['lip_sync'],clip)
                    update_job(job_id,progress=34+round((index+1)/len(manifest)*9))
                timings['lip_sync_seconds']=time.perf_counter()-before
                from app.voices.chatterbox_bangla import ENGINE as CHATTERBOX
                CHATTERBOX.release()
                info=export_video(manifest,directory,job['options'],
                                  progress=lambda value:update_job(job_id,progress=44+round(value*.49)),
                                  check_cancel=lambda:check_cancel(job_id),stage=stage,plan=plan,
                                  scene_progress=lambda scenes:update_job(job_id,render_scenes=scenes))
                warnings.extend(info.pop('warnings'))
                timings.update(info.pop('render_metrics'))
                OUTPUT.mkdir(exist_ok=True)
                destination=OUTPUT/f'{job_id}.mp4'
                (directory/'cartoon.mp4').replace(destination)
                update_job(job_id,video_url=f'/api/videos/{job_id}',poster_url=f'/api/jobs/{job_id}/poster',
                           subtitles_url=f'/api/jobs/{job_id}/subtitles',timeline_url=f'/api/jobs/{job_id}/timeline',**info)
            check_cancel(job_id)
            report={'schema_version':4,'job_id':job_id,'options':job['options'],'video':{k:get_job(job_id).get(k) for k in ('duration_seconds','width','height','fps','video_codec','audio_codec','validated')},
                    'tts':({'device':'not_used','speech_segments':0} if not manifest else get_job(job_id).get('tts_runtime',{'device':'approved cached speech','voices':[s['voice'] for s in job['approved_speech']]} if job.get('approved_speech') else ENGINE.report())),'sprite_renderer':'Godot 4 articulated cutout' if plan['renderer']=='godot' else 'CPU Pillow','timings':{k:round(v,4) if isinstance(v,float) else v for k,v in timings.items()},
                    'assets':references,'warnings':list(dict.fromkeys(warnings)),
                    'output':f'output/{job_id}.mp4' if job['kind']=='video' else f'workspace/{job_id}/audio',
                    'memory':{'peak_process_tree_rss_mb':monitor.peak_mb,'sample_interval_seconds':.25},'total_generation_seconds':round(time.perf_counter()-started,4)}
            if ENGINE.fallback_reason: report['warnings'].append(ENGINE.fallback_reason)
            (directory/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            update_job(job_id,status='completed',stage='completed',progress=100,warnings=report['warnings'],report=report,
                       report_url=f'/api/jobs/{job_id}/report',asset_references=references)
            LOGGER.info('JOB %s | COMPLETE | output: %s | generation: %.2fs | video: %s s | encoder: %s | peak RAM: %.1f MB',
                        job_id[:8],report['output'],report['total_generation_seconds'],report['video'].get('duration_seconds'),
                        report['timings'].get('encoder','audio only'),monitor.peak_mb)
            for warning in report['warnings']: LOGGER.warning('JOB %s | %s',job_id[:8],warning)
    except Cancelled:
        update_job(job_id,status='cancelled',stage='cancelled')
    except Exception as exc:
        LOGGER.exception('JOB %s | Generation failed',job_id[:8])
        update_job(job_id,status='failed',stage='failed',error=str(exc))
    finally:
        attempts=get_job(job_id).get('attempts',[])
        attempts.append({'seconds':round(time.perf_counter()-started,4),'status':get_job(job_id)['status']})
        update_job(job_id,attempts=attempts)


def create_job(payload,kind='video',source=None,approved=None):
    try:
        if approved:
            if approved.production_id:approved_speech(WORKSPACE,approved.production_id,payload.story)
            analysis,parsed,_=analyze(LIBRARY,approved,True)
            if not analysis['ready']: raise HTTPException(422,analysis)
            if approved.renderer=='godot' and parsed['segments'] and not approved.production_id:raise HTTPException(422,'Review and approve the spoken dialogue in the Voice panel before Godot rendering')
            if approved.production_id:
                production_data,_=approved_speech(WORKSPACE,approved.production_id,payload.story)
                signature=lambda rows:[(s['id'],s.get('event_id'),s['speaker'],s['off_screen'],s['text']) for s in rows]
                if signature(parsed['segments'])!=signature(production_data['segments']):raise HTTPException(422,'Character mappings changed after voice approval. Prepare a matching production session.')
            if approved.review_token and approved.review_token!=analysis['review_token']:
                raise HTTPException(409,{'ready':False,'issues':[{'type':'review','source_text':'Review','reason':'changed','message':'The story or selected assets changed. Analyze and review again.'}]})
            approved=ReviewInput(story=payload.story,character_mappings=analysis['character_mappings'],
                                 scenes=[{k:s[k] for k in ('scene_id','start_segment','end_segment','background_id','location_text')} for s in analysis['scenes']],
                                 review_token=analysis['review_token'],duration_mode=approved.duration_mode,video_format=approved.video_format,video_profile=approved.video_profile,
                                 renderer=approved.renderer,production_id=approved.production_id,sound_effects=approved.sound_effects,music=approved.music,script_corrections=approved.script_corrections,audio_levels=approved.audio_levels,voice_preference=approved.voice_preference,interpretation_mode=approved.interpretation_mode,semantic_ai_approved=approved.semantic_ai_approved)
        else:
            parsed=parse_story(payload.story)
            if any(e['type']=='unresolved_instruction' for e in parsed['events']):raise ValueError('Unresolved instructions require screenplay review before speech generation')
            plan_story(parsed)
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    if kind=='video' and (not ffmpeg_binary() or not ffprobe_binary()):
        raise HTTPException(422,'FFmpeg and ffprobe are required. Install both on PATH.')
    with JOB_LOCK:
        if sum(j['status'] not in TERMINAL for j in JOBS.values())>=4:
            raise HTTPException(429,'The generation queue is full. Wait for a job to finish.')
        job_id=uuid.uuid4().hex
        approved_lines=[];storyboard={}
        if approved and approved.production_id:
            directory=WORKSPACE/job_id;directory.mkdir(exist_ok=True)
            approved_lines,storyboard=freeze_speech(WORKSPACE,approved.production_id,payload.story,directory)
        JOBS[job_id]={'schema_version':3,'job_id':job_id,'status':'queued','stage':'queued','kind':kind,'story':payload.story,
                      'options':{'lip_sync':getattr(payload,'lip_sync','auto'),'engine':'vits',
                                 'duration_mode':approved.duration_mode if approved else 'shorts','video_format':approved.video_format if approved else 'auto',
                                 'video_profile':approved.video_profile if approved else 'production',
                                 'renderer':approved.renderer if approved else 'pillow'},'source_job_id':source,
                      'approved_speech':approved_lines,'storyboard':storyboard,
                      'scene_pipeline_version':1,
                      'created_at':datetime.now(timezone.utc).isoformat(),'progress':0,'completed_segments':0,'total_segments':parsed['count'],'clips':[],'warnings':[],
                      'approved_review':approved.model_dump() if approved else None}
        JOBS[job_id]['options'].update(sound_effects=approved.sound_effects if approved else False,music=approved.music if approved else False)
        JOBS[job_id]['options']['audio_levels']=approved.audio_levels if approved else {}
        evaluation_only=any(line.get('voice',{}).get('usage_mode')=='evaluation' for line in approved_lines)
        JOBS[job_id]['evaluation_only']=evaluation_only;JOBS[job_id]['options']['evaluation_only']=evaluation_only
        if evaluation_only:JOBS[job_id]['warnings'].append('EVALUATION ONLY: selected generated demo voices have unverified commercial voice-use permissions.')
        update_job(job_id)
        LOGGER.info('JOB %s | QUEUED | %s | %s clips',job_id[:8],kind,parsed['count'])
        executor.submit(run_job,job_id)
    return {'job_id':job_id,'status':'queued'}


@app.get('/')
def index(): return FileResponse(ROOT/'app/templates/chat.html')


@app.get('/studio',include_in_schema=False)
def legacy_studio():
    from fastapi.responses import RedirectResponse
    return RedirectResponse('/',status_code=307)


@app.get('/api/font')
def bengali_font(): return FileResponse(ROOT/'assets/fonts/NotoSansBengali.ttf',media_type='font/ttf')


@app.get('/api/health')
def health():
    hardware=hardware_info()
    return {'status':'ok' if hardware['ffmpeg'] and hardware['ffprobe'] and hardware['tts_installed'] else 'setup_required',
            'hardware':hardware,'ffmpeg_found':bool(hardware['ffmpeg']),'rhubarb_found':bool(rhubarb_binary()),
            'tts_installed':hardware['tts_installed'],'tts_model':MODEL_ID,'sample_story':SAMPLE,'format':{'width':VIDEO_WIDTH,'height':VIDEO_HEIGHT,'fps':VIDEO_FPS,'orientation':VIDEO_ORIENTATION,'aspect_ratio':VIDEO_ASPECT_RATIO},
            'model_cached':all((ROOT/'models/bangla-vits'/f).is_file() for f in ('config.json','pytorch_model.pth'))}


@app.post('/api/stories/parse')
def parse(payload:StoryInput):
    try:
        LIBRARY.refresh()
        return parse_story(payload.story,resolver(LIBRARY,{},read_mappings(LIBRARY)))
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc


@app.post('/api/generate',status_code=202)
def generate_video(payload:ReviewInput): return create_job(payload,approved=payload)


@app.post('/api/video/generate',status_code=202)
def generate_legacy(payload:SpeechInput): return create_job(payload)


@app.post('/api/audio/generate',status_code=202)
def generate_audio(payload:SpeechInput): return create_job(payload,'audio')


@app.get('/api/jobs')
def list_jobs():
    with JOB_LOCK:
        return [{k:v for k,v in j.items() if k not in ('story','report','asset_references')} for j in sorted(JOBS.values(),key=lambda j:j['created_at'],reverse=True) if j.get('schema_version')==3]


@app.get('/api/jobs/{job_id}')
def job_status(job_id:str): return get_job(job_id)


@app.post('/api/jobs/{job_id}/cancel')
def cancel_job(job_id:str):
    with JOB_LOCK:
        job=get_job(job_id)
        if job['status'] in TERMINAL: raise HTTPException(409,'Job is already finished')
        update_job(job_id,cancel_requested=True,**({'status':'cancelled','stage':'cancelled'} if job['status']=='queued' else {}))
    return {'status':'cancellation_requested'}


@app.post('/api/jobs/{job_id}/retry',status_code=202)
def retry_job(job_id:str):
    job=get_job(job_id)
    if job['status'] not in ('failed','cancelled'): raise HTTPException(409,'Only failed/cancelled jobs can be retried')
    approved=ReviewInput(**job['approved_review']) if job.get('approved_review') else None
    return create_job(SpeechInput(story=job['story'],lip_sync=job['options'].get('lip_sync','auto')),job['kind'],job.get('source_job_id'),approved)


def enqueue_resume(job_id,scene_id=None):
    with JOB_LOCK:
        job=get_job(job_id)
        if job['status'] not in ('failed','cancelled'):raise HTTPException(409,'Only failed or cancelled jobs can resume')
        if not job.get('scene_pipeline_version'):raise HTTPException(409,'This older job needs a fresh generation')
        if sum(j['status'] not in TERMINAL for j in JOBS.values())>=4:raise HTTPException(429,'The generation queue is full')
        if scene_id:
            if not re.fullmatch(r'render_\d{4}',scene_id) or not any(s['scene_id']==scene_id for s in job.get('render_scenes',[])):
                raise HTTPException(404,'Render scene not found')
            (WORKSPACE/job_id/'render/scenes'/f'{scene_id}.json').unlink(missing_ok=True)
        update_job(job_id,status='queued',stage='queued',progress=0,cancel_requested=False,error=None,
                   resume_requested=True,validated=False)
        executor.submit(run_job,job_id)
    return {'job_id':job_id,'status':'queued'}


@app.post('/api/jobs/{job_id}/resume',status_code=202)
def resume_job(job_id:str):return enqueue_resume(job_id)


@app.post('/api/jobs/{job_id}/scenes/{scene_id}/retry',status_code=202)
def retry_scene(job_id:str,scene_id:str):return enqueue_resume(job_id,scene_id)


@app.post('/api/jobs/{job_id}/render',status_code=202)
def render_audio(job_id:str):
    job=get_job(job_id)
    if job['status']!='completed': raise HTTPException(409,'Wait for audio generation to finish')
    return create_job(SpeechInput(story=job['story'],lip_sync=job['options'].get('lip_sync','auto')),'video',job_id)


@app.get('/api/videos/{job_id}')
def video(job_id:str,download:bool=False):
    job=get_job(job_id)
    if job['status']!='completed' or not job.get('validated'): raise HTTPException(404,'Validated video not ready')
    path=OUTPUT/f'{job_id}.mp4'
    if not path.is_file(): raise HTTPException(404,'Video file missing')
    return FileResponse(path,media_type='video/mp4',filename=f'bangla-toon-{"evaluation-" if job.get("evaluation_only") else ""}{job_id[:8]}.mp4' if download else None)


@app.get('/api/jobs/{job_id}/audio/{segment_id}')
def audio_clip(job_id:str,segment_id:str):
    get_job(job_id)
    if not re.fullmatch(r'segment_[0-9]+',segment_id): raise HTTPException(400,'Invalid segment ID')
    path=WORKSPACE/job_id/'audio'/f'{segment_id}.wav'
    if not path.is_file(): raise HTTPException(404,'Audio not ready')
    return FileResponse(path,media_type='audio/wav')


@app.get('/api/jobs/{job_id}/{artifact}')
def artifact(job_id:str,artifact:str):
    job=get_job(job_id)
    if artifact=='video':
        if job.get('schema_version')==3: return video(job_id)
        legacy=WORKSPACE/job_id/'cartoon.mp4'
        if job['status']=='completed' and legacy.is_file(): return FileResponse(legacy,media_type='video/mp4')
    files={'poster':('poster.png','image/png'),'subtitles':('subtitles.srt','application/x-subrip'),
           'timeline':('timeline.json','application/json'),'report':('report.json','application/json')}
    if artifact not in files or job['status']!='completed': raise HTTPException(404,'Artifact not ready')
    name,media=files[artifact]; path=WORKSPACE/job_id/name
    if not path.is_file(): raise HTTPException(404,'Artifact missing')
    return FileResponse(path,media_type=media)
