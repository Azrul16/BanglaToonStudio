"""Paste-to-cartoon orchestration on the existing single heavy worker."""
import json
import logging
import re
import shutil
import threading
import time
import uuid
from datetime import datetime,timezone
from fastapi import APIRouter,HTTPException
from pydantic import Field
from app.review import ReviewInput,analyze
from app.production import prepare_session,read_session,approved_speech,generate_session_take,TakeInput,LOCK
from app.screenplay import assert_speakable
from app.scene_cache import atomic_json,fingerprint,digest
from app.voices import voice_manager as voices
from app.voices.base import VoiceIdentity
from app.voices.studio import configured
from app.voices.assignment import resolve_voices

LOGGER=logging.getLogger('bangla_toon.automatic')
AUTO_LOCK=threading.RLock()
FINISHED={'completed','failed','cancelled'}


class AutomaticInput(ReviewInput):
    renderer:str='godot'
    music:bool=True
    paid_approved:bool=False
    approval_token:str|None=None
    request_id:str=Field(default_factory=lambda:uuid.uuid4().hex,pattern=r'^[a-f0-9]{32}$')


def review_input(payload):
    return ReviewInput(**payload.model_dump(exclude={'paid_approved','approval_token','request_id'}))


def speech_key(lines):
    return fingerprint([{k:s.get(k) for k in ('speaker','off_screen','synthesis_text','voice','emotion')} for s in lines])


def line_cache(library,lines,exclude=None):
    wanted={speech_key([line]) for line in lines};found={}
    for path in sorted((library.storage/'production').glob('*/session.json'),key=lambda p:p.stat().st_mtime,reverse=True):
        if path.parent==exclude:continue
        try:
            data=json.loads(path.read_text(encoding='utf-8'))
            if data.get('schema_version',0)<2:continue
            for line in data['segments']:
                key=speech_key([line])
                if key not in wanted or key in found or not line.get('approved_take'):continue
                assert_speakable(line)
                take=next(t for t in line['takes'] if t['take_id']==line['approved_take'])
                if take['status']!='completed' or take['line_revision']!=line['revision'] or take['voice']!=line['voice'] or take['synthesis_text']!=line['synthesis_text'] or take['emotion']!=line['emotion']:continue
                wav=path.parent/'audio'/(take['take_id']+'.wav');cues=wav.with_suffix('.json')
                if digest(wav)!=take['audio_hash'] or digest(cues)!=take['cues_hash']:continue
                found[key]={'session_id':data['session_id'],'directory':path.parent,'take':take}
        except (ValueError,KeyError,OSError,StopIteration):continue
    return {i:found[speech_key([line])] for i,line in enumerate(lines) if speech_key([line]) in found}


