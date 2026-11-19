"""Signal integrity checks; deliberately not a pronunciation certification."""
import wave
import numpy as np

VERSION=1
def inspect_audio(path,text='',expected_duration=None):
    errors=[];warnings=[]
    try:
        with wave.open(str(path),'rb') as wav:
            rate=wav.getframerate();channels=wav.getnchannels();frames=wav.getnframes();width=wav.getsampwidth();raw=wav.readframes(frames)
        if width!=2 or channels!=1 or rate not in (16000,22050,24000,44100,48000):raise ValueError('Expected mono PCM16 at a supported speech rate')
        if not frames or len(raw)!=frames*2:raise ValueError('Empty or truncated WAV data')
        samples=np.frombuffer(raw,dtype='<i2').astype(np.float64)/32768.;duration=frames/rate
        peak=float(np.max(np.abs(samples)));clipped=int(np.count_nonzero(np.abs(samples)>=32767/32768))
        full_scale=np.abs(samples)>=32767/32768
        edges=np.diff(np.r_[False,full_scale,False].astype(np.int8));starts=np.flatnonzero(edges==1);ends=np.flatnonzero(edges==-1)
        plateau=int(np.max(ends-starts)) if len(starts) else 0
        step=max(1,round(rate*.02));blocks=[float(np.sqrt(np.mean(samples[i:i+step]**2))) for i in range(0,frames,step)]
        silence=[r<.003 for r in blocks];longest=run=0
        for quiet in silence:
            run=run+1 if quiet else 0;longest=max(longest,run)
        words=len(text.split())
        if peak<.005:errors.append('Speech is empty or effectively silent')
        if plateau>=3 or clipped/frames>.0005:errors.append('Clipped PCM plateaus detected')
        elif clipped:warnings.append('Isolated full-scale peak; normalization can cause this without clipping. Review the waveform and speech.')
        if not .12<=duration<=120:errors.append('Speech duration is outside the supported per-take range')
        if expected_duration is not None and abs(duration-expected_duration)>max(1/rate,.001):errors.append('Unexpected processing duration change')
        if words>=4 and duration<words*.12:warnings.append('Unusually short speech for this text; possible truncation or skipped words')
        if longest*.02>1.5:warnings.append('Long silence requires listening review')
        if blocks and blocks[-1]>.04:warnings.append('Active audio at the end may indicate an abrupt cut; review the final word')
        return {'version':VERSION,'sample_rate':rate,'frames':frames,'duration_seconds':duration,'peak':peak,'clipped_samples':clipped,
            'full_scale_plateau_samples':plateau,'rms':float(np.sqrt(np.mean(samples**2))),'dc_offset':float(np.mean(samples)),'longest_silence_seconds':round(longest*.02,3),
            'silence_fraction':sum(silence)/len(silence),'errors':errors,'warnings':warnings,'signal_valid':not errors,
            'human_pronunciation_review':'required','asr_used':False}
    except (OSError,ValueError,wave.Error,EOFError) as exc:
        return {'version':VERSION,'signal_valid':False,'errors':[str(exc)],'warnings':[],'human_pronunciation_review':'required','asr_used':False}

def require_audio(path,text='',expected_duration=None):
    report=inspect_audio(path,text,expected_duration)
    if report['errors']:raise ValueError('Audio quality check failed: '+'; '.join(report['errors']))
    return report
