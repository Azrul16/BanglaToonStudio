"""Persistent conversational jobs over the existing local production pipeline."""
import asyncio
import copy
import json
import logging
import re
import threading
import uuid
from datetime import datetime,timezone
from typing import Literal
from fastapi import APIRouter,HTTPException,Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel,Field,ConfigDict,model_validator
from app.autopilot import AutomaticInput,make_plan
from app.scene_cache import atomic_json,fingerprint
from app.screenplay import EventCorrection
from app.voices.base import VoiceIdentity
from app.voices import voice_manager as voices
from app.voices.studio import configured,category_for
from app.director import ACTIONS,SHOTS

LOCK=threading.RLock();LOGGER=logging.getLogger('bangla_toon.chat')
TERMINAL={'completed','failed','cancelled','needs_input','needs_payment','needs_audio_review','waiting'}


class Preferences(BaseModel):
    model_config=ConfigDict(extra='forbid')
    format:Literal['shorts','mini']='shorts' # Duration only; orientation is fixed.
    voice_preference:Literal['saved','vits','elevenlabs','azure','chatterbox_bangla']='saved'
    music:bool=True
    interpretation_mode:Literal['rules','assisted']='rules'
    semantic_ai_approved:bool=False

    @model_validator(mode='after')
    def consent(self):
        if self.interpretation_mode=='assisted':
            if not self.semantic_ai_approved:raise ValueError('Explicitly accept story sharing and possible costs first')
        return self


class Prompt(BaseModel):
    model_config=ConfigDict(extra='forbid')
    prompt:str=Field(min_length=1,max_length=30000)
    request_id:str=Field(default_factory=lambda:uuid.uuid4().hex,pattern=r'^[a-f0-9]{32}$')


class VoiceChoice(BaseModel):
    speaker_id:str
    voice:VoiceIdentity
    accept_alternative:bool=False


class Answer(BaseModel):
    model_config=ConfigDict(extra='forbid')
    character_mappings:dict[str,str]=Field(default_factory=dict)
    backgrounds:dict[str,str]=Field(default_factory=dict)
    corrections:dict[str,EventCorrection]=Field(default_factory=dict)
    voices:list[VoiceChoice]=Field(default_factory=list)
    paid_approved:bool=False
    approval_token:str|None=None
    revision:int|None=None


def now():return datetime.now(timezone.utc).isoformat()


def preferences(storage):
    path=storage/'preferences.json'
    if not path.exists():return Preferences()
    data=json.loads(path.read_text(encoding='utf-8'))
    if data.get('format')=='vertical_mini':
        backup=storage/'preferences-before-portrait-only.json'
        if not backup.exists():atomic_json(backup,data)
        data={**data,'format':'mini'};atomic_json(path,data)
    return Preferences.model_validate(data)


def safe_error(error):
    text=str(error).lower()
    if any(word in text for word in ('voice','speech','provider','tts','credential')):return 'বাংলা কণ্ঠ তৈরি করা যায়নি। সংযোগ বা সংরক্ষিত কণ্ঠটি পরীক্ষা করে আবার চেষ্টা করুন।'
    if any(word in text for word in ('rig','asset','sprite','background')):return 'এই দৃশ্যের প্রয়োজনীয় চরিত্র বা background পাওয়া যায়নি।'
    return 'কার্টুন তৈরি করতে সমস্যা হয়েছে। সংরক্ষিত কাজটি আবার চালাতে পারেন।'


