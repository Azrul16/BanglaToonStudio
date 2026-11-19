"""Real two-line vertical subtitle/narration probe using an existing Chatterbox WAV."""
import json
import shutil
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.library import AssetLibrary
from app.review import ReviewInput,analyze,snapshot_plan
from app.engines.video_renderer import export_video
from app.scene_cache import atomic_json,digest
from app.hardware import ffmpeg_binary,run


def main():
    sample=json.loads((ROOT/'evaluation/chatterbox-local/results.json').read_text(encoding='utf-8'))[2]
    source=ROOT/'evaluation/chatterbox-local'/sample['file']
    directory=ROOT/'workspace/v7-two-line-subtitles';directory.mkdir(exist_ok=True)
    for name in ('audio','cues'):(directory/name).mkdir(exist_ok=True)
    story='দৃশ্য: আমবাগান\nচরিত্র: নাবিল, রায়ান, অনিকা\nবর্ণনাকারী: '+sample['text']
    report,parsed,plan=analyze(AssetLibrary(ROOT/'assets',ROOT/'workspace'),ReviewInput(story=story,renderer='godot'))
    assert report['ready'] and len(parsed['segments'])==1,report
    clip={**parsed['segments'][0],'duration_seconds':sample['duration_seconds']}
    shutil.copyfile(source,directory/'audio/segment_001.wav')
    atomic_json(directory/'cues/segment_001.json',{'method':'off_screen','mouthCues':[]})
    plan=snapshot_plan(plan,directory);plan['renderer']='godot'
    info=export_video([clip],directory,{'renderer':'godot','duration_mode':'shorts','music':True,'sound_effects':True},plan=plan)
    timeline=json.loads((directory/'timeline.json').read_text(encoding='utf-8'));cue=timeline['subtitles'][0]
    assert len(cue['lines'])==2 and cue['end']-cue['start']==sample['duration_seconds']
    video=ROOT/'output/v7-two-line-subtitle-evaluation.mp4';shutil.copyfile(directory/'cartoon.mp4',video)
    result=run([ffmpeg_binary(),'-y','-v','error','-ss',str((cue['start']+cue['end'])/2),'-i',str(video),'-frames:v','1',str(ROOT/'workspace/v7-two-line-subtitles.png')],60)
    assert result.returncode==0,result.stderr
    atomic_json(directory/'acceptance.json',{'info':info,'subtitle':cue,'audio_source':'Actual prior unconditioned Chatterbox sample 003','source_sha256':digest(source),
        'narrator_offscreen':True,'purpose':'evaluation only; commercial clearance and reference conditioning not established'})
    print(json.dumps(info))


if __name__=='__main__':main()
