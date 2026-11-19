"""Validated 2.5D environment selection and explicit pixel/world conventions."""
import json
from copy import deepcopy
from pathlib import Path
from app.scene_cache import digest
ROOT=Path(__file__).resolve().parents[2]
REGISTRY=ROOT/'assets/environments/library.json'

def environment(background_id,include_prototype=False):
    if not REGISTRY.is_file():return None
    data=json.loads(REGISTRY.read_text(encoding='utf-8'))
    row=data.get('environments',{}).get(background_id)
    if not row or row.get('status') not in (('validated','prototype') if include_prototype else ('validated',)):return None
    path=(REGISTRY.parent/row['file']).resolve()
    if not path.is_relative_to(REGISTRY.parent.resolve()) or not path.is_file():raise ValueError('Hybrid environment file missing or outside asset library')
    spec=json.loads(path.read_text(encoding='utf-8'))
    if spec['background_id']!=background_id or spec['schema_version']!=1:raise ValueError('Hybrid background registration mismatch')
    if spec['pixels_per_meter']!=100 or not 0<=len(spec.get('trees',[]))<=12:raise ValueError('Unsupported hybrid scale or geometry budget')
    return {**spec,'environment_id':row['id'],'background_identity':row['background_identity'],'spec_sha256':digest(path)}

def select_environments(plan,prototype=False):
    backgrounds=plan.get('backgrounds',{plan['background']['background_id']:plan['background']})
    selected={bid:environment(bid,prototype) for bid in backgrounds}
    selected={bid:row if row and row['background_identity']==backgrounds[bid]['identity_hash'] else None for bid,row in selected.items()}
    # Keep one episode visually consistent. A partial conversion stays 2D.
    return selected if selected and all(selected.values()) else {}

def world_position(x_px,depth_m,width):
    return [(x_px-width/2)/100,0.,depth_m]

def resolve_mode(plan):
    if 'hybrid_environments' in plan:return plan['hybrid_environments']
    requested=plan.get('render_mode','auto')
    direction=plan.get('direction',[])
    benefit=any(s['kind']=='camera' or any(a['action'] in ('walk','run','step_back','move_closer','move_away') for a in s.get('actors',{}).values()) for s in direction)
    selected=select_environments(plan,plan.get('allow_hybrid_prototype',False)) if requested=='hybrid_2_5d' or requested=='auto' and benefit else {}
    if requested=='hybrid_2_5d' and not selected:raise ValueError('Hybrid mode requested without validated matching environments')
    plan['hybrid_environments']=selected;plan['effective_render_mode']='hybrid_2_5d' if selected else '2d'
    return selected

def spatial_direction(direction,width,environments):
    result=deepcopy(direction)
    for scene in result:
        spec=environments[scene['background_id']];placements={};visible=scene['visible_characters']
        for index,cid in enumerate(visible):
            actor=scene['actors'][cid];base=(index+.5)*width/len(visible);depth=spec['actor_depths'][index%len(spec['actor_depths'])]
            start=world_position(base+actor.get('from_x',0),depth,width);end=world_position(base+actor.get('to_x',0),depth,width)
            for point in (start,end):
                if any((point[0]-x)**2+(point[2]-z)**2<(radius+.6)**2 for x,z,radius in spec.get('blocked_zones',[])):raise ValueError('Hybrid character intersects registered scenery')
            placements[cid]={'position_from':start,'position_to':end,'scale':.8,'ground_y':0.}
        scene['spatial']={'render_mode':'hybrid_2_5d','environment_id':spec['environment_id'],'actors':placements,'camera':scene['camera']}
    return result
