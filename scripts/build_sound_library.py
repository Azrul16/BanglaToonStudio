"""Original procedural Foley/ambience/music. No third-party recordings."""
import json
import hashlib
import sys
import wave
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
folder=ROOT/'assets/sounds';folder.mkdir(exist_ok=True)
rate=48000;rng=np.random.default_rng(7319)
def write(name,data,description):
    path=folder/(name+'.wav')
    if not path.exists():
        data=np.clip(data,-.85,.85)
        with wave.open(str(path),'wb') as wav:wav.setparams((1,2,rate,0,'NONE','not compressed'));wav.writeframes((data*32767).astype('<i2').tobytes())
    return {'file':name+'.wav','description':description,'license':'CC0-1.0','origin':'Original deterministic procedural synthesis; no sampled recordings'}
items={}
t=np.arange(round(rate*.14))/rate
items['footstep']=write('footstep',(rng.normal(size=len(t))*.1+np.sin(2*np.pi*95*t)*.25)*np.exp(-38*t),'Short soft ground contact')
t=np.arange(round(rate*.8))/rate;noise=rng.normal(size=len(t));noise=noise-np.convolve(noise,np.ones(12)/12,mode='same')
items['rustling_leaves']=write('rustling_leaves',noise*.075*(np.sin(np.pi*t/.8)**2)*(0.6+0.4*np.sin(t*47)**2),'Original dry leaf rustle synthesis')
t=np.arange(rate*6)/rate;noise=rng.normal(size=len(t));noise=np.convolve(noise,np.ones(160)/160,mode='same')
items['wind']=write('wind',noise*.6*(.7+.3*np.sin(t*1.4)),'Soft filtered wind bed')
t=np.arange(rate*4)/rate;phase=2*np.pi*(1400*t+220*np.sin(t*4));envelope=np.maximum(0,np.sin(t*9))**12
items['birds']=write('birds',np.sin(phase)*envelope*.12,'Stylized original bird calls')
items['night']=write('night',np.sin(2*np.pi*3600*t)*np.maximum(0,np.sin(t*17))**20*.05,'Soft synthetic cricket-like night bed')
t=np.arange(round(rate*.3))/rate
items['surprise']=write('surprise',np.sin(2*np.pi*(750*t-400*t*t))*np.exp(-12*t)*.3,'Brief original surprise accent')
t=np.arange(rate*8)/rate;music=np.zeros(len(t))
for index,note in enumerate((261.63,329.63,392.,293.66)):
    local=t-index*2;mask=(local>=0)&(local<2);env=np.sin(np.pi*np.clip(local/2,0,1))**2
    music+=np.where(mask,(np.sin(2*np.pi*note*t)+.35*np.sin(2*np.pi*note*1.5*t))*env*.1,0)
items['music']=write('music',music,'Simple original four-note instrumental bed')
# Separate authored note/harmony patterns, with different tonal centres and pacing.
themes={
 'happy':([60,64,67,72,67,64,69,67],.40,[48,53,55,48]),
 'comedy':([60,72,67,63,65,60,70,67],.28,[48,53,55,48]),
 'mystery':([57,60,64,58,57,65,60,59],.72,[45,46,52,45]),
 'suspense':([45,46,45,52,45,48,46,43],.60,[33,34,40,33]),
 'adventure':([60,67,72,71,69,67,64,67],.42,[48,55,57,53]),
 'emotional':([57,60,64,67,65,64,60,59],.88,[45,53,48,52]),
 'calm':([60,64,67,69,67,64,62,60],.90,[48,53,57,55]),
 'dramatic':([48,55,60,63,62,55,58,60],.55,[36,44,41,43])}
for mood,(notes,step,chords) in themes.items():
    t=np.arange(rate*24)/rate;theme=np.zeros_like(t)
    for i,start in enumerate(np.arange(0,24,step)):
        local=t-start;duration=step*1.8;mask=(local>=0)&(local<duration)
        note=notes[i%len(notes)];frequency=440*2**((note-69)/12)
        env=(1-np.exp(-np.maximum(local,0)*24))*np.exp(-np.maximum(local,0)*3/duration)
        theme+=np.where(mask,(np.sin(2*np.pi*frequency*local)+.16*np.sin(2*np.pi*frequency*2*local))*env*.08,0)
    for i,start in enumerate(range(0,24,6)):
        local=t-start;env=np.sin(np.pi*np.clip(local/6,0,1))**2;frequency=440*2**((chords[i%4]-69)/12)
        theme+=np.where((local>=0)&(local<6),(np.sin(2*np.pi*frequency*local)+.4*np.sin(2*np.pi*frequency*1.5*local))*env*.04,0)
    theme*=np.minimum(1,t/.3)*np.minimum(1,(24-t)/.6)
    items['music_'+mood]=write('music_'+mood,theme,'Original '+mood+' instrumental theme; synthetic instruments')
t=np.arange(rate*8)/rate;water=rng.normal(size=len(t));water=np.convolve(water,np.ones(45)/45,mode='same')
items['water']=write('water',water*.35*(.7+.3*np.sin(t*1.8)),'Original stylized water movement bed')
train=rng.normal(size=len(t));train=np.convolve(train,np.ones(230)/230,mode='same')
items['station_distant']=write('station_distant',train*.25+np.sin(2*np.pi*110*t)*np.sin(np.pi*t/8)**4*.015,'Original distant platform rumble; no sampled trains')
for entry in items.values():entry['sha256']=hashlib.sha256((folder/entry['file']).read_bytes()).hexdigest()
(folder/'library.json').write_text(json.dumps({'license':'CC0-1.0','sounds':items},indent=2),encoding='utf-8')
print('Original sound library:',len(items),'files')
