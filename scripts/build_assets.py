"""Reproducible original sprite art. Run once; --replace explicitly redesigns rigs.

Reference sheets remain untouched. Rendering NEVER invokes this script.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
CANVAS = (384, 640)
ACTIONS = ('idle', 'walk', 'talk', 'surprised', 'afraid', 'blink', 'look_left', 'look_right', 'turn_head')


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def hashes(directory):
    return {p.relative_to(directory).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(directory.rglob('*')) if p.suffix in ('.png', '.json') and p.name not in
            ('character.json', 'metadata.json', 'design_reference.json') and 'reference' not in p.name and 'sheet' not in p.name}


def build_rahat(replace=False,version='1.0.0'):
    directory = ROOT/'assets/characters/rahat'
    metadata = json.loads((directory/'character.json').read_text(encoding='utf-8'))
    if metadata.get('animation_ready') and not replace:
        print('Rahat already locked; skipped. Use --replace only for an intentional redesign.')
        return
    outline, skin, hair, shirt = '#172333', '#E0AC84', '#1A1A1A', '#2F6FB2'

    def layer(name, draw):
        im = Image.new('RGBA', CANVAS)
        draw(ImageDraw.Draw(im))
        path = directory/name
        path.parent.mkdir(parents=True, exist_ok=True)
        im.save(path)

    def body(d):
        d.rounded_rectangle((115,238,269,440), radius=36, fill=shirt, outline=outline, width=5)
        d.polygon([(168,239),(192,280),(216,239),(217,427),(168,427)],fill='#eef0ec')
        d.polygon([(168,239),(150,269),(174,287),(182,257)],fill='#245386',outline=outline)
        d.polygon([(216,239),(234,269),(210,287),(202,257)],fill='#245386',outline=outline)
        d.rounded_rectangle((220,295,251,326),radius=3,fill='#32679d',outline=outline,width=2)
        d.rectangle((125,418,259,443),fill='#202a34')
        d.rectangle((179,420,205,436),fill='#9d9d8f',outline=outline,width=3)
    layer('body.png',body)
    for side,x in [('left',148),('right',233)]:
        def leg(d,x=x):
            d.line((x,435,x,589),fill=outline,width=57)
            d.line((x,443,x,580),fill='#2B2B2B',width=45)
            d.rounded_rectangle((x-29,577,x+35,612),radius=12,fill='#19202b',outline='#0e1622',width=3)
            d.line((x-20,603,x+27,603),fill='#c5c9c6',width=4)
        layer(f'legs/{side}.png',leg)
    for side,x in [('left',116),('right',268)]:
        dx=-17 if side=='left' else 17
        def arm(d,x=x,dx=dx):
            d.line((x,271,x+dx,358),fill=outline,width=43)
            d.line((x,271,x+dx,351),fill=shirt,width=34)
            d.line((x+dx,354,x+dx*1.5,421),fill=outline,width=31)
            d.line((x+dx,354,x+dx*1.5,421),fill=skin,width=24)
            d.ellipse((x+dx*1.5-15,407,x+dx*1.5+15,440),fill=skin,outline=outline,width=3)
        layer(f'arms/{side}.png',arm)
    def head(d):
        d.rounded_rectangle((172,205,212,253),radius=10,fill=skin,outline=outline,width=3)
        d.ellipse((115,137,148,187),fill=skin,outline=outline,width=3)
        d.ellipse((238,137,271,187),fill=skin,outline=outline,width=3)
        d.rounded_rectangle((130,81,255,226),radius=54,fill=skin,outline=outline,width=4)
        d.arc((178,138,199,177),275,85,fill='#9e7157',width=3)
        d.line((188,174,200,175),fill='#9e7157',width=2)
    layer('head.png',head)
    def haircut(d):
        d.pieslice((120,52,261,172),175,360,fill=hair,outline=outline,width=3)
        d.polygon([(121,133),(117,97),(140,72),(152,52),(195,60),(215,45),(248,70),(267,111),(250,146),(240,100),(215,92),(202,119),(181,98),(160,117),(142,127),(133,158)],fill=hair,outline=outline)
        d.arc((138,68,229,120),190,290,fill='#3c4145',width=4)
        d.arc((162,58,247,121),210,300,fill='#34393e',width=3)
    layer('hair.png',haircut)
    def eyes(d,closed=False):
        for x in (164,221):
            d.arc((x-17,121,x+15,137),195,335,fill=outline,width=5)
            if closed:
                d.arc((x-13,138,x+13,150),0,180,fill=outline,width=4)
            else:
                d.ellipse((x-13,139,x+13,157),fill='#fff9eb',outline=outline,width=2)
                d.ellipse((x-5,140,x+5,156),fill='#342d28')
                d.ellipse((x-2,141,x+1,144),fill='white')
    layer('eyes/open.png',eyes)
    layer('eyes/closed.png',lambda d:eyes(d,True))
    for shape in 'ABCDEFGHX':
        def mouth(d,shape=shape):
            x,y=192,197
            if shape=='X':
                d.arc((x-16,y-9,x+16,y+4),5,175,fill='#603b37',width=3)
            elif shape=='A':
                d.line((x-15,y,x+15,y),fill='#603b37',width=4)
            else:
                w,h={'B':(17,7),'C':(19,14),'D':(20,23),'E':(13,19),'F':(10,12),'G':(19,8),'H':(15,13)}[shape]
                d.ellipse((x-w,y-h//2,x+w,y+h),fill='#60313b',outline='#472b31',width=2)
                if shape in 'BCDGH':
                    d.line((x-w+5,y-h//2+4,x+w-5,y-h//2+4),fill='#fff4df',width=5)
                if shape=='D':
                    d.ellipse((x-10,y+9,x+10,y+19),fill='#b96971')
        layer(f'mouths/{shape}.png',mouth)
    for action in ACTIONS:
        frames=[{'t':0,'x':0,'y':0,'head_angle':0},{'t':.5,'x':0,'y':-3,'head_angle':1.5},{'t':1,'x':0,'y':0,'head_angle':0}]
        if action=='walk':
            frames=[{'t':0,'x':-24,'y':0,'head_angle':0},{'t':.5,'x':0,'y':-5,'head_angle':0},{'t':1,'x':24,'y':0,'head_angle':0}]
        if action in ('look_left','look_right','turn_head'):
            angle=-7 if action=='look_left' else 7
            frames=[{'t':0,'x':0,'y':0,'head_angle':0},{'t':.45,'x':0,'y':0,'head_angle':angle},{'t':1,'x':0,'y':0,'head_angle':angle}]
        write_json(directory/f'animations/{action}.json',{'action':action,'version':version,'duration':1.6 if action=='walk' else 2.,'loop':action in ('idle','talk','walk','afraid'),'keyframes':frames})
    metadata.update(version=version,asset_version=version,rig_version=version,animation_ready=True,rig_status='ready',
                    voice_id='default_bn',canvas=list(CANVAS),default_animation='idle',
                    anchors={'head':[192,224],'eyes':[192,148],'mouth':[192,197],'feet':[192,612],
                             'left_arm':[116,271],'right_arm':[268,271],'left_leg':[148,435],'right_leg':[233,435]},
                    notes='Original simplified vector-style rig derived from the saved palette; flattened design references are preserved.',
                    file_hashes=hashes(directory))
    write_json(directory/'character.json',metadata)
    print('Saved and locked Rahat rig',len(metadata['file_hashes']),'files')


def build_background(replace=False,version='1.0.0'):
    directory=ROOT/'assets/backgrounds/railway_station_night'
    if (directory/'metadata.json').exists() and not replace:
        print('Background already locked; skipped.')
        return
    directory.mkdir(parents=True,exist_ok=True)
    im=Image.new('RGB',(900,1500))
    d=ImageDraw.Draw(im)
    for y in range(1500):
        d.line((0,y,900,y),fill=(12+int(y*.012),22+int(y*.016),44+int(y*.012)))
    d.ellipse((675,95,776,196),fill='#e6e3bd')
    for i in range(95):
        x,y=(i*151+17)%900,(i*79+23)%600
        d.ellipse((x,y,x+2,y+2),fill='#8bafc9')
    for x in range(-50,1000,95):
        d.polygon([(x,890),(x+56,455),(x+112,890)],fill='#152f37')
    d.rectangle((0,875,900,1500),fill='#303b43')
    d.rectangle((20,600,570,970),fill='#52616a',outline='#748286',width=5)
    d.polygon([(0,625),(110,520),(500,520),(640,625)],fill='#243b46',outline='#829293')
    d.rectangle((80,720,190,870),fill='#d4ad72',outline='#263845',width=9)
    d.line((135,720,135,870),fill='#263845',width=6)
    d.rectangle((350,720,470,870),fill='#bb9867',outline='#263845',width=9)
    d.rectangle((230,750,310,970),fill='#152b37',outline='#34434c',width=6)
    d.rounded_rectangle((135,555,455,620),radius=5,fill='#14362f',outline='#b1a77e',width=3)
    # Bengali lettering is shaped with the same portable font renderer as captions.
    import sys
    sys.path.insert(0,str(ROOT))
    from app.engines.text_layout import draw_text
    from PIL import ImageFont
    draw_text(im,(295,570),'শেষ স্টেশন',ImageFont.truetype(str(ROOT/'assets/fonts/NotoSansBengali.ttf'),31),'#e7dcb9',anchor='mm')
    d.line((810,480,810,1050),fill='#889691',width=12)
    d.line((750,480,850,480),fill='#889691',width=9)
    d.ellipse((740,475,790,500),fill='#efd298')
    im.save(directory/'background.png')
    front=Image.new('RGBA',im.size)
    f=ImageDraw.Draw(front)
    f.rectangle((0,1090,900,1140),fill='#9c9078')
    f.line((0,1093,900,1093),fill='#d4c29f',width=5)
    for y in (1220,1355):
        f.line((0,y,900,y),fill='#17242c',width=17)
        f.line((0,y-5,900,y-5),fill='#819399',width=4)
    for x in range(-40,980,70):
        f.line((x,1205,x+45,1380),fill='#1a272f',width=17)
    front.save(directory/'foreground.png')
    write_json(directory/'metadata.json',{'background_id':'railway_station_night','name':'Railway Station Night',
               'version':version,'canvas':list(im.size),'lighting':'night','lamp':[765,490],
               'file_hashes':hashes(directory),'license':'Original procedural artwork, generated by scripts/build_assets.py'})
    print('Saved and locked railway station')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--replace',action='store_true',help='Explicitly replace permanent sprites and hashes')
    parser.add_argument('--version',default='1.0.0',help='New semantic version; redesigns must use a new version')
    args=parser.parse_args()
    if not re.fullmatch(r'\d+\.\d+\.\d+',args.version): parser.error('Version must have the form 1.0.0')
    if args.replace:
        for path in (ROOT/'assets/characters/rahat/character.json',ROOT/'assets/backgrounds/railway_station_night/metadata.json'):
            if path.exists() and json.loads(path.read_text(encoding='utf-8')).get('version')==args.version:
                parser.error('--replace requires a new version, for example --version 1.1.0')
    build_rahat(args.replace,args.version)
    build_background(args.replace,args.version)
