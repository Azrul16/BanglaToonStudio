"""Validated speech/cue and immutable asset checkpoints for interrupted jobs."""
import json
import wave
from app.scene_cache import digest,fingerprint,cached_file,atomic_json
from app.assets import load_character,load_background
from app.engines.bangla_tts import MODEL_ID,MODEL_REVISION
from app.engines.lip_sync import validate_cues


def audio_key(segment):
    identity=segment.get('voice_identity',{})
    if isinstance(identity,dict) and identity.get('provider')=='chatterbox_bangla':
        from app.voices.chatterbox_bangla import MODEL_ID as CB_ID,MODEL_REVISION as CB_REV,CACHE_VERSION
        return fingerprint({'speaker':segment['speaker'],'text':segment.get('synthesis_text',segment['text']),'voice':identity,'model':CB_ID,'revision':CB_REV,'cache_version':CACHE_VERSION,'emotion':segment.get('emotion','neutral')})
    return fingerprint({'text':segment.get('synthesis_text',segment['text']),'voice':segment.get('voice_identity',segment['voice_id']),'model':MODEL_ID,'revision':MODEL_REVISION})


def cached_audio(path,segment):
    cache=cached_file(path,path.with_suffix('.cache.json'),audio_key(segment))
    if cache:
        try:
            with wave.open(str(path),'rb') as wav:
                duration=wav.getnframes()/wav.getframerate()
                if duration>0 and wav.getnchannels()==1 and wav.getsampwidth()==2:return duration
        except (OSError,ValueError,EOFError,wave.Error):pass
    return None


def remember_audio(path,segment):
    atomic_json(path.with_suffix('.cache.json'),{'key':audio_key(segment),'sha256':digest(path)})


def cue_key(audio,mode,clip):return fingerprint({'audio':digest(audio),'mode':mode,'off_screen':clip['off_screen'],'kind':clip['kind']})


def cached_cues(path,audio,mode,clip):
    if cached_file(path,path.with_suffix('.cache.json'),cue_key(audio,mode,clip)):
        try:return validate_cues(json.loads(path.read_text(encoding='utf-8')),clip['duration_seconds'])
        except (ValueError,KeyError,TypeError):pass
    return None


def remember_cues(path,audio,mode,clip):
    atomic_json(path.with_suffix('.cache.json'),{'key':cue_key(audio,mode,clip),'sha256':digest(path)})


def remember_plan(plan,directory):
    root=directory/'asset_snapshot'
    value={'characters':list(plan['characters']),'backgrounds':list(plan.get('backgrounds',{plan['background']['background_id']:plan['background']})),
           'background':plan['background']['background_id'],'review_scenes':plan.get('review_scenes',[]),'warnings':plan['warnings'],
           'screenplay':plan.get('screenplay'),
           'metadata':{str(p.relative_to(root)):digest(p) for p in root.rglob('*.json')}}
    atomic_json(directory/'snapshot-ready.json',value)


def restore_plan(directory):
    data=json.loads((directory/'snapshot-ready.json').read_text(encoding='utf-8'));root=directory/'asset_snapshot'
    for relative,expected in data['metadata'].items():
        path=(root/relative).resolve()
        if not path.is_relative_to(root.resolve()) or digest(path)!=expected:raise ValueError('Job snapshot metadata changed; refusing to change character identity on resume.')
    backgrounds={bid:load_background(bid,root) for bid in data['backgrounds']}
    result={'characters':{cid:load_character(cid,root) for cid in data['characters']},'backgrounds':backgrounds,
            'background':backgrounds[data['background']],'review_scenes':data['review_scenes'],'warnings':data['warnings']}
    if data.get('screenplay') is not None:result['screenplay']=data['screenplay']
    return result
