"""Typed, conservative screenplay interpretation. Unlabelled prose is NEVER speech."""
import re
from abc import ABC,abstractmethod
from typing import Literal
from pydantic import BaseModel,Field,model_validator,ConfigDict
from app.assets import normalize,mentions_alias

EventType=Literal['scene_description','action','dialogue','narration','camera','sound_effect','screen_text','emotion','metadata','unresolved_instruction','ignore']
SPEAKABLE_TYPES={'dialogue','narration'}
EMOTION_WORDS={'ভয়ে':'fear','ভয়ে':'fear','ভয়':'fear','ভয়':'fear','ভীত':'fear','কৌতূহলী':'curious','কৌতূহল':'curious',
 'চমকে':'surprised','অবাক':'surprised','রেগে':'angry','রাগে':'angry','আনন্দে':'happy','খুশি':'happy','দুঃখে':'sad','হেসে':'laugh',
 'ফিসফিস':'whisper','চিৎকার':'excited','উত্তেজিত':'excited','বিভ্রান্ত':'confused'}
# Specific phrases precede their shorter overlapping alternatives; all disjoint matches survive.
ACTION_PHRASES=[(r'উঠে দাঁ[ড়ড়]+া[য়য়]*','stand_up'),(r'পেছনে তাক[াা-ৌয়য়]*','turn'),(r'মাথা ঘোরা[য়য়]*','turn'),(r'কাছে যা[য়য়]*|দিকে এগি[য়য়]+[ো]*','move_closer'),
 (r'দৌ[ড়ড়]+[োা-ৌয়য়]*','run'),(r'হাঁট[া-ৌয়য়তে]*|হেঁটে','walk'),(r'সামনে এগি[য়য়]+[ো]*[ যাা-ৌয়য়]*','move_closer'),
 (r'পিছি[য়য়]+[ো]*|পেছনে সরে','step_back'),(r'হাত না[ড়ড়]+[োা-ৌয়য়]*','wave'),(r'ইশারা করে|আঙুল দি[য়য়]+[ো]* দেখ','point'),
 (r'বসে প[ড়ড়]+[ো]*|বসে আছে|বস[োা-ৌয়য়]*','sit'),(r'দাঁ[ড়ড়]+ি[য়য়]+[ো]* আছে|দাঁ[ড়ড়]+াল|থেমে যা[য়য়]*|থামে','stop'),
 (r'হাসতে থাকে|হাস[োা-ৌয়য়]*','celebrate'),(r'চোখ ব[ড়ড়]+ করে|চমকে ওঠে','stop'),
 (r'ভ[য়য়]+ পে[য়য়]+[ো]*|ভীত হ[য়য়]*','fear'),(r'চারপাশে তাকা[য়য়]*|তাক[া-ৌয়য়]*','look_around')]
SCENE_HEADERS={'দৃশ্য','scene','লোকেশন','স্থান','location'}
TIME_HEADERS={'সময়','সময়','time'}
CAST_HEADERS={'চরিত্র','characters','cast'}
NARRATOR={'বর্ণনাকারী','বর্ণনা','কথক','narrator','narration'}
RESERVED={'নোট','note','নির্দেশনা','instruction','আলো','lighting','রং','color','duration','সময়সীমা','সময়সীমা'}
SOUND_ALIASES={'পাতার মর্মর শব্দ':'rustling_leaves','পাতার শব্দ':'rustling_leaves','rustling_leaves':'rustling_leaves','leaves_rustling':'rustling_leaves',
 'বাতাস':'wind','wind':'wind','birds':'birds','পাখির ডাক':'birds','footstep':'footstep','পায়ের শব্দ':'footstep','night':'night','surprise':'surprise'}


class ScriptEvent(BaseModel):
    model_config=ConfigDict(extra='forbid')
    event_id:str
    type:EventType
    source_text:str
    source_line:int=Field(ge=1)
    source_end_line:int=Field(ge=1)
    scene_id:str='scene_001'
    text:str=''
    generate_voice:bool=False
    explicit_narration:bool=False
    speaker_label:str|None=None
    speaker_id:str|None=None
    character_labels:list[str]=Field(default_factory=list)
    character_ids:list[str]=Field(default_factory=list)
    actions:list[str]=Field(default_factory=list)
    emotion:str='neutral'
    delivery:str|None=None
    camera_action:str|None=None
    sound_id:str|None=None
    background_id:str|None=None
    metadata:dict=Field(default_factory=dict)
    reason:str|None=None
    duration_seconds:float|None=Field(default=None,gt=0,le=30)

    @model_validator(mode='after')
    def safe_speech(self):
        if self.generate_voice and (self.type not in SPEAKABLE_TYPES or self.type=='narration' and not self.explicit_narration):
            raise ValueError('Only dialogue or explicitly requested narration may generate voice')
        if self.generate_voice and not self.text.strip():raise ValueError('Spoken text cannot be blank')
        return self


