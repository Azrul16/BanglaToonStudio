"""Permanent voice choices, pronunciation, paid-request approval and WAV output."""
import json
import math
import os
import re
import unicodedata
import wave
import threading
from pathlib import Path
from app.assets import normalize
from app.scene_cache import atomic_json,fingerprint
from app.voices.base import VoiceIdentity,VoiceError
from app.voices import elevenlabs,azure,vits,chatterbox_bangla
from app.hardware import ffmpeg_binary,run

PROVIDERS={'vits':vits,'elevenlabs':elevenlabs,'azure':azure,'chatterbox_bangla':chatterbox_bangla}
SETTINGS_LOCK=threading.RLock()


def validate_identity(identity):
    models={'vits':{'bangladeshi-vits'},'elevenlabs':{'eleven_v4','eleven_v3'},'azure':{'azure-neural'},'chatterbox_bangla':{'BosonLab/chatterbox-bangla'}}
    if not identity.voice_id or identity.model not in models[identity.provider]:raise VoiceError('Choose an accessible voice and a supported provider model before speech generation')
    if identity.provider=='vits' and identity.voice_id!='default_bn':raise VoiceError('Local VITS has one voice; no substitute voice ID is supported')
    if identity.provider=='azure' and identity.voice_id not in azure.ALLOWED:raise VoiceError('Select a supported Bangladesh Bengali Azure voice')


def read_object(path,default):
    if not path.exists():return default
    try:
        value=json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(value,dict):raise ValueError()
        return value
    except (ValueError,OSError):raise VoiceError(f'{path.name} is invalid; restore it instead of overwriting saved settings')


def settings(storage):return {k:VoiceIdentity(**v).model_dump() for k,v in read_object(storage/'voice_assignments.json',{}).items()}


def dictionary(storage):
    data=read_object(storage/'pronunciation.json',{'Rahat':'রাহাত','Nabil':'নাবিল','Rayan':'রায়ান','Fahim':'ফাহিম','Anika':'অনিকা','Maliha':'মালিহা'})
    if any(not isinstance(k,str) or not isinstance(v,str) or not k.strip() or not v.strip() for k,v in data.items()):raise VoiceError('Invalid pronunciation dictionary')
    return data


def spoken_text(text,corrections=None,preserve_spelling=False):
    # The Bengali tokenizer is sensitive to canonically equivalent spellings.
    # Lookup normalization must not silently rewrite approved model input.
    value=text if preserve_spelling else unicodedata.normalize('NFC',text)
    value=''.join(c for c in value if unicodedata.category(c)!='Cf' or preserve_spelling and c in '\u200c\u200d')
    value=re.sub(r'[ \t]+',' ',value).strip()
    for original,replacement in sorted((corrections or {}).items(),key=lambda p:-len(p[0])):
        # Replace whole lexical forms, preserving Bengali combining marks.
        def boundary(c):return c and unicodedata.category(c)[0] in 'LMN'
        pieces=[];start=0
        pattern=original if preserve_spelling else unicodedata.normalize('NFC',original)
        for match in re.finditer(re.escape(pattern),value):
            if boundary(value[match.start()-1:match.start()] if match.start() else '') or boundary(value[match.end():match.end()+1]):continue
            pieces.extend([value[start:match.start()],replacement]);start=match.end()
        if pieces:value=''.join(pieces)+value[start:]
    return value


def catalog(provider):
    if provider not in PROVIDERS:raise VoiceError('Unknown speech provider')
    return PROVIDERS[provider].voices()


def save_assignment(storage,character_id,identity,confirm=False):
    with SETTINGS_LOCK:return _save_assignment(storage,character_id,identity,confirm)


def remember_approved_default(storage,character_id,identity):
    with SETTINGS_LOCK:
        current=settings(storage)
        if character_id not in current:
            current[character_id]=identity.model_dump();atomic_json(storage/'voice_assignments.json',current)
        return current[character_id]


