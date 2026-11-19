"""Persistent speech takes and editable direction, sharing the one heavy worker."""
import json
import re
import shutil
import threading
import uuid
import wave
from array import array
from pathlib import Path
from typing import Literal
from fastapi import APIRouter,HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel,Field,ConfigDict
from app.review import ReviewInput,analyze
from app.scene_cache import atomic_json,digest,fingerprint
from app.voices.base import VoiceIdentity,VoiceError
from app.voices import voice_manager as voices
from app.engines.lip_sync import generate_mouth_cues,validate_cues
from app.director import ACTIONS,EMOTIONS,SHOTS,RULES
from app.screenplay import get_spoken_segments,assert_speakable
from app.voices.assignment import resolve_voices

LOCK=threading.RLock()


def recover_sessions(storage):
    for path in (storage/'production').glob('*/session.json'):
        try:
            data=json.loads(path.read_text(encoding='utf-8'));changed=False
            for line in data['segments']:
                for take in line['takes']:
                    if take['status'] in ('queued','generating'):
                        take.update(status='failed',error='Studio stopped during this take. Request a new take explicitly; paid speech was not retried automatically.');changed=True
            if changed:atomic_json(path,data)
        except (OSError,ValueError,KeyError,TypeError):continue


class EditLine(BaseModel):
    model_config=ConfigDict(extra='forbid')
    synthesis_text:str=Field(min_length=1,max_length=1500)
    emotion:str='neutral'
    action:str='talk'
    shot:str='wide'
    actor_id:str|None=None


class TakeInput(BaseModel):
    paid_approved:bool=False
    approval_token:str|None=None


class AssignmentInput(BaseModel):
    voice:VoiceIdentity
    confirm_change:bool=False


class SelectTake(BaseModel):
    take_id:str=Field(pattern=r'^[a-f0-9]{32}$')


class CueInput(BaseModel):
    mouthCues:list[dict]


def session_directory(storage,session_id):
    if not re.fullmatch(r'[a-f0-9]{32}',session_id):raise VoiceError('Production session not found')
    return storage/'production'/session_id


def read_session(storage,session_id):
    directory=session_directory(storage,session_id)
    if not (directory/'session.json').is_file():raise VoiceError('Production session not found')
    data=json.loads((directory/'session.json').read_text(encoding='utf-8'))
    return data,directory


def line_at(data,segment_id):
    if not re.fullmatch(r'segment_\d+',segment_id):raise VoiceError('Speech segment not found')
    line=next((s for s in data['segments'] if s['id']==segment_id),None)
    if line is None:raise VoiceError('Speech segment not found')
    return line


def ready(data):return all(s.get('approved_take') for s in data['segments'])


def approved_speech(storage,session_id,story):
    data,directory=read_session(storage,session_id)
    if data['review']['story']!=story:raise VoiceError('Story changed after speech review. Create a new production session.')
    if not ready(data):raise VoiceError('Approve an audio take for every segment before rendering')
    result=[];identities={}
    for line in data['segments']:
        assert_speakable(line)
        take=next(t for t in line['takes'] if t['take_id']==line['approved_take'])
        if take['status']!='completed' or take['line_revision']!=line['revision']:raise VoiceError('Speech changed since audio approval; select a current take')
        wav=directory/'audio'/f"{take['take_id']}.wav";cues=directory/'audio'/f"{take['take_id']}.json"
        if digest(wav)!=take['audio_hash'] or digest(cues)!=take['cues_hash']:raise VoiceError('Approved audio or cues changed; approve a valid take again')
        from app.audio.quality import require_audio
        require_audio(wav,take['synthesis_text'],take['duration_seconds'])
        if line['speaker'] in identities and identities[line['speaker']]!=take['voice']:raise VoiceError('Use one approved voice identity for every line of '+line['speaker'])
        identities[line['speaker']]=take['voice']
        result.append({'segment_id':line['id'],'wav':wav,'cues':cues,'voice':take['voice'],
                       'synthesis_text':take['synthesis_text'],'duration_seconds':take['duration_seconds'],
                       'provider_metrics':take.get('provider_metrics',{}),
                       'audio_hash':take['audio_hash'],'cues_hash':take['cues_hash']})
    return data,result