class EventCorrection(BaseModel):
    model_config=ConfigDict(extra='forbid')
    source_text:str
    type:EventType
    text:str|None=None
    speaker_label:str|None=None
    character_id:str|None=None
    action:str|None=None
    emotion:str='neutral'
    background_id:str|None=None
    camera_action:str|None=None
    sound_id:str|None=None
    duration_seconds:float|None=Field(default=None,gt=0,le=30)


class Screenplay(BaseModel):
    events:list[ScriptEvent]


def emotion_for(text):return next((value for phrase,value in EMOTION_WORDS.items() if normalize(phrase) in normalize(text)),'neutral')


def action_matches(text):
    matches=[];occupied=[]
    for pattern,action in ACTION_PHRASES:
        for match in re.finditer(pattern,normalize(text)):
            if any(match.start()<end and match.end()>start for start,end in occupied):continue
            occupied.append((match.start(),match.end()));matches.append((match.start(),action))
    return list(dict.fromkeys(action for _,action in sorted(matches)))


def assert_speakable(event):
    kind=event.get('type',event.get('kind')) if isinstance(event,dict) else event.type
    get=event.get if isinstance(event,dict) else lambda key,default=None:getattr(event,key,default)
    if kind not in SPEAKABLE_TYPES or not get('generate_voice',False) or kind=='narration' and not get('explicit_narration',False):
        raise ValueError('Speech blocked: this is not dialogue or explicitly marked narration. Analyze the screenplay again.')
    if not get('text','').strip():raise ValueError('Speech blocked: blank dialogue')
    return event


def get_spoken_segments(events):
    result=[]
    for event in events:
        get=event.get if isinstance(event,dict) else lambda key,default=None:getattr(event,key,default)
        if get('type',get('kind')) in SPEAKABLE_TYPES and get('generate_voice',False):
            assert_speakable(event);result.append(event)
    return result


class ScriptInterpreter(ABC):
    @abstractmethod
    def interpret(self,script:str,corrections=None)->Screenplay:raise NotImplementedError


def script_units(script):
    """Split prose outside quotation marks, retaining physical source line numbers."""
    for number,line in enumerate(script.replace('\r\n','\n').replace('\r','\n').split('\n'),1):
        if ':' in line or '：' in line or line.lstrip().startswith('['):
            yield number,line;continue
        start=0;closing=None
        for index,char in enumerate(line):
            if closing:
                if char==closing:
                    closing=None
                    if line[index+1:index+2] not in ('।','.','!','?'):
                        yield number,line[start:index+1];start=index+1
            elif char in ('“','‘','"'):closing={'“':'”','‘':'’','"':'"'}[char]
            elif char in ('।','!','?') and (index+1==len(line) or line[index+1].isspace()):
                yield number,line[start:index+1];start=index+1
        if line[start:].strip():yield number,line[start:]