def _save_assignment(storage,character_id,identity,confirm=False):
    validate_identity(identity)
    if identity.voice_id is None:raise VoiceError('Select an actual accessible voice first')
    rows=catalog(identity.provider)
    if identity.voice_id not in {r['voice_id'] for r in rows}:raise VoiceError('Voice is not available in this provider catalog')
    if identity.provider=='elevenlabs' and identity.model not in ('eleven_v4','eleven_v3'):raise VoiceError('Select a documented dialogue model')
    if identity.provider=='azure' and identity.model!='azure-neural':raise VoiceError('Azure uses azure-neural')
    if identity.provider=='vits' and (identity.voice_id!='default_bn' or identity.model!='bangladeshi-vits'):raise VoiceError('VITS has one supported voice/model')
    current=settings(storage)
    if character_id in current and current[character_id]!=identity.model_dump() and not confirm:raise VoiceError('Confirm changing this character’s saved voice identity before overwriting it')
    current[character_id]=identity.model_dump();atomic_json(storage/'voice_assignments.json',current)
    return current[character_id]


def usage(text,identity,emotion='neutral'):
    validate_identity(identity)
    submitted=(elevenlabs.TAGS.get(emotion,'')+' '+text).strip() if identity.provider=='elevenlabs' else text
    chars=len(submitted);paid=identity.provider not in ('vits','chatterbox_bangla')
    rate=os.getenv('TOON_'+identity.provider.upper()+'_USD_PER_MILLION')
    try:cost=round(chars*float(rate)/1000000,6) if rate and paid else None
    except ValueError:raise VoiceError('Configured account pricing rate must be a number')
    if cost is not None and (not math.isfinite(cost) or cost<0):raise VoiceError('Configured account pricing rate must be finite and nonnegative')
    return {'characters':chars,'spoken_characters':len(text),'provider':identity.provider,'model':identity.model,'paid':paid,'estimated_usd':cost,
            'pricing_note':'Character count is exact; account pricing/credits and provider rounding may differ. No price is invented when no account rate is configured.',
            'approval_token':fingerprint({'text':text,'voice':identity.model_dump(),'emotion':emotion})}


def synthesize(text,identity,path,model_dir,emotion='neutral',paid_approved=False,approval_token=None,previous_request_ids=None):
    estimate=usage(text,identity,emotion)
    if estimate['paid'] and (not paid_approved or approval_token!=estimate['approval_token']):raise VoiceError('Review usage and explicitly approve this paid speech take before generation')
    if identity.provider=='vits':return vits.synthesize(text,path,model_dir)
    if identity.provider=='chatterbox_bangla':return chatterbox_bangla.synthesize(text,identity,path,model_dir,emotion)
    if identity.provider=='elevenlabs':raw,headers=elevenlabs.synthesize(text,identity,emotion,previous_request_ids)
    else:raw,headers=PROVIDERS[identity.provider].synthesize(text,identity,emotion)
    request_id=next((str(v) for k,v in headers.items() if k.lower() in ('request-id','x-request-id')),None)
    if request_id:atomic_json(path.with_suffix('.provider.json'),{'request_id':request_id[:150]})
    intermediate=path.with_suffix('.provider-original');intermediate.write_bytes(raw)
    try:
        source_args=['-f','s16le','-ar','44100','-ac','1'] if identity.provider=='elevenlabs' and os.getenv('TOON_ELEVENLABS_OUTPUT_FORMAT')=='pcm_44100' else []
        result=run([ffmpeg_binary(),'-y','-v','error',*source_args,'-i',str(intermediate),'-ac','1','-ar','24000','-c:a','pcm_s16le',str(path)],120)
        if result.returncode:raise VoiceError('Provider audio could not be converted to PCM WAV')
        with wave.open(str(path),'rb') as wav:
            duration=wav.getnframes()/wav.getframerate()
            if duration<=0 or not any(wav.readframes(wav.getnframes())):raise VoiceError('Provider returned empty or silent audio')
        return duration
    finally:pass  # Preserve original provider bytes; all downstream work stays lossless.
