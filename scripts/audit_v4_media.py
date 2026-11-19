"""Actual decoded exports, source speech hashes, stance locks and closed listeners."""
import json
import math
import subprocess
import sys
import wave
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.scene_cache import atomic_json,digest
from app.hardware import ffmpeg_binary,ffprobe_binary
from app.motion import smooth,contacts


def audit(entry):
    directory=ROOT/'workspace'/entry['job_id'];movie=Path(entry['video'])
    timeline=json.loads((directory/'timeline.json').read_text(encoding='utf-8'))
    direction=json.loads((directory/'direction.json').read_text(encoding='utf-8'))
    sounds=json.loads((directory/'sound-events.json').read_text(encoding='utf-8'))
    probe=subprocess.run([ffprobe_binary(),'-v','error','-show_streams','-of','json',str(movie)],capture_output=True,text=True,check=True)
    streams=json.loads(probe.stdout)['streams'];video=next(s for s in streams if s['codec_type']=='video');audio=next(s for s in streams if s['codec_type']=='audio')
    assert video['codec_name']=='h264' and audio['codec_name']=='aac' and video['r_frame_rate']=='30/1'
    assert int(video['nb_frames'])==timeline['total_frames'];difference=abs(float(video['duration'])-float(audio['duration']));assert difference<1/30
    decode=subprocess.run([ffmpeg_binary(),'-hide_banner','-i',str(movie),'-vf','blackdetect=d=0.05:pix_th=0.05','-an','-f','null','-'],capture_output=True,text=True)
    assert decode.returncode==0 and 'black_start:' not in decode.stderr
    traces=[]
    for path in sorted((directory/'render').glob('*-poses.jsonl')):traces.extend(json.loads(line) for line in path.read_text(encoding='utf-8').splitlines())
    talking=set();plants={};sampled_motion=0
    for row in traces:
        clock=row['frame']/30
        scene=next((s for s in direction if s['start']<=clock<s['end']),direction[-1]);actor=scene['actors'][row['character']]
        if scene['kind']!='speech' or row['character']!=scene.get('speaker'):assert row['mouth']=='X'
        elif row['mouth']!='X':talking.add(row['character'])
        if not row.get('walking'):continue
        sampled_motion+=1;local=clock-actor['start'];span=actor['end']-actor['start']
        if not .28<local<span-.28:continue
        scale=.68 if timeline['width']>timeline['height'] else .8
        stride=actor['motion']['stride']*(1.4 if actor['action']=='run' else 1.)
        distance=abs(actor.get('to_x',0)-actor.get('from_x',0))
        cycle=distance*smooth(local/span)/(stride*scale) if distance>.1 else local*max(.15,abs(actor.get('speed',65))/(stride*scale))*actor['motion']['tempo']
        assert abs((cycle%1)-row['walk_phase'])<.0001
        for index,side in enumerate(('left','right')):
            phase=(cycle+index*.5)%1
            if .03<phase<.57:
                key=(row['character'],actor['start'],side,math.floor(cycle+index*.5))
                plants.setdefault(key,[]).append(row[side+'_ankle'])
    drift=max((max(p[0] for p in points)-min(p[0] for p in points) for points in plants.values() if len(points)>1),default=0)
    height=max((max(p[1] for p in points)-min(p[1] for p in points) for points in plants.values() if len(points)>1),default=0)
    assert drift<.15 and height<.15,(drift,height)
    # Each actual footstep must correspond to the same travel clock as the rig.
    for event in (e for e in sounds['events'] if e['track']=='action'):
        matching=[s['actors'][event['character_id']] for s in direction if event['character_id'] in s['actors'] and s['actors'][event['character_id']]['start']<=event['start']<s['actors'][event['character_id']]['end']]
        scale=.68 if timeline['width']>timeline['height'] else .8
        assert any(any(abs(c['time']-event['start'])<1e-6 and c['foot']==event['foot'] for c in contacts(actor,scale)) for actor in matching)
    peak=0;clipped=0
    with wave.open(str(directory/'render/timeline.wav'),'rb') as wav:
        assert wav.getnframes()==timeline['total_frames']*1600
        while raw:=wav.readframes(48000):
            samples=np.frombuffer(raw,dtype='<i2').astype(np.int32);peak=max(peak,int(np.abs(samples).max()));clipped+=int(np.count_nonzero(np.abs(samples)>=32767))
    assert clipped==0
    for speech in entry['approved_speech']:assert digest(directory/'audio'/(speech['segment_id']+'.wav'))==speech['audio_hash']
    return {'job_id':entry['job_id'],'video':str(movie),'duration_seconds':float(video['duration']),'frames':int(video['nb_frames']),'resolution':[int(video['width']),int(video['height'])],
            'av_duration_difference_seconds':difference,'decoded':True,'black_intervals':0,'mouth_trace_rows':len(traces),'active_speakers':sorted(talking),
            'sampled_walking_frames':sampled_motion,'stance_drift_px':drift,'stance_height_drift_px':height,'pcm_peak':peak,'clipped_samples':clipped,
            'footsteps':sum(e['track']=='action' for e in sounds['events']),'music':list({e['sound'] for e in sounds['events'] if e['track']=='music'}),'approved_audio_hashes_unchanged':True}


if __name__=='__main__':
    source=json.loads((ROOT/'workspace/v4-samples-acceptance.json').read_text(encoding='utf-8'))
    results=[audit(entry) for entry in source['videos']]
    atomic_json(ROOT/'workspace/v4-media-audit.json',{'result':'passed','videos':results,'limits':'Numerical checks and decoded media do not certify pronunciation, child voice suitability, profile artwork or TV production quality.'})
    print(json.dumps(results,indent=2))
