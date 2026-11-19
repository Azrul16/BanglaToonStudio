"""Scene-level interpretation and registry-backed command semantics, without an LLM."""
import re
from app.assets import normalize,mentions_alias

META_HEADERS={'শিরোনাম':'title','title':'title','ধরন':'genre','genre':'genre','ব্যাকগ্রাউন্ড':'background_hint','background':'background_hint',
 'screen_text':'screen_text','স্ক্রিন টেক্সট':'screen_text','পর্দার লেখা':'screen_text','ambience':'ambience','পরিবেশের শব্দ':'ambience',
 'transition':'transition','দৃশ্যান্তর':'transition','অ্যাম্বিয়েন্স':'ambience','অ্যাম্বিয়েন্স':'ambience'}
DELIVERY={
 'সাবধান করে':('worried','cautious'),'সাবধানে':('worried','cautious'),'সতর্ক':('worried','cautious'),
 'পড়ার ভঙ্গিতে':('thinking','reading'),'পড়ার ভঙ্গিতে':('thinking','reading'),'পড়ে':('thinking','reading'),
 'আত্মবিশ্বাসী':('happy','confident'),'নিশ্চিত':('neutral','confident'),'অবাক হয়ে':('surprised','surprised'),
 'ধীরে':('neutral','soft'),'শান্তভাবে':('neutral','calm'),'হেসে':('laugh','laughing')}
# Semantic intent is distinct from the actual rig action. Alternatives remain inspectable.
ACTION_INTENTS=[
 ('thinking',r'চুপ করে ভাব|চিন্তা করে|ভাবতে থাকে','touch_chin','thinking'),
 ('scratch_head',r'মাথা চুলকা[া-ৌয়য়]*','scratch_head','confused'),
 ('observe',r'নিচু হ[য়য়]+[ো]*|পর্যবেক্ষণ করে|ভালো করে দেখে','touch_chin','thinking'),
 ('raise_finger',r'আঙুল তুলে|হাত তোলে','raise_hand','excited'),
 ('nod',r'মাথা না[ড়ড়]+[া-ৌয়য়]*','turn','neutral'),
 ('laugh',r'হেসে ওঠে|হাসতে থাকে','celebrate','laugh'),
 ('afraid',r'ভ[য়য়]+ পা[য়য়]*','fear','fear'),
 ('walk',r'ধীরে এগি[য়য়]+[ো]* যা[য়য়]*','walk','neutral'),
 ('look_back',r'পেছনে তাক[া-ৌয়য়]*|পিছনে তাক[া-ৌয়য়]*','turn','neutral'),
 ('clap',r'হাততালি দে[য়য়]*','celebrate','happy'),
 ('jump',r'লাফি[য়য়]+[ো]* ওঠে','celebrate','excited')]
MUSIC_TAGS={'mysterious_playful':'mystery','cheerful_ending':'happy','playful':'comedy','mysterious':'mystery','cheerful':'happy',
 'suspenseful':'suspense','sad':'emotional','peaceful':'calm'}
AMBIENCE_TAGS={'birds_soft_wind':['birds','wind'],'orchard':['birds','wind'],'village':['birds','wind'],'riverside':['water','wind','birds'],'railway':['station_distant','wind']}
SFX_TAGS={'funny_pop':['surprise'],'pop':['surprise'],'idea_chime':[],'idea':[],'leaves_rustling':['rustling_leaves'],'leaves':['rustling_leaves']}


def delivery(text):
    value=normalize(text)
    return next(((emotion,style) for phrase,(emotion,style) in DELIVERY.items() if normalize(phrase) in value),None)


def classify_command(header,value,event):
    """Only explicit syntax enters this pass; no speaker lookup is attempted."""
    key=META_HEADERS.get(header)
    if not key:return False
    event.type='screen_text' if key=='screen_text' else 'metadata';event.text=value
    event.metadata[key]=value
    if key=='ambience':event.metadata['ambience_ids']=AMBIENCE_TAGS.get(normalize(value),[])
    return True


