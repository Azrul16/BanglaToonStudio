"""Check exported bones/foot plants, closed listener mouths, and chunk seeking."""
import json
import math
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.render_godot_benchmark import prepare
from app.rendering.godot_adapter import encode_scene
from app.scene_cache import atomic_json,digest
from app.hardware import encoder_capabilities


def read(path):return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


if __name__=='__main__':
    directory,clips,timeline,plan=prepare()
    full=read(directory/'render/render_0001-poses.jsonl')
    walk=[r for r in full if r['character']=='nabil' and r['action']=='walk']
    assert max(r['left_knee'] for r in walk)-min(r['left_knee'] for r in walk)>.5
    contacts={}
    for row in walk:
        t=row['frame']/30;phase=(t*72/65)%1
        if t>.25 and phase<.6:contacts.setdefault(math.floor(t*72/65),[]).append(row['left_ankle'])
    drift=max(max(p[0] for p in rows)-min(p[0] for p in rows) for rows in contacts.values())
    height=max(max(p[1] for p in rows)-min(p[1] for p in rows) for rows in contacts.values())
    assert drift<.1 and height<.1,(drift,height)
    for scene in timeline['scenes']:
        if scene['kind']!='speech':continue
        listeners=[r for r in full if scene['start_frame']<=r['frame']<scene['end_frame'] and r['character']!=scene['speaker']]
        assert listeners and all(r['mouth']=='X' for r in listeners)
    assert max(r['elbow'] for r in full)-min(r['elbow'] for r in full)>.8
    assert max(r['head'] for r in full)-min(r['head'] for r in full)>.1
    # Evaluate the same timestamps from an independently started Movie Maker.
    chunk={'scene_id':'render_0002','start_frame':360,'end_frame':390,'duration_seconds':1.}
    encode_scene(clips,timeline,plan,directory,encoder_capabilities()['encoder'],lambda p:None,lambda:None,chunk)
    partial=read(directory/'render/render_0002-poses.jsonl')
    indexed={(r['frame'],r['character']):r for r in full}
    maximum=0.
    for row in partial:
        expected=indexed[row['frame'],row['character']]
        for key in ('root_x','left_knee','right_knee','elbow','head','torso'):
            maximum=max(maximum,abs(row[key]-expected[key]))
        assert row['mouth']==expected['mouth']
    assert maximum<.0001,maximum
    result={'result':'passed','sampled_walk_contact_drift_px':drift,'sampled_walk_contact_height_drift_px':height,
            'independent_chunk_max_pose_difference':maximum,'listener_mouths_closed':True,'independent_knee_and_elbow_motion':True,
            'head_motion':'Front-art tilt and gaze only; no true profile turnaround is claimed',
            'video_sha256':digest(ROOT/'output/godot-benchmark.mp4'),'comparison_sha256':digest(ROOT/'output/godot-comparison.mp4'),
            'quality_limit':'Numerical motion checks and inspected stills do not establish professional television quality.'}
    atomic_json(directory/'motion-acceptance.json',result);print(json.dumps(result,indent=2))
