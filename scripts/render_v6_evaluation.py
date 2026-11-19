"""Real v6 regression render using unconditioned Chatterbox, EVALUATION ONLY.

This bypasses no production reference checks: it is an offline benchmark, with
one built-in voice for all speakers. It does not register or approve that voice.
"""
import json
import shutil
import sys
import time
import wave
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.library import AssetLibrary
from app.review import ReviewInput,analyze,snapshot_plan
from app.engines.lip_sync import generate_mouth_cues
from app.engines.video_renderer import export_video
from app.voices.chatterbox_bangla import ENGINE,MODEL_ID,MODEL_REVISION
from app.scene_cache import atomic_json,digest


def main():
    directory=ROOT/'workspace/v6-chatterbox-evaluation';directory.mkdir(exist_ok=True)
    for name in ('audio','cues'):(directory/name).mkdir(exist_ok=True)
    script=(ROOT/'samples/v6_regression_bn.txt').read_text(encoding='utf-8')
    options={'renderer':'godot','duration_mode':'mini','video_format':'auto','music':True,'sound_effects':True,'lip_sync':'rhubarb'}
    report,parsed,plan=analyze(AssetLibrary(ROOT/'assets',ROOT/'workspace'),ReviewInput(story=script,**{k:v for k,v in options.items() if k!='lip_sync'}))
    assert report['ready'],report['issues']
    assert len(parsed['segments'])==5 and len(report['scenes'])==1
    atomic_json(directory/'analysis.json',report);plan=snapshot_plan(plan,directory);plan['renderer']='godot'
    clips=[];started=time.perf_counter()
    try:
        for segment in parsed['segments']:
            path=directory/'audio'/(segment['id']+'.wav');meta=path.with_suffix('.evaluation.json')
            expected={'text':segment['text'],'model':MODEL_ID,'revision':MODEL_REVISION,'purpose':'unconditioned evaluation only'}
            if path.is_file() and meta.is_file() and json.loads(meta.read_text(encoding='utf-8')).get('request')==expected:
                result=json.loads(meta.read_text(encoding='utf-8'))['result']
                assert digest(path)==result['sha256']
            else:
                result=ENGINE.generate(segment['text'],path,evaluation=True);result['sha256']=digest(path)
                atomic_json(meta,{'request':expected,'result':result})
            with wave.open(str(path),'rb') as wav:duration=wav.getnframes()/wav.getframerate()
            clip={**segment,'duration_seconds':duration,'voice_identity':{'provider':'chatterbox_bangla','mode':'unconditioned_evaluation','commercial_clearance':'unverified'}}
            clips.append(clip)
            cues=generate_mouth_cues(path,directory/'cues'/(segment['id']+'.json'),'rhubarb')
            assert cues['method']=='rhubarb',cues
            print(segment['id'],segment['speaker'],duration,result['device'],flush=True)
    finally:ENGINE.release()
    atomic_json(directory/'manifest.json',clips)
    info=export_video(clips,directory,options,plan=plan,progress=lambda v:print('render',round(v,2),flush=True),stage=lambda *v:print('stage',*v,flush=True))
    output=ROOT/'output/v6-chatterbox-evaluation.mp4';shutil.copyfile(directory/'cartoon.mp4',output)
    atomic_json(directory/'acceptance.json',{'purpose':'evaluation only; same built-in voice across speakers; no production voice clearance or distinctness claimed','video':str(output),'info':info,'elapsed_seconds':time.perf_counter()-started})
    print(json.dumps({'video':str(output),'info':info}),flush=True)


if __name__=='__main__':main()
