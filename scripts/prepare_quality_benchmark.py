"""Prepare audio comparisons now; render only after hash-bound human approval."""
import argparse
import json
import shutil
import sys
import wave
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.library import AssetLibrary
from app.review import ReviewInput,analyze,snapshot_plan
from app.scene_cache import atomic_json,digest
from app.timeline import build_timeline
from app.director import IntelligentCartoonDirector
from app.engines.video_renderer import build_audio,export_video
from app.engines.lip_sync import generate_mouth_cues
from app.audio.mixer import mix
from app.audio.quality import require_audio

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--render',action='store_true');args=parser.parse_args()
    root=ROOT/'evaluation/quality-repair';data=json.loads((root/'source-audit.json').read_text(encoding='utf-8'));rows=data['comparisons'][:3]
    story='দৃশ্য: আমবাগান\nচরিত্র: নাবিল, রায়ান, অনিকা\n[MUSIC: mystery]\n[নাবিল ধীরে হাঁটে।]\n'
    for name,emotion,row in zip(('নাবিল','রায়ান','অনিকা'),('উত্তেজিত','সাবধান করে','কৌতূহলী'),rows):story+=name+' ('+emotion+'): '+row['text']+'\n'
    story+='[SFX: rustling_leaves]\n'
    directory=ROOT/'workspace/quality-repair-benchmark';directory.mkdir(exist_ok=True)
    for part in ('audio','cues','render'):(directory/part).mkdir(exist_ok=True)
    options={'renderer':'godot','duration_mode':'shorts','music':True,'sound_effects':True,'evaluation_only':True}
    report,parsed,plan=analyze(AssetLibrary(ROOT/'assets',ROOT/'workspace'),ReviewInput(story=story,renderer='godot'))
    assert report['ready'],report['issues'];assert len(parsed['segments'])==3
    clips=[];hashes={}
    for segment,row in zip(parsed['segments'],rows):
        source=root/row['segment']/'fresh_no_transform.wav';path=directory/'audio'/(segment['id']+'.wav');shutil.copyfile(source,path)
        checks=require_audio(path,segment['text']);clips.append({**segment,'duration_seconds':checks['duration_seconds']});hashes[segment['id']]=digest(path)
    timeline=build_timeline(clips,plan,options);snapshot=snapshot_plan(plan,directory);snapshot['renderer']='godot';direction=IntelligentCartoonDirector().plan(timeline,snapshot,clips)
    build_audio(clips,timeline,directory);shutil.copyfile(directory/'render/timeline.wav',root/'benchmark-speech-only.wav')
    mix(directory/'render/timeline.wav',direction,directory,True);shutil.copyfile(directory/'render/timeline.wav',root/'benchmark-balanced-mix.wav')
    atomic_json(root/'benchmark-plan.json',{'story':story,'duration_seconds':timeline['duration_seconds'],'audio_hashes':hashes,'human_listening_review':'pending','video_rendered':False})
    print('Audio-only benchmark:',timeline['duration_seconds'],'seconds',flush=True)
    if not args.render:return
    approval=root/'listening-approval.json'
    if not approval.exists():raise RuntimeError('Human listening approval is missing. No video was rendered.')
    accepted=json.loads(approval.read_text(encoding='utf-8'))
    if accepted.get('listened') is not True or accepted.get('audio_hashes')!=hashes:raise RuntimeError('Approve the exact current speech clips first')
    for clip in clips:generate_mouth_cues(directory/'audio'/(clip['id']+'.wav'),directory/'cues'/(clip['id']+'.json'),'rhubarb')
    info=export_video(clips,directory,options,plan=snapshot)
    assert 15<=info['duration_seconds']<=20,info['duration_seconds']
    shutil.copyfile(directory/'cartoon.mp4',ROOT/'output/quality-repair-evaluation.mp4')
    atomic_json(root/'benchmark-video.json',{'info':info,'audio_hashes':hashes,'human_approved':True,'commercial_permission_verified':False})
    atomic_json(root/'benchmark-plan.json',{'story':story,'duration_seconds':info['duration_seconds'],'audio_hashes':hashes,'human_listening_review':'approved for this short test','video_rendered':True})
if __name__=='__main__':main()
