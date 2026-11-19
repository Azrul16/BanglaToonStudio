"""Four honest voice groups and permanent, user-selected provider presets."""
import os
import threading
from typing import Literal
from pydantic import BaseModel,Field,ConfigDict,model_validator
from fastapi import APIRouter,HTTPException
from app.voices.base import VoiceIdentity,VoiceError
from app.voices import voice_manager as voices
from app.scene_cache import atomic_json,fingerprint

Category=Literal['male','female','child_male','child_female']
CATEGORIES={'male':'Male','female':'Female','child_male':'Child Male','child_female':'Child Female'}
REGISTRY_LOCK=threading.RLock()


class Preset(BaseModel):
    model_config=ConfigDict(extra='forbid')
    category:Category
    voice:VoiceIdentity
    label:str=Field(min_length=1,max_length=120)
    bengali_reviewed:bool=False
    accept_alternative:bool=False


class Registry(BaseModel):
    model_config=ConfigDict(extra='forbid')
    schema_version:Literal[1]=1
    voice_categories:dict[Category,list[Preset]]=Field(default_factory=lambda:{k:[] for k in CATEGORIES})

    @model_validator(mode='after')
    def complete_categories(self):
        if set(self.voice_categories)!=set(CATEGORIES):raise ValueError('Voice configuration must contain all four categories')
        for key,items in self.voice_categories.items():
            if any(item.category!=key for item in items):raise ValueError('Voice preset category does not match its group')
        return self


def category_for(row):
    meta=row.get('_meta',row);gender=str(meta.get('gender','male')).lower()
    age=meta.get('age',30)
    child=isinstance(age,(int,float)) and age<18 or row.get('age_group')=='child'
    return ('child_' if child else '')+('female' if gender=='female' else 'male')


def registry(storage):
    with REGISTRY_LOCK:
        path=storage/'voice_studio.json'
        if not path.exists():atomic_json(path,Registry().model_dump())
        return Registry.model_validate(voices.read_object(path,Registry().model_dump()))


def configured(provider):
    if provider=='chatterbox_bangla':
        from app.voices.chatterbox_bangla import ROOT
        return (ROOT/'.chatterbox-venv/Scripts/python.exe').is_file() and all((ROOT/'models/chatterbox-bangla'/f).is_file() for f in ('t3_cfg.safetensors','s3gen.safetensors','ve.safetensors','tokenizer.json','conds.pt'))
    return provider=='vits' or provider=='elevenlabs' and bool(os.getenv('ELEVENLABS_API_KEY')) or provider=='azure' and bool(os.getenv('AZURE_SPEECH_KEY') and os.getenv('AZURE_SPEECH_REGION'))


def studio_router(get_library):
    router=APIRouter()
    @router.get('/api/voice-studio')
    def overview():
        library=get_library().refresh()
        try:
            data=registry(library.storage).model_dump();saved=voices.settings(library.storage)
        except ValueError as exc:raise HTTPException(422,str(exc)) from None
        data['categories']=[{'id':key,'name':label,'presets':data['voice_categories'][key]} for key,label in CATEGORIES.items()]
        data['characters']=[{'id':cid,'name':row['name_bn'],'category':category_for(row),'rig_status':row['status'],
                             'voice':saved.get(cid),'selection_status':'saved' if cid in saved else 'offline_default_available'} for cid,row in library.characters.items()]
        data['narrator']={'id':'narrator','voice':saved.get('narrator'),'optional':True}
        data['providers']=[{'id':key,'configured':bool(configured(key))} for key in ('elevenlabs','azure','vits')]
        data['notes']=['No child voice is certified automatically from age labels. Listen to Bengali samples before assigning.',
                       'VITS is one offline voice, shared unless distinct provider voices are saved. Azure bn-BD voices are adults.']
        return data

    @router.post('/api/voice-studio/presets')
    def save(payload:Preset):
        library=get_library()
        try:
            voices.validate_identity(payload.voice)
            catalog=voices.catalog(payload.voice.provider)
            if payload.voice.voice_id not in {r['voice_id'] for r in catalog}:raise VoiceError('Select an actual available provider voice')
            if payload.category.startswith('child_') and not payload.accept_alternative:
                raise VoiceError('Child suitability is not certified by metadata. Explicitly accept this auditioned alternative before saving it.')
            with REGISTRY_LOCK:
                data=registry(library.storage)
                items=data.voice_categories[payload.category];key=fingerprint(payload.voice.model_dump())
                items[:]=[p for p in items if fingerprint(p.voice.model_dump())!=key];items.append(payload)
                atomic_json(library.storage/'voice_studio.json',data.model_dump())
            return payload.model_dump()
        except (ValueError,OSError) as exc:raise HTTPException(422,str(exc)) from None
    return router
