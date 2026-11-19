"""Separate original child-eye pixels for gaze; source sprite files stay locked."""
import json
import sys
from pathlib import Path
from PIL import Image,ImageDraw,ImageChops
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.scene_cache import digest,atomic_json

for cid in ('nabil','rayan','fahim','anika','maliha'):
    source=ROOT/'assets/characters'/cid;folder=source/'articulated/v1'
    data=json.loads((folder/'rig.json').read_text(encoding='utf-8'))
    if 'pupils' in data['parts']:continue
    original=Image.open(source/'eyes/open.png').convert('RGBA')
    mask=Image.new('L',original.size);draw=ImageDraw.Draw(mask)
    for x in (165,220):draw.ellipse((x-8,147,x+8,170),fill=255)
    mask=ImageChops.multiply(mask,original.getchannel('A'))
    pupils=original.copy();pupils.putalpha(mask)
    base=original.copy();base.paste(Image.new('RGBA',original.size,'#FFFCF2'),(0,0),mask)
    # Brow pixels already belong to their independent original-art layer.
    base.alpha_composite(Image.new('RGBA',(1,1)))
    region=Image.new('RGBA',base.size);region.paste(base.crop((0,144,384,640)),(0,144));base=region
    for key,image in [('eyes_open',base),('pupils',pupils)]:
        box=image.getbbox();image.crop(box).save(folder/f'{key}.png')
        data['parts'][key]={'file':f'{key}.png','bone':'Head','origin':[box[0],box[1]],'size':[box[2]-box[0],box[3]-box[1]]}
    data['version']='1.1.0';data['hashes']={p.name:digest(p) for p in folder.glob('*.png')}
    atomic_json(folder/'rig.json',data);print(cid,'gaze layers separated from source pixels')
