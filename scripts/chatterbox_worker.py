"""Isolated Bengali-compatible inference; JSON-line protocol, never an HTTP server."""
import argparse
import gc
import hashlib
import json
import sys
import time
import wave
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--device',choices=['cuda','cpu'],required=True);args=parser.parse_args()
    sys.path.insert(0,str(ROOT/'tools/chatterbox-finetuning'))
    import torch
    torch.set_num_threads(4)
    import torchaudio
    from safetensors import safe_open
    from src.chatterbox_.tts import ChatterboxTTS,Conditionals
    folder=ROOT/'models/chatterbox-bangla';model=None;load_seconds=None
    for raw in sys.stdin:
        try:
            request=json.loads(raw);started=time.perf_counter()
            if model is None:
                before=time.perf_counter()
                sys.path.insert(0,str(ROOT))
                from app.voices.checkpoint import verify_checkpoint
                verified=verify_checkpoint(folder)
                with safe_open(str(folder/'t3_cfg.safetensors'),framework='pt',device='cpu') as checkpoint:vocab=checkpoint.get_slice('text_emb.weight').get_shape()[0]
                if vocab!=2530:raise RuntimeError('Unexpected BosonLab vocabulary; refusing incompatible weights')
                model=ChatterboxTTS.from_local(folder,device=args.device);load_seconds=time.perf_counter()-before
                if model.t3.hp.text_tokens_dict_size!=vocab:raise RuntimeError('Vocabulary-size patch was not applied')
            if args.device=='cuda':torch.cuda.reset_peak_memory_stats()
            settings=request.get('settings',{});seed=int(settings.get('seed',1234));torch.manual_seed(seed)
            if args.device=='cuda':torch.cuda.manual_seed_all(seed)
            reference=request.get('reference')
            if not reference:model.conds=Conditionals.load(folder/'conds.pt',map_location='cpu').to(args.device)
            with torch.inference_mode():
                audio=model.generate(request['text'],audio_prompt_path=reference,exaggeration=float(settings.get('exaggeration',.5)),
                    cfg_weight=float(settings.get('cfg_weight',.5)),temperature=float(settings.get('temperature',.8)))
            path=Path(request['output']);path.parent.mkdir(parents=True,exist_ok=True)
            pcm=audio.detach().cpu().reshape(-1)
            if not torch.isfinite(pcm).all():raise RuntimeError('Chatterbox returned non-finite audio')
            import soundfile as sf
            raw_path=path.with_suffix('.model-float.wav')
            sf.write(str(raw_path),pcm.numpy(),model.sr,subtype='FLOAT')
            float_peak=float(pcm.abs().max());raw_out_of_range=int((pcm.abs()>1).sum())
            gain=min(1.,.95/max(float_peak,1e-9));pcm=pcm*gain;clipped=int((pcm.abs()>1).sum())
            with wave.open(str(path),'wb') as output:
                output.setparams((1,2,model.sr,0,'NONE','not compressed'))
                output.writeframes((pcm.clamp(-1,1).numpy()*32767).astype('<i2').tobytes())
            result={'ok':True,'sample_rate':model.sr,'duration_seconds':audio.shape[-1]/model.sr,'device':args.device,'torch':torch.__version__,'torchaudio':torchaudio.__version__,
                    'model_id':'BosonLab/chatterbox-bangla','revision':'025a56f71bef7fddc9ee878c9e9557d2ca559499',
                    'tokenizer_sha256':hashlib.sha256((folder/'tokenizer.json').read_bytes()).hexdigest(),
                    'reference_sha256':hashlib.sha256(Path(reference).read_bytes()).hexdigest() if reference else None,
                    'input_text_sha256':hashlib.sha256(request['text'].encode('utf-8')).hexdigest(),
                    'verified_checkpoint_sha256':verified['sha256'],'vocabulary':vocab,'load_seconds':load_seconds,'generation_seconds':time.perf_counter()-started,'float_peak':float_peak,'clipped_float_samples':clipped,
                    'raw_out_of_range_model_samples':raw_out_of_range,'pcm_headroom_gain':gain,'raw_model_waveform':str(raw_path),
                    'peak_cuda_allocated_mb':torch.cuda.max_memory_allocated()/1024**2 if args.device=='cuda' else 0.,'reference_applied':bool(reference),'generation_settings':settings}
            del audio;gc.collect()
        except Exception as exc:
            import traceback;traceback.print_exc(file=sys.stderr)
            text=str(exc);oom=any(word in text.lower() for word in ('out of memory','cuda','cublas','cudnn','nvidia driver'))
            result={'ok':False,'device':args.device,'cuda_oom':args.device=='cuda' and oom,'error':type(exc).__name__+': '+text[:500]}
        print('@@CHATTERBOX '+json.dumps(result),flush=True)
        if not result['ok']:return


if __name__=='__main__':main()
