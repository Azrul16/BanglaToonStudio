"""Matched real 2D/hybrid render using already human-approved Bengali WAVs."""
import argparse
import json
import shutil
import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.library import AssetLibrary
from app.review import ReviewInput,analyze,snapshot_plan
from app.engines.video_renderer import export_video,build_audio
from app.engines.lip_sync import generate_mouth_cues
from app.scene_cache import atomic_json,digest
from app.audio.quality import require_audio
from app.hardware import ResourceMonitor
from app.rendering.godot_adapter import encode_scene
from app.hardware import encoder_capabilities
from app.timeline import build_timeline
from app.director import IntelligentCartoonDirector

def prepare(mode,low_memory=False,background_id='mango_orchard_day'):
    source=ROOT/'evaluation/quality-repair';approved=json.loads((source/'listening-approval.json').read_text(encoding='utf-8'))
    if approved.get('listened') is not True:raise RuntimeError('Approved speech required')
    rows=json.loads((source/'source-audit.json').read_text(encoding='utf-8'))['comparisons'][:3]
    story='দৃশ্য: আমবাগান\nচরিত্র: নাবিল, রায়ান, অনিকা\n[MUSIC: mystery]\n[নাবিল ধীরে হাঁটে।]\n[রায়ান মাথা ঘোরায়।]\n'
    for name,emotion,row in zip(('নাবিল','রায়ান','অনিকা'),('উত্তেজিত','সাবধান করে','অবাক হয়ে'),rows):story+=name+' ('+emotion+'): '+row['text']+'\n'
    story+='[ক্যামেরা: medium]\n[SFX: rustling_leaves]\n'
    suffix=('-720p' if low_memory else '-1080p')+('' if background_id=='mango_orchard_day' else '-'+background_id)
    directory=ROOT/'workspace'/(('hybrid-portrait' if mode=='hybrid_2_5d' else 'flat-portrait')+suffix);directory.mkdir(exist_ok=True)
    for part in ('audio','cues','render/scenes'):(directory/part).mkdir(parents=True,exist_ok=True)
    report,parsed,plan=analyze(AssetLibrary(ROOT/'assets',ROOT/'workspace'),ReviewInput(story=story,renderer='godot'))
    if background_id!='mango_orchard_day':
        choices=[{k:s[k] for k in ('scene_id','start_segment','end_segment','background_id','location_text')} for s in report['scenes']]
        for choice in choices:choice['background_id']=background_id
        report,parsed,plan=analyze(AssetLibrary(ROOT/'assets',ROOT/'workspace'),ReviewInput(story=story,renderer='godot',scenes=choices))
    assert report['ready'],report['issues'];assert len(parsed['segments'])==3
    clips=[]
    for clip,row in zip(parsed['segments'],rows):
        path=source/row['segment']/'fresh_no_transform.wav';target=directory/'audio'/(clip['id']+'.wav');assert digest(path)==approved['audio_hashes'][clip['id']]
        shutil.copyfile(path,target);quality=require_audio(target,clip['text']);clips.append({**clip,'duration_seconds':quality['duration_seconds']})
        generate_mouth_cues(target,directory/'cues'/(clip['id']+'.json'),'rhubarb')
    snapshot=snapshot_plan(plan,directory);snapshot.update(renderer='godot',render_mode=mode,allow_hybrid_prototype=mode=='hybrid_2_5d',capture_hybrid_viewports=mode=='hybrid_2_5d')
    options={'renderer':'godot','duration_mode':'shorts','video_profile':'low_memory' if low_memory else 'production','music':True,'evaluation_only':True}
    return directory,clips,snapshot,options

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--probe',action='store_true');parser.add_argument('--low-memory',action='store_true');parser.add_argument('--background',default='mango_orchard_day');parser.add_argument('--mode',choices=['2d','hybrid_2_5d','both'],default='both');args=parser.parse_args();results=[]
    for mode in ('2d','hybrid_2_5d') if args.mode=='both' else (args.mode,):
        directory,clips,plan,options=prepare(mode,args.low_memory,args.background)
        with ResourceMonitor() as monitor:
            start=time.perf_counter()
            if args.probe:
                timeline=build_timeline(clips,plan,options);plan['direction']=IntelligentCartoonDirector().plan(timeline,plan,clips)
                result=encode_scene(clips,timeline,plan,directory,encoder_capabilities()['encoder'],lambda v:None,lambda:None,{'scene_id':'probe','start_frame':0,'end_frame':30,'duration_seconds':1.})
            else:
                result=export_video(clips,directory,options,plan=plan,progress=lambda value:print(mode,value,flush=True))
                output=ROOT/'output'/(('hybrid-portrait' if mode=='hybrid_2_5d' else 'flat-portrait')+('-720p' if args.low_memory else '-1080p')+'-evaluation.mp4');shutil.copyfile(directory/'cartoon.mp4',output)
        results.append({'mode':mode,'directory':str(directory),'result':result,'elapsed_seconds':time.perf_counter()-start,'peak_process_tree_rss_mb':monitor.peak_mb,'speech_hashes':{c['id']:digest(directory/'audio'/(c['id']+'.wav')) for c in clips}})
        atomic_json(ROOT/'workspace/hybrid-benchmark-results.json',{'results':results,'probe':args.probe,'commercial_permission_verified':False});print(mode,'finished',flush=True)
        atomic_json(directory/'acceptance.json',results[-1])
if __name__=='__main__':main()
