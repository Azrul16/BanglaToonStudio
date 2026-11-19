"""Stream original quiet ambience/Foley into the frame-aligned master PCM."""
import json
import math
import wave
from pathlib import Path
import numpy as np
from app.scene_cache import atomic_json
from app.hardware import ffmpeg_binary,run
ROOT=Path(__file__).resolve().parents[2]


def ducking_envelope(clock,speech):
    duck=np.ones_like(clock)
    for line in speech:
        attack=np.clip((clock-(line['start']-.18))/.18,0,1)
        release=np.clip((clock-line['end'])/.5,0,1)
        influence=attack*(1-release)
        duck=np.minimum(duck,1.-.84*influence*influence*(3-2*influence))
    return duck


def mix(path,direction,directory,music=False,levels=None):
    from app.audio.sound_director import SoundDirector
    levels={'dialogue':1.,'narration':1.,'music':1.,'ambience':1.,'sfx':1.,'action':1.,**(levels or {})}
    if any(not math.isfinite(v) or not 0<=v<=2 for v in levels.values()):raise ValueError('Audio levels must be between zero and two')
    director=SoundDirector();library=director.library;events=director.plan(direction,music)
    speech=[{'start':s['start'],'end':s['start']+s.get('audio_duration',s['end']-s['start']),
             'track':'narration' if s.get('instruction',{}).get('type')=='narration' else 'dialogue'} for s in direction if s['kind']=='speech']
    sounds={}
    for name in {e['sound'] for e in events}:
        try:
            with wave.open(str(ROOT/'assets/sounds'/library[name]['file']),'rb') as wav:
                if wav.getframerate()!=48000 or wav.getnchannels()!=1 or wav.getsampwidth()!=2 or not wav.getnframes():raise ValueError('Sound library must contain nonempty mono 48kHz PCM')
                sounds[name]=np.frombuffer(wav.readframes(wav.getnframes()),dtype='<i2').astype(np.float32)
        except (OSError,EOFError,wave.Error,ValueError) as exc:director.diagnostics.append('Skipped optional sound '+name+': '+str(exc))
    events=[e for e in events if e['sound'] in sounds]
    atomic_json(directory/'sound-warnings.json',{'skipped_optional_sounds':director.diagnostics})
    target=path.with_name('mixed.wav');bed=path.with_name('foley.wav');scaled_voice=path.with_name('voice-levels.wav');offset=0;peak=0.;limited=0
    with wave.open(str(path),'rb') as voice,wave.open(str(bed),'wb') as output,wave.open(str(scaled_voice),'wb') as spoken:
        output.setparams(voice.getparams());spoken.setparams(voice.getparams());rate=voice.getframerate()
        while raw:=voice.readframes(rate):
            block=np.frombuffer(raw,dtype='<i2').astype(np.float32);clock=(offset+np.arange(len(block)))/rate
            bus=np.zeros_like(block);duck=ducking_envelope(clock,speech)
            for line in speech:
                mask=(clock>=line['start'])&(clock<line['end']);block[mask]*=levels[line['track']]
            for event in events:
                start=max(offset,round(event['start']*rate));end=min(offset+len(block),round(event['end']*rate))
                if end<=start:continue
                sound=sounds[event['sound']];indices=np.arange(start,end)-round(event['start']*rate)
                if event['loop']:indices%=len(sound)
                else:
                    valid=indices<len(sound);end=start+int(valid.sum());indices=indices[valid]
                current=(np.arange(start,end))/rate
                fade=np.minimum(1.,np.maximum(0.,(current-event['start'])/event['fade_in']))*np.minimum(1.,np.maximum(0.,(event['end']-current)/event['fade_out']))
                gain=event['gain']*levels[event['track']]*fade
                if event['track']=='music':gain*=duck[start-offset:end-offset]
                elif event['track']=='ambience':gain*=.45+.55*duck[start-offset:end-offset]
                bus[start-offset:end-offset]+=sound[indices]*gain
            peak=max(peak,float(np.max(np.abs(block+bus))))
            limited+=int(np.count_nonzero(np.abs(block+bus)>31000))
            output.writeframes(np.clip(bus,-31000,31000).astype('<i2').tobytes())
            spoken.writeframes(np.clip(block,-32767,32767).astype('<i2').tobytes());offset+=len(block)
    result=run([ffmpeg_binary(),'-y','-v','error','-i',str(scaled_voice),'-i',str(bed),'-filter_complex',
                f'amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95:level=false:latency=true,apad=whole_len={offset},atrim=end_sample={offset}',
                '-ac','1','-ar','48000','-c:a','pcm_s16le',str(target)],120)
    if result.returncode:raise RuntimeError('FFmpeg Foley/music mix failed: '+result.stderr[-1200:])
    with wave.open(str(target),'rb') as output:
        if output.getnframes()!=offset:raise RuntimeError('Audio mixing changed the master sample clock')
    target.replace(path);bed.unlink(missing_ok=True);scaled_voice.unlink(missing_ok=True)
    atomic_json(directory/'sound-events.json',{'events':events,'speech':speech,'tracks':['dialogue','narration','music','ambience','sfx','action'],
                'levels':levels,'ducking':{'attack_seconds':.18,'release_seconds':.5,'music_during_speech':.16},
                'source_license':'CC0-1.0 original procedural','peak_before_limiter':peak,'limited_samples':limited,'voice_overlap':'One speech segment at a time; sample-accurate envelope ducking'})
    return events
