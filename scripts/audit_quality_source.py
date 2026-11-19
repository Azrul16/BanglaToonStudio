"""Export aligned, same-take comparisons from the reported 87.5-second movie."""
import json
import shutil
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.hardware import ffmpeg_binary,run
from app.scene_cache import atomic_json,digest
from app.audio.quality import inspect_audio

def main():
    directory=ROOT/'workspace/35334dd3d8a541c1a9de2ceb54854c4f';job=json.loads((directory/'job.json').read_text(encoding='utf-8'))
    timeline=json.loads((directory/'timeline.json').read_text(encoding='utf-8'));movie=ROOT/'output/35334dd3d8a541c1a9de2ceb54854c4f.mp4'
    folder=ROOT/'evaluation/quality-repair';folder.mkdir(exist_ok=True);rows=[]
    for index in (0,1,2,9,16):
        clip=job['clips'][index];take=job['approved_speech'][index];target=folder/clip['id'];target.mkdir(exist_ok=True)
        original=Path(take['provider_metrics']['original_path']);processed=directory/'audio'/(clip['id']+'.wav')
        assert digest(processed)==take['audio_hash']
        shutil.copyfile(original,target/'original_tts.wav');shutil.copyfile(processed,target/'processed_voice.wav')
        shot=next(s for s in timeline['scenes'] if s.get('clip_id')==clip['id'])
        result=run([ffmpeg_binary(),'-y','-v','error','-i',str(movie),'-ss',str(shot['start']),'-t',str(clip['duration_seconds']),'-vn','-ac','1','-c:a','pcm_s16le',str(target/'final_mix_excerpt.wav')],60)
        if result.returncode:raise RuntimeError(result.stderr)
        reports={name:inspect_audio(target/(name+'.wav'),clip['text']) for name in ('original_tts','processed_voice','final_mix_excerpt')}
        row={'segment':clip['id'],'speaker':clip['speaker'],'text':clip['text'],'synthesis_text':take['synthesis_text'],'start':shot['start'],
            'voice':take['voice'],'provider_metrics':take['provider_metrics'],'reports':reports,'original_equals_processed':digest(original)==digest(processed)}
        rows.append(row)
    atomic_json(folder/'source-audit.json',{'source_video':str(movie),'source_job':job['job_id'],'comparisons':rows,'human_listening_review':'pending','commercial_permission_verified':False})
    print('Exported five same-take original / processed / final-mix comparisons.',flush=True)
if __name__=='__main__':main()
