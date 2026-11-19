"""Frame-aligned timing driven by actual WAV lengths, with limited visual holds."""
import math
from app.video_modes import output_size,duration_target

from app.video_config import VIDEO_FPS
FPS=VIDEO_FPS


def frames(seconds,fps=FPS):
    return math.ceil(seconds*fps-1e-8)


def build_timeline(clips,plan,options=None):
    if 'screenplay' in plan:
        from app.screenplay_timeline import build_screenplay_timeline
        return build_screenplay_timeline(clips,plan,options or {})
    if not clips: raise ValueError('No speech clips to animate')
    speech=sum(c['duration_seconds'] for c in clips)
    if speech>600: raise ValueError('Story exceeds the ten-minute limit; split it into chapters.')
    visible=list(plan['characters'])
    fps=VIDEO_FPS
    scenes=[]
    cursor=0
    clip_scenes={clips[i]['id']:s for s in plan.get('review_scenes',[]) for i in range(s['start_segment'],s['end_segment'])}
    current_review=clip_scenes.get(clips[0]['id'])

    def add(kind,length,clip=None,action='idle'):
        nonlocal cursor
        count=frames(length,fps)
        scene={'kind':kind,'start_frame':cursor,'end_frame':cursor+count,'start':cursor/fps,'end':(cursor+count)/fps,
               'action':action,'visible_characters':current_review['visible_characters'] if current_review else visible,
               'background_id':current_review['background_id'] if current_review else plan['background']['background_id'],
               'source_scene_id':current_review['scene_id'] if current_review else 'scene_001',
               'previous_action':scenes[-1]['action'] if scenes else 'idle'}
        if clip:
            scene.update(clip_id=clip['id'],speaker=clip['speaker'],speaker_name=clip['speaker_name'],
                         text=clip['text'],off_screen=clip['off_screen'],audio_duration=clip['duration_seconds'])
        scenes.append(scene); cursor+=count

    # At most six seconds of authored atmosphere/reactions, never an arbitrary
    # 15-second freeze merely to make a very short story hit thirty seconds.
    hold_budget=min(6.,max(0.,30-speech-.3*max(0,len(clips)-1)))
    intro=min(1.6,hold_budget/3)
    outro=min(1.8,hold_budget/3)
    reactions=max(0,hold_budget-intro-outro)
    if intro: add('intro',intro,action='walk' if visible else 'idle')
    for index,clip in enumerate(clips):
        current_review=clip_scenes.get(clip['id'])
        if clip['kind']=='narration':
            content=clip['text']
            action='walk' if 'হাঁট' in content else 'look_left' if 'বাঁ' in content and 'তাকা' in content else 'look_right' if 'ডান' in content and 'তাকা' in content else 'idle'
        elif clip['off_screen']: action='afraid'
        else: action='talk'
        add('speech',clip['duration_seconds'],clip,action)
        if index<len(clips)-1:
            add('reaction',.3+min(.8,reactions/max(1,len(clips)-1)),action='look_right' if clip['off_screen'] else 'surprised')
    if outro: add('outro',outro,action='turn_head')
    warnings=list(plan['warnings'])
    duration=cursor/fps
    if duration>600: raise ValueError('The complete audio/scene timeline exceeds ten minutes; split the story into chapters.')
    low,high=duration_target(options)
    if duration<low: warnings.append(f'This story produces {duration:.1f}s after limited visual holds. Extend the story for the {low}–{high}s target; no excessive padding was added.')
    if duration>high: warnings.append(f'This story is {duration:.1f}s long, exceeding the {high}s target. All narration and dialogue are preserved.')
    events=[{'character_id':cid,'events':[{'start':s['start'],'end':s['end'],
             'action':s['action'] if s.get('speaker') in (None,cid,'narrator','unknown_voice') else 'idle'} for s in scenes if cid in s['visible_characters']]} for cid in visible]
    width,height=output_size(options)
    return {'fps':fps,'width':width,'height':height,'total_frames':cursor,'duration_seconds':duration,
            'speech_seconds':speech,'scenes':scenes,'character_events':events,'warnings':warnings}
