import time
import wave
import numpy as np
import pytest
from app.audio.quality import inspect_audio,require_audio
from app.voices import variation
from test_v9 import four_config,configure,tone

def test_quality_rejects_empty_clipping_and_duration_drift(tmp_path):
    path=tmp_path/'test.wav'
    def write(samples):
        with wave.open(str(path),'wb') as wav:
            wav.setparams((1,2,24000,0,'NONE','not compressed'));wav.writeframes(np.array(samples,dtype='<i2').tobytes())
    write([]);assert not inspect_audio(path)['signal_valid']
    write([32767]*24000);assert 'Clipped PCM' in inspect_audio(path)['errors'][0]
    path.write_bytes(tone());assert require_audio(path)['human_pronunciation_review']=='required'
    with pytest.raises(ValueError,match='duration'):require_audio(path,expected_duration=9)

def test_neutral_policy_preserves_exact_waveform_and_invalidates_old_dsp(tmp_path,monkeypatch):
    monkeypatch.setattr(variation,'CACHE_ROOT',tmp_path/'cache');source=tmp_path/'source.wav';source.write_bytes(tone())
    target=tmp_path/'neutral.wav';result=variation.VoiceVariationEngine().process(source,target,'nabil',{'pitch_semitones':.7,'formant':'preserved'})
    assert target.read_bytes()==source.read_bytes() and not result['transformation_applied']
    assert result['transform_policy']==variation.TRANSFORM_POLICY and variation.VERSION>2

def test_chatterbox_preserves_approved_bengali_spelling():
    import unicodedata
    from app.voices.voice_manager import spoken_text
    text='রায়ান, নিশ্চয়ই আমরা একসঙ্গে প্রশ্নের উত্তর খুঁজব।'
    assert unicodedata.normalize('NFC',text)!=text
    assert spoken_text(text,preserve_spelling=True)==text
    assert spoken_text(text)==unicodedata.normalize('NFC',text)
    assert spoken_text('Nabil: '+text,{'Nabil':'নাবিল'},preserve_spelling=True)=='নাবিল: '+text

def test_isolated_normalized_peak_is_not_a_clipped_plateau(tmp_path):
    import io
    path=tmp_path/'normalized.wav';path.write_bytes(tone())
    with wave.open(str(path),'rb') as wav:params=wav.getparams();samples=np.frombuffer(wav.readframes(wav.getnframes()),dtype='<i2').copy()
    samples[100]=32767
    with wave.open(str(path),'wb') as wav:wav.setparams(params);wav.writeframes(samples.tobytes())
    report=inspect_audio(path)
    assert report['signal_valid'] and report['warnings'] and report['full_scale_plateau_samples']==1

def test_checkpoint_verification_rejects_changed_tokenizer(tmp_path):
    import hashlib
    import json
    from app.voices.checkpoint import verify_checkpoint
    path=tmp_path/'tokenizer.json';path.write_bytes(b'original')
    manifest=tmp_path/'manifest.json';manifest.write_text(json.dumps({'model_id':'test','sha256':{'tokenizer.json':hashlib.sha256(b'original').hexdigest()}}))
    assert verify_checkpoint(tmp_path,manifest)['model_id']=='test'
    path.write_bytes(b'changed')
    with pytest.raises(ValueError,match='checksum mismatch'):verify_checkpoint(tmp_path,manifest)

def test_automatic_chatterbox_requires_bound_human_review(studio,four_config,monkeypatch):
    import app.main as main
    from app.voices.chatterbox_bangla import ENGINE
    configure();monkeypatch.setenv('DEFAULT_TTS_PROVIDER','chatterbox_bangla')
    def generate(text,target,*args,**kwargs):target.write_bytes(tone());return {'device':'test_double','sample_rate':24000}
    monkeypatch.setattr(ENGINE,'generate',generate)
    created=studio.post('/api/conversations',json={'prompt':'দৃশ্য: আমবাগান\nনাবিল: তোরা কিছু শুনলি?'}).json();cid=created['id']
    for _ in range(200):
        data=studio.get('/api/conversations/'+cid).json()
        if data['status'] in ('needs_audio_review','failed'):break
        time.sleep(.05)
    assert data['status']=='needs_audio_review',data
    assert not main.JOBS and data['audio_review']['clips']
    assert studio.post('/api/conversations/'+cid+'/approve-audio',json={'listened':True,'token':'stale'}).status_code==409
    assert not main.JOBS
    assert studio.post('/api/conversations/'+cid+'/approve-audio',json={'listened':False,'token':data['audio_review']['token']}).status_code==409
    submitted=[]
    def create_render(payload,**kwargs):
        submitted.append(payload);job={'job_id':'a'*32,'status':'queued','stage':'queued','progress':0,'created_at':'2026-11-18T00:00:00Z'};main.JOBS[job['job_id']]=job;return job
    monkeypatch.setattr(main,'create_job',create_render)
    accepted=studio.post('/api/conversations/'+cid+'/approve-audio',json={'listened':True,'token':data['audio_review']['token']})
    assert accepted.status_code==200,accepted.text
    assert len(submitted)==1 and accepted.json()['status']=='queued'
    assert studio.post('/api/conversations/'+cid+'/approve-audio',json={'listened':True,'token':data['audio_review']['token']}).status_code==409
