"""Fresh model inference without character transformations; no video render."""
import json
import argparse
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.voices.chatterbox_bangla import ENGINE,MODEL_ID,MODEL_REVISION
from app.voices.four_voices import configuration,CONFIG
from app.audio.quality import inspect_audio
from app.scene_cache import atomic_json,digest

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--exact-input',action='store_true');args=parser.parse_args()
    folder=ROOT/'evaluation/quality-repair';source=json.loads((folder/'source-audit.json').read_text(encoding='utf-8')) if (folder/'source-audit.json').exists() else json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    rows=source['comparisons'];config=configuration();job=json.loads((ROOT/'workspace/35334dd3d8a541c1a9de2ceb54854c4f/job.json').read_text(encoding='utf-8'));results=[]
    try:
        for index,row in enumerate(rows):
            source_index=next(i for i,c in enumerate(job['clips']) if c['id']==row['segment']);clip=job['clips'][source_index];take=job['approved_speech'][source_index];identity=take['voice'];category=identity['category']
            selected=config['references'][config['base_voices'][category]['reference_id']];reference=(CONFIG.parent/selected['file']).resolve()
            assert digest(reference)==identity['reference_audio_hash']
            target=folder/clip['id']/('exact_input_no_transform.wav' if args.exact_input else 'fresh_no_transform.wav');settings=take['provider_metrics']['runtime']['generation_settings']
            submitted=take['synthesis_text'] if args.exact_input else clip['text']
            runtime=ENGINE.generate(submitted,target,reference,settings)
            runtime.update(model_id=MODEL_ID,revision=MODEL_REVISION,reference_sha256=digest(reference),official_sample_id=identity['official_sample_id'])
            results.append({'segment_id':clip['id'],'text':submitted,'speaker':clip['speaker'],'runtime':runtime,'audio':inspect_audio(target,submitted),'transformation_applied':False})
            atomic_json(folder/('exact-input-benchmark.json' if args.exact_input else 'fresh-benchmark.json'),{'results':results,'human_listening_review':'pending','commercial_permission_verified':False});print(clip['id'],runtime['duration_seconds'],flush=True)
    finally:ENGINE.release()
if __name__=='__main__':main()