def make_plan(library,payload):
    review=review_input(payload);report,parsed,_=analyze(library,review,True)
    settings,voice_issues=resolve_voices(library,parsed['segments'],payload.voice_preference);report['issues'].extend(voice_issues)
    dictionary=voices.dictionary(library.storage)
    lines=[];usage=[]
    for segment in parsed['segments']:
        assert_speakable(segment)
        selected=settings.get(segment['speaker'])
        if selected is None:
            lines.append({**segment,'voice':None,'synthesis_text':voices.spoken_text(segment['text'],dictionary)})
            usage.append({'paid':False,'characters':0,'spoken_characters':0,'estimated_usd':None});continue
        voice=VoiceIdentity(**selected)
        text=voices.spoken_text(segment['text'],dictionary,preserve_spelling=voice.provider=='chatterbox_bangla')
        line={**segment,'voice':voice.model_dump(),'synthesis_text':text}
        lines.append(line)
        if not configured(voice.provider):
            report['issues'].append({'type':'voice','source_text':segment['speaker_name'],'segment_id':segment['id'],'reason':'credentials','message':f'{voice.provider} is selected but its server credentials are missing. Select a configured voice; no fallback was made.'})
        usage.append(voices.usage(text,voice,segment['emotion']))
    cached_lines=line_cache(library,lines) if lines else {}
    cached_ids={lines[i]['id'] for i in cached_lines}
    report['issues']=[issue for issue in report['issues'] if not (issue['type']=='voice' and issue['reason']=='credentials' and issue.get('segment_id') in cached_ids)]
    report['ready']=not report['issues']
    for i,item in enumerate(usage):item['cached']=i in cached_lines
    paid=[u for u in usage if u['paid'] and not u['cached']]
    cached=next(iter(cached_lines.values()))['session_id'] if cached_lines and len(cached_lines)==len(lines) else None
    # Token binds the entire reviewed plan, exact provider submissions and sound options.
    token=fingerprint({'review':report.get('review_token'),'speech':lines,'usage':usage})
    return {'review':report,'lines':lines,'usage':usage,'paid':bool(paid),'approval_token':token,'cached_production_id':cached,'cached_segments':len(cached_lines),
            'spoken_characters':sum(u['spoken_characters'] for u in usage),'characters':sum(u['characters'] for u in paid),
            'estimated_usd':sum(u['estimated_usd'] for u in paid) if paid and all(u['estimated_usd'] is not None for u in paid) else None,
            'voice_note':'Chatterbox uses saved category references in their declared evaluation or production mode. Missing references block generation. The shared VITS voice is available only when explicitly selected.'}


def reuse_approved(library,data,directory):
    cache=line_cache(library,data['segments'],exclude=directory)
    for index,previous in cache.items():
        line=data['segments'][index];take=previous['take']
        for suffix in ('.wav','.json'):
            source=previous['directory']/'audio'/(take['take_id']+suffix)
            shutil.copyfile(source,directory/'audio'/source.name)
        line['takes']=[{**take,'line_revision':line['revision']}];line['approved_take']=take['take_id']
        line['approval_source']='reused_approved_audio'
        line['takes'][0]['audio_url']=f"/api/production/{data['session_id']}/takes/{take['take_id']}/audio"
    data.update(ready=all(s.get('approved_take') for s in data['segments']),reused_sessions=sorted({s['session_id'] for s in cache.values()}))
    atomic_json(directory/'session.json',data)
    return len(cache)


def recover_automatic(storage):
    for path in (storage/'automatic').glob('*/automatic.json'):
        try:
            data=json.loads(path.read_text(encoding='utf-8'))
            if data['status'] not in FINISHED|{'needs_audio_review'} and not data.get('job_id'):
                data.update(status='failed',error='Studio stopped during automatic preparation. Completed approved takes remain cached. No paid retry was made.')
                atomic_json(path,data)
        except (ValueError,OSError,KeyError):continue


