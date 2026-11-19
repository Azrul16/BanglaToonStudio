"""Create original antialiased child rigs from the supplied flattened designs.

Never invoked by video generation. Existing locked rigs are validated and kept.
The original sheets and their metadata are preserved byte-for-byte.
"""
import hashlib
import argparse
import json
import math
import re
import sys
from pathlib import Path
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.assets import ACTIONS,load_character,load_background
from scripts.build_assets import write_json

CHILDREN={
 'nabil':{'name_bn':'নাবিল','name_en':'Nabil','skin':'#FDB874','hair':'#684E3D','shirt':'#2E7D73','pants':'#0D3866','shoes':'#F57C00','style':'checked_shirt','height':1.00},
 'rayan':{'name_bn':'রায়ান','name_en':'Rayan','skin':'#F7C77E','hair':'#242629','shirt':'#E0A600','pants':'#374151','shoes':'#34383D','style':'hoodie','height':1.04},
 'fahim':{'name_bn':'ফাহিম','name_en':'Fahim','skin':'#E8B18A','hair':'#282725','shirt':'#881E3F','pants':'#F5E8D3','shoes':'#2F2F2F','style':'panjabi','height':.94},
 'anika':{'name_bn':'অনিকা','name_en':'Anika','skin':'#F5C8A9','hair':'#302724','shirt':'#14B8A6','pants':'#F4F3ED','shoes':'#DC2626','style':'tunic','height':.99},
 'maliha':{'name_bn':'মালিহা','name_en':'Maliha','skin':'#F8C7A1','hair':'#352821','shirt':'#FF6F61','pants':'#F8C7A1','shoes':'#36B3DC','style':'frock','height':.91},
}
S=3
INK='#26313A'


class Pen:
    def __init__(self,image): self.d=ImageDraw.Draw(image)
    def box(self,box): return tuple(round(x*S) for x in box)
    def ellipse(self,box,fill,outline=None,width=1): self.d.ellipse(self.box(box),fill=fill,outline=outline,width=round(width*S))
    def rect(self,box,fill,outline=None,width=1): self.d.rectangle(self.box(box),fill=fill,outline=outline,width=round(width*S))
    def round(self,box,radius,fill,outline=None,width=1): self.d.rounded_rectangle(self.box(box),radius=round(radius*S),fill=fill,outline=outline,width=round(width*S))
    def line(self,points,fill,width=1): self.d.line([(round(x*S),round(y*S)) for x,y in points],fill=fill,width=round(width*S),joint='curve')
    def polygon(self,points,fill,outline=None,width=1):
        points=[(round(x*S),round(y*S)) for x,y in points]
        self.d.polygon(points,fill=fill)
        if outline: self.d.line(points+[points[0]],fill=outline,width=round(width*S),joint='curve')
    def arc(self,box,start,end,fill,width=1): self.d.arc(self.box(box),start,end,fill=fill,width=round(width*S))


def flower(p,x,y,color='#FFF5E4',size=5):
    for a in range(5):
        dx=math.cos(a*math.tau/5)*size; dy=math.sin(a*math.tau/5)*size
        p.ellipse((x+dx-size*.65,y+dy-size*.65,x+dx+size*.65,y+dy+size*.65),color)
    p.ellipse((x-2,y-2,x+2,y+2),'#F6D29A')