def chat_router(get_library,automatic,get_job,get_jobs,resume_job,cancel_job,video_exists):
    router=APIRouter()
    def folder():
        root=get_library().storage/'conversations';root.mkdir(exist_ok=True);return root
    def path(cid):
        if not re.fullmatch('[a-f0-9]{32}',cid):raise HTTPException(404,'Conversation not found')
        return folder()/(cid+'.json')
    def read(cid):
        try:return json.loads(path(cid).read_text(encoding='utf-8'))
        except (OSError,ValueError):raise HTTPException(404,'Conversation not found') from None
    def save(data):
        data['updated_at']=now();atomic_json(path(data['id']),data)
    def public(data):
        return {key:data.get(key) for key in ('id','prompt','created_at','updated_at','status','stage','progress','speech_completed','speech_total',
                'scene_completed','scene_total','scene_times','processing_seconds','audio_review','message','video_url','video_path','job_id','duration_seconds','width','height','clarifications','payment','selected_assets','settings','revision','evaluation_only')}

    def render_state(data,job):
        status=job['status'];data.update(status=status,stage=job.get('stage',status),job_id=job['job_id'],progress=job.get('progress'),
            scene_completed=sum(s['status']=='completed' for s in job.get('render_scenes',[])),scene_total=len(job.get('render_scenes',[])))
        data['scene_times']=[{'scene_id':s['scene_id'],'seconds':s.get('processing_seconds'),'cached':s.get('cached',False)} for s in job.get('render_scenes',[]) if s['status']=='completed']
        data['processing_seconds']=job.get('report',{}).get('total_generation_seconds')
        if status=='completed':
            if not job.get('validated') or not job.get('video_url') or not video_exists(job):
                data.update(status='failed',message='তৈরি ভিডিওটি যাচাই করা যায়নি। আবার চেষ্টা করুন।');return
            references=job.get('asset_references',{})
            data.update(video_url=job['video_url'],video_path=job.get('report',{}).get('output'),duration_seconds=job['duration_seconds'],width=job['width'],height=job['height'],
                message='আপনার কার্টুন তৈরি।',selected_assets={'characters':[r['character_id'] for r in references.get('characters',[])],
                    'backgrounds':[r['background_id'] for r in references.get('backgrounds',[])]})
        elif status=='failed':data['message']=safe_error(job.get('error',''))
        elif status=='cancelled':data['message']='কার্টুন তৈরি বন্ধ করা হয়েছে।'

    def refresh(cid):
        with LOCK:
            data=read(cid);before=fingerprint(data)
            if data['status']=='needs_input' and any(q.get('kind')=='reference' for q in data.get('clarifications',[])):
                from app.voices.four_voices import category_for as voice_category
                grouped={};retained=[]
                for question in data['clarifications']:
                    if question.get('kind')!='reference':retained.append(question);continue
                    category=voice_category(question['key']);label=category.replace('_',' ').title()
                    grouped[category]={'kind':'category_reference','key':'category-'+category,'source':label,'question':label+' voice is not configured. Open Default Cartoon Voices in Settings.'}
                data['clarifications']=retained+list(grouped.values());data['revision']+=1
            if data['status']=='needs_input' and any(q.get('kind')=='category_reference' for q in data.get('clarifications',[])):
                from app.voices.four_voices import reference as category_reference,configuration as voice_configuration
                remaining=[]
                for question in data['clarifications']:
                    if question.get('kind')!='category_reference':remaining.append(question);continue
                    try:category_reference(question['key'].removeprefix('category-'))
                    except (ValueError,OSError):remaining.append(question)
                if len(remaining)!=len(data['clarifications']):
                    data['clarifications']=remaining;data['revision']+=1
                    if not remaining:data.update(status='waiting',message='Saved category voices are ready. Resume this story when you want to generate it.',evaluation_only=voice_configuration().get('mode')=='evaluation')
            try:
                if data.get('job_id') and (data.get('direct_job') or data['status']=='completed'):render_state(data,get_job(data['job_id']))
                elif data.get('automatic_id') and data['status'] not in ('needs_input','needs_payment','waiting'):
                    state=automatic['status'](data['automatic_id'])
                    data.update(status=state['status'],stage=state['status'],speech_completed=state.get('completed_segments',0),speech_total=state.get('total_segments',0))
                    if state.get('audio_review'):data['audio_review']=state['audio_review']
                    if state.get('render'):render_state(data,state['render'])
                    elif state['status']=='failed':data['message']=safe_error(state.get('error',''))
                    elif state['status']=='cancelled':data['message']='কার্টুন তৈরি বন্ধ করা হয়েছে।'
            except HTTPException as exc:
                LOGGER.warning('Conversation %s lookup failed: %s',cid,exc.detail)
                data.update(status='failed',message='সংরক্ষিত কাজটি পাওয়া যায়নি। আবার চেষ্টা করুন।')
            if before!=fingerprint(data):save(data)
            return data

    def clarifications(plan):
        library=get_library().refresh();report=plan['review'];items=[]
        ready=[{'value':cid,'label':r['name_bn']+' / '+r['name_en']} for cid,r in library.characters.items() if r['status']=='ready']
        backgrounds=[{'value':bid,'label':r['name_bn']} for bid,r in library.backgrounds.items() if r['status']=='ready']
        for row in report['characters']:
            if row['status']!='ready':items.append({'kind':'character','key':row['key'],'source':row['speaker_text'],
                'question':'এই চরিত্রটি ব্যবহার করা যাচ্ছে না। কোন বিদ্যমান চরিত্র বোঝাতে চেয়েছেন?',
                'options':sorted(ready,key=lambda r:r['value'] not in row['candidates'])+[{'value':'unknown_voice','label':'শুধু পর্দার বাইরের কণ্ঠ'}]})
        for row in report['scenes']:
            if row['status']!='ready' or not row['background_id']:items.append({'kind':'background','key':row['scene_id'],'source':row['location_text'],
                'question':'এই দৃশ্যের জন্য কোন background ব্যবহার করব?',
                'options':sorted(backgrounds,key=lambda r:r['value'] not in row['candidates'])})
        seen=set()
        for issue in report['issues']:
            if issue['type']=='voice':
                if issue.get('reason')=='category_reference_required':
                    key='category-'+issue['category']
                    if key not in seen:seen.add(key);items.append({'kind':'category_reference','key':key,'source':issue['source_text'],'question':issue['message']})
                    continue
                segment=next((s for s in plan['lines'] if s['id']==issue.get('segment_id')),None)
                cid=issue.get('speaker_id') or (segment['speaker'] if segment else None)
                if cid and cid not in seen:
                    if issue.get('reason')=='reference_required':
                        seen.add(cid);items.append({'kind':'reference','key':cid,'source':issue['source_text'],'question':issue['message']});continue
                    seen.add(cid);items.append({'kind':'voice','key':cid,'source':issue['source_text'],
                        'category':category_for(library.characters[cid]) if cid in library.characters else 'male',
                        'question':'এই চরিত্রের জন্য একবার একটি উপলব্ধ কণ্ঠ বেছে নিন। এটি পরের কার্টুনেও মনে থাকবে।',
                        'providers':[{'value':p,'label':{'vits':'Offline voice','elevenlabs':'ElevenLabs','azure':'Azure Speech'}[p]} for p in ('elevenlabs','azure','vits') if configured(p)]})
            elif issue.get('event_id') and issue['event_id'] not in seen:
                seen.add(issue['event_id']);event=next(e for e in report['events'] if e['event_id']==issue['event_id'])
                items.append({'kind':'instruction','key':issue['event_id'],'source':event['source_text'],'source_text':event['source_text'],
                    'text':event['text'],'question':'এই লাইনটি কীভাবে ব্যবহার করব?',
                    'characters':ready,'actions':list(ACTIONS),'shots':[s for s in SHOTS if s!='over_shoulder'],
                    'options':[{'value':key,'label':label} for key,label in [('ignore','বাদ দিন'),('scene_description','দৃশ্যের বর্ণনা'),('action','চরিত্রের কাজ'),('dialogue','চরিত্রের সংলাপ'),('narration','বর্ণনাকারীর কথা'),('camera','ক্যামেরার নির্দেশ'),('sound_effect','শব্দের নির্দেশ')]]})
        if not items:
            items.append({'kind':'notice','key':'setup','question':'প্রয়োজনীয় স্থানীয় উপকরণ পাওয়া যায়নি। ইনস্টলেশন বা সংরক্ষিত সেটিংস পরীক্ষা করুন।'})
        return items

    def advance(data,answer=None):
        try:
            payload=AutomaticInput(**data['payload']);plan=make_plan(get_library(),payload)
            data['evaluation_only']=any((line.get('voice') or {}).get('usage_mode')=='evaluation' for line in plan['lines'])
            data['review_scenes']=plan['review']['scenes'];data['clarifications']=[];data['payment']=None
            if not plan['review']['ready']:
                data.update(status='needs_input',message='কার্টুনটি তৈরির আগে একটি বিষয় নিশ্চিত করুন।',clarifications=clarifications(plan));save(data);return data
            if plan['paid']:
                token=answer.approval_token if answer else None
                if not answer or not answer.paid_approved or token!=plan['approval_token']:
                    data.update(status='needs_payment',message='এই কণ্ঠ তৈরি করতে paid speech ব্যবহার হবে।',payment={
                        'approval_token':plan['approval_token'],'characters':plan['characters'],'estimated_usd':plan['estimated_usd'],
                        'lines':[{'speaker':s['speaker_name'],'text':s['synthesis_text'],'cached':plan['usage'][i]['cached']} for i,s in enumerate(plan['lines'])]})
                    save(data);return data
                payload.paid_approved=True;payload.approval_token=token
            result=automatic['start'](payload)
            data.update(automatic_id=result['automatic_id'],status=result['status'],stage=result['status'],message='আপনার গল্প থেকে কার্টুন তৈরি হচ্ছে…')
            data.setdefault('attempts',[]).append(result['automatic_id']);save(data);return data
        except HTTPException as exc:
            if exc.status_code==429:data.update(status='waiting',message='আরেকটি কার্টুন তৈরি হচ্ছে। সেটি শেষ হলে এখান থেকেই আবার চালাতে পারবেন।')
            else:
                LOGGER.warning('Chat production rejected: %s',exc.detail)
                data.update(status='failed',message=safe_error(exc.detail))
        except Exception:
            LOGGER.exception('Conversation generation failed')
            data.update(status='failed',message='গল্পটি বিশ্লেষণ করা যায়নি। সংরক্ষিত কাজটি আবার চেষ্টা করুন।')
        save(data);return data

    @router.get('/api/preferences')
    def settings():
        try:prefs=preferences(get_library().storage)
        except (ValueError,OSError):raise HTTPException(422,'Saved preferences are invalid; restore preferences.json') from None
        library=get_library().refresh();saved=voices.settings(library.storage)
        from app.semantic_ai import configured as ai_configured
        return {**prefs.model_dump(),'semantic_ai_configured':ai_configured(),'providers':[{'id':p,'configured':bool(configured(p))} for p in ('elevenlabs','azure','vits','chatterbox_bangla')],
                'saved_voices':[{'character':library.characters[cid]['name_bn'] if cid in library.characters else 'বর্ণনাকারী' if cid=='narrator' else cid,'provider':v['provider']} for cid,v in saved.items()]}

    @router.put('/api/preferences')
    def set_settings(payload:Preferences):
        from app.semantic_ai import configured as ai_configured
        if payload.interpretation_mode=='assisted' and not ai_configured():raise HTTPException(422,'Configure an AI interpreter before enabling AI Assisted mode')
        with LOCK:atomic_json(get_library().storage/'preferences.json',payload.model_dump())
        return settings()

    @router.post('/api/conversations',status_code=201)
    def create(payload:Prompt):
        if not payload.prompt.strip():raise HTTPException(422,'আপনার গল্প লিখুন।')
        with LOCK:
            if path(payload.request_id).is_file():
                existing=refresh(payload.request_id)
                if existing['prompt']!=payload.prompt:raise HTTPException(409,'Request ID belongs to a different story')
                return public(existing)
            prefs=preferences(get_library().storage)
            data={'id':payload.request_id,'prompt':payload.prompt,'created_at':now(),'status':'planning','settings':prefs.model_dump(),'revision':1,
                'payload':{'story':payload.prompt,'renderer':'godot','duration_mode':'shorts' if prefs.format=='shorts' else 'mini',
                    'video_format':'portrait','music':prefs.music,'voice_preference':prefs.voice_preference,
                    'interpretation_mode':prefs.interpretation_mode,'semantic_ai_approved':prefs.semantic_ai_approved,'request_id':uuid.uuid4().hex}}
            save(data);return public(advance(data))

    @router.get('/api/conversations')
    def history(limit:int=30,offset:int=0):
        entries=[];linked=set()
        for file in folder().glob('*.json'):
            try:
                data=refresh(file.stem);entries.append(public(data))
                if data.get('job_id'):linked.add(data['job_id'])
            except (ValueError,OSError,HTTPException):continue
        for job in get_jobs():
            if job['job_id'] in linked or job['status']!='completed' or not job.get('validated') or not job.get('video_url') or not video_exists(job):continue
            data={'id':'legacy-'+job['job_id'],'prompt':job.get('story','সংরক্ষিত কার্টুন'),'created_at':job['created_at'],'status':'completed','settings':job.get('options',{}),'revision':0}
            render_state(data,job);entries.append(public(data))
        start=max(0,offset)
        return sorted(entries,key=lambda r:r['created_at'],reverse=True)[start:start+max(1,min(limit,100))]

    @router.get('/api/conversations/{cid}')
    def get(cid:str):
        if cid.startswith('legacy-'):
            job=get_job(cid[7:]);data={'id':cid,'prompt':job.get('story',''),'created_at':job['created_at'],'revision':0};render_state(data,job);return public(data)
        return public(refresh(cid))

    @router.post('/api/conversations/{cid}/resolve')
    def resolve(cid:str,payload:Answer):
        with LOCK:
            data=refresh(cid)
            if data['status'] not in ('needs_input','needs_payment','waiting','failed'):raise HTTPException(409,'This cartoon is already running or complete')
            if payload.revision is not None and payload.revision!=data['revision']:raise HTTPException(409,'The clarification changed. Reload this conversation.')
            project=data['payload'];project.setdefault('character_mappings',{}).update(payload.character_mappings)
            project.setdefault('script_corrections',{}).update({key:value.model_dump() for key,value in payload.corrections.items()})
            if payload.backgrounds:
                scenes=[{k:s[k] for k in ('scene_id','start_segment','end_segment','background_id','location_text')} for s in data['review_scenes']]
                for scene in scenes:scene['background_id']=payload.backgrounds.get(scene['scene_id'],scene['background_id'])
                project['scenes']=scenes
            library=get_library().refresh()
            allowed={c['key'] for c in data.get('clarifications',[]) if c['kind']=='voice'}
            for choice in payload.voices:
                if choice.speaker_id not in allowed:raise HTTPException(422,'Choose a voice for the requested character')
                category=category_for(library.characters[choice.speaker_id]) if choice.speaker_id in library.characters else 'male'
                if category.startswith('child_') and not choice.accept_alternative:raise HTTPException(422,'Listen and explicitly accept this alternative voice first')
                try:voices.save_assignment(library.storage,choice.speaker_id,choice.voice,confirm=True)
                except ValueError as exc:raise HTTPException(422,'এই কণ্ঠটি পাওয়া যাচ্ছে না। অন্য উপলব্ধ কণ্ঠ নির্বাচন করুন।') from exc
            if data.get('automatic_id'):project['request_id']=uuid.uuid4().hex;data.pop('automatic_id',None)
            data['revision']+=1;data.pop('direct_job',None)
            return public(advance(data,payload))

    @router.post('/api/conversations/{cid}/retry')
    def retry(cid:str):
        with LOCK:
            data=refresh(cid)
            if data['status'] not in ('failed','cancelled','waiting'):raise HTTPException(409,'Only stopped cartoons can resume')
            if data.get('job_id'):
                result=resume_job(data['job_id']);data.update(job_id=result['job_id'],direct_job=True,status='queued',stage='queued',progress=0)
                save(data);return public(data)
            data['payload']['request_id']=uuid.uuid4().hex;data.pop('automatic_id',None);return public(advance(data))

    @router.post('/api/conversations/{cid}/regenerate',status_code=201)
    def regenerate(cid:str,payload:Prompt):
        """New history entry, preserving corrections but never paid approval."""
        with LOCK:
            original=refresh(cid)
            if original['status'] not in ('completed','failed','cancelled'):
                raise HTTPException(409,'Stop the active cartoon before regenerating')
            if payload.prompt!=original['prompt']:
                raise HTTPException(409,'Use a new conversation for an edited story')
            if path(payload.request_id).is_file():
                existing=read(payload.request_id)
                if existing.get('regenerated_from')!=cid:raise HTTPException(409,'Request ID already used')
                return public(refresh(payload.request_id))
            project=copy.deepcopy(original['payload'])
            project.update(request_id=uuid.uuid4().hex,paid_approved=False,approval_token=None)
            data={'id':payload.request_id,'prompt':original['prompt'],'created_at':now(),
                'status':'planning','settings':copy.deepcopy(original['settings']),'revision':1,
                'payload':project,'regenerated_from':cid}
            save(data);return public(advance(data))

    @router.post('/api/conversations/{cid}/cancel')
    def cancel(cid:str):
        with LOCK:
            data=refresh(cid)
            if data['status']=='completed':return public(data)
            if data.get('direct_job') and data.get('job_id'):cancel_job(data['job_id'])
            elif data.get('automatic_id'):automatic['cancel'](data['automatic_id'])
            else:data['status']='cancelled'
            save(data);return public(data)

    @router.post('/api/conversations/{cid}/approve-audio')
    def approve_audio(cid:str,payload:dict):
        with LOCK:
            data=refresh(cid)
            if data['status']!='needs_audio_review':raise HTTPException(409,'No speech review is pending')
            automatic['approve_audio'](data['automatic_id'],payload)
            return public(refresh(cid))

    @router.get('/api/conversations/{cid}/events')
    async def events(cid:str,request:Request):
        read(cid)
        async def stream():
            previous=None
            while not await request.is_disconnected():
                data=await asyncio.to_thread(refresh,cid);value=public(data);key=fingerprint(value)
                if key!=previous:
                    yield 'event: update\ndata: '+json.dumps(value,ensure_ascii=False)+'\n\n';previous=key
                if data['status'] in TERMINAL:break
                yield ': keepalive\n\n';await asyncio.sleep(.85)
        return StreamingResponse(stream(),media_type='text/event-stream',headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})
    return router
