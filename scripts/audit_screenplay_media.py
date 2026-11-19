"""Decode the real acceptance movies and verify frame clocks/lip-sync ownership."""
import json
import subprocess
import sys
import wave
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.scene_cache import atomic_json
from app.hardware import ffmpeg_binary,ffprobe_binary


def run():
    source=json.loads((ROOT/'workspace/screenplay-browser-acceptance.json').read_text(encoding='utf-8'))
    results=[]
    for entry in source['videos']:
        directory=ROOT/'workspace'/entry['job_id'];movie=Path(entry['video'])
        timeline=json.loads((directory/'timeline.json').read_text(encoding='utf-8'))
        raw=subprocess.run([ffprobe_binary(),'-v','error','-show_streams','-of','json',str(movie)],capture_output=True,text=True,check=True)
        streams=json.loads(raw.stdout)['streams'];video=next(s for s in streams if s['codec_type']=='video');audio=next(s for s in streams if s['codec_type']=='audio')
        assert video['codec_name']=='h264' and audio['codec_name']=='aac'
        assert video['r_frame_rate']=='30/1' and int(video['nb_frames'])==timeline['total_frames']
        difference=abs(float(video['duration'])-float(audio['duration']));assert difference<1/30
        decode=subprocess.run([ffmpeg_binary(),'-hide_banner','-i',str(movie),'-vf','blackdetect=d=0.05:pix_th=0.05','-an','-f','null','-'],capture_output=True,text=True)
        assert decode.returncode==0 and 'black_start:' not in decode.stderr
        frames=[]
        for path in (directory/'render').glob('*-poses.jsonl'):
            frames.extend(json.loads(line) for line in path.read_text(encoding='utf-8').splitlines())
        talking=set()
        for frame in frames:
            t=frame['frame']/30
            speech=next((s for s in timeline['scenes'] if s['kind']=='speech' and s['start']<=t<s['end']),None)
            if not speech or speech['speaker']!=frame['character']:assert frame['mouth']=='X'
            elif frame['mouth']!='X':talking.add(frame['character'])
        assert talking==({'nabil','rayan'} if entry['test']=='dialogue' else set())
        with wave.open(str(directory/'render/timeline.wav'),'rb') as wav:
            assert wav.getnframes()==timeline['total_frames']*1600
            samples=np.frombuffer(wav.readframes(wav.getnframes()),dtype='<i2').astype(np.int32)
        assert not np.any(np.abs(samples)>=32767)
        results.append({'test':entry['test'],'job_id':entry['job_id'],'frames':int(video['nb_frames']),'duration_seconds':float(video['duration']),
                        'av_difference_seconds':difference,'decoded':True,'black_intervals':0,'mouth_trace_rows':len(frames),'active_speakers':sorted(talking),'pcm_peak':int(np.abs(samples).max()),'clipped_samples':0})
    atomic_json(ROOT/'workspace/screenplay-media-audit.json',{'result':'passed','videos':results,'note':'Validates source text, clocks and mouth ownership; human listening remains necessary for pronunciation quality.'})
    print(json.dumps(results,indent=2))


if __name__=='__main__':run()
