"""Extract articulated cutout pieces from locked rigs, never redraw their faces.

Original files are untouched. Front-view derived pieces are explicitly prototypes;
reference-only designs still need an artist and are never registered by this tool.
"""
import json
import sys
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.assets import load_character
from app.scene_cache import digest,atomic_json


def build(cid):
    source=load_character(cid);directory=source['directory'];target=directory/'articulated/v1'
    target.mkdir(parents=True,exist_ok=True)
    if (target/'rig.json').exists():
        data=json.loads((target/'rig.json').read_text())
        if data['source_identity']!=source['identity_hash']:raise ValueError('Source redesign requires a new articulated rig version')
        if all(digest(target/name)==h for name,h in data['hashes'].items()):return
        raise ValueError('Restore changed articulated assets; refusing silent regeneration')
    parts={};bones={};feet=source['anchors']['feet'];scale=source['canvas'][0]/384
    def point(x,y):return [round(x*scale,3),round(y*scale,3)]
    def bone(name,position,parent=None):bones[name]={'position':position,'parent':parent}
    def piece(name,file,bone_name,clip=None):
        with Image.open(directory/file) as image:
            if clip:
                region=Image.new('RGBA',image.size);region.paste(image.crop(clip),(clip[0],clip[1]));image=region
            box=image.getbbox()
            if not box:raise ValueError(f'Empty derived art: {cid}/{name}')
            image.crop(box).save(target/f'{name}.png')
            parts[name]={'file':f'{name}.png','bone':bone_name,'origin':[box[0],box[1]],'size':[box[2]-box[0],box[3]-box[1]]}
    bone('Hips',point(192,423))
    bone('Torso',point(192,330),'Hips');bone('Neck',point(192,250),'Torso');bone('Head',source['anchors']['head'],'Neck')
    piece('torso','body.png','Torso')
    for name in ('hair_back','head','hair'):
        if (directory/f'{name}.png').exists():piece(name,f'{name}.png','Head')
    w,h=source['canvas']
    # Preserve the original brows and eye/glasses artwork as separate regions.
    piece('brows','eyes/open.png','Head',(0,0,w,round(144*scale)))
    piece('eyes_open','eyes/open.png','Head',(0,round(144*scale),w,h))
    piece('eyes_closed','eyes/closed.png','Head',(0,round(144*scale),w,h))
    for mouth in 'ABCDEFGHX':piece(f'mouth_{mouth}',f'mouths/{mouth}.png','Head')
    for side,label,x,dx in [('left','Left',122,-17),('right','Right',262,17)]:
        shoulder=source['anchors'][side+'_arm'];elbow=point(x+dx,369);hand=point(x+dx*1.3,433)
        bone(label+'UpperArm',shoulder,'Torso');bone(label+'Forearm',elbow,label+'UpperArm');bone(label+'Hand',hand,label+'Forearm')
        piece(side+'_upper_arm',f'arms/{side}.png',label+'UpperArm',(0,0,w,round(380*scale)))
        piece(side+'_forearm',f'arms/{side}.png',label+'Forearm',(0,round(355*scale),w,round(438*scale)))
        piece(side+'_hand',f'arms/{side}.png',label+'Hand',(0,round(423*scale),w,h))
        hip=source['anchors'][side+'_leg'];knee=[hip[0],round(510*scale)];ankle=[hip[0],round(578*scale)]
        bone(label+'Thigh',hip,'Hips');bone(label+'Leg',knee,label+'Thigh');bone(label+'Foot',ankle,label+'Leg')
        piece(side+'_thigh',f'legs/{side}.png',label+'Thigh',(0,0,w,round(522*scale)))
        piece(side+'_leg',f'legs/{side}.png',label+'Leg',(0,round(498*scale),w,round(588*scale)))
        piece(side+'_foot',f'legs/{side}.png',label+'Foot',(0,round(575*scale),w,h))
    atomic_json(target/'rig.json',{'character_id':cid,'version':'1.0.0','source_identity':source['identity_hash'],'canvas':source['canvas'],
                'feet':feet,'bones':bones,'parts':parts,'quality_status':'front_cutout_prototype',
                'limitations':['True profile/back turnaround art is not available as separated rig layers.','Hand silhouettes are the supplied neutral hands; pointing uses arm direction.'],
                'hashes':{p.name:digest(p) for p in target.glob('*.png')}})
    print(cid,'derived',len(parts),'art layers and',len(bones),'bones; original art unchanged')


if __name__=='__main__':
    for folder in (ROOT/'assets/characters').iterdir():
        if (folder/'character.json').exists():
            try:load_character(folder.name)
            except ValueError:continue
            build(folder.name)