def build(cid,c,replace=False,version='1.0.0'):
    directory=ROOT/'assets/characters'/cid
    original_path=directory/'character.json'
    original=json.loads(original_path.read_text(encoding='utf-8'))
    if original.get('animation_ready') and not replace:
        load_character(cid)
        print(cid,'already valid; artwork unchanged')
        return
    sheet=directory/'character_sheet.png'
    if not sheet.is_file(): raise RuntimeError(f'Missing supplied design sheet: {cid}')
    reference_copy=directory/'design_reference.json'
    if not reference_copy.exists(): reference_copy.write_bytes(original_path.read_bytes())
    files=[]

    def layer(name,draw):
        image=Image.new('RGBA',(384*S,640*S))
        draw(Pen(image))
        path=directory/name; path.parent.mkdir(parents=True,exist_ok=True)
        image.resize((384,640),Image.Resampling.LANCZOS).save(path)
        files.append(name)

    skin,hair,shirt=c['skin'],c['hair'],c['shirt']
    style=c['style']
    for side,x in [('left',155),('right',228)]:
        def leg(p,x=x):
            top=411 if style in ('panjabi','tunic','frock') else 421
            p.round((x-23,top,x+23,586),16,c['pants'],INK,3)
            if style=='checked_shirt':
                p.round((x-29,top,x+29,510),7,c['pants'],INK,3)
                p.rect((x-18,519,x+18,565),skin)
                p.line([(x-16,568),(x+16,568)],'#FAF3E5',12)
            if style in ('panjabi','frock'):
                p.round((x-27,579,x+32,611),10,c['shoes'],INK,3)
                p.line([(x-14,585),(x+17,599)],'#E3AC6E' if style=='panjabi' else '#257697',7)
                if style=='frock': p.line([(x-20,587),(x+24,587)],c['shoes'],8)
            else:
                p.round((x-29,576,x+34,611),11,c['shoes'],INK,3)
                p.line([(x-24,604),(x+29,604)],'#F5F0E3',6)
                for y in (584,591): p.line([(x-10,y),(x+12,y)],'#FFF6DE',2)
        layer(f'legs/{side}.png',leg)
    for side,x,dx in [('left',122,-17),('right',262,17)]:
        def arm(p,x=x,dx=dx):
            p.line([(x,278),(x+dx,369),(x+dx*1.3,439)],INK,34)
            p.line([(x,278),(x+dx,366),(x+dx*1.3,434)],skin,27)
            end=334 if style in ('checked_shirt','frock') else 421 if style=='hoodie' else 374
            p.line([(x,278),(x+dx*(end-278)/91,end)],INK,45)
            p.line([(x,278),(x+dx*(end-278)/91,end-2)],shirt,37)
            if style=='checked_shirt':
                for y in (291,312): p.line([(x-16,y),(x+15,y)],'#205F61',4)
                p.line([(x-5,282),(x+dx*.6-5,end)],'#74B7A7',3)
            if style=='tunic':
                p.line([(x+dx-17,369),(x+dx+17,369)],'#ECF7DF',5)
            p.ellipse((x+dx*1.3-14,424,x+dx*1.3+14,456),skin,INK,2)
            p.line([(x+dx*1.3-6,442),(x+dx*1.3+4,446)],'#B77B59',1)
        layer(f'arms/{side}.png',arm)

    def body(p):
        if style in ('panjabi','tunic'):
            p.polygon([(132,252),(252,252),(270,480),(114,480)],shirt,INK,3)
            p.line([(192,260),(192,320)],'#A4EBDB' if style=='tunic' else '#5E182C',3)
        elif style=='frock':
            p.polygon([(140,253),(244,253),(255,375),(280,506),(104,506),(129,375)],shirt,INK,3)
            p.line([(126,374),(258,374)],'#C3474A',4)
        else:
            p.round((121,251,263,435),29,shirt,INK,3)
        if style=='checked_shirt':
            for x in range(132,261,22): p.line([(x,268),(x,427)],'#246367',7)
            for y in range(280,426,25): p.line([(127,y),(258,y)],'#23716A',6)
            for x in range(141,260,22): p.line([(x,268),(x,427)],'#55A595',2)
            p.polygon([(172,253),(212,253),(214,431),(170,431)],'#F0EBDD',INK,2)
            p.polygon([(170,251),(152,269),(175,291),(183,260)],shirt,INK,2)
            p.polygon([(214,251),(232,269),(209,291),(201,260)],shirt,INK,2)
            p.round((224,307,251,340),3,shirt,INK,2)
        elif style=='hoodie':
            p.ellipse((140,238,244,298),'#EABD38',INK,3)
            p.polygon([(161,252),(192,281),(224,252),(212,292),(172,292)],'#B17B06',INK,2)
            p.round((151,363,237,409),12,'#D3980B','#A97C14',2)
            for x in (172,214):
                p.line([(x,287),(x,344)],'#FFF0A9',3); p.ellipse((x-3,339,x+3,346),'#D7C28A',INK,1)
            p.line([(237,279),(139,427)],'#343B40',17)
            p.round((116,402,158,449),6,'#71573B',INK,2)
        elif style=='panjabi':
            p.polygon([(168,252),(192,272),(216,252),(208,288),(176,288)],'#A12C47',INK,2)
            for y in (285,303,321): p.ellipse((189,y,194,y+5),'#D6B182',INK,1)
            p.polygon([(222,254),(245,257),(251,415),(220,415)],'#F4D1AF',INK,2)
            for y in range(268,413,15): p.line([(222,y),(246,y)],'#C44745',5)
            for x in (228,239): p.line([(x,263),(x,411)],'#D76E5D',4)
        elif style=='tunic':
            for x in (161,173,210,223):
                p.line([(x,280),(x,335)],'#DDF4DD',2)
                for y in (291,310,330): flower(p,x,y,'#E8F4E5',3)
            for x in range(125,263,15): flower(p,x,464,'#DDF4DD',4)
            p.line([(149,262),(130,420)],'#9B5F2D',11)
        elif style=='frock':
            for row,y in enumerate(range(292,493,36)):
                for x in range(133+row%2*12,253,34): flower(p,x,y,size=6)
            p.line([(235,264),(146,434)],'#8E5F2B',12)
            p.round((121,405,169,454),9,'#BF963B',INK,2)
            p.line([(144,441),(144,416)],'#4E9843',3)
            p.ellipse((131,418,145,428),'#6DAC45'); p.ellipse((144,411,158,423),'#6DAC45')
    layer('body.png',body)

    def back_hair(p):
        if style=='tunic':
            p.round((112,83,272,245),50,hair,INK,3)
            for x in (119,131,251,263): p.arc((x-9,154,x+14,242),55,130,'#59453A',2)
        elif style=='frock':
            p.round((118,75,269,227),55,hair,INK,3)
            for side,x in [('left',125),('right',261)]:
                for i in range(6):
                    xx=x+(-1 if side=='left' else 1)*i*.8
                    p.ellipse((xx-15,201+i*13,xx+15,230+i*13),hair,INK,2)
                    p.arc((xx-10,202+i*13,xx+12,226+i*13),30,160,'#5C4734',2)
                p.round((x-17,267,x+18,278),3,'#F4C542',INK,1)
        else:
            p.ellipse((120,75,269,205),hair,INK,3)
    layer('hair_back.png',back_hair)

    def head(p):
        p.round((173,216,211,268),12,skin,INK,3)
        p.ellipse((113,148,144,188),skin,INK,2)
        p.ellipse((240,148,271,188),skin,INK,2)
        p.round((129,89,255,234),52,skin,INK,3)
        p.arc((119,154,137,177),220,60,'#BF845C',2)
        p.arc((185,153,200,183),275,80,'#C18D68',2)
        p.line([(190,180),(200,180)],'#C18D68',2)
        p.ellipse((145,185,162,194),'#F4AC8C'); p.ellipse((225,185,240,194),'#F4AC8C')
    layer('head.png',head)

    def front_hair(p):
        if style=='checked_shirt':
            p.polygon([(121,160),(111,131),(128,111),(111,107),(135,82),(130,63),(162,73),(185,45),(193,66),(224,47),(222,67),(261,70),(250,92),(275,109),(254,128),(253,151),(237,114),(216,102),(200,128),(183,106),(163,137),(147,129),(138,163)],hair,INK,3)
            p.line([(137,104),(164,84),(189,77),(216,83)],'#987452',4)
        elif style=='hoodie':
            p.ellipse((117,59,270,141),hair,INK,3)
            # Large connected fringe leaves the eyes and glasses unobstructed.
            p.polygon([(123,117),(130,154),(148,140),(157,107),(174,139),(188,129),(195,104),(211,138),(226,128),(234,110),(250,154),(262,133),(255,88),(147,80)],hair)
            p.arc((132,73,243,129),195,285,'#4C4A42',3)
        elif style=='panjabi':
            p.ellipse((122,62,265,133),hair,INK,3)
            for x,y,r in [(127,113,18),(128,86,21),(149,68,20),(177,62,21),(204,67,23),(233,73,22),(253,96,19),(250,123,15),(145,120,17),(177,109,20),(207,111,17),(233,126,16)]:
                p.ellipse((x-r,y-r,x+r,y+r),hair,INK,2)
                p.arc((x-r+6,y-r+5,x+r-4,y+r-5),185,280,'#4E4C43',2)
        else:
            p.polygon([(119,164),(123,110),(142,80),(186,64),(225,74),(252,100),(260,151),(247,137),(231,100),(207,109),(178,131),(151,139),(136,166)],hair,INK,3)
            p.line([(139,117),(161,95),(188,87),(209,87)],'#75513A',4)
            if style=='tunic':
                p.round((128,116,159,131),5,'#A16AF1',INK,2)
                p.line([(137,121),(151,126)],'#DBB6FD',3)
            else:
                for box,color in [((125,113,143,131),'#F4C542'),((142,110,159,129),'#FFAB24'),((127,131,143,145),'#FFD45A'),((143,129,160,144),'#F4C542')]:
                    p.ellipse(box,color,INK,1)
                p.line([(142,121),(143,139)],INK,3)
                p.line([(141,120),(137,114)],INK,1); p.line([(143,120),(148,113)],INK,1)
    layer('hair.png',front_hair)

    def eyes(p,closed=False):
        for x in (165,220):
            p.arc((x-16,130,x+15,143),195,340,INK,3)
            if closed: p.arc((x-13,148,x+13,164),0,180,INK,3)
            else:
                p.ellipse((x-13,146,x+13,171),'#FFFCF2',INK,2)
                p.ellipse((x-7,147,x+7,170),'#324249' if cid=='rayan' else '#3D2B22')
                p.ellipse((x-3,148,x+3,155),'#FFFFFF')
                if style in ('tunic','frock'): p.line([(x-14,150),(x-18,145)],INK,2)
        if cid=='rayan':
            for x in (165,220): p.ellipse((x-24,136,x+24,181),None,'#2563EB',3)
            p.arc((187,147,199,165),190,340,'#2563EB',3)
            p.line([(137,155),(124,147)],'#2563EB',3); p.line([(247,155),(259,148)],'#2563EB',3)
    layer('eyes/open.png',eyes)
    layer('eyes/closed.png',lambda p:eyes(p,True))
    for mouth in 'ABCDEFGHX':
        def draw_mouth(p,mouth=mouth):
            x,y=192,205
            if mouth=='X': p.arc((x-13,y-8,x+13,y+3),5,175,'#78483C',2)
            elif mouth=='A': p.line([(x-13,y),(x+13,y)],'#78483C',3)
            else:
                w,h={'B':(18,6),'C':(19,13),'D':(20,21),'E':(11,17),'F':(9,11),'G':(18,8),'H':(15,13)}[mouth]
                p.ellipse((x-w,y-h/2,x+w,y+h),'#592C32',INK,2)
                if mouth in 'BCDGH': p.line([(x-w+5,y-h/2+3),(x+w-5,y-h/2+3)],'#FFF4DE',4)
                if mouth=='D': p.ellipse((x-10,y+9,x+11,y+17),'#D07D78')
        layer(f'mouths/{mouth}.png',draw_mouth)

    for action in ACTIONS:
        frames=[{'t':0,'x':0,'y':0,'head_angle':0},{'t':.5,'x':0,'y':-3,'head_angle':1.5},{'t':1,'x':0,'y':0,'head_angle':0}]
        if action=='walk': frames=[{'t':0,'x':-20,'y':0,'head_angle':0},{'t':.5,'x':0,'y':-4,'head_angle':0},{'t':1,'x':20,'y':0,'head_angle':0}]
        if action in ('look_left','look_right','turn_head'):
            angle=-6 if action=='look_left' else 6
            frames=[{'t':0,'x':0,'y':0,'head_angle':0},{'t':.45,'x':0,'y':0,'head_angle':angle},{'t':1,'x':0,'y':0,'head_angle':angle}]
        if action=='surprised': frames=[{'t':0,'x':0,'y':0,'head_angle':0},{'t':.3,'x':0,'y':-6,'head_angle':-5},{'t':1,'x':0,'y':0,'head_angle':0}]
        filename=f'animations/{action}.json'
        write_json(directory/filename,{'action':action,'version':version,'duration':1.6 if action=='walk' else 2.,'loop':action in ('idle','talk','walk','afraid'),'keyframes':frames})
        files.append(filename)
    source_metadata=json.loads(reference_copy.read_text(encoding='utf-8'))
    meta={**original,**{k:c[k] for k in ('name_bn','name_en')},'character_id':cid,'legacy_character_id':source_metadata['character_id'],
          'version':version,'asset_version':version,'rig_version':version,'animation_ready':True,'rig_status':'ready',
          'asset_type':'layered_png_rig','voice_id':'default_bn','age_group':'child','canvas':[384,640],'default_animation':'idle','render_scale':c['height'],
          'anchors':{'head':[192,234],'eyes':[192,158],'mouth':[192,205],'feet':[192,612],
                     'left_arm':[122,278],'right_arm':[262,278],'left_leg':[155,423],'right_leg':[228,423]},
          'palette_reference':{k:c[k] for k in ('skin','hair','shirt','pants','shoes')},
          'reference_sha256':hashlib.sha256(sheet.read_bytes()).hexdigest(),
          'reference_file':'character_sheet.png','source_generator':'scripts/build_child_rigs.py',
          'note':'Original simplified layered recreation of the supplied design. Flattened source artwork and original metadata are preserved. Never generated at runtime.',
          'file_hashes':{name:hashlib.sha256((directory/name).read_bytes()).hexdigest() for name in files}}
    write_json(original_path,meta)
    try: load_character(cid)
    except Exception:
        original_path.write_bytes(reference_copy.read_bytes())
        raise
    print('Validated',cid,len(files),'permanent files')


