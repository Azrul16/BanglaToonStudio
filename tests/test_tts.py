import contextlib
import sys
import types
import wave
from pathlib import Path
import pytest
from app.engines.bangla_tts import VITSTTSEngine,TTSError


@pytest.fixture
def fake_torch(monkeypatch):
    torch=types.SimpleNamespace(inference_mode=contextlib.nullcontext,set_num_threads=lambda n:None,
                                cuda=types.SimpleNamespace(is_available=lambda:True))
    monkeypatch.setitem(sys.modules,'torch',torch)
    return torch


def write_wav(path,silent=False):
    with wave.open(str(path),'wb') as wav:
        wav.setparams((1,2,22050,0,'NONE','not compressed'))
        wav.writeframes((b'\0\0' if silent else b'\x23\x04')*2205)


def test_cuda_runtime_failure_retries_cpu_once(tmp_path,fake_torch):
    calls=[]
    class Model:
        def to(self,device): calls.append(device); return self
        def tts_to_file(self,**kwargs):
            calls.append('synthesize')
            if calls==['synthesize']: raise RuntimeError('CUDA out of memory')
            write_wav(kwargs['file_path'])
    engine=VITSTTSEngine(tmp_path)
    engine.model=Model(); engine.device='cuda'
    duration=engine.synthesize('কে ওখানে?',tmp_path/'বাংলা.wav')
    assert duration==.1 and calls==['synthesize','cpu','synthesize']
    assert engine.device=='cpu' and 'CUDA inference failed' in engine.fallback_reason


def test_silent_output_is_failure(tmp_path,fake_torch):
    class Model:
        def tts_to_file(self,**kwargs): write_wav(kwargs['file_path'],True)
    engine=VITSTTSEngine(tmp_path); engine.model=Model(); engine.device='cpu'
    with pytest.raises(TTSError,match='silent audio'): engine.synthesize('কে ওখানে?',tmp_path/'bad.wav')
    assert not (tmp_path/'bad.wav').exists()


def test_model_shared_across_syntheses(tmp_path,fake_torch):
    class Model:
        def tts_to_file(self,**kwargs): write_wav(kwargs['file_path'])
    engine=VITSTTSEngine(tmp_path); engine.model=Model(); engine.device='cpu'
    model=engine.model
    engine.synthesize('প্রথম কথা।',tmp_path/'one.wav')
    engine.synthesize('দ্বিতীয় কথা।',tmp_path/'two.wav')
    assert engine.model is model


def test_cpu_fallback_on_cuda_initialization_failure(tmp_path,fake_torch,monkeypatch):
    for file in ('pytorch_model.pth','config.json'): (tmp_path/file).write_text('{}')
    class Model:
        def __init__(self,**kwargs): pass
        def to(self,device):
            if device=='cuda': raise RuntimeError('driver unavailable')
            return self
    monkeypatch.setitem(sys.modules,'TTS.api',types.SimpleNamespace(TTS=Model))
    engine=VITSTTSEngine(tmp_path)
    engine.load()
    assert engine.device=='cpu' and 'initialization failed' in engine.fallback_reason
