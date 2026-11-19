"""Compare immutable pre-upgrade assets/media and audit final-audio mouth cues."""
import hashlib
import json
import sys
import wave
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.scene_cache import atomic_json,digest

def main():
    baseline=json.loads((ROOT/'workspace/v10-baseline-inventory.json').read_text(encoding='utf-8'))
    changed={key:[name for name,sha in baseline[key].items() if not (ROOT/name).is_file() or digest(ROOT/name)!=sha] for key in ('assets','existing_mp4')}
    assert not any(changed.values()),changed
    browser=json.loads((ROOT/'workspace/v10-browser-acceptance.json').read_text(encoding='utf-8'))
    entries=list(browser['videos']);mini=ROOT/'workspace/v10-mini-verification.json'
    if mini.exists():entries.append({'job_id':json.loads(mini.read_text(encoding='utf-8'))['media']['job_id']})
    checks=[]
    for entry in entries:
        directory=ROOT/'workspace'/entry['job_id'];job=json.loads((directory/'job.json').read_text(encoding='utf-8'))
        timing={c['id']:c for c in job['clips']}
        for clip in job['approved_speech']:
            audio=directory/'audio'/(clip['segment_id']+'.wav');cues=json.loads((directory/'cues'/(clip['segment_id']+'.json')).read_text(encoding='utf-8'))
            assert digest(audio)==clip['audio_hash']
            with wave.open(str(audio),'rb') as wav:duration=wav.getnframes()/wav.getframerate()
            if not timing[clip['segment_id']]['off_screen']:
                assert cues['method']=='rhubarb'
                assert all(c['value'] in 'ABCDEFGHX' and 0<=c['start']<=c['end']<=duration+.011 for c in cues['mouthCues'])
                source=Path(cues.get('metadata',{}).get('soundFile',''))
                assert source.is_file() and digest(source)==digest(audio),'Cues must follow final processed audio'
            else:
                assert cues['method']=='off_screen' and not cues['mouthCues']
            voice=clip['voice'];assert voice['usage_mode']=='evaluation' and voice['official_sample_id'] in ('007','006','002','005')
            checks.append({'job_id':entry['job_id'],'segment':clip['segment_id'],'category':voice['category'],'official_sample_id':voice['official_sample_id'],'final_audio_unchanged':True,'cue_method':cues['method']})
    result={'baseline_asset_files_preserved':len(baseline['assets']),'baseline_mp4_files_preserved':len(baseline['existing_mp4']),'changed':changed,'audio_cue_checks':checks,'commercial_permission_verified':False,'human_listening_review':'pending'}
    atomic_json(ROOT/'workspace/v10-preservation-verification.json',result);print(json.dumps({k:v for k,v in result.items() if k!='audio_cue_checks'}));print('Final audio/cue checks:',len(checks))
if __name__=='__main__':main()
