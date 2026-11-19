"""Deterministic recognition, explicit review choices and atomic saved aliases."""
import hashlib
import importlib.util
import json
import re
import shutil
import threading
from pathlib import Path
from pydantic import BaseModel,ConfigDict,Field,model_validator
from typing import Literal
from app.assets import AssetError,normalize,mentions_alias,load_character,load_background,asset_references,safe_path
from app.engines.story_parser import parse_story
from app.hardware import ffmpeg_binary,ffprobe_binary
from app.screenplay import EventCorrection

ROLES={
 'narrator':{'character_id':'narrator','name_bn':'বর্ণনাকারী','off_screen':True,'voice_id':'default_bn','status':'ready'},
 'unknown_voice':{'character_id':'unknown_voice','name_bn':'অচেনা কণ্ঠ','off_screen':True,'voice_id':'default_bn','status':'ready'}}
ROLE_ALIASES={'narrator':['narrator','narration','বর্ণনাকারী','বর্ণনা','কথক'],
              'unknown_voice':['unknown_voice','unknown voice','unknown','অচেনা কণ্ঠ','অজানা কণ্ঠ','রহস্যময় কণ্ঠ','অফস্ক্রিন']}
GENERIC={'একজন ছেলে','একটি ছেলে','একজন মেয়ে','একজন মেয়ে','কেউ','boy','girl','he','she','someone'}
MAPPING_LOCK=threading.RLock()


class SceneChoice(BaseModel):
    model_config=ConfigDict(extra='forbid')
    scene_id:str=Field(pattern=r'^scene_\d+$')
    start_segment:int=Field(ge=0)
    end_segment:int=Field(gt=0)
    background_id:str|None=None
    location_text:str=''


class ReviewInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    story:str=Field(min_length=1,max_length=30000)
    character_mappings:dict[str,str]=Field(default_factory=dict)
    scenes:list[SceneChoice]|None=None
    review_token:str|None=None
    duration_mode:Literal['shorts','mini']='shorts'
    video_format:Literal['auto','vertical','portrait']='portrait'
    video_profile:Literal['production','low_memory']='production'
    renderer:Literal['pillow','godot']='pillow'
    production_id:str|None=Field(default=None,pattern=r'^[a-f0-9]{32}$')
    sound_effects:bool=True
    music:bool=False
    script_corrections:dict[str,EventCorrection]=Field(default_factory=dict)
    audio_levels:dict[str,float]=Field(default_factory=dict)
    voice_preference:Literal['saved','vits','elevenlabs','azure','chatterbox_bangla']='saved'
    interpretation_mode:Literal['rules','assisted']='rules'
    semantic_ai_approved:bool=False

    @model_validator(mode='after')
    def valid_format(self):
        if self.interpretation_mode=='assisted' and not self.semantic_ai_approved:raise ValueError('Enable AI assistance only after privacy and cost consent')
        import math
        if any(k not in ('dialogue','narration','music','ambience','sfx','action') or not math.isfinite(v) or not 0<=v<=2 for k,v in self.audio_levels.items()):raise ValueError('Audio levels require known tracks and values between 0 and 2')
        return self


class Issue(BaseModel):
    type:str
    source_text:str
    reason:str
    message:str
    scene_id:str|None=None
    event_id:str|None=None
    source_line:int|None=None


class AssetOut(BaseModel):
    model_config=ConfigDict(extra='allow')
    id:str
    name_bn:str
    name_en:str
    status:Literal['ready','reference_only','incomplete']
    preview_url:str|None=None
    reason:str|None=None


class AnalysisOut(BaseModel):
    ready:bool
    characters:list[dict]
    scenes:list[dict]
    segments:list[dict]
    issues:list[Issue]
    character_mappings:dict[str,str]
    review_token:str|None=None
    warnings:list[str]=Field(default_factory=list)
    estimated_duration:dict=Field(default_factory=dict)
    tools:dict=Field(default_factory=dict)
    events:list[dict]=Field(default_factory=list)
    spoken_segments:list[dict]=Field(default_factory=list)
    diagnostics:list[dict]=Field(default_factory=list)


class MappingInput(BaseModel):
    model_config=ConfigDict(extra='forbid')
    asset_type:Literal['character','background']
    alias:str=Field(min_length=1,max_length=250)
    asset_id:str=Field(min_length=1,max_length=80)
    scope:Literal['project','remember']='project'
    confirm_conflict:bool=False
    confirm_generic:bool=False


class MappingConflict(ValueError):
    def __init__(self,message,reason): self.reason=reason; super().__init__(message)


