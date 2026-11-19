"""Audit the actual v6 Chatterbox export and extract its screen-text frame."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.audit_v4_media import audit
from app.scene_cache import digest,atomic_json
from app.hardware import ffmpeg_binary,run


def main():
    directory=ROOT/'workspace/v6-chatterbox-evaluation';clips=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    video=ROOT/'output/v6-chatterbox-evaluation.mp4'
    result=audit({'job_id':directory.name,'video':str(video),'approved_speech':[{'segment_id':c['id'],'audio_hash':digest(directory/'audio'/(c['id']+'.wav'))} for c in clips]})
    assert result['active_speakers']==['anika','nabil','rayan'],result
    assert set(result['music'])=={'music_mystery','music_happy'},result
    timeline=json.loads((directory/'timeline.json').read_text(encoding='utf-8'))
    text=next(s for s in timeline['scenes'] if s['kind']=='screen_text')
    assert text['screen_text']=='অনুমান নয়, যুক্তি দিয়ে চিন্তা করো!'
    result['screen_text_seconds']=text['end']-text['start']
    result['speech_count']=len(clips)
    result['cue_methods']=[json.loads((directory/'cues'/(c['id']+'.json')).read_text(encoding='utf-8'))['method'] for c in clips]
    assert result['cue_methods']==['rhubarb']*5
    for label,clock in [('screen-text',(text['start']+text['end'])/2),('three-characters',3.5)]:
        output=ROOT/'workspace'/('v6-'+label+'.png')
        command=run([ffmpeg_binary(),'-y','-v','error','-ss',str(clock),'-i',str(video),'-frames:v','1',str(output)],60)
        assert command.returncode==0,command.stderr
    atomic_json(ROOT/'workspace/v6-media-audit.json',result)
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
