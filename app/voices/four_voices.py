"""Four persistent authorized base references, never one setup per character."""
import base64
import hashlib
import io
import json
import shutil
import threading
import wave
from pathlib import Path
from app.scene_cache import atomic_json,digest
from app.voices.base import VoiceError

ROOT=Path(__file__).resolve().parents[2]
CONFIG=ROOT/'assets/voice_references/four_voices.json'
LOCK=threading.RLock()
CATEGORIES=('male','female','child_male','child_female')
CHARACTER_CATEGORIES={'rahat':'male','arif':'male','sami':'male','mehna':'female','tithi':'female','nabil':'child_male','rayan':'child_male','fahim':'child_male','anika':'child_female','maliha':'child_female','narrator':'male','unknown_voice':'male'}
PITCH={'rahat':0.,'arif':.6,'sami':-.7,'mehna':0.,'tithi':.6,'nabil':.7,'rayan':-.5,'fahim':1.1,'anika':.4,'maliha':-.5,'narrator':0.,'unknown_voice':0.}
SETTINGS={'exaggeration':.5,'cfg_weight':.5,'temperature':.8,'seed':42}
OFFICIAL_SELECTIONS={'male':'007','female':'006','child_male':'002','child_female':'005'}


def usable(row,mode):
    return bool(row and ((row.get('approved') and row.get('authorization')) or
        mode=='evaluation' and row.get('evaluation_only') and row.get('source_kind')=='official_generated_demo_output'))


def select_official_evaluation():
    """Explicit user-selected generated outputs, never a production approval."""
    with LOCK:
        data=configuration();backup=CONFIG.parent/'before-official-evaluation-selection.json'
        if not backup.exists():shutil.copyfile(CONFIG,backup)
        manifest=json.loads((ROOT/'evaluation/chatterbox-bangla-official/manifest.json').read_text(encoding='utf-8'))
        samples={s['id']:s for s in manifest['samples']};managed=CONFIG.parent/'managed';managed.mkdir(exist_ok=True)
        for category,sid in OFFICIAL_SELECTIONS.items():
            sample=samples[sid];source=ROOT/'evaluation/chatterbox-bangla-official'/sample['path']
            if digest(source)!=sample['sha256']:raise VoiceError('Official sample checksum mismatch: '+sid)
            info=inspect_wav(source.read_bytes());rid='official_output_'+sid+'_'+info['sha256'][:16];target=managed/(rid+'.wav')
            if not target.exists():shutil.copyfile(source,target)
            data['references'][rid]={'id':rid,'label':'Official Demo '+sid+' · generated output · evaluation only',
                'file':str(target.relative_to(CONFIG.parent)).replace('\\','/'),'approved':False,'authorization':None,
                'evaluation_only':True,'commercial_permission_verified':False,'source_kind':'official_generated_demo_output',
                'official_sample_id':sid,'source_url':sample['output_url'],'original_reference_url':sample['original_reference_url'],
                'conditioning_test_status':'pending',**info}
            data['base_voices'][category]={'reference_id':rid,'official_sample_id':sid}
        data['mode']='evaluation';data['official_evaluation_selections']=dict(OFFICIAL_SELECTIONS)
        atomic_json(CONFIG,data);return data


def inspect_wav(raw):
    import audioop
    try:
        with wave.open(io.BytesIO(raw),'rb') as wav:
            if wav.getsampwidth()!=2 or wav.getnchannels() not in (1,2) or not 16000<=wav.getframerate()<=48000:raise VoiceError('Use 16-bit PCM WAV, 16–48 kHz, mono or stereo')
            duration=wav.getnframes()/wav.getframerate();pcm=wav.readframes(wav.getnframes())
            if not 3<=duration<=30 or len(pcm)!=wav.getnframes()*wav.getnchannels()*2:raise VoiceError('Use a complete 3–30 second reference WAV')
            if audioop.rms(pcm,2)<100:raise VoiceError('Reference is silent or too quiet')
            from array import array
            samples=array('h',pcm)
            if sum(abs(v)>=32760 for v in samples)>len(samples)*.001:raise VoiceError('Reference is clipped; use a clean recording')
            mono=audioop.tomono(pcm,2,.5,.5) if wav.getnchannels()==2 else pcm
            canonical=audioop.ratecv(mono,2,1,wav.getframerate(),24000,None)[0]
            return {'duration_seconds':duration,'sample_rate':wav.getframerate(),'channels':wav.getnchannels(),'peak':audioop.max(pcm,2),
                'sha256':hashlib.sha256(raw).hexdigest(),'pcm_sha256':hashlib.sha256(canonical).hexdigest()}
    except (wave.Error,EOFError,ValueError) as exc:raise VoiceError('Invalid reference WAV: '+str(exc)) from None


def category_for(cid,row=None):
    if cid in CHARACTER_CATEGORIES:return CHARACTER_CATEGORIES[cid]
    from app.voices.studio import category_for as metadata_category
    return metadata_category(row or {})


