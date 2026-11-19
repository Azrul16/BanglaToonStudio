"""Session-scoped local worker with one bounded CUDA-to-CPU fallback."""
import json
import os
import queue
import subprocess
import threading
import logging
from pathlib import Path
from app.voices.base import VoiceError

ROOT=Path(__file__).resolve().parents[2]
MODEL_ID='BosonLab/chatterbox-bangla';MODEL_REVISION='025a56f71bef7fddc9ee878c9e9557d2ca559499';CACHE_VERSION=3
LOGGER=logging.getLogger('bangla_toon.chatterbox')


class LocalChatterbox:
    def __init__(self):self.process=None;self.lock=threading.RLock();self.result={};self.messages=None;self.log=None;self.device=None

    def start(self,device):
        self.release();python=ROOT/'.chatterbox-venv/Scripts/python.exe'
        if not python.is_file():raise VoiceError('Install the Chatterbox Bangla runtime before generation')
        (ROOT/'workspace').mkdir(exist_ok=True)
        LOGGER.info('Loading pinned Chatterbox Bangla locally on %s; model startup may take time',device)
        self.log=(ROOT/'workspace/chatterbox-runtime.log').open('a',encoding='utf-8')
        environment=os.environ.copy();environment.update(PYTHONUTF8='1',PYTHONUNBUFFERED='1',TOKENIZERS_PARALLELISM='false')
        self.process=subprocess.Popen([str(python),'-u',str(ROOT/'scripts/chatterbox_worker.py'),'--device',device],cwd=ROOT,env=environment,
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.log,text=True,encoding='utf-8',creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        self.device=device;self.messages=queue.Queue();process=self.process;messages=self.messages
        def receive():
            for line in process.stdout:
                if line.startswith('@@CHATTERBOX '):messages.put(json.loads(line[len('@@CHATTERBOX '):]))
                elif line.strip():LOGGER.info('Chatterbox | %s',line.strip()[:500])
            messages.put({'ok':False,'error':'Chatterbox worker stopped; see its local runtime log'})
        threading.Thread(target=receive,daemon=True).start()

    def generate(self,text,path,reference=None,settings=None,device='auto',evaluation=False):
        if not reference and not evaluation:raise VoiceError('An authorized character reference is required for Chatterbox production')
        with self.lock:
            preferred='cuda' if device=='auto' else device
            if self.process is None or self.process.poll() is not None or device!='auto' and self.device!=device:self.start(preferred)
            request={'text':text,'output':str(Path(path).resolve()),'reference':str(Path(reference).resolve()) if reference else None,'settings':settings or {}}
            fallback=None
            LOGGER.info('Chatterbox speech | %s characters | reference: %s',len(text),'provided; permission state is recorded separately' if reference else 'unconditioned evaluation')
            for attempt in range(2):
                self.process.stdin.write(json.dumps(request,ensure_ascii=False)+'\n');self.process.stdin.flush()
                try:result=self.messages.get(timeout=1200)
                except queue.Empty:self.release();raise VoiceError('Chatterbox generation timed out; no speech was substituted') from None
                if result.get('ok'):
                    LOGGER.info('Chatterbox WAV | %.3fs | %s | %.1fs processing',result['duration_seconds'],result['device'],result['generation_seconds'])
                    self.result={**result,'provider':'chatterbox_bangla','model_id':MODEL_ID,'revision':MODEL_REVISION,'fallback_reason':fallback};return self.result
                if attempt==0 and result.get('cuda_oom'):
                    LOGGER.warning('Chatterbox CUDA failed; releasing GPU worker and retrying once on CPU')
                    fallback=result['error'];self.release();self.start('cpu');continue
                self.release();raise VoiceError('Chatterbox Bangla failed: '+result.get('error','unknown error'))
            raise VoiceError('Chatterbox inference failed')

    def cancel_inference(self):
        """Wake the owning inference call through worker EOF without taking its lock."""
        process=self.process
        if process is not None and process.poll() is None:process.terminate()

    def release(self):
        if self.process is not None:
            self.process.kill() if self.process.poll() is None else None
            self.process.wait(timeout=10);self.process=None
        if self.log:self.log.close();self.log=None


ENGINE=LocalChatterbox()


def acting_settings(settings,emotion):
    """Only the model's documented exaggeration control is used for expression."""
    result=dict(settings)
    delta=.1 if emotion in ('excited','angry','surprised','fear') else -.08 if emotion in ('sad','worried','thinking') else 0.
    result['exaggeration']=max(.35,min(.65,float(result.get('exaggeration',.5))+delta))
    return result


def voices():
    from app.voices.four_voices import configuration,CHARACTER_CATEGORIES,reference
    rows=[]
    for cid,category in CHARACTER_CATEGORIES.items():
        try:reference(category)
        except ValueError:continue
        rows.append({'provider':'chatterbox_bangla','voice_id':cid,'name':cid,'labels':{'category':category,'language':'bn'}})
    return rows


def synthesize(text,identity,path,model_dir,emotion='neutral'):
    from app.voices.four_voices import reference,category_for,SETTINGS,configuration
    from app.voices.variation import synthesize_cached
    profile,recording=reference(category_for(identity.voice_id),identity.reference_audio_hash)
    if identity.usage_mode!=configuration().get('mode','production'):raise VoiceError('Voice usage mode changed; prepare speech again')
    preset=configuration()['character_presets'][identity.voice_id]
    if not identity.variation or any(identity.variation.get(k)!=preset[k] for k in ('pitch_semitones','formant')):raise VoiceError('Character variation changed; prepare the speech again to reuse its original audio safely')
    if identity.model_revision!=MODEL_REVISION or identity.generation_settings!=SETTINGS or identity.synthesis_version!=CACHE_VERSION:raise VoiceError('Chatterbox settings changed; prepare the speech again')
    return synthesize_cached(text,identity,path,recording,emotion,ENGINE,acting_settings(SETTINGS,emotion))
