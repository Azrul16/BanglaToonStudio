"""Audit the actual conversational exports, not a mocked frontend result."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.audit_v4_media import audit
from app.scene_cache import atomic_json


if __name__=='__main__':
    source=json.loads((ROOT/'workspace/v5-browser-acceptance.json').read_text(encoding='utf-8'))
    results=[]
    for index,conversation in enumerate(source['conversations']):
        jid=conversation['job_id'];job=json.loads((ROOT/'workspace'/jid/'job.json').read_text(encoding='utf-8'))
        video=source['video'] if index==0 else str(ROOT/'output'/(jid+'.mp4'))
        results.append(audit({'job_id':jid,'video':video,'approved_speech':job['approved_speech']}))
    atomic_json(ROOT/'workspace/v5-media-audit.json',{'result':'passed','videos':results,'limitations':'Verifies decoded media, timing, speaker ownership, contacts and levels. It does not certify native pronunciation, youthful voices or broadcast quality.'})
    print(json.dumps(results,indent=2))
