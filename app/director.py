"""Explicit, inspectable Bengali direction rules; no unrestricted story inference."""
from copy import deepcopy
from app.assets import normalize,mentions_alias
from app.motion import PROFILES,DEFAULT

ACTIONS=('idle','walk','run','stop','talk','wave','point','raise_hand','fold_arms','scratch_head','touch_chin','look_around','explain','confused','celebrate','fear','sit','stand_up','step_back','move_closer','move_away','turn')
EMOTIONS=('neutral','happy','sad','surprised','angry','worried','curious','fear','thinking','laugh','cry','excited','confused','whisper')
SHOTS=('establishing','wide','medium','close_up','two_shot','reaction','over_shoulder')
RULES=[(('দৌড়','দৌড়'),'run','neutral'),(('হাঁট','হেঁটে'),'walk','neutral'),(('থাম','দাঁড়াল','দাঁড়াল'),'stop','neutral'),
       (('ভয়','ভয়','ভীত'),'fear','fear'),(('অবাক','আশ্চর্য','চমকে'),'stop','surprised'),
       (('হাত নাড়','হাত নাড়'),'wave','happy'),(('ইশারা','আঙুল'),'point','curious'),(('বস','বসে'),'sit','neutral'),
       (('উঠে দাঁড়','উঠে দাঁড়'),'stand_up','neutral'),(('পেছনে','পিছিয়ে'),'step_back','worried'),
       (('হাস','আনন্দ'),'celebrate','happy'),(('কাঁদ','দুঃখ'),'idle','sad'),(('রাগ','রেগে'),'explain','angry'),
       (('ভাব','চিন্তা'),'touch_chin','thinking'),(('কী','কেন','কোথায়','কোথায়','?'),'confused','curious')]


class ListenerReactionController:
    def direction(self,cid,index,speaker_index,scene,emotion):
        return {'action':'idle','emotion':'curious' if emotion=='curious' else 'worried' if emotion=='fear' else 'neutral',
                'gaze':1 if index<speaker_index else -1,'start':scene['start']+.3,'end':scene['end'],
                'reason':'Listen toward the active speaker; mouth closed.'}


