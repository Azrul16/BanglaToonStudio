"""Real DSP/lip-sync/render evaluation using existing unconditioned Chatterbox WAVs.

This does NOT claim that four authorized category recordings were supplied.
It never registers these generated evaluation voices as production references.
"""
import json
import shutil
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.voices.variation import VARIATIONS
from app.voices.four_voices import PITCH,CHARACTER_CATEGORIES
from app.library import AssetLibrary
from app.review import analyze,ReviewInput,snapshot_plan
from app.scene_cache import atomic_json,digest
from app.engines.lip_sync import generate_mouth_cues
from app.engines.video_renderer import export_video


def main():
    folder=ROOT/'evaluation/v9-dsp-benchmark';folder.mkdir(parents=True,exist_ok=True)
    generated=json.loads((ROOT/'evaluation/chatterbox-local/results.json').read_text(encoding='utf-8'))
    entries=[];lines=['দৃশ্য: আমবাগান','চরিত্র: নাবিল, রায়ান, ফাহিম, অনিকা','[নাবিল ধীরে হাঁটে।]']
    for cid,name in [('nabil','নাবিল'),('rayan','রায়ান'),('fahim','ফাহিম'),('anika','অনিকা')]:
        sample=generated[0 if cid!='anika' else 2];source=ROOT/'evaluation/chatterbox-local'/sample['file']
        original=folder/(cid+'.original.wav');shutil.copyfile(source,original)
        output=folder/(cid+'.wav');preset={'category':CHARACTER_CATEGORIES[cid],'pitch_semitones':PITCH[cid],'formant':'preserved','experimental':True}
        report=VARIATIONS.process(original,output,cid,preset)
        assert report['original']['frames']==report['final']['frames']
        entries.append({'character_id':cid,'text':sample['text'],'original':original.name,'processed':output.name,'report':report})
        lines.append(name+': '+sample['text'])
    atomic_json(folder/'manifest.json',{'purpose':'DSP-only unconditioned evaluation; no approved Male/Female/Child base recordings supplied; not selectable production voices',
        'human_listening_review':'pending','entries':entries})
    directory=ROOT/'workspace/v9-dsp-evaluation';directory.mkdir(exist_ok=True)
    for name in ('audio','cues'):(directory/name).mkdir(exist_ok=True)
    story='\n'.join(lines)
    report,parsed,plan=analyze(AssetLibrary(ROOT/'assets',ROOT/'workspace'),ReviewInput(story=story,renderer='godot',duration_mode='mini'))
    assert report['ready'],report['issues']
    clips=[]
    for segment,entry in zip(parsed['segments'],entries):
        audio=directory/'audio'/(segment['id']+'.wav');shutil.copyfile(folder/entry['processed'],audio)
        cues=generate_mouth_cues(audio,directory/'cues'/(segment['id']+'.json'),'rhubarb');assert cues['method']=='rhubarb'
        clips.append({**segment,'duration_seconds':entry['report']['final']['duration_seconds'],'voice_identity':{'purpose':'unconditioned DSP evaluation','preset':entry['report']['preset']}})
    plan=snapshot_plan(plan,directory);plan['renderer']='godot'
    info=export_video(clips,directory,{'renderer':'godot','duration_mode':'mini','music':True,'sound_effects':True},plan=plan)
    movie=ROOT/'output/v9-dsp-evaluation.mp4';shutil.copyfile(directory/'cartoon.mp4',movie)
    atomic_json(directory/'acceptance.json',{'purpose':'DSP evaluation only, not a configured four-reference benchmark','video':str(movie),'info':info,
        'job_id':directory.name,'approved_speech':[{'segment_id':c['id'],'audio_hash':digest(directory/'audio'/(c['id']+'.wav'))} for c in clips]})
    print(json.dumps(info))


if __name__=='__main__':main()
