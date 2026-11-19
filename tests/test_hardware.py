import json
from types import SimpleNamespace
import pytest
import app.hardware as hardware


def test_nvenc_probe_failure_selects_cpu(monkeypatch):
    hardware.encoder_capabilities.cache_clear()
    monkeypatch.setattr(hardware,'ffmpeg_binary',lambda:'ffmpeg')
    monkeypatch.setattr(hardware,'ffprobe_binary',lambda:'ffprobe')
    calls=[]
    def probe(command,timeout=30):
        calls.append(command)
        return SimpleNamespace(returncode=int('h264_nvenc' in command),stderr='unsupported NVENC',stdout='')
    monkeypatch.setattr(hardware,'run',probe)
    try:
        info=hardware.encoder_capabilities()
        assert info['encoder']=='libx264' and info['nvenc_tested'] and not info['nvenc_available']
        assert all('-frames:v' in call for call in calls)
    finally: hardware.encoder_capabilities.cache_clear()


def test_corrupt_output_is_rejected(monkeypatch,tmp_path):
    monkeypatch.setattr(hardware,'ffprobe_binary',lambda:'ffprobe')
    monkeypatch.setattr(hardware,'run',lambda *args:SimpleNamespace(returncode=0,stdout=json.dumps({'streams':[],'format':{'duration':'10'}}),stderr=''))
    with pytest.raises(RuntimeError,match='Invalid MP4'): hardware.validate_video(tmp_path/'bad.mp4',10)
