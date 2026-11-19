"""Verify actual native exports and preserved media; save review frames."""
import json,sys,subprocess
from pathlib import Path
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.hardware import validate_video,ffmpeg_binary
from app.scene_cache import digest,atomic_json

def main():
    results={};sheet=Image.new('RGB',(6*270,2*480))
    for row,mode in enumerate(('flat','hybrid')):
        path=ROOT/'output'/f'{mode}-portrait-1080p-evaluation.mp4'
        results[mode]=validate_video(path,21.3333333333)
        for col,second in enumerate((0.5,4,8,12,16,20)):
            frame=ROOT/'workspace'/f'portrait-{mode}-{col}.png'
            subprocess.run([ffmpeg_binary(),'-v','error','-y','-ss',str(second),'-i',str(path),'-frames:v','1',str(frame)],check=True)
            image=Image.open(frame);assert image.size==(1080,1920)
            sheet.paste(image.resize((270,480)),(col*270,row*480))
    sheet.save(ROOT/'workspace/portrait-review.jpg')
    folder=ROOT/'workspace/hybrid-portrait-1080p/render'
    alpha=json.loads((folder/'viewport-alpha.json').read_text(encoding='utf-8'))
    for entry in alpha.values():
        x,y,w,h=entry['bounds'];assert entry['corner_alpha']==0 and x>0 and y>0 and x+w<512 and y+h<768
    poses=[json.loads(line) for p in folder.glob('render_*-poses.jsonl') for line in p.read_text(encoding='utf-8').splitlines()]
    minimum=min(min(p['sole_heights']) for p in poses)
    assert minimum>-.00001
    cameras=[json.loads(line) for p in folder.glob('render_*-camera.jsonl') for line in p.read_text(encoding='utf-8').splitlines()]
    clipped=[]
    for camera in cameras:
        for cid,rect in camera['subject_head_rects'].items():
            x,y,right,bottom=rect
            if x<0 or y<0 or right>1080 or bottom>1920:clipped.append((camera['frame'],cid,rect))
    assert not clipped,clipped[:5]
    baseline=json.loads((ROOT/'workspace/hybrid-baseline.json').read_text(encoding='utf-8'))
    preserved={}
    for group,entries in baseline.items():
        if isinstance(entries,dict):
            for name,expected in entries.items():
                path=ROOT/name
                if isinstance(expected,str) and len(expected)==64:
                    assert path.is_file() and digest(path)==expected,name
                    preserved[group]=preserved.get(group,0)+1
    lip_sync={}
    for mode in ('flat','hybrid'):
        directory=ROOT/'workspace'/f'{mode}-portrait-1080p'
        timeline=json.loads((directory/'timeline.json').read_text(encoding='utf-8'))
        speech=[s for s in timeline['scenes'] if s['kind']=='speech']
        traces=[json.loads(line) for p in (directory/'render').glob('render_*-poses.jsonl') for line in p.read_text(encoding='utf-8').splitlines()]
        shapes={cid:set() for cid in ('nabil','rayan','anika')};checked=0
        for pose in traces:
            t=pose['frame']/30
            scene=next((s for s in speech if s['start']<=t<s['end']),None)
            if not scene or pose['character']!=scene['speaker']:
                assert pose['mouth']=='X';continue
            cues=json.loads((directory/'cues'/(scene['clip_id']+'.json')).read_text(encoding='utf-8'))['mouthCues']
            relative=t-scene['start']
            if any(abs(relative-c[key])<.00001 for c in cues for key in ('start','end')):continue
            expected=next((c['value'] for c in cues if c['start']<=relative<c['end']),'X')
            assert pose['mouth']==expected,(mode,pose,expected)
            shapes[pose['character']].add(pose['mouth']);checked+=1
        assert all(len(values)>1 for values in shapes.values())
        lip_sync[mode]={'matched_cue_samples':checked,'shapes_by_character':{cid:sorted(values) for cid,values in shapes.items()},'listeners_closed':True}
    results.update(preserved=preserved,hybrid_pose_samples=len(poses),camera_samples=len(cameras),clipped_heads=clipped,minimum_sole_height=minimum,viewport_alpha=alpha,lip_sync=lip_sync)
    atomic_json(ROOT/'workspace/portrait-verification.json',results)
    print(json.dumps(results,indent=2))
if __name__=='__main__':main()