class RuleBasedScriptInterpreter(ScriptInterpreter):
    def __init__(self,resolve,character_aliases=None,location_aliases=None):
        self.resolve=resolve;self.character_aliases=character_aliases or [];self.location_aliases=location_aliases or []

    def interpret(self,script,corrections=None):
        if not isinstance(script,str) or not script.strip():raise ValueError('Please enter a Bengali screenplay.')
        if len(script)>30000:raise ValueError('Script is too long (max 30,000 characters).')
        from app.screenplay_semantics import classify_command,delivery,MUSIC_TAGS
        events=[];scene=0;pending_emotions={};seen_scene=False
        for number,original in script_units(script):
            if not original.strip():continue
            source=original.strip();body=source
            bracketed=(body.startswith('[') and body.endswith(']'))
            if bracketed:body=body[1:-1].strip()
            body=re.sub(r'^(?:[-–—]|#{1,6})\s*','',body).strip('* ')
            event=ScriptEvent(event_id=f'event_{len(events)+1:03}',type='unresolved_instruction',source_text=original,
                              source_line=number,source_end_line=number,text=body)
            # Explicit nested headings are syntax, never character identities.
            body=re.sub(r'^(?:সংলাপ|dialogue)\s*[:：]\s*','',body,flags=re.I)
            action_header=re.match(r'^(?:অ্যাকশন|কাজ|action)\s*[:：]\s*(.+)$',body,re.I)
            if action_header:body=action_header[1];event.text=body
            attributed=re.match(r'^(.+?)\s+(ফিসফিস করে বলল|চিৎকার করে বলল|জিজ্ঞেস করল|উত্তর দিল|বললো|বলল|বলে)\s*[,،:]\s*(.+)$',body)
            if attributed and not re.search(r'মনে মনে|মনে ভাব|লিখ|লেখা|সাইনবোর্ড',attributed[1]):
                prefix=attributed[1]
                known=sorted((a for a in self.character_aliases if normalize(prefix).startswith(normalize(a)+' ') or normalize(prefix)==normalize(a)),key=len,reverse=True)
                if known:
                    actor=known[0];spoken=attributed[3].strip()
                    quoted_text=re.match(r'^[“"‘](.*)[”"’][।.!?]*$',spoken)
                    if quoted_text:spoken=quoted_text[1]
                    stage=prefix[len(actor):].strip();feeling=emotion_for(prefix)
                    target=next((a for a in self.character_aliases if normalize(a)!=normalize(actor) and mentions_alias(normalize(stage),a)),None)
                    if stage and ('তাক' in stage or 'হেসে' in stage):
                        action=ScriptEvent(event_id=event.event_id,type='action',source_text=original,source_line=number,source_end_line=number,
                            scene_id=f'scene_{max(1,scene):03}',text=prefix,character_labels=[actor],actions=['turn'] if 'তাক' in stage else ['celebrate'],emotion=feeling,
                            metadata={'gaze_target_label':target,'prose_attribution':True})
                        events.append(action);event.event_id=f'event_{len(events)+1:03}'
                    body=actor+(' (ফিসফিস)' if 'ফিসফিস' in attributed[2] else ' (চিৎকার)' if 'চিৎকার' in attributed[2] else '')+': '+spoken
                    event.metadata.update(quoted_dialogue=True,attribution_context=prefix)
                    event.emotion=feeling
            quoted=re.match(r'^(.{1,55}?)\s+(ফিসফিস করে বলল|চিৎকার করে বলল|জিজ্ঞেস করল|উত্তর দিল|বললো|বলল|বলে)\s*[,،:—-]?\s*[“"‘](.+)[”"’][।.!?]*$',body)
            if quoted and not re.search(r'মনে মনে|মনে ভাব|লিখ|লেখা|সাইনবোর্ড',quoted[1]):
                label=quoted[1];tag=' (ফিসফিস)' if 'ফিসফিস' in quoted[2] else ' (চিৎকার)' if 'চিৎকার' in quoted[2] else ''
                body=label+tag+': '+quoted[3];event.metadata['quoted_dialogue']=True
            colon=re.match(r'^([^:：\n]{1,100})[:：]\s*(.*)$',body)
            if not colon:
                dash=re.match(r'^(.+?)\s+[—–]\s+(.+)$',body)
                if dash and normalize(dash[1]) in {normalize(a) for a in self.character_aliases}:colon=re.match(r'^([^:]+):\s*(.*)$',dash[1]+': '+dash[2])
            header=normalize(colon[1].strip('* ')) if colon else None
            if colon and classify_command(header,colon[2],event):pass
            elif header in SCENE_HEADERS:
                scene=scene+1 if seen_scene else 1;seen_scene=True;pending_emotions={};event.type='scene_description';event.text=colon[2];event.metadata['explicit_scene']=True
            elif header in TIME_HEADERS:event.type='metadata';event.metadata={'time_of_day':colon[2]};event.text=colon[2]
            elif header in CAST_HEADERS:
                event.type='metadata';event.character_labels=[s.strip() for s in re.split(r'[,،;]| এবং | ও ',colon[2]) if s.strip()];event.metadata={'cast':True}
            elif header in {'music','bgm','সঙ্গীত','সংগীত','মিউজিক','আবহসংগীত'}:
                from app.audio.sound_director import MOODS
                content=normalize(colon[2]);mood=MUSIC_TAGS.get(content) or next((key for key,words in MOODS.items() if key==content or any(w in content for w in words)),None)
                event.type='metadata';event.metadata={'music_mood':mood};event.text=colon[2]
                if content in ('fade_out','fade out','বন্ধ','stop'):event.metadata={'music_control':'fade_out'}
                elif not mood:event.metadata={'sound_diagnostic':'No registered compatible music mood; automatic scene music retained.'}
            elif header in {'silence','নীরবতা'}:
                event.type='metadata';event.metadata={'intentional_silence':normalize(colon[2]) not in ('off','না','false')}
            elif header in {'sfx','sound','শব্দ','শব্দ প্রভাব','সাউন্ড ইফেক্ট'}:
                event.type='sound_effect';event.text=colon[2];event.sound_id=SOUND_ALIASES.get(normalize(colon[2]))
                if not event.sound_id:event.reason='Select a registered sound asset; the sound instruction is not speech.'
            elif header in {'emotion','আবেগ','অনুভূতি','delivery'}:
                event.type='emotion';event.emotion=emotion_for(colon[2])
            elif header in {'camera','ক্যামেরা'} or normalize(body).startswith(('ক্যামেরা','camera ')):
                event.type='camera';event.camera_action='wide' if any(p in normalize(body) for p in ('দূরে','zoom out','wide')) else 'close_up' if any(p in normalize(body) for p in ('কাছে','এগো','এগি','zoom','মুখের')) else None
                from app.director import SHOTS
                requested=normalize(colon[2]) if colon else ''
                if requested in SHOTS:event.camera_action=requested
                if not event.camera_action:event.reason='Choose a supported camera shot; the instruction is not speech.'
            elif colon and header not in RESERVED and not bracketed:
                label=colon[1].strip('*【】 ')
                if label.startswith('[') and label.endswith(']'):label=label[1:-1].strip()
                tag=re.search(r'\s*[\(\[]([^\)\]]+)[\)\]]\s*$',label)
                if tag:
                    label=label[:tag.start()].strip();event.emotion=emotion_for(tag[1]);event.delivery='shout' if 'চিৎকার' in tag[1] else 'whisper' if 'ফিসফিস' in tag[1] else None
                    event.metadata['delivery_tag']=tag[1]
                    interpreted=delivery(tag[1])
                    if interpreted:event.emotion,event.delivery=interpreted
                    elif event.emotion=='neutral' and normalize(tag[1]) not in ('স্বাভাবিক','neutral','normal'):event.metadata['delivery_diagnostic']='Unrecognized delivery retained; neutral supported voice delivery used.'
                # Unknown short names remain resolvable via the existing character picker.
                if label and len(label.split())<=4 and normalize(label) not in RESERVED:
                    info=self.resolve(label)
                    event.type='narration' if normalize(label) in NARRATOR or info['character_id']=='narrator' else 'dialogue'
                    event.explicit_narration=event.type=='narration';event.generate_voice=True
                    event.speaker_label=label;event.speaker_id=info['character_id'];event.text=colon[2].strip('* ').strip('“”"')
                    if event.type=='dialogue':event.character_labels=[label]
            else:
                event.actions=action_matches(body);event.emotion=emotion_for(body)
                event.character_labels=[a for a in self.character_aliases if mentions_alias(normalize(body),a)]
                if event.actions:
                    event.type='action'
                    acting_text=re.split(r'\s+[^ ]+(?:ের|র) দিকে',body,maxsplit=1)[0]
                    if acting_text!=body:event.character_labels=[a for a in event.character_labels if mentions_alias(normalize(acting_text),a)]
                    if not event.character_labels and any(p in body for p in ('দুজন','তারা','সবাই','একে অপর')):event.metadata['ensemble']=True
                    elif not event.character_labels:
                        first=re.split(r'\s+(?:ধীরে|ভয়|ভয়|গাছের|হাঁট|দৌ|সামনে|পেছনে|হাত|মাথা|বসে|উঠে)',body,maxsplit=1)[0].strip()
                        if first and len(first.split())<=3:event.character_labels=[first]
                elif event.character_labels and event.emotion!='neutral':event.type='emotion'
                elif any(mentions_alias(normalize(body),a) or normalize(a) in normalize(body) for a in self.location_aliases if len(normalize(a))>2) or re.search(r'পৌঁছ|প্রবেশ কর|ঢুক',body):event.type='scene_description'
                elif any(p in body for p in ('পাতার শব্দ','শব্দ শোনা','মর্মর')):
                    event.type='sound_effect';event.sound_id='rustling_leaves'
            if scene==0:scene=1
            if event.type not in ('dialogue','ignore'):
                event.character_labels=list(dict.fromkeys([*event.character_labels,*[a for a in self.character_aliases if mentions_alias(normalize(event.text),a)]]))
            event.scene_id=f'scene_{scene:03}'
            correction=(corrections or {}).get(event.event_id)
            if correction:
                correction=EventCorrection.model_validate(correction)
                if correction.source_text!=event.source_text:raise ValueError('Script correction is stale; review the edited source line again.')
                event.type=correction.type;event.text=correction.text if correction.text is not None else event.text
                event.speaker_label=correction.speaker_label;event.character_labels=[correction.character_id] if correction.character_id else []
                event.actions=[correction.action] if correction.action else [];event.emotion=correction.emotion
                event.delivery='whisper' if correction.emotion=='whisper' else None;event.metadata.pop('unresolved_delivery',None)
                event.background_id=correction.background_id;event.camera_action=correction.camera_action;event.sound_id=correction.sound_id
                event.duration_seconds=correction.duration_seconds;event.reason=None
                event.generate_voice=event.type in SPEAKABLE_TYPES;event.explicit_narration=event.type=='narration'
                if event.type=='narration':event.speaker_label='narrator'
                if event.type=='dialogue' and not event.speaker_label:raise ValueError('Select a speaker for dialogue')
                if event.generate_voice:
                    event.speaker_id=self.resolve(event.speaker_label)['character_id']
                    if event.type=='dialogue':event.character_labels=[event.speaker_label]
            if event.type=='unresolved_instruction':event.reason='Uncertain instruction: classify this line. It will never be spoken automatically.'
            if event.type=='action':event.metadata['continuous']='থাকে' in body
            if event.type=='emotion':
                keys=[self.resolve(label)['character_id'] for label in event.character_labels] or ['*']
                for key in keys:pending_emotions[key]=event.emotion
            elif event.generate_voice and event.emotion=='neutral' and not event.metadata.get('delivery_tag') and not correction:
                event.emotion=pending_emotions.pop(event.speaker_id,pending_emotions.get('*','neutral'))
                if event.emotion=='whisper':event.delivery='whisper'
            events.append(ScriptEvent.model_validate(event.model_dump()))
        from app.screenplay_semantics import SceneSemanticInterpreter
        diagnostics=SceneSemanticInterpreter(self.character_aliases,self.resolve).apply(events)
        for event in events:event.metadata['diagnostics']=[d for d in diagnostics if d['event_id']==event.event_id]
        from app.emotion import EmotionAnalyzer
        EmotionAnalyzer().apply(events,self.resolve)
        return Screenplay(events=events)


def spoken_rows(events,resolve):
    result=[]
    for item in get_spoken_segments(events):
        event=item.model_dump() if isinstance(item,ScriptEvent) else item
        info=resolve(event['speaker_label'])
        chunks=[];current=''
        sentences=[]
        for sentence in re.split(r'(?<=[।!?\.])\s+',event['text']):
            if len(sentence)>1500:raise ValueError('A spoken sentence exceeds 1,500 characters. Split the explicitly spoken line.')
            fragment=''
            for word in sentence.split():
                if fragment and len(fragment)+len(word)+1>140:sentences.append(fragment);fragment=''
                fragment=(fragment+' '+word).strip()
            if fragment:sentences.append(fragment)
        for sentence in sentences:
            if current and len(current)+len(sentence)+1>140:chunks.append(current);current=''
            current=(current+' '+sentence).strip()
        if current:chunks.append(current)
        for part,text in enumerate(chunks):
            result.append({**event,'text':text,'part_index':part,'id':f'segment_{len(result)+1:03}','kind':event['type'],'speaker':info['character_id'],
                           'speaker_name':info['name_bn'],'off_screen':info['off_screen'],'voice_id':info['voice_id'],
                           'scene_index':len(result)+1,'resolution_status':info.get('status','ready')})
    return result
