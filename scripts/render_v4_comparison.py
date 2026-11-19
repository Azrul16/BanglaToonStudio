"""Same approved audio, timeline and original art; only old/new walk clocks differ."""
import json
import shutil
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.job_cache import restore_plan
from app.engines.video_renderer import export_video
from app.scene_cache import atomic_json,digest
from app.hardware import ffmpeg_binary,encoder_capabilities,run


def main():
    acceptance=json.loads((ROOT/'workspace/v4-browser-acceptance.json').read_text(encoding='utf-8'))
    entry=acceptance['videos'][0];source=ROOT/'workspace'/entry['job_id']
    job=json.loads((source/'job.json').read_text(encoding='utf-8'));clips=job['clips']
    original_hashes={p.name:digest(p) for p in (source/'audio').glob('*.wav')}
    results=[]
    for version in (1,2):
        directory=ROOT/f'workspace/v4-motion-{version}';directory.mkdir(exist_ok=True)
        for area in ('audio','cues'):shutil.copytree(source/area,directory/area,dirs_exist_ok=True)
        plan=restore_plan(source);plan.update(renderer='godot',motion_version=version,storyboard=job['storyboard'])
        result=export_video(clips,directory,job['options'],plan=plan)
        target=ROOT/f'output/v4-walk-{version}.mp4';shutil.copyfile(directory/'cartoon.mp4',target)
        results.append({'version':version,'directory':str(directory),'video':str(target),'sha256':digest(target),'master_pcm_sha256':digest(directory/'render/timeline.wav'),'video_info':result})
        print('Rendered motion version',version,flush=True)
    assert results[0]['master_pcm_sha256']==results[1]['master_pcm_sha256']
    codec=encoder_capabilities()['encoder']
    filters="[0:v]scale=360:640,setsar=1[a];[1:v]scale=360:640,setsar=1[b];[a][b]hstack,pad=720:690:0:50:black,drawtext=text='Old walk clock':x=25:y=14:fontsize=18:fontcolor=white,drawtext=text='Travel-based cycle':x=390:y=14:fontsize=18:fontcolor=white[v]"
    target=ROOT/'output/v4-walk-comparison.mp4'
    result=run([ffmpeg_binary(),'-y','-v','error','-i',results[0]['video'],'-i',results[1]['video'],'-filter_complex',filters,'-map','[v]','-map','1:a','-c:v',codec,'-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart',str(target)],180)
    if result.returncode:raise RuntimeError(result.stderr[-1500:])
    assert original_hashes=={p.name:digest(p) for p in (source/'audio').glob('*.wav')}
    atomic_json(ROOT/'workspace/v4-comparison.json',{'result':'passed','comparison':str(target),'sha256':digest(target),'renders':results,'unchanged_speech_hashes':original_hashes,'method':'Same story, audio PCM, timeline, artwork, camera, emotions, and sound mix. Motion version 1 retains the prior walk clock; version 2 uses eased travel, outward knee poles and character motion profiles.'})
    print(target,flush=True)


if __name__=='__main__':main()
