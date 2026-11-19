"""Asset resolution for all screenplay events, with speech kept separately."""
import importlib.util
from pathlib import Path
import json
import os
from app.assets import normalize,mentions_alias,AssetError,asset_references
from app.engines.story_parser import parse_story
from app.review import read_mappings,resolver,resolve_character,background_match,WEAK
from app.director import ACTIONS,EMOTIONS,SHOTS
from app.scene_cache import fingerprint
from app.hardware import ffmpeg_binary,ffprobe_binary


def analyze_screenplay(library,payload,tools=False):
    library.refresh();issues=[];warnings=[]
    try:saved=read_mappings(library)
    except AssetError as exc:
        saved={'character_aliases':{},'background_aliases':{}}
        issues.append({'type':'mappings','source_text':'Saved aliases','reason':'invalid_json','message':str(exc)})
    project={}
    for key,value in payload.character_mappings.items():
        key=normalize(key)
        if key in project and project[key]!=value:raise AssetError('Conflicting normalized character aliases')
        project[key]=value
    aliases=set(project)|set(saved['character_aliases'])
    for row in library.characters.values():aliases.update(row['aliases'])
    locations=[a for row in library.backgrounds.values() for a in row['aliases'] if normalize(a) not in WEAK]+list(saved['background_aliases'])
    resolve=resolver(library,project,saved)
    parsed=parse_story(payload.story,resolve,character_aliases=sorted(aliases),location_aliases=locations,corrections=payload.script_corrections)
    events=parsed['events'];detected={}
    from app.semantic_ai import apply_assistance
    semantic_diagnostics=apply_assistance(events,library,payload.story,payload.interpretation_mode=='assisted',payload.semantic_ai_approved)
    from app.emotion import EmotionAnalyzer
    from app.screenplay import ScriptEvent,spoken_rows
    interpreted=[ScriptEvent.model_validate(e) for e in events]
    EmotionAnalyzer().apply(interpreted,resolve)
    events=[e.model_dump() for e in interpreted];parsed['events']=events;parsed['segments']=spoken_rows(interpreted,resolve)
    from app.screenplay_semantics import resolve_sound_events,ClarificationManager
    soundfile=Path(__file__).resolve().parents[1]/'assets/sounds/library.json'
    sounds=json.loads(soundfile.read_text(encoding='utf-8'))['sounds'];resolve_sound_events(events,sounds)
    for event in events:
        if event['metadata'].get('gaze_target_label'):
            target=resolve_character(library,event['metadata']['gaze_target_label'],project,saved)
            detected.setdefault(normalize(event['metadata']['gaze_target_label']),target)
            if target['status']=='ready':event['metadata']['gaze_target_id']=target['character_id']
        labels=list(event['character_labels'])
        if event['generate_voice']:labels.append(event['speaker_label'])
        for label in labels:
            key=normalize(label);row=resolve_character(library,label,project,saved);detected.setdefault(key,row)
            if row['status']=='ready' and row['role']=='visible' and row['character_id'] not in event['character_ids']:event['character_ids'].append(row['character_id'])
        def issue(message):issues.append({'type':'instruction','source_text':event['source_text'],'source_line':event['source_line'],
                                        'event_id':event['event_id'],'reason':'unresolved_instruction','message':message})
        if event['type']=='unresolved_instruction' and event['metadata'].get('blocking',True):issue(event['reason'])
        if event['metadata'].get('unresolved_delivery'):issue('Choose an emotion/delivery for the unrecognized parenthetical instruction.')
        if event['type']=='action':
            if not event['actions'] or any(a not in ACTIONS for a in event['actions']):issue('Select a supported rig action for this instruction.')
            if not labels and not event['metadata'].get('ensemble'):issue('Select a character for this action.')
        if event['emotion'] not in (*EMOTIONS,'whisper'):issue('Select a supported emotion or delivery.')
        if event['type']=='camera' and (event['camera_action'] not in SHOTS or event['camera_action']=='over_shoulder'):issue('Select a supported camera instruction. Over-shoulder framing requires missing back/profile artwork.')
        if event['type']=='sound_effect':
            soundfile=Path(__file__).resolve().parents[1]/'assets/sounds/library.json'
            sounds=json.loads(soundfile.read_text(encoding='utf-8'))['sounds']
            if event['sound_id'] not in sounds:issue('Select an available sound asset; this cue will never become speech.')
    characters=list(detected.values())
    if payload.renderer=='pillow':
        from app.engines.animation import LEGACY_ACTIONS
        for event in events:
            if event['type']=='action':
                for cid in event['character_ids']:
                    bundle=library.characters.get(cid,{}).get('_bundle',{})
                    if any(LEGACY_ACTIONS.get(a,a) not in bundle.get('animations',{}) for a in event['actions']):
                        issues.append({'type':'instruction','source_text':event['source_text'],'event_id':event['event_id'],'reason':'unsupported_action',
                                       'message':'This action needs the Godot rig. Choose Godot or a supported legacy animation.'})
    for row in characters:
        if row['status']!='ready':issues.append({'type':'character','source_text':row['speaker_text'],'reason':row['status'],'message':row.get('reason') or 'Choose a registered ready character or voice role.'})
    approved={r['key']:r['character_id'] for r in characters if r['status']=='ready'}
    if payload.scenes is not None:
        scenes=[s.model_dump() for s in payload.scenes];previous=0;ids=set()
        for scene in scenes:
            if scene['scene_id'] in ids or scene['start_segment']!=previous or not previous<scene['end_segment']<=len(events):raise AssetError('Scene ranges must partition every screenplay event in order')
            previous=scene['end_segment'];ids.add(scene['scene_id'])
        if previous!=len(events):raise AssetError('Scenes must cover every screenplay event')
    else:
        starts=[0]
        for index,event in enumerate(events):
            if index and event['type']=='scene_description' and event['metadata'].get('explicit_scene'):
                if any(e['type'] not in ('metadata','ignore') for e in events[starts[-1]:index]):starts.append(index)
            elif index and event['type']=='scene_description':
                prior=' '.join(e['text'] for e in events[starts[-1]:index] if e['type']=='scene_description')
                before=background_match(library,prior,saved);after=background_match(library,event['text'],saved)
                if before['background_id'] and after['background_id']!=before['background_id']:starts.append(index)
        scenes=[{'scene_id':f'scene_{i+1:03}','start_segment':start,'end_segment':starts[i+1] if i+1<len(starts) else len(events),'background_id':None,'location_text':''} for i,start in enumerate(starts)]
    for scene in scenes:
        group=events[scene['start_segment']:scene['end_segment']]
        descriptions=' '.join(e['text'] for e in group if e['type'] in ('scene_description','action'))
        times=' '.join(e['metadata'].get('time_of_day','') for e in group)
        explicit=next((e['background_id'] for e in group if e['background_id']),None)
        hint=next((e['metadata']['background_hint'] for e in group if e['metadata'].get('background_hint')),None)
        if hint in library.backgrounds:explicit=hint
        elif hint:
            family=[bid for bid in library.backgrounds if bid.startswith(hint+'_')]
            if family:
                desired='misty' if any(w in normalize(times+' '+descriptions) for w in ('কুয়াশা','কুয়াশা','fog','mist')) else 'night' if any(w in normalize(times) for w in ('রাত','night')) else 'day'
                explicit=next((bid for bid in family if bid.endswith('_'+desired)),next((bid for bid in family if bid.endswith('_day')),family[0]))
        match=background_match(library,descriptions+' '+times,saved)
        selected=explicit or scene['background_id'] or match['background_id']
        row=library.backgrounds.get(selected)
        scene.update(background_id=selected,status=row['status'] if row else match['status'],location_text=scene.get('location_text') or descriptions or 'Unspecified location',
                     candidates=match['candidates'],source='project' if payload.scenes is not None or explicit else match['source'])
        if not row or row['status']!='ready':issues.append({'type':'background','source_text':scene['location_text'],'scene_id':scene['scene_id'],'reason':'unresolved','message':'Choose a registered background for this scene.'})
        visible=list(dict.fromkeys(cid for e in group for cid in [*e['character_ids'],*([e['metadata']['gaze_target_id']] if e['metadata'].get('gaze_target_id') else [])]))
        scene['visible_characters']=visible
        scene['sound_settings']={k:v for e in group for k,v in e['metadata'].items() if k in ('ambience_ids','intentional_silence')}
        for event in group:
            event['scene_id']=scene['scene_id']
            if event['metadata'].get('ensemble'):event['character_ids']=visible
            if event['type']=='action' and not event['character_ids'] and not any(i.get('type')=='character' for i in issues):
                issues.append({'type':'instruction','source_text':event['source_text'],'event_id':event['event_id'],'reason':'unresolved_instruction','message':'Select a character present in this scene.'})
    tool_info={}
    if tools:
        selected_provider=os.getenv('DEFAULT_TTS_PROVIDER','chatterbox_bangla') if payload.voice_preference=='saved' else payload.voice_preference
        if selected_provider=='chatterbox_bangla':
            from app.voices.studio import configured
            tts_ready=configured('chatterbox_bangla')
        else:tts_ready=importlib.util.find_spec('TTS') is not None if selected_provider=='vits' else True
        tool_info={'tts_installed':not parsed['segments'] or tts_ready,'ffmpeg_found':bool(ffmpeg_binary()),'ffprobe_found':bool(ffprobe_binary())}
        for key,found in tool_info.items():
            if not found:issues.append({'type':'tool','source_text':key,'reason':'missing','message':key+' is required before generation.'})
    plan=None
    if not issues:
        bundles={r['character_id']:library.characters[r['character_id']]['_bundle'] for r in characters if r['role']=='visible'}
        backgrounds={s['background_id']:library.backgrounds[s['background_id']]['_bundle'] for s in scenes}
        plan={'characters':bundles,'backgrounds':backgrounds,'background':next(iter(backgrounds.values())),
              'review_scenes':[{k:s[k] for k in ('scene_id','start_segment','end_segment','background_id','location_text','visible_characters','sound_settings')} for s in scenes],
              'screenplay':events,'warnings':warnings}
        if payload.renderer=='godot':
            from app.rendering.godot_adapter import godot_binary,rig_description
            if not godot_binary():issues.append({'type':'tool','source_text':'Godot','reason':'missing','message':'Install Godot 4 or explicitly choose the legacy renderer.'})
            for cid,char in bundles.items():
                try:rig_description(char)
                except (ValueError,OSError,KeyError) as exc:issues.append({'type':'character','source_text':cid,'reason':'articulated_rig','message':str(exc)})
            warnings.append('Front-view articulated prototypes: review artwork/style and motion before production use.')
    # UI boundaries use events; speech preview/production use ONLY spoken segments.
    spoken_by_event={s['event_id']:s for s in parsed['segments']}
    units=[{**e,**spoken_by_event.get(e['event_id'],{}),'id':e['event_id'],'speaker_name':spoken_by_event.get(e['event_id'],{}).get('speaker_name') or e.get('speaker_label') or e['type'],'kind':e['type']} for e in events]
    spoken=parsed['segments']
    issues=ClarificationManager().group(issues)
    diagnostics=[d for e in events for d in e['metadata'].get('diagnostics',[])]+[{'event_id':e['event_id'],'source_line':e['source_line'],'reason':'sound_mapping','detail':e['metadata']['sound_diagnostic']} for e in events if e['metadata'].get('sound_diagnostic')]
    output={'ready':not issues,'diagnostics':diagnostics+semantic_diagnostics,'characters':characters,'scenes':scenes,'segments':units,'events':events,'spoken_segments':spoken,
            'character_mappings':approved,'issues':issues,'warnings':warnings,'tools':tool_info,
            'estimated_duration':{'min':round(sum(len(s['text']) for s in spoken)/16+sum(1.2 for e in events if e['type']=='action')),
                                  'max':round(sum(len(s['text']) for s in spoken)/8+sum(3.5 for e in events if e['type'] in ('action','camera','sound_effect'))),'is_estimate':True}}
    if plan and not issues:
        stable={'events':events,'characters':approved,'scenes':plan['review_scenes'],'assets':asset_references(plan),'mode':payload.duration_mode,'format':payload.video_format,
                'renderer':payload.renderer,'sounds':payload.sound_effects,'music':payload.music,'audio_levels':payload.audio_levels}
        stable['configuration']={kind:{cid:{k:v for k,v in value.items() if k not in ('directory','animations')} for cid,value in plan[kind].items()} for kind in ('characters','backgrounds')}
        if payload.renderer=='godot':stable['articulated']={cid:rig_description(c)['rig'] for cid,c in plan['characters'].items()}
        output['review_token']=fingerprint(stable)
    return output,parsed,plan
