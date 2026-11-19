"""Shared frame clock: approved speech, visible acting and effects stay separate."""
import math
from app.video_modes import output_size,duration_target
from app.video_config import VIDEO_FPS

ACTION_SECONDS={'walk':2.5,'run':2.0,'turn':1.0,'fear':1.1,'stop':.8,'look_around':1.2,'wave':1.4,'sit':1.8,'stand_up':1.8,'move_closer':2.0}


def build_screenplay_timeline(clips,plan,options):
    fps=VIDEO_FPS
    by_event={}
    for clip in clips:by_event.setdefault(clip['event_id'],[]).append(clip)
    scenes=[];cursor=0;initialized=set();event_times=[];effects=[]
    by_source={s['scene_id']:s for s in plan['review_scenes']}
    def add(event,kind,seconds,clip=None,action='idle'):
        nonlocal cursor
        count=max(1,math.ceil(seconds*fps-1e-8));setting=by_source[event['scene_id']]
        event={**event,'metadata':{**event['metadata'],**setting.get('sound_settings',{})}}
        scene={'kind':kind,'start_frame':cursor,'end_frame':cursor+count,'start':cursor/fps,'end':(cursor+count)/fps,
               'action':action,'previous_action':scenes[-1]['action'] if scenes else 'idle','visible_characters':setting['visible_characters'],
               'background_id':setting['background_id'],'source_scene_id':event['scene_id'],'event_id':event['event_id'],
               'source_line':event['source_line'],'instruction':event,'off_screen':True}
        if clip:scene.update(clip_id=clip['id'],speaker=clip['speaker'],speaker_name=clip['speaker_name'],off_screen=clip['off_screen'],
                             text=clip['text'],audio_duration=clip['duration_seconds'])
        scenes.append(scene);cursor+=count
        return scene
    for event in plan['screenplay']:
        begin=cursor/fps
        if event['scene_id'] not in initialized:
            initialized.add(event['scene_id']);add(event,'establishing',1.0)
        kind=event['type']
        if kind in ('dialogue','narration'):
            spoken=by_event.get(event['event_id'])
            if not spoken:raise ValueError('Approved speech is missing for '+event['event_id'])
            for clip in spoken:add(event,'speech',clip['duration_seconds'],clip,'talk' if not clip['off_screen'] else 'idle')
        elif kind=='action':
            for action in event['actions']:
                add({**event,'actions':[action]},'action',event['duration_seconds'] or ACTION_SECONDS.get(action,1.4),action=action)
        elif kind=='camera':add(event,'camera',event['duration_seconds'] or 1.6)
        elif kind=='sound_effect':
            scene=add(event,'sound_effect',event['duration_seconds'] or .8)
            effects.append({'sound':event['sound_id'],'start':scene['start'],'end':scene['end'],'gain':.6,'loop':False,'event_id':event['event_id']})
        elif kind=='screen_text':
            shot=add(event,'screen_text',event['duration_seconds'] or max(3.,min(8.,len(event['text'])/9.)));shot['screen_text']=event['text']
        elif kind=='metadata' and ('music_mood' in event['metadata'] or 'music_control' in event['metadata']):add(event,'music',1.0 if event['metadata'].get('music_control')=='fade_out' else .3)
        elif kind=='unresolved_instruction' and event['metadata'].get('blocking',True):raise ValueError('Unresolved instruction reached the renderer')
        event_times.append({'event_id':event['event_id'],'source_line':event['source_line'],'start':begin,'end':cursor/fps,'type':kind})
    if not scenes:raise ValueError('No screenplay events to render')
    # A description-only scene is still a real silent shot, not a narrator clip.
    if len(scenes)==1 and scenes[0]['kind']=='establishing':
        scenes[0]['end_frame']=fps*2;scenes[0]['end']=2.;cursor=fps*2
    # A short closing hold lets expressions settle and the sound bed fade naturally.
    ending={**plan['screenplay'][-1],'event_id':'closing_hold','type':'metadata','text':'','generate_voice':False,'actions':[],'character_ids':[]}
    shot=add(ending,'ending',.5)
    event_times.append({'event_id':'closing_hold','source_line':ending['source_line'],'start':shot['start'],'end':shot['end'],'type':'metadata'})
    duration=cursor/fps
    if duration>600:raise ValueError('Screenplay exceeds the ten-minute limit; split it into chapters.')
    width,height=output_size(options);warnings=list(plan.get('warnings',[]));low,high=duration_target(options)
    if duration<low or duration>high:warnings.append(f'Actual screenplay duration is {duration:.1f}s; selected target is {low}–{high}s. Speech was not stretched or truncated.')
    speech_track=[{'event_id':s['event_id'],'clip_id':s['clip_id'],'speaker_id':s['speaker'],'start':s['start'],
                   'end':s['start']+s['audio_duration'],'text':s['text']} for s in scenes if s['kind']=='speech']
    return {'fps':fps,'width':width,'height':height,'total_frames':cursor,'duration_seconds':duration,'scenes':scenes,
            'speech_seconds':sum(c['duration_seconds'] for c in clips),'speech_track':speech_track,
            'visual_track':event_times,'effects_track':effects,'warnings':warnings,'character_events':[]}
