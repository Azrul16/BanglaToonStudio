import base64
import io
import math
import wave
from array import array
import pytest
from app.voices.base import VoiceError,VoiceIdentity
from app.semantic_ai import SemanticResponse,apply_assistance
from app.voices.assignment import resolve_voices


def test_missing_chatterbox_references_never_substitute(studio,monkeypatch,tmp_path):
    import app.main as main
    monkeypatch.setenv('DEFAULT_TTS_PROVIDER','chatterbox_bangla')
    from app.voices import four_voices
    monkeypatch.setattr(four_voices,'CONFIG',tmp_path/'refs/four_voices.json')
    identities,issues=resolve_voices(main.LIBRARY,[{'speaker':'nabil','speaker_name':'নাবিল'},{'speaker':'rayan','speaker_name':'রায়ান'}])
    assert identities=={'nabil':None,'rayan':None}
    assert {i['reason'] for i in issues}=={'category_reference_required'}
    assert len(issues)==1
    assert studio.get('/api/benchmarks/chatterbox').json()['samples'][0]['production_approved'] is False
    assert studio.get('/api/benchmarks/chatterbox/001.wav').status_code==200
    assert studio.get('/api/benchmarks/chatterbox/008.wav').status_code==404


def test_retired_reference_setup_preserves_category_workflow(studio):
    assert studio.get('/api/voice-references').status_code==410
    assert studio.post('/api/voice-references/nabil',json={}).status_code==410


def test_semantic_ai_is_opt_in_and_rejects_invented_assets(studio):
    import app.main as main
    report=studio.post('/api/analyze',json={'story':'দৃশ্য: আমবাগান\n[নাবিল আকাশে উড়ে যায়।]','renderer':'godot'}).json()
    events=report['events'];unknown=next(e for e in events if e['type']=='unresolved_instruction')
    class Fake:
        calls=0
        def propose(self,payload):
            self.calls+=1
            return SemanticResponse(suggestions=[{'event_id':unknown['event_id'],'source_line':unknown['source_line'],'type':'action','character_ids':['invented_person'],'actions':['walk']}])
    provider=Fake()
    assert apply_assistance(events,main.LIBRARY,'private',False,False,provider)==[]
    assert provider.calls==0
    with pytest.raises(ValueError):apply_assistance(events,main.LIBRARY,'private',True,False,provider)
    assert apply_assistance(events,main.LIBRARY,'private',True,True,provider)[0]['reason']=='ai_rejected'
    assert unknown['type']=='unresolved_instruction' and not unknown['generate_voice']


def test_semantic_ai_only_valid_non_speech_proposals(studio):
    import app.main as main
    report=studio.post('/api/analyze',json={'story':'দৃশ্য: আমবাগান\nঅদ্ভুত আবহাওয়া।','renderer':'godot'}).json()
    events=report['events'];unknown=events[-1]
    class Valid:
        def propose(self,payload):
            return SemanticResponse(suggestions=[{'event_id':unknown['event_id'],'source_line':unknown['source_line'],'type':'scene_description','background_id':'mango_orchard_day'}])
    assert apply_assistance(events,main.LIBRARY,'test',True,True,Valid())[0]['reason']=='ai_assisted'
    assert events[-1]['type']=='scene_description' and not events[-1]['generate_voice']
    with pytest.raises(ValueError):SemanticResponse(suggestions=[{'event_id':'e1','source_line':1,'type':'dialogue','text':'invented speech'}])


def test_cuda_fallback_releases_worker_and_retries_cpu_once(monkeypatch,tmp_path):
    import io
    import queue
    from app.voices.chatterbox_bangla import LocalChatterbox
    engine=LocalChatterbox();starts=[];released=[]
    class Process:
        stdin=io.StringIO()
        def poll(self):return None
    def start(device):
        starts.append(device);engine.device=device;engine.process=Process();engine.messages=queue.Queue()
        engine.messages.put({'ok':False,'cuda_oom':True,'error':'CUDA out of memory'} if device=='cuda' else
            {'ok':True,'device':'cpu','duration_seconds':1.,'generation_seconds':2.})
    def release():released.append(engine.device);engine.process=None
    monkeypatch.setattr(engine,'start',start);monkeypatch.setattr(engine,'release',release)
    result=engine.generate('বাংলা',tmp_path/'test.wav',evaluation=True)
    assert starts==['cuda','cpu'] and released==['cuda']
    assert result['device']=='cpu' and result['fallback_reason']=='CUDA out of memory'
    with pytest.raises(VoiceError,match='authorized'):engine.generate('বাংলা',tmp_path/'production.wav')
