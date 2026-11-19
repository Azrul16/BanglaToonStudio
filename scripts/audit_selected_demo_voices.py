"""Audit actual selected-demo conditioning, DSP, and normal-workflow video."""
import json
import shutil
import sys
import zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.scene_cache import atomic_json,digest
from app.hardware import run,ffprobe_binary
from scripts.audit_v4_media import audit


def main():
    folder=ROOT/'evaluation/selected-demo-conditioning'
    data=json.loads((folder/'results.json').read_text(encoding='utf-8'))
    categories={}
    for entry in data['results']:
        result=entry['result'];runtime=result['runtime']
        assert runtime['reference_applied'] and runtime['vocabulary']==2530
        assert runtime['clipped_float_samples']==0 and runtime['float_peak']*runtime['pcm_headroom_gain']<=.950001
        assert result['original']['frames']==result['final']['frames']
        assert result['final']['peak']<32767
        raw=Path(runtime['raw_model_waveform']);target=folder/(entry['character_id']+'.model-float.wav')
        shutil.copyfile(raw,target);assert digest(raw)==digest(target)
        entry['raw_model_file']=target.name
        categories.setdefault(entry['category'],{'sample_id':entry['official_sample_id'],'duration_seconds':entry['duration_seconds'],'device':runtime['device'],
            'vocabulary':runtime['vocabulary'],'peak_cuda_allocated_mb':runtime['peak_cuda_allocated_mb'],'conditioning_applied':True,'pcm_clipped_samples':0,
            'raw_model_preserved':True,'pcm_headroom_gain':runtime['pcm_headroom_gain'],'source_kind':entry['reference_source_kind']})
    atomic_json(folder/'results.json',data)
    source=json.loads((ROOT/'workspace/selected-demo-browser-acceptance.json').read_text(encoding='utf-8'))
    movie=audit(source)
    probe=run([ffprobe_binary(),'-v','error','-show_format','-of','json',source['video']],60)
    comment=json.loads(probe.stdout)['format'].get('tags',{}).get('comment','')
    assert 'EVALUATION ONLY' in comment
    job=json.loads((ROOT/'workspace'/source['job_id']/'job.json').read_text(encoding='utf-8'))
    assert job['evaluation_only']
    assert all(line['voice']['usage_mode']=='evaluation' for line in job['approved_speech'])
    assert all(line['provider_metrics']['original_cache_hit'] for line in job['approved_speech'])
    folder.joinpath('README.txt').write_text('EVALUATION ONLY. Generated official demo outputs 007/006/002/005 were used as conditioning inputs. Commercial voice permissions remain unverified. Original reference recordings were not substituted. Each character has a PCM before-DSP WAV, a processed WAV, preserved unmodified FLOAT model output and Rhubarb cues. Human pronunciation/similarity/naturalness review is pending.\n',encoding='utf-8')
    archive=ROOT/'output/selected-demo-audio-comparisons.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as zipped:
        for path in folder.iterdir():
            if path.suffix in ('.wav','.json','.txt'):zipped.write(path,path.name)
    atomic_json(ROOT/'workspace/selected-demo-verification.json',{'categories':categories,'characters_tested':len(data['results']),
        'model_inferences':sum(not e['result']['original_cache_hit'] for e in data['results']),'video':movie,'mp4_comment':comment,
        'speech_cache_reused_for_video':True,'render_timings':job.get('report',{}).get('timings',job.get('timings')),
        'archive':str(archive),'commercial_permission_verified':False,'human_listening_review':'pending'})
    print(json.dumps({'categories':categories,'video':movie,'archive':str(archive)}))


if __name__=='__main__':main()
