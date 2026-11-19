"""Small on-disk checkpoints; no frame sequences are retained in memory."""
import hashlib
import json
import wave
import os
import tempfile
import time
from pathlib import Path

PIPELINE_VERSION=1


def digest(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def atomic_json(path,value):
    # Unique temporaries avoid collisions across independent status writers.
    # Windows readers/indexers can briefly deny replacement of an open file.
    temp=None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,prefix=path.stem+'.',suffix='.tmp',delete=False) as stream:
            temp=Path(stream.name);json.dump(value,stream,ensure_ascii=False,indent=2)
        for attempt in range(10):
            try:os.replace(temp,path);return
            except PermissionError:
                if attempt==9:raise
                time.sleep(min(.1,.01*2**attempt))
    finally:
        if temp is not None:
            try:temp.unlink(missing_ok=True)
            except OSError:pass


def cached_file(path,metadata,key):
    try:
        data=json.loads(metadata.read_text(encoding='utf-8'))
        return data if data['key']==key and data['sha256']==digest(path) else None
    except (OSError,ValueError,KeyError):return None


def split_scenes(timeline,max_seconds=12):
    """Partition the exact frame clock at source scene boundaries, then bounded cuts."""
    groups=[]
    for scene in timeline['scenes']:
        start,end=scene['start_frame'],scene['end_frame']
        if groups and groups[-1]['source_scene_id']==scene['source_scene_id']:
            groups[-1]['end_frame']=end
        else:groups.append({'source_scene_id':scene['source_scene_id'],'start_frame':start,'end_frame':end})
    chunks=[];limit=round(max_seconds*timeline['fps'])
    for group in groups:
        for start in range(group['start_frame'],group['end_frame'],limit):
            end=min(start+limit,group['end_frame'])
            chunks.append({**group,'scene_id':f"render_{len(chunks)+1:04}",'start_frame':start,'end_frame':end,
                           'duration_seconds':(end-start)/timeline['fps'],'status':'pending','progress':0})
    return chunks


def slice_audio(source,target,start_frame,end_frame,fps=30):
    with wave.open(str(source),'rb') as src,wave.open(str(target),'wb') as dst:
        samples=48000//fps
        dst.setparams(src.getparams());src.setpos(start_frame*samples)
        remaining=(end_frame-start_frame)*samples
        while remaining:
            count=min(remaining,48000);data=src.readframes(count)
            if len(data)!=count*2:raise RuntimeError('Scene PCM does not cover its exact frame interval')
            dst.writeframesraw(data);remaining-=count