def read_mappings(library):
    path=library.storage/'user_mappings.json'
    if not path.exists(): return {'character_aliases':{},'background_aliases':{}}
    try:
        data=json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data,dict): raise ValueError('expected object')
        for key in ('character_aliases','background_aliases'):
            if not isinstance(data.get(key),dict) or any(not isinstance(a,str) or not isinstance(v,str) for a,v in data[key].items()):
                raise ValueError('expected alias-to-ID dictionaries')
            normalized={}
            for alias,target in data[key].items():
                alias=normalize(alias)
                if not alias or alias in normalized and normalized[alias]!=target: raise ValueError('conflicting normalized aliases')
                normalized[alias]=target
            data[key]=normalized
        return data
    except (ValueError,OSError) as exc:
        raise AssetError(f'Saved mappings are invalid; restore user_mappings.json from a valid copy. The registry was not modified: {exc}') from exc


def exact_character_candidates(library,label):
    label=normalize(label)
    result=[]
    for cid,row in library.characters.items():
        for alias in row['aliases']:
            alias=normalize(alias)
            suffix=label[len(alias):] if label.startswith(alias) else None
            if label==alias or suffix in ('এর','ের','কে','রা','দের') and any('\u0980'<=c<='\u09ff' for c in alias):
                result.append(cid); break
    return result


def candidate_characters(library,label):
    rows=[r for r in library.characters.values() if r['status']=='ready']
    label=normalize(label)
    if any(t in label for t in ('ছেলে','boy')): rows=[r for r in rows if r['age_group']=='child' and r['gender']=='male']
    elif any(t in label for t in ('মেয়ে','মেয়ে','girl')): rows=[r for r in rows if r['age_group']=='child' and r['gender']=='female']
    return [r['id'] for r in rows]


def resolve_character(library,label,project,saved):
    key=normalize(label)
    target=project.get(key,saved['character_aliases'].get(key))
    source='project' if key in project else 'remembered' if key in saved['character_aliases'] else 'automatic'
    if target is None:
        for role,aliases in ROLE_ALIASES.items():
            if key in {normalize(a) for a in aliases}: target=role; break
    matches=exact_character_candidates(library,label) if target is None else [target]
    if len(matches)==1:
        target=matches[0]
        if target in ROLES:
            return {'speaker_text':label,'key':key,'character_id':target,'status':'ready','source':source,'candidates':[],
                    'role':'narration' if target=='narrator' else 'off_screen','name_bn':ROLES[target]['name_bn']}
        row=library.characters.get(target)
        if row:
            return {'speaker_text':label,'key':key,'character_id':target,'status':row['status'],'source':source,'candidates':matches,
                    'role':'visible','name_bn':row['name_bn'],'reason':row['reason']}
    return {'speaker_text':label,'key':key,'character_id':None,'status':'ambiguous' if len(matches)>1 else 'unresolved',
            'source':source,'candidates':matches if len(matches)>1 else candidate_characters(library,label),'role':'visible',
            'reason':'Select a validated character, off-screen voice, or narration.'}


def resolver(library,project,saved):
    def resolve(label):
        result=resolve_character(library,label,project,saved)
        target=result['character_id']
        if target in ROLES: return ROLES[target]
        return {'character_id':target or 'unresolved','name_bn':result.get('name_bn',label),'off_screen':False,
                'voice_id':'default_bn','status':result['status']}
    return resolve


TIME_WORDS={'misty':['কুয়াশা','কুয়াশা','কুয়াশাচ্ছন্ন','কুয়াশাচ্ছন্ন','mist','fog'],
            'night':['রাত','রাতে','রাতের','midnight','night'],'dusk':['সন্ধ্যা','সন্ধ্যায়','সন্ধ্যায়','সন্ধ্যার','dusk','evening','sunset'],
 'day':['দিন','দুপুর','সকাল','বিকেল','day','morning','afternoon']}
WEAK={'সন্ধ্যা','গ্রাম','রহস্য','ফল','দিন','রাত','কুয়াশা','কুয়াশা'}


def location_match(text,term):
    term=normalize(term)
    return any(mentions_alias(text,term+suffix) for suffix in ('','ে','তে','য়','য়','য়ে','য়ে','য়ের','য়ের'))


