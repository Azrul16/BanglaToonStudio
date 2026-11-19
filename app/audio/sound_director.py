"""Validated scene-aware music, ambience, contact Foley and intentional silence."""
import json
import logging
from pathlib import Path
from app.assets import normalize
from app.motion import contacts
from app.scene_cache import digest

ROOT=Path(__file__).resolve().parents[2]
MOODS={
 'happy':('খুশি','আনন্দ','happy'), 'comedy':('মজার','হাসি','comedy'),
 'mystery':('রহস্য','অচেনা','mystery'), 'suspense':('ভয়','ভয়','অন্ধকার','suspense'),
 'adventure':('অভিযান','গুপ্তধন','adventure'), 'emotional':('দুঃখ','কান্না','emotional'),
 'calm':('শান্ত','calm'), 'dramatic':('বিপদ','dramatic')}


class SoundDirector:
    def __init__(self,root=None):
        self.root=Path(root or ROOT/'assets/sounds')
        self.diagnostics=[]
        try:
            self.library=json.loads((self.root/'library.json').read_text(encoding='utf-8'))['sounds']
            if not isinstance(self.library,dict):raise ValueError('Invalid sound library')
        except (OSError,ValueError,KeyError) as exc:
            self.library={};self.diagnostics.append('Optional sound library unavailable: '+str(exc))
            logging.getLogger('bangla_toon.sound').warning('%s',self.diagnostics[-1])

    def mood(self,scenes):
        # Dialogue words cannot accidentally direct physical actions or narration.
        text=normalize(' '.join(s.get('instruction',{}).get('source_text','') for s in scenes if s['kind']!='speech'))
        explicit=next((s.get('instruction',{}).get('metadata',{}).get('music_mood') for s in scenes if s.get('instruction',{}).get('metadata',{}).get('music_mood')),None)
        if explicit:return explicit
        if any(s.get('emotion')=='fear' for s in scenes):return 'suspense'
        background=scenes[0]['background_id']
        neutral='mystery' if 'station' in background else 'happy' if 'courtyard' in background else 'comedy' if 'market' in background else 'calm'
        return next((key for key,words in MOODS.items() if any(w in text for w in words)),neutral)

    def plan(self,direction,music=True):
        events=[];groups={};seen=set()
        def add(sound,start,end,track,gain=.2,loop=False,**extra):
            try:
                if sound not in self.library:raise ValueError('Unregistered sound asset: '+str(sound))
                path=(self.root/self.library[sound]['file']).resolve()
                if not path.is_relative_to(self.root.resolve()) or not path.is_file():raise ValueError('Missing or invalid sound file: '+sound)
                if not self.library[sound].get('license'):raise ValueError('Sound has no license: '+sound)
                if self.library[sound].get('sha256') and digest(path)!=self.library[sound]['sha256']:raise ValueError('Sound asset changed: '+sound)
            except (OSError,ValueError) as exc:
                self.diagnostics.append(str(exc));logging.getLogger('bangla_toon.sound').warning('Skipping optional sound: %s',exc);return
            events.append({'sound':sound,'start':start,'end':end,'track':track,'gain':gain,'loop':loop,'fade_in':.35 if loop else .008,'fade_out':.6 if loop else .025,**extra})
        for scene in direction:groups.setdefault(scene['source_scene_id'],[]).append(scene)
        for sid,scenes in groups.items():
            begin=scenes[0]['start'];end=scenes[-1]['end'];bg=scenes[0]['background_id']
            silent=any(s.get('instruction',{}).get('metadata',{}).get('intentional_silence') for s in scenes)
            if not silent:
                names=['wind','birds'] if 'night' not in bg else ['wind','night']
                if 'river' in bg:names=['water','wind','birds']
                elif 'station' in bg:names=['wind','station_distant']
                requested=next((s.get('instruction',{}).get('metadata',{}).get('ambience_ids') for s in scenes if s.get('instruction',{}).get('metadata',{}).get('ambience_ids')),None)
                if requested:names=requested
                for name in names:
                    if name in self.library:add(name,begin,end,'ambience',.11 if name!='station_distant' else .07,True)
                if music:
                    cues=[s for s in scenes if s['kind']=='music']
                    if cues:
                        current=None;start=begin
                        for cue in cues:
                            meta=cue['instruction']['metadata'];stop=cue['end'] if meta.get('music_control')=='fade_out' else cue['start']
                            if current and stop>start and 'music_'+current in self.library:add('music_'+current,start,stop,'music',.18,True,mood=current,fade_out=1.0 if meta.get('music_control')=='fade_out' else .6)
                            current=None if meta.get('music_control')=='fade_out' else meta.get('music_mood',current);start=cue['start']
                        if current and end>start and 'music_'+current in self.library:add('music_'+current,start,end,'music',.18,True,mood=current)
                    else:
                        mood=self.mood(scenes);name='music_'+mood
                        if name in self.library:add(name,begin,end,'music',.18,True,mood=mood)
            for scene in scenes:
                for effect in scene.get('sound_effects',[]):add(effect['sound'],effect['start'],effect['end'],'sfx',effect['gain'],effect['loop'],event_id=effect['event_id'])
                for cid,actor in scene['actors'].items():
                    key=(sid,cid,actor['start'],actor['end'],actor['action'])
                    if key in seen:continue
                    seen.add(key)
                    for contact in contacts(actor,.80):
                        add('footstep',contact['time'],min(end,contact['time']+.14),'action',.36,False,character_id=cid,foot=contact['foot'],contact_cycle=contact['cycle'])
                    if actor['emotion']=='surprised' and scene['kind']=='reaction':add('surprise',scene['start']+.1,min(end,scene['start']+.4),'sfx',.15)
        return events