class IntelligentCartoonDirector:
    def plan(self,timeline,plan,clips,overrides=None):
        if 'screenplay' in plan:return self.screenplay_plan(timeline,plan,clips,overrides or {})
        overrides=overrides or {};directions=[];listeners=ListenerReactionController()
        by_id={c['id']:c for c in clips}
        for sequence,source in enumerate(timeline['scenes']):
            scene=deepcopy(source);clip=by_id.get(scene.get('clip_id'),{});content=normalize(clip.get('text',''))
            visible=scene['visible_characters'];speaker=scene.get('speaker');speaker_index=visible.index(speaker) if speaker in visible else 0
            named=[(content.find(normalize(alias)),cid) for cid in visible for alias in [cid,plan['characters'][cid].get('name_bn','')]
                   if alias and mentions_alias(content,alias)]
            active=speaker if speaker in visible else min(named)[1] if named else visible[0] if visible else None
            action='talk' if speaker in visible else 'walk' if scene['kind']=='intro' else 'idle';emotion='neutral';reason='Neutral direction; edit the storyboard for a specific intended action.'
            for words,selected,feeling in RULES:
                if any(word in content for word in words):action,emotion,reason=selected,feeling,'Bengali keyword: '+next(w for w in words if w in content);break
            if speaker in visible and action in ('idle','stop','confused'):action='explain' if emotion=='curious' else 'talk'
            override=overrides.get(scene.get('clip_id',''),{})
            if override.get('actor_id'):
                if override['actor_id'] not in visible:raise ValueError('The storyboard actor is not present in this scene')
                active=override['actor_id']
            if speaker not in visible and active in visible:speaker_index=visible.index(active)
            action=override.get('action',action);emotion=override.get('emotion',emotion)
            if action not in ACTIONS or emotion not in EMOTIONS:raise ValueError('Unsupported storyboard action or emotion')
            actors={}
            for index,cid in enumerate(visible):
                actor=listeners.direction(cid,index,speaker_index,scene,emotion)
                actor.update(position_x=(index+1)/(len(visible)+1),ground_y=.82 if timeline['width']>timeline['height'] else .82)
                if cid==speaker and cid!=active:actor.update(action='talk',reason='Speak the approved dialogue while the separately selected actor reacts.')
                if cid==active:
                    actor.update(action=action,emotion=emotion,start=scene['start'],reason=override.get('reason',reason),
                                 gaze=1 if index<len(visible)-1 else -1)
                    if action in ('walk','run','move_closer','move_away','step_back'):
                        distance=90 if action!='run' else 180
                        if action=='step_back':distance=-45
                        actor.update(from_x=-distance,to_x=0,speed=distance/max(.2,scene['end']-scene['start'])/.7)
                actors[cid]=actor
            shot=override.get('shot','establishing' if scene['kind']=='intro' else 'reaction' if scene['kind']=='reaction' and emotion in ('fear','surprised') else 'medium' if emotion in ('fear','surprised') else 'two_shot' if len(visible)==2 else 'wide')
            if shot not in SHOTS:raise ValueError('Unsupported camera shot')
            scene.update(actors=actors,camera={'shot':shot,'target':override.get('target',active)},emotion=emotion,
                         environment={'ambience':'birds' if 'day' in scene['background_id'] else 'night' if 'night' in scene['background_id'] else 'wind'},
                         direction_reason=reason)
            directions.append(scene)
        return directions

    def screenplay_plan(self,timeline,plan,clips,overrides):
        directions=[];persistent={};camera={'shot':'wide','target':None};source=None;last_speaker=None;explicit_camera=False
        for original in timeline['scenes']:
            scene=deepcopy(original);event=scene['instruction'];visible=scene['visible_characters']
            if source!=scene['source_scene_id']:persistent={};camera={'shot':'establishing','target':None};source=scene['source_scene_id'];last_speaker=None;explicit_camera=False
            speaker=scene.get('speaker');index=visible.index(speaker) if speaker in visible else 0
            actors={cid:ListenerReactionController().direction(cid,i,index,scene,event['emotion']) for i,cid in enumerate(visible)}
            for cid,state in persistent.items():
                if cid in actors:actors[cid].update(state)
            targets=event['character_ids']
            if scene['kind']=='action':
                for cid in targets:
                    if cid not in actors:raise ValueError('Action character is not present in its scene')
                    action=event['actions'][0]
                    state={'action':action,'emotion':event['emotion'],'start':scene['start'],'end':scene['end'],
                           'gaze':-1 if 'পেছনে' in event['source_text'] else actors[cid]['gaze'],'reason':'Explicit screenplay instruction, line '+str(event['source_line'])}
                    if event['metadata'].get('ensemble'):state['gaze']=1 if visible.index(cid)==0 else -1
                    if action in ('walk','run','move_closer','move_away','step_back'):
                        state.update(from_x=-75 if action!='step_back' else 30,to_x=0,speed=60 if action!='run' else 130)
                    actors[cid].update(state)
                    if event['metadata'].get('continuous'):persistent[cid]=state
                    else:persistent.pop(cid,None)
            elif scene['kind']=='speech':
                override=overrides.get(scene['clip_id'],{})
                if speaker in actors:
                    # Spoken words are NOT scanned for physical action keywords.
                    actors[speaker].update(action=actors[speaker]['action'] if speaker in persistent else override.get('action','talk'),
                                           emotion=override.get('emotion',event['emotion']),reason='Approved dialogue only; delivery tags are not spoken.')
                if override.get('actor_id') and override['actor_id'] in actors:
                    actors[override['actor_id']].update(action=override.get('action','idle'),emotion=override.get('emotion','neutral'))
                if override.get('shot') and override['shot']!='wide':camera={'shot':override['shot'],'target':speaker if speaker in visible else None}
                else:
                    # Explicit camera cues own their shot; subsequent dialogue
                    # resumes conversation framing rather than latching forever.
                    explicit_camera=False
                    partner=last_speaker if last_speaker in visible and last_speaker!=speaker else next((c for c in visible if c!=speaker),None)
                    shot='wide' if speaker not in visible else 'close_up' if event['emotion'] in ('fear','surprised','sad','excited') else 'two_shot' if partner and speaker!=last_speaker else 'medium'
                    camera={'shot':shot,'target':speaker if speaker in visible else None}
                    if shot=='two_shot':camera['partner']=partner
                last_speaker=speaker
            elif scene['kind']=='camera':
                target=targets[0] if targets else next((cid for cid in visible if cid!=last_speaker),None) if event['camera_action']=='reaction' else None
                if target is None and event['camera_action'] in ('medium','close_up','two_shot'):target=last_speaker if last_speaker in visible else next(iter(visible),None)
                camera={'shot':event['camera_action'],'target':target};explicit_camera=True
                if event['camera_action']=='two_shot':camera['partner']=next((cid for cid in visible if cid!=target),None)
                if event['camera_action']=='reaction' and target in actors:actors[target]['emotion']='curious' if event['emotion']=='neutral' else event['emotion']
            for cid,actor in actors.items():actor['motion']=dict(PROFILES.get(cid,DEFAULT))
            scene.update(actors=actors,camera=deepcopy(camera),emotion=event['emotion'],
                         landscape=False,
                         sound_effects=[e for e in timeline['effects_track'] if e['event_id']==event['event_id']] if scene['kind']=='sound_effect' else [],
                         environment={'ambience':'birds' if 'day' in scene['background_id'] else 'night' if 'night' in scene['background_id'] else 'wind'})
            directions.append(scene)
        # Continuous actions share one time interval rather than restarting at each speech.
        for i,scene in enumerate(directions):
            for cid,cue in scene['actors'].items():
                if cue.get('start',scene['start'])<scene['start'] or scene['instruction']['metadata'].get('continuous'):
                    end=scene['end']
                    for later in directions[i+1:]:
                        if later['source_scene_id']!=scene['source_scene_id'] or cid not in later['actors'] or later['actors'][cid].get('start')!=cue.get('start'):break
                        end=later['end']
                    cue['end']=max(cue['end'],end)
        return self.continuity(directions,timeline)

    def continuity(self,directions,timeline):
        """Carry physical/emotional state; never infer objects that lack artwork."""
        offsets={};movements={};emotions={};expression_starts={};source=None;tracks=[];recent=None;music=None
        for scene in directions:
            if source!=scene['source_scene_id']:source=scene['source_scene_id'];offsets={};movements={};emotions={};expression_starts={};recent=None;music=None
            event=scene['instruction'];explicit={r['character_id']:r for r in event['metadata'].get('emotion_states',[])}
            emotions.update(explicit)
            from app.video_config import STAGE_WIDTH
            visible=scene['visible_characters'];spacing=STAGE_WIDTH/max(1,len(visible))
            for cid,actor in scene['actors'].items():
                origin=offsets.get(cid,0.)
                travel=actor.get('to_x',0)-actor.get('from_x',0) if scene['kind']=='action' and cid in event['character_ids'] else 0.
                limit=min(90.,spacing*.20)
                destination=max(-limit,min(limit,origin+travel))
                motion=movements.get(cid)
                continuation=motion and actor['action']==motion['action'] and actor['start']==motion['start'] and scene['start']<motion['end']
                if not continuation:
                    motion={'from_x':origin,'to_x':destination,'start':actor['start'],'end':actor['end'],'action':actor['action']}
                    movements[cid]=motion
                actor.update(from_x=motion['from_x'],to_x=motion['to_x'])
                phase=max(0.,min(1.,(scene['end']-motion['start'])/max(.01,motion['end']-motion['start'])))
                offsets[cid]=motion['from_x']+(motion['to_x']-motion['from_x'])*phase*phase*(3-2*phase)
                state=emotions.get(cid)
                if state and (cid!=scene.get('speaker') or cid in explicit):actor['emotion']=state['rig_emotion']
                target=event['metadata'].get('gaze_target_id')
                if target in visible:
                    if target and cid in event['character_ids']:actor['gaze']=1 if visible.index(target)>visible.index(cid) else -1
                current=state or {'character_id':cid,'emotion':actor['emotion'],'rig_emotion':actor['emotion'],'confidence':.65,'trigger_event':event['event_id'],'evidence':['listener context']}
                if cid not in expression_starts or expression_starts[cid][0]!=actor['emotion']:expression_starts[cid]=(actor['emotion'],scene['start'])
                actor['emotion_started']=expression_starts[cid][1]
                actor['emotion_state']={**current,'start':scene['start'],'end':scene['end']}
                tracks.append(actor['emotion_state'])
            if scene.get('speaker'):recent=scene['speaker']
            if event['metadata'].get('music_mood'):music=event['metadata']['music_mood']
            if event['metadata'].get('music_control')=='fade_out':music=None
            scene['continuity']={'location':scene['background_id'],'positions':dict(offsets),'emotions':{cid:a['emotion'] for cid,a in scene['actors'].items()},
                'active_characters':list(visible),'camera':dict(scene['camera']),'objects':[],'recent_speaker':recent,'music_mood':music}
        timeline['emotion_track']=tracks
        return directions


# Preserve integrations that imported the previous class name.
CartoonDirector=IntelligentCartoonDirector
