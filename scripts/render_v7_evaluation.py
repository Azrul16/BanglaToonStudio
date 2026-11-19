"""Actual Chatterbox -> Rhubarb -> Godot -> FFmpeg portrait benchmark.

Unconditioned evaluation only. No production reference/rights checks are relaxed.
"""
import argparse
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
from app.voices.chatterbox_bangla import ENGINE,MODEL_ID,MODEL_REVISION,CACHE_VERSION,acting_settings
from app.scene_cache import atomic_json,digest


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--format',choices=['vertical'],default='vertical');args=parser.parse_args()
    started=time.perf_counter();directory=ROOT/'workspace/v7-chatterbox-evaluation';directory.mkdir(exist_ok=True)
    for name in ('audio','cues'):(directory/name).mkdir(exist_ok=True)
    script=(ROOT/'samples/v7_benchmark_bn.txt').read_text(encoding='utf-8')
    library=AssetLibrary(ROOT/'assets',ROOT/'workspace')
    report,parsed,plan=analyze(library,ReviewInput(story=script,renderer='godot',duration_mode='mini'))
    assert report['ready'],report['issues']
    assert len(parsed['segments'])==5
    atomic_json(directory/'analysis.json',report)
    clips=[]
    try:
        for segment in parsed['segments']:
            path=directory/'audio'/(segment['id']+'.wav');meta=path.with_suffix('.evaluation.json')
            settings=acting_settings({'exaggeration':.5,'cfg_weight':.5,'temperature':.8,'seed':42},segment['emotion'])
            expected={'text':segment['text'],'model':MODEL_ID,'revision':MODEL_REVISION,'settings':settings,'version':CACHE_VERSION,'purpose':'unconditioned evaluation only'}
            stored=json.loads(meta.read_text(encoding='utf-8')) if meta.is_file() else None
            if stored and path.is_file() and stored['request']==expected and digest(path)==stored['result']['sha256']:result=stored['result']
            else:
                result=ENGINE.generate(segment['text'],path,evaluation=True,settings=settings);result['sha256']=digest(path)
                atomic_json(meta,{'request':expected,'result':result})
            with wave.open(str(path),'rb') as wav:
                assert wav.getsampwidth()==2 and wav.getnchannels()==1
                duration=wav.getnframes()/wav.getframerate()
            clips.append({**segment,'duration_seconds':duration,'voice_identity':{'provider':'chatterbox_bangla','mode':'unconditioned_evaluation','settings':settings,'commercial_clearance':'unverified'}})
            cues=generate_mouth_cues(path,directory/'cues'/(segment['id']+'.json'),'rhubarb')
            assert cues['method']=='rhubarb'
            print(segment['id'],segment['speaker'],segment['emotion'],duration,result['device'],flush=True)
    finally:ENGINE.release()
    atomic_json(directory/'manifest.json',clips)
    outputs=[]
    for format in [args.format]:
        target=ROOT/'workspace'/('v7-'+format);target.mkdir(exist_ok=True)
        for name in ('audio','cues'):
            (target/name).mkdir(exist_ok=True)
            for source in (directory/name).glob('*'):shutil.copyfile(source,target/name/source.name)
        snapshot=snapshot_plan(plan,target);snapshot['renderer']='godot'
        options={'renderer':'godot','duration_mode':'mini','video_format':'auto','music':True,'sound_effects':True}
        info=export_video(clips,target,options,plan=snapshot,progress=lambda v:print(format,'render',v,flush=True))
        output=ROOT/'output'/('v7-'+format+'-evaluation.mp4');shutil.copyfile(target/'cartoon.mp4',output)
        atomic_json(target/'manifest.json',clips)
        entry={'job_id':target.name,'video':str(output),'info':info,'approved_speech':[{'segment_id':c['id'],'audio_hash':digest(target/'audio'/(c['id']+'.wav'))} for c in clips]}
        outputs.append(entry);print(json.dumps(entry),flush=True)
    atomic_json(directory/'acceptance.json',{'purpose':'unconditioned evaluation only; same built-in voice, no distinct-character conditioning or commercial clearance claimed',
        'videos':outputs,'elapsed_seconds':time.perf_counter()-started,'human_pronunciation_review':'pending'})


if __name__=='__main__':main()
