"""Final movie integrity/clock/black-frame/PCM audit; not a voice-quality claim."""
import json
import subprocess
import sys
import wave
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.scene_cache import atomic_json

source=json.loads((ROOT/'workspace/v3-resume-acceptance.json').read_text(encoding='utf-8'))
results=[]
for entry in source['videos']:
    movie=ROOT/entry['output'];directory=ROOT/'workspace'/entry['job_id']
    timeline=json.loads((directory/'timeline.json').read_text(encoding='utf-8'))
    probe=subprocess.run(['ffprobe','-v','error','-show_streams','-of','json',str(movie)],capture_output=True,text=True,check=True)
    streams=json.loads(probe.stdout)['streams'];video=next(s for s in streams if s['codec_type']=='video');audio=next(s for s in streams if s['codec_type']=='audio')
    assert video['r_frame_rate']=='30/1' and int(video['nb_frames'])==timeline['total_frames']
    difference=abs(float(video['duration'])-float(audio['duration']))
    assert difference<1/30
    assert abs(float(video['start_time'])-float(audio['start_time']))<1/30
    checked=subprocess.run(['ffmpeg','-hide_banner','-i',str(movie),'-vf','blackdetect=d=0.05:pix_th=0.05','-an','-f','null','-'],capture_output=True,text=True)
    assert checked.returncode==0 and 'black_start:' not in checked.stderr
    peak=0;full_scale=0;square=0.;count=0
    with wave.open(str(directory/'render/timeline.wav'),'rb') as wav:
        assert wav.getnframes()==timeline['total_frames']*1600
        while block:=wav.readframes(48000):
            samples=np.frombuffer(block,dtype='<i2').astype(np.float64)
            peak=max(peak,float(np.abs(samples).max()));full_scale+=int(np.count_nonzero(np.abs(samples)>=32767))
            square+=float(np.dot(samples,samples));count+=len(samples)
    assert full_scale==0 and peak>1000
    results.append({'job_id':entry['job_id'],'mode':entry['mode'],'frames':int(video['nb_frames']),
                    'av_duration_difference_seconds':difference,'black_intervals':0,'master_pcm_peak':peak,
                    'full_scale_pcm_samples':full_scale,'rms':(square/count)**.5,'fps':30})
atomic_json(ROOT/'workspace/v3-media-audit.json',{'result':'passed','videos':results,'note':'Does not certify pronunciation, accent, acting naturalness or television production quality.'})
print(json.dumps(results,indent=2))