def background_match(library,text,saved,carry_time=None):
    normalized=normalize(text)
    for alias,target in sorted(saved['background_aliases'].items(),key=lambda p:-len(p[0])):
        if location_match(normalized,alias):
            row=library.backgrounds.get(target)
            return {'background_id':target,'status':row['status'] if row else 'unresolved','candidates':[target],
                    'location_text':alias,'source':'remembered','time':carry_time}
    time_hint=next((time for time,terms in TIME_WORDS.items() if any(location_match(normalized,t) for t in terms)),carry_time)
    found={}
    for bid,row in library.backgrounds.items():
        terms=[a for a in row['aliases'] if normalize(a) not in WEAK and a!=bid]
        evidence=[a for a in terms if location_match(normalized,a)]
        if evidence: found[bid]=max(evidence,key=len)
    if not found:
        match=re.search(r'(?:একটি|একটা|এক)\s+(.+?)\s+(?:পৌঁছ|গেল|ঢুক|দাঁড়|দাঁড়)',text)
        return {'background_id':None,'status':'unresolved','candidates':[],'location_text':match.group(1) if match else text,
                'source':'automatic','time':time_hint}
    # Variant-only generic keywords cannot introduce a different location.
    found={bid:term for bid,term in found.items() if not any(normalize(term)!=normalize(other) and normalize(term) in normalize(other)
                                                            for other in found.values())}
    families={library.backgrounds[bid]['family_id'] for bid in found}
    candidates=list(found)
    if len(families)==1:
        family=next(iter(families))
        candidates=[bid for bid,row in library.backgrounds.items() if row['family_id']==family]
        desired=time_hint or 'day'
        times={'dusk','evening','sunset'} if desired=='dusk' else {desired}
        preferred=[bid for bid in candidates if library.backgrounds[bid]['time_of_day'] in times]
        if len(preferred)==1: candidates=preferred
        elif not time_hint and len(candidates)==1: pass
        elif not preferred and time_hint: return {'background_id':None,'status':'unresolved','candidates':candidates,'location_text':next(iter(found.values())),
                                                 'source':'automatic','time':time_hint,'reason':f'No matching {time_hint} variant is available. Choose a saved background.'}
    ready=[bid for bid in candidates if library.backgrounds[bid]['status']=='ready']
    target=ready[0] if len(candidates)==1 and len(ready)==1 else None
    return {'background_id':target,'status':'ready' if target else 'ambiguous','candidates':candidates,
            'location_text':next(iter(found.values())),'source':'automatic','time':time_hint}


def analyze(library,payload,tools=False):
    from app.screenplay_review import analyze_screenplay
    return analyze_screenplay(library,payload,tools)


def save_mapping(library,payload):
    library.refresh()
    key=normalize(payload.alias)
    if not key: raise AssetError('Alias cannot be blank')
    rows=library.characters if payload.asset_type=='character' else library.backgrounds
    target=payload.asset_id
    if not (payload.asset_type=='character' and target in ROLES) and (target not in rows or rows[target]['status']!='ready'):
        raise AssetError('Only a validated ready asset or a supported voice role can be selected')
    field='character_aliases' if payload.asset_type=='character' else 'background_aliases'
    with MAPPING_LOCK:
        saved=read_mappings(library)
        existing=saved[field].get(key)
        permanent=exact_character_candidates(library,key) if payload.asset_type=='character' else [cid for cid,r in rows.items() if key in {normalize(a) for a in r['aliases']}]
        if payload.asset_type=='character':
            permanent += [role for role,aliases in ROLE_ALIASES.items() if key in {normalize(a) for a in aliases}]
        if payload.scope=='remember':
            if (key in rows or payload.asset_type=='character' and key in ROLES) and key!=target: raise AssetError('Stable asset IDs cannot be reassigned')
            if (existing is not None and existing!=target or any(cid!=target for cid in permanent)) and not payload.confirm_conflict:
                raise MappingConflict('This alias already points to another asset. Confirm replacement before saving it for future stories.','alias_conflict')
            if key in GENERIC and not payload.confirm_generic:
                raise MappingConflict('This is a generic reference. Remembering it affects future unrelated stories. Confirm that you want a global mapping.','generic_alias')
            saved[field][key]=target
            library.storage.mkdir(parents=True,exist_ok=True)
            path=library.storage/'user_mappings.json'; temp=path.with_suffix('.tmp')
            temp.write_text(json.dumps(saved,ensure_ascii=False,indent=2),encoding='utf-8'); temp.replace(path)
    return {'scope':payload.scope,'alias':key,'asset_id':target,'saved':payload.scope=='remember'}


def snapshot_plan(plan,directory):
    """Freeze reviewed bytes for the job; edits in the live library cannot alter it."""
    root=directory/'asset_snapshot'
    result={**plan,'characters':{},'backgrounds':{}}
    for kind,bundles in (('characters',plan['characters']),('backgrounds',plan.get('backgrounds',{plan['background']['background_id']:plan['background']}))):
        for cid,bundle in bundles.items():
            target=root/kind/cid; target.mkdir(parents=True,exist_ok=True)
            for name in bundle['file_hashes']:
                destination=safe_path(target,name); destination.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(safe_path(bundle['directory'],name),destination)
            meta={k:v for k,v in bundle.items() if k not in ('directory','identity_hash','animations')}
            (target/('character.json' if kind=='characters' else 'metadata.json')).write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
            checked=load_character(cid,root) if kind=='characters' else load_background(cid,root)
            if checked['identity_hash']!=bundle['identity_hash']: raise AssetError('An asset changed during snapshot creation; review again.')
            result[kind][cid]=checked
            derived=bundle['directory']/'articulated/v1'
            if kind=='characters' and (derived/'rig.json').is_file():
                spec=json.loads((derived/'rig.json').read_text(encoding='utf-8'))
                destination=target/'articulated/v1';destination.mkdir(parents=True,exist_ok=True)
                for name in ['rig.json',*spec['hashes']]:shutil.copyfile(safe_path(derived,name),safe_path(destination,name))
    result['background']=result['backgrounds'][plan['background']['background_id']]
    return result