def freeze_speech(storage,session_id,story,directory):
    data,lines=approved_speech(storage,session_id,story)
    (directory/'audio').mkdir(exist_ok=True);(directory/'cues').mkdir(exist_ok=True)
    for line in lines:
        shutil.copyfile(line.pop('wav'),directory/'audio'/f"{line['segment_id']}.wav")
        shutil.copyfile(line.pop('cues'),directory/'cues'/f"{line['segment_id']}.json")
    return lines,{s['id']:{k:s.get(k) for k in ('action','emotion','shot','actor_id')} for s in data['segments']}


def prepare_session(library,payload):
    report,parsed,plan=analyze(library,payload)
    if not report['ready']:raise HTTPException(422,report)
    sid=uuid.uuid4().hex;directory=session_directory(library.storage,sid);(directory/'audio').mkdir(parents=True)
    assigned,voice_issues=resolve_voices(library,parsed['segments'],payload.voice_preference);corrections=voices.dictionary(library.storage)
    if voice_issues:raise HTTPException(422,{**report,'ready':False,'issues':voice_issues})
    segments=[]
    for segment in get_spoken_segments(parsed['segments']):
        action='idle' if segment['off_screen'] else 'talk';emotion=segment.get('emotion','neutral')
        assigned_voice=assigned.get(segment['speaker'],VoiceIdentity().model_dump())
        segments.append({**segment,'original_text':segment['text'],'synthesis_text':voices.spoken_text(segment['text'],corrections,preserve_spelling=assigned_voice['provider']=='chatterbox_bangla'),
                         'voice':assigned.get(segment['speaker'],VoiceIdentity().model_dump()),'action':action,'emotion':emotion,'shot':'wide',
                         'revision':1,'takes':[],'approved_take':None})
        segments[-1]['actor_id']=segment['speaker'] if not segment['off_screen'] else None
    approved_review={**payload.model_dump(),'character_mappings':report['character_mappings'],'review_token':report['review_token'],
                     'scenes':[{k:s[k] for k in ('scene_id','start_segment','end_segment','background_id','location_text')} for s in report['scenes']]}
    data={'session_id':sid,'review':approved_review,'segments':segments,'events':report['events'],'ready':not segments,'schema_version':2}
    atomic_json(directory/'session.json',data);return data


def generate_session_take(library,session_id,segment_id,take_id,payload):
    try:
        with LOCK:
            data,directory=read_session(library.storage,session_id);line=line_at(data,segment_id)
            assert_speakable(line)
            take=next(t for t in line['takes'] if t['take_id']==take_id);take['status']='generating';atomic_json(directory/'session.json',data)
            text=take['synthesis_text'];voice=VoiceIdentity(**take['voice']);emotion=take['emotion']
            previous=[t['provider_request_id'] for s in data['segments'][:data['segments'].index(line)] for t in s['takes'] if t.get('provider_request_id') and t['voice']['provider']=='elevenlabs' and t['status']=='completed'][-3:]
        path=directory/'audio'/f'{take_id}.wav'
        duration=voices.synthesize(text,voice,path,library.root.parent/'models/bangla-vits',emotion,payload.paid_approved,payload.approval_token,previous)
        metrics={'provider':voice.provider}
        if voice.provider=='chatterbox_bangla':
            from app.voices.chatterbox_bangla import ENGINE as CHATTERBOX
            metrics.update(CHATTERBOX.result)
        if voice.provider=='vits':
            from app.engines.bangla_tts import ENGINE
            metrics.update(ENGINE.report())
        from app.audio.quality import require_audio
        quality=require_audio(path,text,duration)
        metrics['audio_quality']=quality
        cue_path=path.with_suffix('.json')
        if not line['off_screen']:generate_mouth_cues(path,cue_path,'auto')
        else:atomic_json(cue_path,{'method':'off_screen','mouthCues':[]})
        with LOCK:
            data,directory=read_session(library.storage,session_id);line=line_at(data,segment_id);take=next(t for t in line['takes'] if t['take_id']==take_id)
            take.update(status='completed',duration_seconds=duration,audio_hash=digest(path),cues_hash=digest(cue_path),
                        provider_metrics=metrics,
                        audio_url=f'/api/production/{session_id}/takes/{take_id}/audio')
            metadata=path.with_suffix('.provider.json')
            if metadata.is_file():take['provider_request_id']=json.loads(metadata.read_text())['request_id']
            atomic_json(directory/'session.json',data)
    except Exception as exc:
        with LOCK:
            data,directory=read_session(library.storage,session_id);line=line_at(data,segment_id);take=next(t for t in line['takes'] if t['take_id']==take_id)
            take.update(status='failed',error=str(exc));atomic_json(directory/'session.json',data)


