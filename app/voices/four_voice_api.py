"""Compact four-voice configuration and serialized local auditions."""
import base64
import json
import uuid
from typing import Literal
from fastapi import APIRouter,HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel,Field,ConfigDict
from app.voices import four_voices as voices
from app.scene_cache import atomic_json,digest
from app.voices.base import VoiceIdentity
PREVIEW_RUN_ID=uuid.uuid4().hex


class Upload(BaseModel):
    model_config=ConfigDict(extra='forbid')
    wav_base64:str=Field(max_length=14000000)
    label:str=Field(min_length=1,max_length=120)
    authorization:str=Field(min_length=20,max_length=2000)
    consent:bool=False


class Selection(BaseModel):
    model_config=ConfigDict(extra='forbid')
    base_voices:dict[str,str]
    mode:Literal['evaluation','production']|None=None


class Preview(BaseModel):
    model_config=ConfigDict(extra='forbid')
    category:str
    reference_id:str|None=None
    character_id:str|None=None


def four_voice_router(get_executor,get_storage):
    router=APIRouter()
    def folder():
        root=get_storage()/'voice_previews_v9';root.mkdir(parents=True,exist_ok=True);return root
    def location(pid):
        if len(pid)!=32 or any(c not in '0123456789abcdef' for c in pid):raise HTTPException(404,'Preview not found')
        return folder()/pid
    @router.get('/api/default-voices')
    def overview():
        data=voices.configuration();statuses={}
        for category in voices.CATEGORIES:
            try:
                row,_=voices.reference(category);statuses[category]='evaluation_only' if row.get('evaluation_only') else 'configured'
            except ValueError:statuses[category]='not_configured'
        from app.voices.variation import dsp_capabilities
        available=[]
        for rid,row in data['references'].items():
            path=(voices.CONFIG.parent/row['file']).resolve()
            if voices.usable(row,'evaluation') and path.is_relative_to(voices.CONFIG.parent.resolve()) and path.is_file() and digest(path)==row['sha256']:
                available.append({'id':rid,'label':row['label'],'duration_seconds':row['duration_seconds'],'evaluation_only':bool(row.get('evaluation_only')),'official_sample_id':row.get('official_sample_id')})
        return {'mode':data.get('mode','production'),'base_voices':data['base_voices'],'status':statuses,'references':available,
            'presets':data['character_presets'],'migration_conflicts':data['migration_conflicts'],'dsp':dsp_capabilities()}
    @router.post('/api/default-voices/references')
    def upload(payload:Upload):
        try:return {'reference_id':voices.upload(base64.b64decode(payload.wav_base64,validate=True),payload.label,payload.authorization,payload.consent)}
        except (ValueError,OSError) as exc:raise HTTPException(422,str(exc)) from None
    @router.get('/api/default-voices/references/{rid}/audio')
    def reference_audio(rid:str):
        row=voices.configuration()['references'].get(rid)
        if not voices.usable(row,'evaluation'):raise HTTPException(404,'Recording not found')
        path=(voices.CONFIG.parent/row['file']).resolve()
        if not path.is_relative_to(voices.CONFIG.parent.resolve()) or not path.is_file() or digest(path)!=row['sha256']:raise HTTPException(404,'Recording is missing or changed')
        return FileResponse(path,media_type='audio/wav')
    @router.put('/api/default-voices')
    def save(payload:Selection):
        try:
            voices.save_four(payload.base_voices,payload.mode)
            from app.chat import preferences,LOCK as PREFERENCES_LOCK
            with PREFERENCES_LOCK:
                prefs=preferences(get_storage()).model_dump();prefs['voice_preference']='chatterbox_bangla';atomic_json(get_storage()/'preferences.json',prefs)
            return overview()
        except (ValueError,OSError) as exc:raise HTTPException(422,str(exc)) from None
    @router.post('/api/default-voices/variations/reset')
    def reset(character_id:str|None=None):
        if character_id and character_id not in voices.CHARACTER_CATEGORIES:raise HTTPException(422,'Unknown character')
        voices.reset_variations(character_id);return overview()
    @router.get('/api/default-voices/dsp-benchmark')
    def benchmark():
        path=voices.ROOT/'evaluation/v9-dsp-benchmark/manifest.json'
        if not path.exists():return {'entries':[]}
        data=json.loads(path.read_text(encoding='utf-8'))
        return {'purpose':data['purpose'],'entries':[{'character_id':e['character_id'],'text':e['text'],
            'audio_url':f'/api/default-voices/dsp-benchmark/{e["character_id"]}/processed','original_url':f'/api/default-voices/dsp-benchmark/{e["character_id"]}/original'} for e in data['entries']]}
    @router.get('/api/default-voices/dsp-benchmark/{cid}/{kind}')
    def benchmark_audio(cid:str,kind:str):
        if cid not in ('nabil','rayan','fahim','anika') or kind not in ('original','processed'):raise HTTPException(404)
        path=voices.ROOT/'evaluation/v9-dsp-benchmark'/(cid+('.original.wav' if kind=='original' else '.wav'))
        if not path.is_file():raise HTTPException(404)
        return FileResponse(path,media_type='audio/wav')
    @router.get('/api/default-voices/conditioning-comparisons')
    def conditioning_comparisons():
        path=voices.ROOT/'evaluation/selected-demo-conditioning/results.json'
        if not path.exists():return {'entries':[]}
        data=json.loads(path.read_text(encoding='utf-8'))
        return {'mode':'evaluation','commercial_permission_verified':False,'entries':[{'character_id':e['character_id'],'category':e['category'],
            'official_sample_id':e['official_sample_id'],'text':e['text'],'conditioning_execution':e['conditioning_execution'],
            'audio_url':f'/api/default-voices/conditioning-comparisons/{e["character_id"]}/processed',
            'original_url':f'/api/default-voices/conditioning-comparisons/{e["character_id"]}/original'} for e in data['results']]}
    @router.get('/api/default-voices/conditioning-comparisons/{cid}/{kind}')
    def conditioned_audio(cid:str,kind:str):
        if cid not in voices.CHARACTER_CATEGORIES or kind not in ('original','processed'):raise HTTPException(404)
        path=voices.ROOT/'evaluation/selected-demo-conditioning'/(cid+('.original.wav' if kind=='original' else '.wav'))
        if not path.is_file():raise HTTPException(404)
        return FileResponse(path,media_type='audio/wav')
    @router.get('/api/default-voices/conditioning-comparisons/archive')
    def comparison_archive():
        path=voices.ROOT/'output/selected-demo-audio-comparisons.zip'
        if not path.is_file():raise HTTPException(404,'Comparison archive is not ready')
        return FileResponse(path,media_type='application/zip',filename='evaluation-audio-comparisons.zip')
    @router.post('/api/default-voices/preview',status_code=202)
    def preview(payload:Preview):
        data=voices.configuration()
        if payload.category not in voices.CATEGORIES:raise HTTPException(422,'Unknown voice category')
        cid=payload.character_id or next(k for k,c in voices.CHARACTER_CATEGORIES.items() if c==payload.category)
        if voices.CHARACTER_CATEGORIES.get(cid)!=payload.category:raise HTTPException(422,'Character/category mismatch')
        selected=payload.reference_id or (data['base_voices'][payload.category] or {}).get('reference_id')
        reference=data['references'].get(selected)
        if not voices.usable(reference,'evaluation'):raise HTTPException(422,'Select an authorized or explicitly evaluation-only reference first')
        path=(voices.CONFIG.parent/reference['file']).resolve()
        if not path.is_relative_to(voices.CONFIG.parent.resolve()) or not path.is_file() or digest(path)!=reference['sha256']:raise HTTPException(422,'Reference is missing or changed')
        active=0
        for saved in folder().glob('*/job.json'):
            try:
                job=json.loads(saved.read_text(encoding='utf-8'))
                active+=job.get('instance')==PREVIEW_RUN_ID and job.get('status') in ('queued','running')
            except (OSError,ValueError):continue
        if active>=4:raise HTTPException(429,'Wait for the queued voice previews to finish')
        pid=uuid.uuid4().hex;directory=location(pid);directory.mkdir()
        atomic_json(directory/'job.json',{'id':pid,'instance':PREVIEW_RUN_ID,'status':'queued','category':payload.category,'character_id':payload.character_id})
        def work():
            try:
                from app.voices.chatterbox_bangla import ENGINE,MODEL_REVISION,CACHE_VERSION,acting_settings
                from app.voices.variation import synthesize_cached
                atomic_json(directory/'job.json',{'id':pid,'instance':PREVIEW_RUN_ID,'status':'running'})
                preset=data['character_presets'][cid] if payload.character_id else {'pitch_semitones':0.,'formant':'preserved','category':payload.category}
                identity=VoiceIdentity(provider='chatterbox_bangla',model='BosonLab/chatterbox-bangla',voice_id=cid,reference_audio_hash=reference['sha256'],
                    category=payload.category,variation=preset,model_revision=MODEL_REVISION,generation_settings=voices.SETTINGS,synthesis_version=CACHE_VERSION,
                    usage_mode='evaluation' if reference.get('evaluation_only') else data.get('mode','production'),official_sample_id=reference.get('official_sample_id'))
                duration=synthesize_cached('এই রায়ান! তুই কোথায় যাচ্ছিস? দাঁড়া, আমিও আসছি!',identity,directory/'preview.wav',path,'neutral',ENGINE,acting_settings(voices.SETTINGS,'neutral'))
                atomic_json(directory/'job.json',{'id':pid,'status':'completed','duration_seconds':duration,'audio_url':f'/api/default-voices/previews/{pid}/audio','original_url':f'/api/default-voices/previews/{pid}/original'})
            except Exception as exc:atomic_json(directory/'job.json',{'id':pid,'status':'failed','error':str(exc)})
        get_executor().submit(work);return {'id':pid,'status':'queued'}
    @router.get('/api/default-voices/previews/{pid}')
    def status(pid:str):
        path=location(pid)/'job.json'
        if not path.exists():raise HTTPException(404,'Preview not found')
        data=json.loads(path.read_text(encoding='utf-8'))
        if data.get('status') in ('queued','running') and data.get('instance')!=PREVIEW_RUN_ID:
            data.update(status='failed',error='Application restarted during the audition. Request a new preview; completed original speech remains cached.');atomic_json(path,data)
        return data
    @router.get('/api/default-voices/previews/{pid}/{kind}')
    def audio(pid:str,kind:str):
        if kind not in ('audio','original') or status(pid)['status']!='completed':raise HTTPException(404,'Preview not ready')
        return FileResponse(location(pid)/('preview.wav' if kind=='audio' else 'preview.original.wav'),media_type='audio/wav')
    @router.get('/api/voice-references')
    @router.post('/api/voice-references/{cid}')
    def retired_references(cid:str=''):
        raise HTTPException(410,'Use /api/default-voices for four category voices. Existing recordings are preserved.')
    @router.get('/api/benchmarks/chatterbox')
    def benchmarks():
        path=voices.ROOT/'evaluation/chatterbox-bangla-official/manifest.json'
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'samples':[]}
    @router.get('/api/benchmarks/chatterbox/{sample_id}.wav')
    def sample(sample_id:str):
        if sample_id not in [f'{i:03}' for i in range(1,8)]:raise HTTPException(404)
        return FileResponse(voices.ROOT/'evaluation/chatterbox-bangla-official/audios/output'/(sample_id+'.wav'),media_type='audio/wav')
    return router
