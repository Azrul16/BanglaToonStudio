"""Explicit alternative-model evaluation; never changes production assignments."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.engines.bangla_tts import VITSTTSEngine,MODEL_ID,MODEL_REVISION
from app.audio.quality import inspect_audio
from app.scene_cache import atomic_json,digest

def main():
    root=ROOT/'evaluation/quality-repair';source=json.loads((root/'source-audit.json').read_text(encoding='utf-8'));engine=VITSTTSEngine()
    rows=[{'segment':r['segment'],'text':r['synthesis_text']} for r in source['comparisons']]
    rows.append({'segment':'pronunciation_words','text':'নাবিল, রায়ান আর অনিকা, তোমরা কোথায় যাচ্ছ? একটু দাঁড়াও! আমরা একসঙ্গে প্রশ্নের উত্তর খুঁজব। বন্ধুত্ব, শ্রদ্ধা আর দায়িত্বের কথা মনে রেখো।'})
    results=[]
    for row in rows:
        folder=root/row['segment'];folder.mkdir(exist_ok=True);target=folder/'alternative_vits.wav';duration=engine.synthesize(row['text'],target)
        results.append({**row,'provider':'vits','model':MODEL_ID,'revision':MODEL_REVISION,'voice':'default_bn','duration_seconds':duration,
            'sha256':digest(target),'audio':inspect_audio(target,row['text']),'runtime':engine.report(),'reference_applied':False,'character_voice_claim':False})
        atomic_json(root/'alternative-vits.json',{'results':results,'purpose':'Explicit alternative Bengali model comparison after human rejection of Chatterbox speech. One shared VITS voice, no automatic fallback or assignment change.',
            'human_listening_review':'pending','commercial_permission_verified':False});print(row['segment'],duration,flush=True)
if __name__=='__main__':main()
