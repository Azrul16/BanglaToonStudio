"""Real conditioning of selected GENERATED demo outputs; evaluation only."""
import json
import shutil
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.library import AssetLibrary
from app.voices.four_voices import configuration,reference,OFFICIAL_SELECTIONS,CHARACTER_CATEGORIES
from app.voices.assignment import resolve_voices
from app.voices.base import VoiceIdentity
from app.voices.chatterbox_bangla import synthesize,ENGINE
from app.voices.variation import wav_info
from app.engines.lip_sync import generate_mouth_cues
from app.scene_cache import atomic_json,digest

TEXT='এই! তোরা কিছু শুনলি? চল, আমরা একসঙ্গে ভালো করে দেখি।'


def main():
    directory=ROOT/'evaluation/selected-demo-conditioning';directory.mkdir(parents=True,exist_ok=True)
    library=AssetLibrary(ROOT/'assets',ROOT/'workspace')
    characters=['rahat','arif','sami','mehna','tithi','nabil','rayan','fahim','anika','maliha']
    identities,issues=resolve_voices(library,[{'speaker':cid,'speaker_name':cid} for cid in characters],'chatterbox_bangla')
    assert not issues,issues
    reports=[]
    try:
        for cid in characters:
            identity=VoiceIdentity(**identities[cid]);assert identity.usage_mode=='evaluation'
            row,path=reference(identity.category)
            output=directory/(cid+'.wav')
            duration=synthesize(TEXT,identity,output,ROOT/'models/chatterbox-bangla')
            result=dict(ENGINE.result);assert result['runtime']['reference_applied']
            assert result['original']['frames']==result['final']['frames']
            cue=generate_mouth_cues(output,directory/(cid+'.cues.json'),'rhubarb');assert cue['method']=='rhubarb'
            entry={'character_id':cid,'category':identity.category,'official_sample_id':identity.official_sample_id,'reference_source_kind':row['source_kind'],
                'reference_hash':row['sha256'],'reference_file':str(path),'text':TEXT,'processed_file':output.name,'original_file':cid+'.original.wav',
                'sha256':digest(output),'duration_seconds':duration,'identity':identity.model_dump(),'result':result,'rhubarb':'rhubarb',
                'conditioning_execution':'passed','human_pronunciation_and_similarity_review':'pending','commercial_permission_verified':False}
            reports.append(entry)
            atomic_json(directory/'results.json',{'mode':'evaluation','purpose':'Generated official outputs tested as conditioning inputs; Original reference recordings not downloaded or substituted',
                'selected_samples':OFFICIAL_SELECTIONS,'commercial_permissions_verified':False,'results':reports})
            print(cid,identity.category,identity.official_sample_id,duration,result['runtime']['device'],'original_cache_hit',result['original_cache_hit'],flush=True)
    finally:ENGINE.release()
    with __import__('app.voices.four_voices',fromlist=['LOCK']).LOCK:
        from app.voices.four_voices import CONFIG
        data=configuration()
        for category in OFFICIAL_SELECTIONS:
            rid=data['base_voices'][category]['reference_id']
            data['references'][rid]['conditioning_test_status']='execution_passed_listening_review_pending'
        atomic_json(CONFIG,data)


if __name__=='__main__':main()
