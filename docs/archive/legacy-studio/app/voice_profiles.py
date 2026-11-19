"""Permanent local reference profiles. Demo audio is evaluation-only."""
import base64
import hashlib
import io
import json
import threading
import wave
from pathlib import Path
from fastapi import APIRouter,HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel,Field,ConfigDict
from app.scene_cache import atomic_json,digest
from app.voices.base import VoiceError

ROOT=Path(__file__).resolve().parents[1]
PROFILE_PATH=ROOT/'assets/voice_references/profiles.json'
LOCK=threading.RLock()
CHARACTERS={'rahat':('Rahat','male'),'arif':('Arif','male'),'sami':('Sami','male'),'mehna':('Mehna','female'),'tithi':('Tithi','female'),
            'nabil':('Nabil','child_male'),'rayan':('Rayan','child_male'),'fahim':('Fahim','child_male'),'anika':('Anika','child_female'),'maliha':('Maliha','child_female'),
            'narrator':('Narrator','male'),'unknown_voice':('Off-screen voice','male')}
SETTINGS={'exaggeration':0.5,'cfg_weight':0.5,'temperature':0.8,'seed':42}


def profiles():
    with LOCK:
        if not PROFILE_PATH.exists():
            PROFILE_PATH.parent.mkdir(parents=True,exist_ok=True)
            atomic_json(PROFILE_PATH,{'schema_version':1,'categories':['male','female','child_male','child_female'],
                'characters':{cid:{'name':name,'category':category,'reference_audio':None,'reference_audio_hash':None,
                    'authorization':None,'generation_settings':dict(SETTINGS)} for cid,(name,category) in CHARACTERS.items()}})
        data=json.loads(PROFILE_PATH.read_text(encoding='utf-8'))
        if data.get('schema_version')!=1 or set(data['characters'])!=set(CHARACTERS):raise VoiceError('Invalid permanent voice profiles')
        return data


def production_reference(cid,expected_hash=None):
    profile=profiles()['characters'].get(cid)
    if not profile or not profile.get('reference_audio') or not profile.get('authorization'):raise VoiceError('An authorized reference recording is required for '+cid)
    path=(PROFILE_PATH.parent/profile['reference_audio']).resolve()
    if not path.is_relative_to(PROFILE_PATH.parent.resolve()) or not path.is_file():raise VoiceError('Voice reference is missing')
    actual=digest(path)
    if actual!=profile['reference_audio_hash'] or expected_hash and expected_hash!=actual:raise VoiceError('Voice reference changed; review the character assignment again')
    return profile,path


class ReferenceUpload(BaseModel):
    model_config=ConfigDict(extra='forbid')
    wav_base64:str=Field(max_length=14000000)
    authorization:str=Field(min_length=20,max_length=2000)
    consent:bool=False


def save_reference(cid,payload):
    if cid not in CHARACTERS or not payload.consent:raise VoiceError('Choose a registered character and confirm permission to condition its voice')
    try:
        raw=base64.b64decode(payload.wav_base64,validate=True)
        with wave.open(io.BytesIO(raw),'rb') as wav:
            if wav.getsampwidth()!=2 or wav.getnchannels() not in (1,2) or not 16000<=wav.getframerate()<=48000:raise VoiceError('Use 16-bit PCM WAV, 16–48 kHz, mono or stereo')
            duration=wav.getnframes()/wav.getframerate();pcm=wav.readframes(wav.getnframes())
            if not 3<=duration<=30 or not any(pcm):raise VoiceError('Use a non-silent 3–30 second reference')
            import audioop
            if audioop.rms(pcm,2)<100:raise VoiceError('Reference audio is too quiet')
            # Canonical mono PCM prevents accidental duplicate voices with different WAV headers/rates.
            mono=audioop.tomono(pcm,2,.5,.5) if wav.getnchannels()==2 else pcm
            canonical=audioop.ratecv(mono,2,1,wav.getframerate(),24000,None)[0]
    except (ValueError,wave.Error,EOFError) as exc:raise VoiceError('Invalid reference WAV') from exc
    sha=hashlib.sha256(raw).hexdigest();pcm_sha=hashlib.sha256(canonical).hexdigest()
    benchmark=ROOT/'evaluation/chatterbox-bangla-official/audios/output'
    for sample in benchmark.glob('*.wav'):
        with wave.open(str(sample),'rb') as wav:
            frames=wav.readframes(wav.getnframes())
            mono=audioop.tomono(frames,2,.5,.5) if wav.getnchannels()==2 else frames
            canonical_sample=audioop.ratecv(mono,2,1,wav.getframerate(),24000,None)[0]
        if digest(sample)==sha or hashlib.sha256(canonical_sample).hexdigest()==pcm_sha:raise VoiceError('Official demo outputs are evaluation-only, not production references')
    with LOCK:
        data=profiles()
        if any(key!=cid and p.get('pcm_hash')==pcm_sha for key,p in data['characters'].items()):raise VoiceError('This reference already belongs to another character; provide a distinct authorized recording')
        path=PROFILE_PATH.parent/(cid+'-'+sha[:16]+'.wav');path.write_bytes(raw)
        data['characters'][cid].update(reference_audio=path.name,reference_audio_hash=sha,pcm_hash=pcm_sha,authorization=payload.authorization)
        atomic_json(PROFILE_PATH,data)
    return data['characters'][cid]


def reference_router(get_library):
    router=APIRouter()
    @router.get('/api/voice-references')
    def overview():
        return {'characters':[{'id':cid,'name':p['name'],'category':p['category'],'configured':bool(p['reference_audio'])} for cid,p in profiles()['characters'].items()]}
    @router.post('/api/voice-references/{cid}')
    def upload(cid:str,payload:ReferenceUpload):
        raise HTTPException(410,'Per-character recording setup was replaced by Default Cartoon Voices. Use the four category selectors; existing recordings are preserved.')
    @router.get('/api/benchmarks/chatterbox')
    def benchmarks():
        path=ROOT/'evaluation/chatterbox-bangla-official/manifest.json'
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'samples':[]}
    @router.get('/api/benchmarks/chatterbox/{sample_id}.wav')
    def sample(sample_id:str):
        if sample_id not in [f'{i:03}' for i in range(1,8)]:raise HTTPException(404)
        return FileResponse(ROOT/'evaluation/chatterbox-bangla-official/audios/output'/(sample_id+'.wav'),media_type='audio/wav')
    return router