def _register(data,raw,label,authorization):
    if len(authorization.strip())<20:raise VoiceError('Record the owner, source, permission/license and intended use')
    info=inspect_wav(raw)
    # Reject the known generated demonstrations, including repackaged PCM.
    benchmark_paths=[*(ROOT/'evaluation/chatterbox-bangla-official/audios/output').glob('*.wav'),
        *(ROOT/'evaluation/chatterbox-local').rglob('*.wav'),*(ROOT/'evaluation/v9-dsp-benchmark').glob('*.wav')]
    for path in benchmark_paths:
        try:demo=inspect_wav(path.read_bytes())
        except ValueError:continue
        if demo['pcm_sha256']==info['pcm_sha256']:raise VoiceError('Evaluation samples are not approved production references')
    rid='reference_'+info['sha256']
    folder=CONFIG.parent/'managed';folder.mkdir(parents=True,exist_ok=True)
    path=folder/(rid+'.wav')
    if not path.exists():
        temp=path.with_suffix('.upload');temp.write_bytes(raw);temp.replace(path)
    data['references'][rid]={'id':rid,'label':label[:120],'file':str(path.relative_to(CONFIG.parent)).replace('\\','/'),'authorization':authorization,
        'approved':True,**info}
    return rid


def configuration():
    with LOCK:
        if not CONFIG.exists():
            CONFIG.parent.mkdir(parents=True,exist_ok=True)
            data={'schema_version':2,'provider':'chatterbox_bangla','model_id':'BosonLab/chatterbox-bangla','base_voices':{c:None for c in CATEGORIES},'references':{},
                'character_presets':{cid:{'category':cat,'pitch_semitones':PITCH.get(cid,0.),'formant':'preserved','experimental':True} for cid,cat in CHARACTER_CATEGORIES.items()},'migration_conflicts':{}}
            legacy=CONFIG.parent/'profiles.json'
            if legacy.exists():
                backup=CONFIG.parent/'migration-v9-backup';backup.mkdir(exist_ok=True)
                if not (backup/'profiles.json').exists():shutil.copyfile(legacy,backup/'profiles.json')
                assignments=ROOT/'workspace/voice_assignments.json'
                if assignments.exists() and not (backup/'voice_assignments.json').exists():shutil.copyfile(assignments,backup/'voice_assignments.json')
                old=json.loads(legacy.read_text(encoding='utf-8'));candidates={c:set() for c in CATEGORIES}
                for cid,profile in old.get('characters',{}).items():
                    if not profile.get('reference_audio') or not profile.get('authorization'):continue
                    path=(legacy.parent/profile['reference_audio']).resolve()
                    if not path.is_relative_to(legacy.parent.resolve()) or not path.is_file() or digest(path)!=profile.get('reference_audio_hash'):continue
                    try:rid=_register(data,path.read_bytes(),profile.get('name',cid),profile['authorization'])
                    except ValueError:continue
                    candidates[category_for(cid)].add(rid)
                for category,ids in candidates.items():
                    if len(ids)==1:data['base_voices'][category]={'reference_id':next(iter(ids))}
                    elif ids:data['migration_conflicts'][category]=sorted(ids)
            atomic_json(CONFIG,data)
        data=json.loads(CONFIG.read_text(encoding='utf-8'))
        if data.get('schema_version')!=2 or set(data['base_voices'])!=set(CATEGORIES):raise VoiceError('Invalid four-voice configuration; restore its backup')
        return data


def reference(category,expected=None):
    data=configuration();selected=data['base_voices'].get(category)
    if not selected:raise VoiceError(category.replace('_',' ').title()+' voice is not configured')
    row=data['references'].get(selected['reference_id'])
    if not usable(row,data.get('mode','production')):raise VoiceError('Category reference is not approved for production; replace it with a licensed recording or use evaluation mode')
    path=(CONFIG.parent/row['file']).resolve()
    if not path.is_relative_to(CONFIG.parent.resolve()) or not path.is_file() or digest(path)!=row['sha256'] or expected and expected!=row['sha256']:raise VoiceError('Category reference changed or is missing; select it again in Settings')
    return row,path


def upload(raw,label,authorization,consent):
    if not consent:raise VoiceError('Confirm permission for voice conditioning and the intended distribution')
    with LOCK:
        data=configuration();rid=_register(data,raw,label,authorization);atomic_json(CONFIG,data);return rid


def save_four(selected,mode=None):
    if set(selected)!=set(CATEGORIES):raise VoiceError('Save exactly four category selections')
    with LOCK:
        data=configuration();mode=mode or data.get('mode','production')
        if mode not in ('evaluation','production'):raise VoiceError('Choose evaluation or production mode')
        for category,rid in selected.items():
            if rid not in data['references']:raise VoiceError('Select an approved reference for '+category)
            row=data['references'][rid];path=(CONFIG.parent/row['file']).resolve()
            if not path.is_relative_to(CONFIG.parent.resolve()) or not path.is_file() or digest(path)!=row['sha256'] or not usable(row,mode):raise VoiceError('Reference is missing, changed or not permitted in '+mode+' mode')
        data['base_voices']={c:{'reference_id':rid,**({'official_sample_id':data['references'][rid]['official_sample_id']} if data['references'][rid].get('official_sample_id') else {})} for c,rid in selected.items()};data['mode']=mode;data['migration_conflicts']={};atomic_json(CONFIG,data)
        return data


def reset_variations(cid=None):
    with LOCK:
        data=configuration()
        for key,preset in data['character_presets'].items():
            if cid is None or key==cid:preset['pitch_semitones']=0.
        atomic_json(CONFIG,data);return data
