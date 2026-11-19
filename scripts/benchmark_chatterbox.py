"""Real local inference evaluation, without claiming authorization for built-in voices."""
import json
import sys
import time
import wave
import argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.voices.chatterbox_bangla import ENGINE

TEXTS=['এই রায়ান! তুই কোথায় যাচ্ছিস? দাঁড়া, আমিও আসছি!',
       'নাবিল, তুই কি সত্যিই ভয় পেয়েছিস? আরে, এখানে তো কিছুই নেই!',
       'পানি বাঁচানো আমাদের সবার দায়িত্ব। ছোট ছোট অভ্যাসই বড় পরিবর্তন আনে।']


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--device',choices=['auto','cuda','cpu'],default='auto');parser.add_argument('--limit',type=int,choices=[1,2,3],default=3);args=parser.parse_args()
    folder=ROOT/'evaluation/chatterbox-local'
    if args.device!='auto':folder=folder/args.device
    folder.mkdir(parents=True,exist_ok=True)
    reports=[]
    try:
        for i,text in enumerate(TEXTS[:args.limit],1):
            path=folder/f'benchmark-{i:03}.wav'
            result=ENGINE.generate(text,path,evaluation=True,device=args.device)
            import audioop
            with wave.open(str(path),'rb') as wav:
                pcm=wav.readframes(wav.getnframes());peak=audioop.max(pcm,wav.getsampwidth())
                assert wav.getnchannels()==1 and wav.getnframes()>0 and audioop.rms(pcm,wav.getsampwidth())>50
            reports.append({'id':f'{i:03}','text':text,'file':path.name,**result,'peak_pcm':peak,'human_pronunciation_review':'pending','voice_consistency_review':'pending; built-in unconditioned voice, not distinct character profiles'})
            (folder/'results.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps({'sample':i,**result}),flush=True)
    finally:ENGINE.release()


if __name__=='__main__':main()