class SceneSemanticInterpreter:
    def __init__(self,aliases,resolve):self.aliases=aliases;self.resolve=resolve

    def apply(self,events):
        scene=None;cast=[];subject=[];emotions={};diagnostics=[]
        # Explicit casts can be placed before or after the first scene heading.
        first_scene=next((e.source_line for e in events if e.type=='scene_description' and e.metadata.get('explicit_scene')),0)
        global_cast=list(dict.fromkeys(label for e in events if e.metadata.get('cast') and (not first_scene or e.source_line<first_scene) for label in e.character_labels))
        scene_cast={}
        for e in events:
            if e.metadata.get('cast'):scene_cast[e.scene_id]=list(e.character_labels)
        for event in events:
            unique={}
            for label in event.character_labels:
                try:key=self.resolve(label)['character_id']
                except ValueError:key=normalize(label)
                if key=='unresolved':key=normalize(label)
                unique.setdefault(key,label)
            event.character_labels=list(unique.values())
            if event.scene_id!=scene:scene=event.scene_id;cast=list(scene_cast.get(scene,global_cast));subject=[];emotions={}
            if event.metadata.get('cast'):cast=list(event.character_labels)
            text=normalize(event.text);source=normalize(event.source_text)
            essential=bool(re.search(r'আকাশ|উ[ড়ড়]|নদী পার|আগুন|বিস্ফোর|মারা|বাঁচা|essential|গুরুত্বপূর্ণ',text))
            if essential and event.type in ('action','unresolved_instruction'):
                event.type='unresolved_instruction';event.metadata['blocking']=True;event.reason='Essential movement or effect has no validated animation; choose how to represent it.'
                continue
            intents=[(name,action,emotion) for name,pattern,action,emotion in ACTION_INTENTS if re.search(pattern,text)]
            if intents and event.type in ('action','unresolved_instruction'):
                event.type='action';event.actions=list(dict.fromkeys(event.actions+[a for _,a,_ in intents]));event.metadata['action_intents']=[name for name,_,_ in intents]
                if event.emotion=='neutral':event.emotion=next((feeling for _,_,feeling in intents if feeling!='neutral'),'neutral')
                for name,_,_ in intents:
                    if name in ('jump','clap','nod','observe','raise_finger'):diagnostics.append({'event_id':event.event_id,'source_line':event.source_line,'reason':'visual_alternative','detail':name+' uses the existing supported gesture; literal pose detail is not authored.'})
            if event.type=='action':
                if not event.character_labels:
                    pronoun=re.match(r'^(সে|ও|তারা|দুজন|তিনজন|সবাই)(?:\s|[।.!?]|$)',text)
                    if pronoun:
                        word=pronoun[1]
                        if word in ('সে','ও') and len(subject)==1:event.character_labels=list(subject)
                        elif word in ('তারা','সবাই') and cast:event.character_labels=list(cast);event.metadata['ensemble']=True
                        elif word=='দুজন' and len({self.resolve(c)['character_id'] for c in cast})==2:event.character_labels=list(cast);event.metadata['ensemble']=True
                        elif word=='তিনজন' and len({self.resolve(c)['character_id'] for c in cast})==3:event.character_labels=list(cast);event.metadata['ensemble']=True
                # The syntax pass may have tentatively extracted a pronoun as a name.
                elif all(normalize(c) in ('সে','ও','তারা','দুজন','তিনজন','সবাই') for c in event.character_labels):
                    event.character_labels=[]
                    word=text.split()[0]
                    if word in ('সে','ও') and len(subject)==1:event.character_labels=list(subject)
                    elif word in ('তারা','সবাই') and cast:event.character_labels=list(cast);event.metadata['ensemble']=True
                    elif word=='দুজন' and len({self.resolve(c)['character_id'] for c in cast})==2:event.character_labels=list(cast);event.metadata['ensemble']=True
                if len(event.character_labels)==1:
                    subject=list(event.character_labels)
                    if event.emotion!='neutral':emotions[self.resolve(subject[0])['character_id']]=event.emotion
            elif event.type=='dialogue':
                subject=[event.speaker_label]
                if event.emotion=='neutral' and not event.metadata.get('delivery_tag'):
                    event.emotion=emotions.get(event.speaker_id,'neutral');event.metadata['emotion_inherited']=event.emotion!='neutral'
            if event.type=='unresolved_instruction':
                bracketed=event.source_text.strip().startswith('[')
                labels=[a for a in self.aliases if mentions_alias(text,a)]
                optional=bool(re.search(r'মাথা|ভঙ্গি|মুখ|চোখ|ভাব|পর্যবেক্ষণ|নিচু|হাত',text))
                if labels and optional and not essential:
                    event.type='action';event.character_labels=labels;event.actions=['idle'];event.reason=None
                    diagnostics.append({'event_id':event.event_id,'source_line':event.source_line,'reason':'minor_motion_omitted','detail':event.source_text})
                elif not bracketed and not labels and not essential:
                    event.metadata['blocking']=False;event.metadata['narrative_context']=True
                    diagnostics.append({'event_id':event.event_id,'source_line':event.source_line,'reason':'unspoken_context','detail':event.source_text})
        return diagnostics


class ClarificationManager:
    """One blocking issue per identity or instruction, never one question per mention."""
    def group(self,issues):
        result=[];seen=set()
        for issue in issues:
            key=(issue['type'],issue.get('event_id') or issue.get('scene_id') or normalize(issue.get('source_text','')))
            if key not in seen:result.append(issue);seen.add(key)
        return result


def resolve_sound_events(events,library):
    for event in events:
        metadata=event['metadata']
        if event['type']=='sound_effect' and event['sound_id'] not in library:
            requested=normalize(event['text']);choices=SFX_TAGS.get(requested,[requested])
            matched=next((key for key in choices if key in library),None)
            if matched:
                event['sound_id']=matched
                if matched!=requested:metadata['sound_diagnostic']='Requested '+requested+'; compatible registered accent '+matched+' selected.'
            else:
                event['type']='metadata';metadata['sound_diagnostic']='Requested '+requested+'; no suitable registered SFX, omitted.'
        if 'ambience' in metadata:
            requested=normalize(metadata['ambience']);ids=metadata.get('ambience_ids') or [key for key in library if key in requested.split('_') and not key.startswith('music')]
            metadata['ambience_ids']=[key for key in ids if key in library]
            if not metadata['ambience_ids']:metadata['sound_diagnostic']='No matching registered ambience; location ambience retained.'
