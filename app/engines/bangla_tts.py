"""Shared lazy Coqui VITS runtime with CUDA selection and CPU recovery."""
from __future__ import annotations
import os
import threading
import time
import wave
from pathlib import Path

MODEL_ID='EMTIAZZ/bangladeshi-bangla-tts-vits'
MODEL_REVISION='6f4b22c88c2fcc74805aa54c5f2c5f612d463d08'


class TTSError(RuntimeError):
    pass


class VITSTTSEngine:
    def __init__(self,cache_dir=None,device='auto'):
        self.cache_dir=Path(cache_dir or Path(__file__).resolve().parents[2]/'models/bangla-vits')
        self.requested_device=device
        self.device='not_loaded'
        self.model=None
        self.lock=threading.RLock()
        self.fallback_reason=None
        self.load_seconds=0.

    def load(self):
        with self.lock:
            if self.model is not None: return self.model
            started=time.perf_counter()
            try:
                import torch
                from TTS.api import TTS
                from huggingface_hub import snapshot_download
            except (ImportError,OSError) as exc:
                raise TTSError(f'Compatible TTS dependencies are missing: {exc}. Install requirements-tts.txt with matching torch/torchaudio 2.8.0.') from exc
            torch.set_num_threads(min(4,os.cpu_count() or 1))
            self.cache_dir.mkdir(parents=True,exist_ok=True)
            checkpoint=self.cache_dir/'pytorch_model.pth'
            config=self.cache_dir/'config.json'
            if not checkpoint.is_file() or not config.is_file():
                if os.getenv('HF_HUB_OFFLINE')=='1':
                    raise TTSError('VITS checkpoint missing in offline mode; download the pinned model first.')
                try:
                    snapshot_download(repo_id=MODEL_ID,revision=MODEL_REVISION,token=False,
                                      allow_patterns=['config.json','pytorch_model.pth'],local_dir=str(self.cache_dir))
                except Exception as exc:
                    raise TTSError(f'VITS model download failed: {exc}. Internet is needed only for the first download.') from exc
            if self.requested_device not in ('auto','cpu','cuda'):
                raise TTSError('TTS device must be auto, cpu, or cuda')
            self.device='cuda' if self.requested_device!='cpu' and torch.cuda.is_available() else 'cpu'
            if self.requested_device=='cuda' and self.device=='cpu':
                self.fallback_reason='CUDA is unavailable in this PyTorch installation; using CPU.'
            try:
                # One CPU load; only the selected shared instance is moved to CUDA.
                with torch.inference_mode():
                    self.model=TTS(model_path=str(checkpoint),config_path=str(config),progress_bar=False).to('cpu')
                    if self.device=='cuda':
                        try: self.model.to('cuda')
                        except (RuntimeError,AssertionError) as exc:
                            self.fallback_reason=f'CUDA initialization failed; using CPU: {exc}'
                            self.model.to('cpu'); self.device='cpu'
                self.load_seconds=time.perf_counter()-started
            except Exception as exc:
                self.model=None
                raise TTSError(f'Failed to load the Coqui VITS checkpoint: {exc}') from exc
            return self.model

    def synthesize(self,text:str,output_path:str|Path)->float:
        if not isinstance(text,str) or not text.strip(): raise TTSError('Cannot synthesize empty text')
        if len(text)>1500: raise TTSError('Speech segments must contain at most 1,500 characters')
        output=Path(output_path)
        output.parent.mkdir(parents=True,exist_ok=True)
        with self.lock:
            model=self.load()
            import torch
            try:
                with torch.inference_mode():
                    try:
                        model.tts_to_file(text=text.strip(),file_path=str(output),split_sentences=False)
                    except RuntimeError as exc:
                        if self.device!='cuda': raise
                        # Includes CUDA OOM and driver/runtime failures. Never retry
                        # forever or invent silent audio when both devices fail.
                        self.fallback_reason=f'CUDA inference failed; retried on CPU: {exc}'
                        self.model.to('cpu'); self.device='cpu'
                        output.unlink(missing_ok=True)
                        model.tts_to_file(text=text.strip(),file_path=str(output),split_sentences=False)
                with wave.open(str(output),'rb') as wav:
                    duration=wav.getnframes()/wav.getframerate()
                    if wav.getnchannels()!=1 or wav.getsampwidth()!=2 or duration<=0:
                        raise TTSError('VITS returned invalid PCM speech audio')
                    pcm=wav.readframes(wav.getnframes())
                    if not any(pcm): raise TTSError('VITS returned silent audio; generation failed')
                return duration
            except Exception as exc:
                output.unlink(missing_ok=True)
                if isinstance(exc,TTSError): raise
                raise TTSError(f'Bengali speech generation failed on {self.device}: {exc}') from exc

    def report(self):
        info={'device':self.device,'fallback_reason':self.fallback_reason,'load_seconds':round(self.load_seconds,4)}
        if self.device=='cuda':
            import torch
            info['worker_peak_cuda_allocated_mb']=round(torch.cuda.max_memory_allocated()/1024**2,1)
        return info


ENGINE=VITSTTSEngine(device=os.getenv('TOON_TTS_DEVICE','auto'))


def synthesize(text: str,output_file:Path,cache_dir:Path)->float:
    # Compatibility entry point; all jobs share this one loaded engine.
    ENGINE.cache_dir=Path(cache_dir)
    return ENGINE.synthesize(text,output_file)