def lock_supplied_station():
    """Adapt the user's replacement painting without altering its pixels."""
    directory=ROOT/'assets/backgrounds/railway_station_night'
    path=directory/'metadata.json'; meta=json.loads(path.read_text(encoding='utf-8'))
    if meta.get('file_hashes'): load_background('railway_station_night'); return
    original=directory/'design_reference.json'
    if not original.exists(): original.write_bytes(path.read_bytes())
    with Image.open(directory/'background.png') as im: size=list(im.size)
    meta.update(background_id='railway_station_night',version='1.0.0',canvas=size,layer_mode='flat',
                file_hashes={'background.png':hashlib.sha256((directory/'background.png').read_bytes()).hexdigest()})
    write_json(path,meta)
    load_background('railway_station_night')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--replace',action='store_true')
    parser.add_argument('--version',default='1.0.0')
    args=parser.parse_args()
    if not re.fullmatch(r'\d+\.\d+\.\d+',args.version): parser.error('Use a semantic version such as 1.1.0')
    if args.replace:
        for cid in CHILDREN:
            meta=json.loads((ROOT/'assets/characters'/cid/'character.json').read_text(encoding='utf-8'))
            if meta.get('animation_ready') and meta['version']==args.version: parser.error('Replacement requires a new version')
    for cid,design in CHILDREN.items(): build(cid,design,args.replace,args.version)
    lock_supplied_station()
    # Publication follows validation of every full rig, never before it.
    reg_path=ROOT/'assets/registry.json'; reg=json.loads(reg_path.read_text(encoding='utf-8'))
    manifest_path=ROOT/'assets/characters/manifest.json'; manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    for cid,design in CHILDREN.items():
        reg['speakers'][cid]={'name_bn':design['name_bn'],'aliases':[design['name_bn'],design['name_en'],f'child_{cid}',*(['রায়ান'] if cid=='rayan' else [])],
                              'off_screen':False,'voice_id':'default_bn','requires_complete_rig':True}
        entry={'character_id':cid,'name_bn':design['name_bn'],'name_en':design['name_en'],'path':f'assets/characters/{cid}/character.json','animation_ready':True}
        manifest['characters']=[c for c in manifest['characters'] if c['character_id'] not in (cid,f'child_{cid}')]+[entry]
    manifest['count']=len(manifest['characters'])
    manifest['animation_ready']=list(dict.fromkeys([*manifest.get('animation_ready',[]),*CHILDREN]))
    write_json(reg_path,reg); write_json(manifest_path,manifest)
    print('Registered all five children after validation')