def automatic_router(get_library,get_executor,create_render,get_render,cancel_render=None,services=None):
    router=APIRouter()
    def path(aid):
        if not re.fullmatch('[a-f0-9]{32}',aid):raise HTTPException(404,'Automatic production not found')
        return get_library().storage/'automatic'/aid/'automatic.json'
    def read(aid):
        with AUTO_LOCK:
            for attempt in range(3):
                try:return json.loads(path(aid).read_text(encoding='utf-8'))
                except (OSError,ValueError):
                    if attempt==2:raise HTTPException(404,'Automatic production not found') from None
                    time.sleep(.02)
    def update(aid,**values):
        with AUTO_LOCK:
            data=read(aid);data.update(values);atomic_json(path(aid),data)
        LOGGER.info('AUTO %s | %s | %s',aid[:8],data['status'],data.get('message',''))
        return data
    def cancelled(aid):
        if read(aid).get('cancel_requested'):raise InterruptedError('Automatic generation cancelled')

    def work(aid,payload,plan):
        started=time.perf_counter();library=get_library()
        try:
            cancelled(aid);update(aid,status='preparing_speech',message='Preparing saved voices and exact dialogue')
            # Fresh validated asset review; no unreviewed speech can enter the queue.
            fresh=make_plan(library,payload)
            if not fresh['review']['ready'] or fresh['approval_token']!=plan['approval_token']:raise ValueError('Story assets, voices or pricing changed while queued. Generate again to review the current plan.')
            data=prepare_session(library,review_input(payload));sid=data['session_id'];_,directory=read_session(library.storage,sid)
            update(aid,production_id=sid,total_segments=len(data['segments']),completed_segments=0)
            reused=reuse_approved(library,data,directory)
            for index,line in enumerate(data['segments']):
                cancelled(aid)
                if line.get('approved_take'):continue
                assert_speakable(line)
                estimate=voices.usage(line['synthesis_text'],VoiceIdentity(**line['voice']),line['emotion'])
                if estimate['paid'] and not payload.paid_approved:raise ValueError('Paid speech was not approved')
                tid=uuid.uuid4().hex
                with LOCK:
                    current,_=read_session(library.storage,sid);item=current['segments'][index]
                    item['takes'].append({'take_id':tid,'status':'queued','voice':item['voice'],'synthesis_text':item['synthesis_text'],'line_revision':item['revision'],'emotion':item['emotion']})
                    atomic_json(directory/'session.json',current)
                update(aid,status='generating_speech',message=f"Generating dialogue {index+1}/{len(data['segments'])}",completed_segments=index)
                generate_session_take(library,sid,line['id'],tid,TakeInput(paid_approved=payload.paid_approved,approval_token=estimate['approval_token']))
                with LOCK:
                    current,_=read_session(library.storage,sid);item=current['segments'][index];take=item['takes'][-1]
                    if take['status']!='completed':raise ValueError(take.get('error','Speech generation failed'))
                    item['approved_take']=tid;item['approval_source']='automatic_paid_batch' if estimate['paid'] else 'automatic_local'
                    current['ready']=all(s.get('approved_take') for s in current['segments']);atomic_json(directory/'session.json',current)
                update(aid,completed_segments=index+1)
            cancelled(aid)
            current,_=read_session(library.storage,sid)
            if any(s['voice']['provider']=='chatterbox_bangla' for s in current['segments']):
                review=audio_review(current,directory)
                update(aid,status='needs_audio_review',audio_review=review,reused_speech=reused,completed_segments=len(data['segments']),
                    preparation_seconds=round(time.perf_counter()-started,3),message='Listen to Bengali speech before rendering. Signal checks do not approve pronunciation.')
                return
            job=create_render(ReviewInput(**{**current['review'],'production_id':sid}))
            update(aid,status='rendering',job_id=job['job_id'],reused_speech=reused,completed_segments=len(data['segments']),
                   message='Animating, directing sound and assembling the cartoon',preparation_seconds=round(time.perf_counter()-started,3))
            if read(aid).get('cancel_requested') and cancel_render:cancel_render(job['job_id'])
        except InterruptedError as exc:update(aid,status='cancelled',error=str(exc))
        except Exception as exc:
            LOGGER.exception('Automatic production failed')
            update(aid,status='cancelled' if read(aid).get('cancel_requested') else 'failed',error=str(getattr(exc,'detail',exc)),preparation_seconds=round(time.perf_counter()-started,3))

    @router.post('/api/automatic/plan')
    def plan(payload:AutomaticInput):
        try:return make_plan(get_library(),payload)
        except ValueError as exc:raise HTTPException(422,str(exc)) from None

    @router.post('/api/automatic/generate',status_code=202)
    def generate(payload:AutomaticInput):
        with AUTO_LOCK:
            file=path(payload.request_id)
            if file.is_file():
                existing=read(payload.request_id)
                if existing['input_hash']!=fingerprint(review_input(payload).model_dump()):raise HTTPException(409,'Request ID belongs to a different story')
                return existing
            try:plan=make_plan(get_library(),payload)
            except ValueError as exc:raise HTTPException(422,str(exc)) from None
            if not plan['review']['ready']:raise HTTPException(422,plan['review'])
            if plan['paid'] and (not payload.paid_approved or payload.approval_token!=plan['approval_token']):
                raise HTTPException(409,{'message':'Approve this exact batch before paid speech generation','plan':plan})
            # One automatic production at a time, with idempotent request IDs.
            for other in file.parent.parent.glob('*/automatic.json'):
                row=json.loads(other.read_text(encoding='utf-8'))
                if row['status'] not in FINISHED|{'needs_audio_review'}:
                    if row.get('job_id') and get_render(row['job_id'])['status'] in FINISHED:continue
                    raise HTTPException(429,'Another cartoon is being generated. Wait for it to finish.')
            file.parent.mkdir(parents=True,exist_ok=True)
            data={'automatic_id':payload.request_id,'status':'queued','input_hash':fingerprint(review_input(payload).model_dump()),'created_at':datetime.now(timezone.utc).isoformat(),
                  'message':'Analyzing characters, scenes and dialogue','voice_note':plan['voice_note'],'spoken_preview':[{'speaker':s['speaker'],'text':s['synthesis_text']} for s in plan['lines']]}
            atomic_json(file,data);get_executor().submit(work,payload.request_id,payload,plan)
            return data

    @router.get('/api/automatic/{aid}')
    def status(aid:str):
        data=read(aid)
        if data.get('job_id'):
            job=get_render(data['job_id']);data['render']=job
            if job['status'] in FINISHED:data=update(aid,status=job['status'],error=job.get('error'),job_id=job['job_id']);data['render']=job
        return data

    def audio_review(current,directory):
        from app.audio.quality import require_audio
        clips=[]
        for line in current['segments']:
            take=next(t for t in line['takes'] if t['take_id']==line['approved_take'])
            path=directory/'audio'/(take['take_id']+'.wav')
            if digest(path)!=take['audio_hash']:raise ValueError('Speech changed since preparation')
            checks=require_audio(path,line['synthesis_text'],take['duration_seconds'])
            clips.append({'segment_id':line['id'],'text':line['synthesis_text'],'speaker':line['speaker'],'sha256':take['audio_hash'],
                'audio_url':take['audio_url'],'checks':checks})
        return {'clips':clips,'token':fingerprint(clips),'human_approved':False}

    @router.post('/api/automatic/{aid}/approve-audio')
    def approve_audio(aid:str,payload:dict):
        with AUTO_LOCK:
            data=read(aid)
            if data['status']!='needs_audio_review' or data.get('cancel_requested'):raise HTTPException(409,'Speech is not awaiting review')
            current,directory=read_session(get_library().storage,data['production_id'])
            try:review=audio_review(current,directory)
            except (OSError,ValueError) as exc:raise HTTPException(409,'Speech changed or failed quality checks; prepare and review it again') from exc
            if payload.get('listened') is not True or payload.get('token')!=review['token']:raise HTTPException(409,'Listen and approve these exact current clips first')
            from app.voices.assignment import resolve_voices
            identities,issues=resolve_voices(get_library(),current['segments'],current['review'].get('voice_preference','saved'))
            if issues or any(line['voice']!=identities.get(line['speaker']) for line in current['segments']):
                raise HTTPException(409,'Voice reference or processing settings changed. Prepare current speech and listen again.')
            job=create_render(ReviewInput(**{**current['review'],'production_id':data['production_id']}))
            return update(aid,status='rendering',job_id=job['job_id'],audio_review={**review,'human_approved':True},message='Rendering reviewed speech')

    @router.post('/api/automatic/{aid}/cancel')
    def cancel(aid:str):
        data=update(aid,cancel_requested=True)
        if data.get('status') in ('queued','needs_audio_review'):data=update(aid,status='cancelled')
        if data.get('status')=='generating_speech':
            from app.voices.chatterbox_bangla import ENGINE
            ENGINE.cancel_inference()
        if data.get('job_id') and get_render(data['job_id'])['status'] not in FINISHED and cancel_render:cancel_render(data['job_id'])
        return data
    if services is not None:services.update(start=generate,status=status,cancel=cancel,approve_audio=approve_audio)
    return router