def production_router(get_library,get_executor,create_render):
    router=APIRouter()
    def storage():return get_library().storage
    def save(directory,data):atomic_json(directory/'session.json',data)
    def checked(call):
        try:return call()
        except (VoiceError,ValueError,OSError,KeyError,StopIteration) as exc:raise HTTPException(422,str(exc)) from None

    @router.get('/api/voices/providers')
    def providers():
        import os
        return {'providers':[{'id':'elevenlabs','configured':bool(os.getenv('ELEVENLABS_API_KEY')),'models':['eleven_v4','eleven_v3']},
                             {'id':'azure','configured':bool(os.getenv('AZURE_SPEECH_KEY') and os.getenv('AZURE_SPEECH_REGION')),'models':['azure-neural']},
                             {'id':'vits','configured':True,'models':['bangladeshi-vits']}],
                'assignments':checked(lambda:voices.settings(storage())),
                'notes':['Cloud voices are never silently replaced by VITS.','The local VITS model has one voice; distinct natural voices require a configured provider.']}

    @router.get('/api/voices/{provider}/catalog')
    def catalog(provider:str):return checked(lambda:voices.catalog(provider))

    @router.put('/api/voices/assignments/{character_id}')
    def assignment(character_id:str,payload:AssignmentInput):
        library=get_library().refresh()
        if character_id not in library.characters and character_id not in ('narrator','unknown_voice'):raise HTTPException(404,'Registered character or narrator required')
        with LOCK:return checked(lambda:voices.save_assignment(storage(),character_id,payload.voice,payload.confirm_change))

    @router.get('/api/pronunciation')
    def pronunciation():return checked(lambda:voices.dictionary(storage()))

    @router.put('/api/pronunciation')
    def save_pronunciation(payload:dict[str,str]):
        if len(payload)>500 or any(not k.strip() or not v.strip() or max(len(k),len(v))>150 for k,v in payload.items()):raise HTTPException(422,'Use at most 500 non-empty pronunciation pairs, each up to 150 characters')
        with LOCK:
            checked(lambda:voices.dictionary(storage()))
            atomic_json(storage()/'pronunciation.json',payload)
        return payload

    @router.post('/api/production',status_code=201)
    def create(payload:ReviewInput):
        return checked(lambda:prepare_session(get_library(),payload))

    @router.get('/api/production/{session_id}')
    def get(session_id:str):return checked(lambda:read_session(storage(),session_id)[0])

    @router.put('/api/production/{session_id}/segments/{segment_id}')
    def edit(session_id:str,segment_id:str,payload:EditLine):
        if payload.action not in ACTIONS or payload.emotion not in (*EMOTIONS,'whisper') or payload.shot not in SHOTS:raise HTTPException(422,'Unsupported direction choice')
        if payload.shot=='over_shoulder':raise HTTPException(422,'True over-the-shoulder framing needs back/profile rig artwork. Use a two-character shot until those layers are supplied.')
        with LOCK:
            data,directory=checked(lambda:read_session(storage(),session_id));line=checked(lambda:line_at(data,segment_id))
            if payload.actor_id and payload.actor_id not in set(data['review']['character_mappings'].values()):raise HTTPException(422,'Choose an acting character present in the reviewed cast')
            if any(t['status'] in ('queued','generating') for t in line['takes']):raise HTTPException(409,'Wait for the current take before editing this line')
            changed=line['synthesis_text']!=payload.synthesis_text or line['emotion']!=payload.emotion
            line.update(payload.model_dump())
            if changed:line['revision']+=1;line['approved_take']=None
            data['ready']=ready(data);save(directory,data)
        return line

    @router.put('/api/production/{session_id}/segments/{segment_id}/voice')
    def line_voice(session_id:str,segment_id:str,payload:VoiceIdentity):
        checked(lambda:voices.validate_identity(payload))
        rows=checked(lambda:voices.catalog(payload.provider))
        if payload.voice_id not in {r['voice_id'] for r in rows}:raise HTTPException(422,'Select an accessible provider voice')
        with LOCK:
            data,directory=checked(lambda:read_session(storage(),session_id));line=checked(lambda:line_at(data,segment_id))
            if line['voice']!=payload.model_dump():line['voice']=payload.model_dump();line['revision']+=1;line['approved_take']=None
            data['ready']=ready(data);save(directory,data)
        return line

    @router.get('/api/production/{session_id}/segments/{segment_id}/estimate')
    def estimate(session_id:str,segment_id:str):
        data,_=checked(lambda:read_session(storage(),session_id));line=checked(lambda:line_at(data,segment_id))
        checked(lambda:assert_speakable(line))
        return checked(lambda:voices.usage(line['synthesis_text'],VoiceIdentity(**line['voice']),line['emotion']))

    def generate_take(session_id,segment_id,take_id,payload):
        return generate_session_take(get_library(),session_id,segment_id,take_id,payload)

    @router.post('/api/production/{session_id}/segments/{segment_id}/takes',status_code=202)
    def take(session_id:str,segment_id:str,payload:TakeInput):
        with LOCK:
            data,directory=checked(lambda:read_session(storage(),session_id));line=checked(lambda:line_at(data,segment_id))
            checked(lambda:assert_speakable(line))
            if any(t['status'] in ('queued','generating') for t in line['takes']):raise HTTPException(409,'A take is already queued for this line')
            estimate=checked(lambda:voices.usage(line['synthesis_text'],VoiceIdentity(**line['voice']),line['emotion']))
            if estimate['paid'] and (not payload.paid_approved or payload.approval_token!=estimate['approval_token']):raise HTTPException(409,{'message':'Approve the displayed paid usage before creating this take','estimate':estimate})
            tid=uuid.uuid4().hex;line['takes'].append({'take_id':tid,'status':'queued','voice':line['voice'],'synthesis_text':line['synthesis_text'],
                                                     'line_revision':line['revision'],'emotion':line['emotion']})
            save(directory,data);get_executor().submit(generate_take,session_id,segment_id,tid,payload)
        return {'take_id':tid,'status':'queued'}

    @router.post('/api/production/{session_id}/segments/{segment_id}/approve')
    def approve(session_id:str,segment_id:str,payload:SelectTake):
        with LOCK:
            data,directory=checked(lambda:read_session(storage(),session_id));line=checked(lambda:line_at(data,segment_id))
            take=next((t for t in line['takes'] if t['take_id']==payload.take_id),None)
            if not take or take['status']!='completed' or take['synthesis_text']!=line['synthesis_text'] or take['emotion']!=line['emotion']:raise HTTPException(409,'Select a completed take matching the current spoken text and emotion')
            line['voice']=take['voice'];take['line_revision']=line['revision']
            line['approved_take']=payload.take_id;data['ready']=ready(data);save(directory,data)
        return data

    def take_path(session_id,take_id):
        if not re.fullmatch(r'[a-f0-9]{32}',take_id):raise VoiceError('Invalid take ID')
        data,directory=read_session(storage(),session_id)
        take=next((t for s in data['segments'] for t in s['takes'] if t['take_id']==take_id and t['status']=='completed'),None)
        if not take:raise VoiceError('Completed take not found')
        path=directory/'audio'/f'{take_id}.wav'
        if not path.is_file() or not path.with_suffix('.json').is_file():raise VoiceError('Take audio or mouth cues are missing. Generate and approve a replacement take explicitly.')
        return path,take

    @router.get('/api/production/{session_id}/takes/{take_id}/audio')
    def audio(session_id:str,take_id:str):return FileResponse(checked(lambda:take_path(session_id,take_id)[0]),media_type='audio/wav')

    @router.get('/api/production/{session_id}/takes/{take_id}/waveform')
    def waveform(session_id:str,take_id:str):
        path,_=checked(lambda:take_path(session_id,take_id))
        peaks=[]
        with wave.open(str(path),'rb') as wav:
            step=max(1,wav.getnframes()//300)
            while raw:=wav.readframes(step):peaks.append(round(max(abs(n) for n in array('h',raw))/32768,4))
        return {'peaks':peaks,'duration_seconds':wav.getnframes()/wav.getframerate()}

    @router.get('/api/production/{session_id}/takes/{take_id}/cues')
    def cues(session_id:str,take_id:str):
        path,_=checked(lambda:take_path(session_id,take_id));return json.loads(path.with_suffix('.json').read_text(encoding='utf-8'))

    @router.put('/api/production/{session_id}/takes/{take_id}/cues')
    def edit_cues(session_id:str,take_id:str,payload:CueInput):
        with LOCK:
            path,take=checked(lambda:take_path(session_id,take_id))
            checked(lambda:validate_cues({'mouthCues':payload.mouthCues},take['duration_seconds']))
            atomic_json(path.with_suffix('.json'),{'method':'manual','mouthCues':payload.mouthCues,'approximate':True})
            data,directory=read_session(storage(),session_id)
            for line in data['segments']:
                for item in line['takes']:
                    if item['take_id']==take_id:item['cues_hash']=digest(path.with_suffix('.json'));line['approved_take']=None
            data['ready']=ready(data);save(directory,data)
        return {'saved':True,'requires_audio_reapproval':True}

    @router.post('/api/production/{session_id}/render',status_code=202)
    def render(session_id:str):
        data,_=checked(lambda:approved_speech(storage(),session_id,read_session(storage(),session_id)[0]['review']['story']))
        return checked(lambda:create_render(ReviewInput(**{**data['review'],'production_id':session_id})))

    @router.post('/api/production/{session_id}/segments/{segment_id}/preview',status_code=202)
    def preview_animation(session_id:str,segment_id:str):
        with LOCK:
            data,directory=checked(lambda:read_session(storage(),session_id));line=checked(lambda:line_at(data,segment_id))
            if not line.get('approved_take'):raise HTTPException(409,'Approve a speech take for this line first')
            index=next((i for i,e in enumerate(data.get('events',[])) if e['event_id']==line.get('event_id')),data['segments'].index(line))
            review=data['review'];scene=next(s for s in review['scenes'] if s['start_segment']<=index<s['end_segment'])
            sid=uuid.uuid4().hex;child_dir=session_directory(storage(),sid);(child_dir/'audio').mkdir(parents=True)
            clone=json.loads(json.dumps(line));clone['id']='segment_001';clone['event_id']='event_001'
            story=('বর্ণনাকারী' if line['kind']=='narration' else line['speaker_label'])+': '+line['original_text']
            child={'session_id':sid,'review':{**review,'story':story,'review_token':None,'production_id':sid,'script_corrections':{},
                                             'scenes':[{'scene_id':'scene_001','start_segment':0,'end_segment':1,'background_id':scene['background_id'],'location_text':'Animation preview'}]},
                   'segments':[clone],'ready':True,'schema_version':2}
            for take in clone['takes']:
                for suffix in ('.wav','.json'):
                    source=directory/'audio'/(take['take_id']+suffix)
                    if source.is_file():shutil.copyfile(source,child_dir/'audio'/source.name)
            save(child_dir,child)
        return checked(lambda:create_render(ReviewInput(**child['review'])))
    return router
