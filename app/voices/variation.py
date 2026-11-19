"""Separate original-TTS and character-DSP caches; lossless intermediates."""
import json
import math
import shutil
import threading
import wave
import os
from functools import lru_cache
from pathlib import Path
from app.scene_cache import fingerprint,digest,atomic_json
from app.hardware import ffmpeg_binary,run
from app.voices.base import VoiceError

ROOT=Path(__file__).resolve().parents[2]
CACHE_ROOT=ROOT/'workspace/voice_cache_v9'
LOCK=threading.RLock()
VERSION=3
TRANSFORM_POLICY='neutral-until-listening-approved-v1'


def wav_info(path):
    import audioop
    try:
        with wave.open(str(path),'rb') as wav:
            pcm=wav.readframes(wav.getnframes())
            if wav.getnchannels()!=1 or wav.getsampwidth()!=2 or not wav.getnframes() or len(pcm)!=wav.getnframes()*2 or audioop.rms(pcm,2)<30:raise VoiceError('Speech WAV is corrupt, empty or silent')
            return {'frames':wav.getnframes(),'sample_rate':wav.getframerate(),'duration_seconds':wav.getnframes()/wav.getframerate(),'peak':audioop.max(pcm,2)}
    except (wave.Error,EOFError) as exc:raise VoiceError('Invalid speech WAV') from exc


@lru_cache(maxsize=1)
def dsp_capabilities():
    executable=ffmpeg_binary()
    if not executable:return {'algorithm':'neutral-copy','version':'1','formant_preserved':False,'diagnostic':'FFmpeg unavailable; transformation disabled'}
    result=run([executable,'-hide_banner','-h','filter=rubberband'],20)
    supported='preserved' in result.stdout+result.stderr and 'pitchq' in result.stdout+result.stderr
    version=run([executable,'-version'],20).stdout.splitlines()[0]
    return {'algorithm':'ffmpeg-rubberband' if supported else 'neutral-copy','version':version,'formant_preserved':supported,
        'diagnostic':None if supported else 'Rubber Band formant processing unavailable; neutral audio preserved'}


class VoiceVariationEngine:
    def process(self,source,target,character,preset):
        info=wav_info(source);cap=dsp_capabilities();pitch=float(preset['pitch_semitones'])
        if not math.isfinite(pitch) or abs(pitch)>1.1:raise VoiceError('Character pitch preset exceeds the conservative 1.1-semitone limit')
        target.parent.mkdir(parents=True,exist_ok=True)
        key=fingerprint({'source':digest(source),'character':character,'preset':preset,'dsp':cap,'version':VERSION,'policy':TRANSFORM_POLICY,'format':'pcm_s16le'})
        cached=CACHE_ROOT/'transformed'/key;cached.mkdir(parents=True,exist_ok=True);wav=cached/'character.wav';meta=cached/'metadata.json'
        if wav.exists() and meta.exists():
            data=json.loads(meta.read_text(encoding='utf-8'))
            if digest(wav)==data['sha256']:shutil.copyfile(wav,target);return {**data,'cache_hit':True}
        diagnostic='Character transformations disabled pending pronunciation review; saved presets retained';applied=False
        shutil.copyfile(source,wav)
        final=wav_info(wav)
        if final['peak']>=32767:
            diagnostic='DSP reached clipping; neutral original retained';applied=False;shutil.copyfile(source,wav);final=wav_info(wav)
        data={'key':key,'sha256':digest(wav),'source_sha256':digest(source),'character_id':character,'preset':preset,'dsp':cap,'transformation_applied':applied,
            'diagnostic':diagnostic,'transform_policy':TRANSFORM_POLICY,'effective_pitch_semitones':0.,'original':info,'final':final,'cache_hit':False,'listening_review':'pending; signal metrics do not approve pronunciation'}
        atomic_json(meta,data);shutil.copyfile(wav,target);return data


VARIATIONS=VoiceVariationEngine()


def synthesize_cached(text,identity,path,reference,emotion,engine,settings):
    from app.voices.chatterbox_bangla import MODEL_ID,MODEL_REVISION
    key=fingerprint({'model':MODEL_ID,'revision':MODEL_REVISION,'reference':identity.reference_audio_hash,'text':text,'settings':settings,'format':'pcm_s16le_model_rate','schema':VERSION})
    folder=CACHE_ROOT/'original'/key;folder.mkdir(parents=True,exist_ok=True);original=folder/'original.wav';metadata=folder/'metadata.json'
    with LOCK:
        hit=False
        if original.exists() and metadata.exists():
            report=json.loads(metadata.read_text(encoding='utf-8'));hit=digest(original)==report['sha256']
        if not hit:
            result=engine.generate(text,original,reference,settings,device=os.getenv('CHATTERBOX_DEVICE','auto'))
            report={'sha256':digest(original),'request_key':key,'text':text,'reference_hash':identity.reference_audio_hash,'settings':settings,'runtime':result,'audio':wav_info(original)}
            atomic_json(metadata,report)
        output=VARIATIONS.process(original,path,identity.voice_id,identity.variation)
        shutil.copyfile(original,path.with_suffix('.original.wav'))
        output.update(original_cache_hit=hit,original_cache_key=key,original_path=str(original),provider='chatterbox_bangla',runtime=report['runtime'],
            usage_mode=identity.usage_mode,official_sample_id=identity.official_sample_id,commercial_permission_verified=False if identity.usage_mode=='evaluation' else None)
        atomic_json(path.with_suffix('.variation.json'),output)
        engine.result=output
        return output['final']['duration_seconds']
