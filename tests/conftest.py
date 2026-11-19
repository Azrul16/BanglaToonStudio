import math
import time
import wave
from array import array
import pytest
from fastapi.testclient import TestClient
import app.main as main


@pytest.fixture
def studio(monkeypatch,tmp_path):
    # Legacy VITS tests explicitly select that manual provider; these do not test Chatterbox inference.
    monkeypatch.setenv('DEFAULT_TTS_PROVIDER','vits')
    workspace=tmp_path/'workspace'; workspace.mkdir()
    output=tmp_path/'output'; output.mkdir()
    monkeypatch.setattr(main,'WORKSPACE',workspace)
    monkeypatch.setattr(main,'OUTPUT',output)
    monkeypatch.setattr(main,'JOBS',{})
    from app.library import AssetLibrary
    monkeypatch.setattr(main,'LIBRARY',AssetLibrary(main.ROOT/'assets',workspace))
    with TestClient(main.app) as client: yield client


@pytest.fixture
def tone_synth(monkeypatch):
    def synth(text,path,cache):
        path.parent.mkdir(parents=True,exist_ok=True)
        with wave.open(str(path),'wb') as wav:
            wav.setparams((1,2,22050,0,'NONE','not compressed'))
            samples=array('h',[int(7000*math.sin(i*.12)) for i in range(5513)])
            wav.writeframes(samples.tobytes())
        return 5513/22050
    monkeypatch.setattr(main,'synthesize',synth)
    return synth


def wait(client,job_id,timeout=90):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        job=client.get(f'/api/jobs/{job_id}').json()
        if job['status'] in main.TERMINAL: return job
        time.sleep(.03)
    pytest.fail('Generation timed out')
